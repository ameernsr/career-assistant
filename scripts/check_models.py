"""Pick the Module A chat model with data instead of guesses.

    .venv/bin/python scripts/check_models.py                    # list every model the gateway offers
    .venv/bin/python scripts/check_models.py MODEL_A MODEL_B    # benchmark candidates on a Persian JSON task

For each candidate: latency (must stay well under 10 s, NF-02), valid JSON rate, whether the
extraction is right, and tokens used. Needs OPENAI_BASE_URL and OPENAI_API_KEY in .env.
"""
import json
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(base_url=os.environ["OPENAI_BASE_URL"], api_key=os.environ["OPENAI_API_KEY"], timeout=30)

SYSTEM = (
    "You extract a career profile from a Persian conversation. Reply with JSON only: "
    '{"target_role": one of ["data_analyst","backend_developer","product_manager"] or null, '
    '"target_level": "junior"|"mid"|"senior"|null, "claims": [{"concept_id": str, "proficiency": "none"|"heard"|"used"|"proficient"}], '
    '"next_question_fa": a short Persian follow-up question, or null if enough is known}. '
    "Allowed concept ids: excel, sql_basics, statistics, python_basics, bi_tools."
)
USER = "سلام، دانشجوی سال آخر آمارم و می‌خوام تحلیلگر داده‌ی جونیور بشم. اکسل رو توی پروژه‌های درسی زیاد استفاده کردم ولی SQL رو فقط اسمش رو شنیدم."
EXPECTED = {"target_role": "data_analyst", "target_level": "junior", "excel": {"used", "proficient"}, "sql_basics": {"heard", "none"}}


def check(model: str, runs: int = 3) -> None:
    lat, valid, correct, tokens = [], 0, 0, 0
    for _ in range(runs):
        t0 = time.time()
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}],
                response_format={"type": "json_object"},
                temperature=0,
            )
        except Exception as exc:
            print(f"  {model}: ERROR {exc.__class__.__name__}: {str(exc)[:120]}")
            return
        lat.append(time.time() - t0)
        tokens += r.usage.total_tokens if r.usage else 0
        try:
            d = json.loads(r.choices[0].message.content)
            valid += 1
        except (json.JSONDecodeError, TypeError):
            continue
        claims = {c.get("concept_id"): c.get("proficiency") for c in d.get("claims", []) if isinstance(c, dict)}
        if (
            d.get("target_role") == EXPECTED["target_role"]
            and d.get("target_level") == EXPECTED["target_level"]
            and claims.get("excel") in EXPECTED["excel"]
            and claims.get("sql_basics", "none") in EXPECTED["sql_basics"]
        ):
            correct += 1
        last_q = d.get("next_question_fa")
    print(
        f"  {model:40} latency avg {sum(lat)/len(lat):4.1f}s max {max(lat):4.1f}s | "
        f"valid JSON {valid}/{runs} | correct {correct}/{runs} | ~{tokens // runs} tokens/call"
    )
    if valid:
        print(f"    sample question: {last_q}")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        for m in sorted(client.models.list(), key=lambda m: m.id):
            print(m.id)
    else:
        for model in sys.argv[1:]:
            check(model)
