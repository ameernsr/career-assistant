"""A-09: Persian roadmap summary built only from the computed stages, so text and graph always agree."""
from core.schemas import Roadmap
from core.taxonomy import Taxonomy

LEVEL_FA = {"junior": "جونیور", "mid": "میدلول", "senior": "ارشد"}
ORDINAL_FA = ["اول", "دوم", "سوم", "چهارم", "پنجم", "ششم", "هفتم", "هشتم", "نهم", "دهم"]


def summarize(rm: Roadmap, tax: Taxonomy, goal: str | None = None) -> str:
    if goal is None:
        role = tax.roles.get(rm.role_id)
        goal = f"{role['name_fa']} در سطح {LEVEL_FA.get(rm.target_level, rm.target_level)}" if role else "این هدف"
    total = sum(len(s) for s in rm.stages)
    if total == 0:
        return f"برای {goal} همه‌ی مهارت‌های لازم را دارید. می‌توانید سطح بالاتر را هدف بگیرید."
    lines = [f"برای {goal}، {total} مهارت در {len(rm.stages)} مرحله پیش رو دارید:"]
    for i, stage in enumerate(rm.stages):
        names = "، ".join(tax.concepts[c]["name_fa"] for c in stage)
        lines.append(f"مرحله‌ی {ORDINAL_FA[i] if i < len(ORDINAL_FA) else i + 1}: {names}")
    return "\n".join(lines)
