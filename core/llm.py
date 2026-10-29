"""The only door to the AI gateway: validated JSON chat, embeddings, per-session usage and cost."""
from __future__ import annotations

import time
from typing import TypeVar

import numpy as np
import openai
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from core.config import Settings

M = TypeVar("M", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised with a Persian, user-presentable message (NF-06)."""


class LLM:
    retry_delay = 1.0  # seconds before the single retry of a transient gateway error

    def __init__(self, settings: Settings, client=None):
        self.settings = settings
        self.client = client or OpenAI(base_url=settings.base_url, api_key=settings.api_key, timeout=30, max_retries=0)
        self._usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0, "seconds": 0.0}
        self._unpriced: set[str] = set()
        self._emb_cache: dict[str, np.ndarray] = {}

    @property
    def usage(self) -> dict:
        """Per-session totals for the cost dashboard (NF-05). Never contains prompt or resume text."""
        return {**self._usage, "unpriced_models": sorted(self._unpriced)}

    def embed(self, texts: list[str], *, model: str | None = None) -> np.ndarray:
        """Embedding matrix (len(texts) × dim). Repeated texts are served from the session cache."""
        model = model or self.settings.embed_model
        todo = [t for t in dict.fromkeys(texts) if t not in self._emb_cache]
        if todo:
            self._check_budget()
            r = self._call(lambda: self.client.embeddings.create(model=model, input=todo))
            for t, d in zip(todo, r.data):
                self._emb_cache[t] = np.asarray(d.embedding, dtype=np.float32)
            self._record(model, getattr(r.usage, "prompt_tokens", 0), 0)
        return np.stack([self._emb_cache[t] for t in texts]) if texts else np.zeros((0, 0), dtype=np.float32)

    def chat_json(self, messages: list[dict], model_cls: type[M], *, model: str | None = None) -> M:
        """Ask for JSON and validate it. One retry that shows the model its own error, then LLMError."""
        msgs = list(messages)
        for attempt in range(2):
            content = self._complete(msgs, model or self.settings.chat_model)
            try:
                return model_cls.model_validate_json(content)
            except ValidationError as exc:
                if attempt == 1:
                    raise LLMError("پاسخ مدل قابل‌استفاده نبود. لطفاً دوباره امتحان کنید.") from exc
                msgs = msgs + [
                    {"role": "assistant", "content": content or ""},
                    {"role": "user", "content": f"Your reply was not valid JSON for the schema: {exc.errors()[:3]}. "
                                                "Reply again with JSON only."},
                ]
        raise AssertionError("unreachable")

    def _complete(self, messages: list[dict], model: str) -> str:
        self._check_budget()
        r = self._call(lambda: self.client.chat.completions.create(
            model=model, messages=messages, response_format={"type": "json_object"}, temperature=0
        ))
        u = r.usage
        self._record(model, getattr(u, "prompt_tokens", 0), getattr(u, "completion_tokens", 0))
        return r.choices[0].message.content or ""

    def _record(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        self._usage["calls"] += 1
        self._usage["prompt_tokens"] += prompt_tokens or 0
        self._usage["completion_tokens"] += completion_tokens or 0
        price = self.settings.prices.get(model)
        if price is None:
            self._unpriced.add(model)
            return
        self._usage["cost_usd"] += ((prompt_tokens or 0) * price[0] + (completion_tokens or 0) * price[1]) / 1_000_000

    def _check_budget(self) -> None:
        if self._usage["cost_usd"] >= self.settings.session_budget_usd:
            raise LLMError("به سقف هزینه‌ی این جلسه رسیدید. برای ادامه صفحه را تازه کنید.")

    def _call(self, fn):
        """Run a gateway request; one retry on timeouts, network errors, 429 and 5xx."""
        for attempt in range(2):
            t0 = time.time()
            try:
                result = fn()
                self._usage["seconds"] += time.time() - t0
                return result
            except (openai.APITimeoutError, openai.APIConnectionError, openai.RateLimitError, openai.InternalServerError) as exc:
                if attempt == 1:
                    raise LLMError("سرویس هوش مصنوعی فعلاً در دسترس نیست. چند لحظه بعد دوباره امتحان کنید.") from exc
                time.sleep(self.retry_delay)
            except openai.APIError as exc:  # 4xx: bad request, auth, unknown model → retrying will not help
                raise LLMError("درخواست به سرویس هوش مصنوعی رد شد. تنظیمات مدل یا کلید را بررسی کنید.") from exc
