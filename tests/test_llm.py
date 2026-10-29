"""LLM wrapper tests. The gateway is the system boundary, so it is the only thing faked."""
from types import SimpleNamespace as NS

import pytest
from pydantic import BaseModel

from core.config import Settings
from core.llm import LLM, LLMError

LLM.retry_delay = 0  # keep tests fast


class Answer(BaseModel):
    role: str
    level: str


def _completion(content, prompt_tokens=100, completion_tokens=20):
    return NS(choices=[NS(message=NS(content=content))],
              usage=NS(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens))


class FakeGateway:
    """Mimics openai.OpenAI: replies are consumed in order; an Exception instance is raised."""

    def __init__(self, replies=(), embeddings=None):
        self.replies = list(replies)
        self.calls = []
        self.chat = NS(completions=NS(create=self._create))
        self.embeddings = NS(create=self._embed)
        self._vectors = embeddings or {}

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    def _embed(self, model, input):
        self.calls.append({"model": model, "input": input})
        return NS(data=[NS(embedding=self._vectors.get(t, [1.0, 0.0])) for t in input],
                  usage=NS(prompt_tokens=10 * len(input)))


SETTINGS = Settings(base_url="http://x", api_key="k", chat_model="chat-mini", embed_model="emb",
                    session_budget_usd=0.01, prices={"chat-mini": [1.0, 2.0], "emb": [0.1, 0.0]})


def test_chat_json_returns_validated_model():
    gw = FakeGateway([_completion('{"role": "data_analyst", "level": "junior"}')])
    out = LLM(SETTINGS, client=gw).chat_json([{"role": "user", "content": "سلام"}], Answer)
    assert out == Answer(role="data_analyst", level="junior")
    assert gw.calls[0]["response_format"] == {"type": "json_object"}


def test_malformed_output_is_retried_once_with_the_error():
    gw = FakeGateway([_completion("not json at all"), _completion('{"role": "x", "level": "mid"}')])
    out = LLM(SETTINGS, client=gw).chat_json([{"role": "user", "content": "hi"}], Answer)
    assert out.level == "mid"
    retry_messages = gw.calls[1]["messages"]
    assert retry_messages[-1]["role"] == "user" and "JSON" in retry_messages[-1]["content"]


def test_schema_mismatch_twice_raises_persian_error():
    gw = FakeGateway([_completion('{"role": "x"}'), _completion('{"level": "mid"}')])
    with pytest.raises(LLMError) as err:
        LLM(SETTINGS, client=gw).chat_json([{"role": "user", "content": "hi"}], Answer)
    assert "پاسخ" in str(err.value)  # message is shown to the user as-is


def _network_error():
    import openai

    # The SDK only stores the request object, so any stand-in works (avoids depending on its HTTP library).
    return openai.APITimeoutError(request=NS(method="POST", url="http://x/chat"))


def test_transient_gateway_error_is_retried():
    gw = FakeGateway([_network_error(), _completion('{"role": "x", "level": "senior"}')])
    assert LLM(SETTINGS, client=gw).chat_json([{"role": "user", "content": "hi"}], Answer).level == "senior"


def test_gateway_down_raises_persian_error_not_traceback():
    gw = FakeGateway([_network_error(), _network_error()])
    with pytest.raises(LLMError) as err:
        LLM(SETTINGS, client=gw).chat_json([{"role": "user", "content": "hi"}], Answer)
    assert "دسترس" in str(err.value)


def test_usage_records_tokens_and_cost_per_session():
    gw = FakeGateway([_completion('{"role": "x", "level": "mid"}', prompt_tokens=100, completion_tokens=20)])
    llm = LLM(SETTINGS, client=gw)
    llm.chat_json([{"role": "user", "content": "hi"}], Answer)
    u = llm.usage
    assert (u["calls"], u["prompt_tokens"], u["completion_tokens"]) == (1, 100, 20)
    assert u["cost_usd"] == pytest.approx((100 * 1.0 + 20 * 2.0) / 1_000_000)
    assert u["unpriced_models"] == []


def test_budget_exhausted_blocks_further_calls():
    from dataclasses import replace

    tight = replace(SETTINGS, session_budget_usd=0.0001)  # first call costs 0.00014
    gw = FakeGateway([_completion('{"role": "x", "level": "mid"}')] * 2)
    llm = LLM(tight, client=gw)
    llm.chat_json([{"role": "user", "content": "hi"}], Answer)
    with pytest.raises(LLMError, match="سقف"):
        llm.chat_json([{"role": "user", "content": "again"}], Answer)
    assert len(gw.calls) == 1  # the second request never reached the gateway


def test_embed_returns_matrix_and_caches_repeated_texts():
    import numpy as np

    gw = FakeGateway(embeddings={"پایتون": [0.0, 1.0], "اکسل": [1.0, 0.0]})
    llm = LLM(SETTINGS, client=gw)
    v = llm.embed(["پایتون", "اکسل"])
    assert isinstance(v, np.ndarray) and v.shape == (2, 2)
    assert v[0].tolist() == [0.0, 1.0]
    llm.embed(["اکسل"])
    assert len(gw.calls) == 1  # cached
    assert llm.usage["prompt_tokens"] == 20


def test_transcribe_and_speak_go_through_gateway():
    calls = {}

    def transcriptions_create(**kw):
        calls["stt"] = kw
        return NS(text="می‌خوام تحلیلگر داده بشم")

    def speech_create(**kw):
        calls["tts"] = kw
        return NS(content=b"ID3fake-mp3")

    gw = FakeGateway()
    gw.audio = NS(transcriptions=NS(create=transcriptions_create), speech=NS(create=speech_create))
    from dataclasses import replace

    llm = LLM(replace(SETTINGS, stt_model="stt-m", tts_model="tts-m"), client=gw)
    assert llm.transcribe(b"webm-bytes", "voice.wav") == "می‌خوام تحلیلگر داده بشم"
    assert calls["stt"]["model"] == "stt-m" and calls["stt"]["language"] == "fa"
    assert llm.speak("سلام") == b"ID3fake-mp3" and calls["tts"]["model"] == "tts-m"
    assert llm.usage["calls"] == 2
