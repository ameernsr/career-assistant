"""دستیار مسیر شغلی — Streamlit app. Run: ./run.sh  (or .venv/bin/streamlit run app.py)"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import streamlit as st

from core.config import ConfigError, load_settings
from core.conversation import ConversationState, known_sets, next_turn
from core.graph_view import roadmap_dot, roadmap_html
from core.llm import LLM, LLMError
from core.matching import job_skill_ids, rank
from core.resume_parser import ResumeError, parse_resume
from core.roadmap import compute_roadmap, compute_roadmap_for_targets
from core.schemas import JobPosting, ResumeProfile
from core.summary import LEVEL_FA, summarize
from core.taxonomy import load_taxonomy

ROOT = Path(__file__).resolve().parent
GREETING = "سلام! من دستیار مسیر شغلی هستم. بگویید دوست دارید در چه شغلی کار کنید، تا با چند سؤال کوتاه نقشه‌ی راه یادگیری‌تان را بسازم."
SENIORITY_FA = {"intern": "کارآموز", "junior": "جونیور", "mid": "میدلول", "senior": "ارشد", "lead": "مدیر/لید"}
SOURCE_FA = {"jobinja": "جابینجا", "jobvision": "جاب‌ویژن", "karboom": "کاربوم", "irantalent": "ایران‌تلنت", "quera": "کوئرا"}

st.set_page_config(page_title="دستیار مسیر شغلی", page_icon="🧭", layout="wide")
st.markdown(
    """
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;700&display=swap" rel="stylesheet">
<style>
html, body, .stApp, [class*="st-"], .stMarkdown, .stChatMessage, input, textarea, button, label {
  font-family: Vazirmatn, Tahoma, sans-serif !important; }
.stApp, .main, [data-testid="stSidebar"] { direction: rtl; text-align: right; }
[data-testid="stChatInput"] textarea { direction: rtl; text-align: right; }
.chip { display:inline-block; padding:2px 10px; margin:2px; border-radius:999px; font-size:0.85rem; }
.chip.ok { background:#D8F0DD; color:#1F5E2A; } .chip.miss { background:#FBE0DC; color:#8A2A1F; }
.chip.heard { background:#ECEFF3; color:#45505E; }
.job-meta { color:#56657A; font-size:0.9rem; }
[data-testid="stGraphVizChart"] { direction: ltr; }
</style>""",
    unsafe_allow_html=True,
)


# ---------------- shared data (loaded once per server) ----------------
@st.cache_resource
def taxonomy():
    return load_taxonomy()


@st.cache_resource
def jobs_and_vectors():
    jobs = [JobPosting(**j) for j in json.loads((ROOT / "data" / "jobs.json").read_text(encoding="utf-8"))]
    vec_file = ROOT / "data" / "job_embeddings.npz"
    vectors = {}
    if vec_file.exists():
        d = np.load(vec_file)
        vectors = dict(zip(d["ids"].tolist(), d["vectors"]))
    meta_file = ROOT / "data" / "jobs_meta.json"
    meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
    return jobs, vectors, meta


@st.cache_resource
def resources() -> dict[str, list[dict]]:
    f = ROOT / "data" / "resources.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


tax = taxonomy()
JOBS, JOB_VECTORS, JOBS_META = jobs_and_vectors()
JOB_BY_ID = {j.id: j for j in JOBS}

# ---------------- per-session state ----------------
if "llm" not in st.session_state:
    try:
        st.session_state.llm = LLM(load_settings())
    except ConfigError as exc:
        st.error(f"تنظیمات ناقص است: {exc}")
        st.stop()
ss = st.session_state
ss.setdefault("conv", ConversationState())
ss.setdefault("chat", [{"role": "assistant", "content": GREETING}])
ss.setdefault("resume", None)
ss.setdefault("resume_hash", None)
llm: LLM = ss.llm


def chips(ids, kind):
    return " ".join(f'<span class="chip {kind}">{tax.concepts[c]["name_fa"]}</span>' for c in ids if c in tax.concepts)


def show_roadmap(rm, goal_title: str, key: str):
    total = sum(len(s) for s in rm.stages)
    summary = summarize(rm, tax, goal=goal_title)
    if total == 0:
        st.success(summary)
        return
    st.graphviz_chart(roadmap_dot(rm, tax), width="stretch")
    st.markdown(summary.replace("\n", "  \n"))
    res = resources()
    with st.expander("📚 منابع یادگیری پیشنهادی (لینک‌های بررسی‌شده)", expanded=False):
        any_res = False
        for i, stage in enumerate(rm.stages, 1):
            for c in stage:
                for r in res.get(c, [])[:2]:
                    any_res = True
                    st.markdown(f"- **مرحله‌ی {i} — {tax.concepts[c]['name_fa']}:** [{r['title']}]({r['url']})")
        if not any_res:
            st.caption("برای این مفاهیم هنوز منبع تأییدشده‌ای ثبت نشده است.")
    st.download_button("⬇️ دانلود نقشه‌ی راه (HTML)", roadmap_html(rm, tax, goal_title, summary, res),
                       file_name="roadmap.html", mime="text/html", key=f"dl-{key}")


# ---------------- sidebar: cost & privacy ----------------
with st.sidebar:
    st.header("🧭 دستیار مسیر شغلی")
    u = llm.usage
    st.metric("هزینه‌ی این جلسه", f"${u['cost_usd']:.4f}", help="بر اساس قیمت‌های متیس (MODEL_PRICES در .env)")
    st.caption(f"درخواست به مدل: {u['calls']}")
    st.caption(f"توکن ورودی/خروجی: {u['prompt_tokens']:,} / {u['completion_tokens']:,} · زمان مدل: {u['seconds']:.1f} ثانیه")
    st.progress(min(u["cost_usd"] / llm.settings.session_budget_usd, 1.0),
                text=f"سقف بودجه‌ی جلسه: ${llm.settings.session_budget_usd}")
    if u["unpriced_models"]:
        st.caption("بدون قیمت ثبت‌شده: " + "، ".join(u["unpriced_models"]))
    st.divider()
    st.caption("🔒 رزومه و گفتگوی شما فقط در همین جلسه نگه داشته می‌شود، جایی ذخیره یا لاگ نمی‌شود و فقط برای پردازش به سرویس هوش مصنوعی فرستاده می‌شود.")
    if st.button("🔄 شروع دوباره (پاک کردن داده‌های من)"):
        for k in ("conv", "chat", "resume", "resume_hash"):
            ss.pop(k, None)
        st.rerun()

tab_path, tab_jobs, tab_eval = st.tabs(["🗺️ مسیر شغلی", "💼 تطبیق رزومه با شغل", "📊 ارزیابی و هزینه"])

# ---------------- Module A ----------------
with tab_path:
    left, right = st.columns([1, 1.25], gap="large")
    with left:
        for m in ss.chat:
            st.chat_message(m["role"], avatar="🧑" if m["role"] == "user" else "🧭").markdown(m["content"])
        hint = "اصلاح کنید، مثلاً «من اکسل بلد نیستم»" if ss.conv.done else "پیامتان را بنویسید…"
        if msg := st.chat_input(hint):
            ss.chat.append({"role": "user", "content": msg})
            with st.spinner("در حال فکر کردن…"):
                reply, ss.conv = next_turn(ss.conv, msg, llm, tax)
            ss.chat.append({"role": "assistant", "content": reply})
            st.rerun()
        st.caption(f"سؤال‌های پرسیده‌شده: {ss.conv.questions_asked} از ۶")
    with right:
        p = ss.conv.profile
        if ss.conv.done and p.target_role is None:
            st.info("نقش هدفتان را انتخاب کنید:")
            role = st.selectbox("نقش", list(tax.roles), format_func=lambda r: tax.roles[r]["name_fa"])
            level = st.radio("سطح هدف", ["junior", "mid", "senior"], format_func=LEVEL_FA.get, horizontal=True)
            if st.button("ساختن نقشه‌ی راه"):
                p.target_role, p.target_level = role, level
                st.rerun()
        elif ss.conv.done:
            known, not_known = known_sets(p, tax)
            rm = compute_roadmap(tax, p.target_role, p.target_level or "junior", known, not_known)
            goal = f"{tax.roles[p.target_role]['name_fa']} در سطح {LEVEL_FA[rm.target_level]}"
            st.subheader(f"نقشه‌ی راه: {goal}")
            heard = [c.concept_id for c in p.claims if c.proficiency == "heard"]
            st.markdown("**آنچه از شما فهمیدم** (اگر اشتباه است در چت اصلاح کنید):", unsafe_allow_html=True)
            st.markdown(f"بلد هستید: {chips(rm.known, 'ok') or '—'}", unsafe_allow_html=True)
            if heard:
                st.markdown(f"فقط اسمش را شنیده‌اید: {chips(heard, 'heard')}", unsafe_allow_html=True)
            show_roadmap(rm, goal, key="path")
        else:
            st.markdown("#### نقشه‌ی راه شما اینجا نمایش داده می‌شود")
            st.caption("بعد از چند سؤال کوتاه، مسیر یادگیری به‌صورت گراف مرحله‌به‌مرحله ساخته می‌شود.")

# ---------------- Module B ----------------
with tab_jobs:
    st.info("🔒 پیش از بارگذاری: رزومه فقط برای همین جلسه پردازش می‌شود، روی دیسک ذخیره یا لاگ نمی‌شود و فقط برای استخراج اطلاعات به سرویس هوش مصنوعی ارسال می‌شود. لطفاً فقط رزومه‌ی خودتان را بارگذاری کنید.")
    consent = st.checkbox("موافقم", key="consent")
    up = st.file_uploader("رزومه (PDF یا DOCX، فارسی یا انگلیسی)", type=["pdf", "docx"], disabled=not consent)
    if up and consent:
        data = up.getvalue()
        h = hashlib.sha256(data).hexdigest()
        if h != ss.resume_hash:
            try:
                with st.spinner("در حال خواندن رزومه…"):
                    profile = parse_resume(data, up.name, llm, tax)
                    profile_text = f"{' '.join(r.get('title', '') for r in profile.previous_roles)}\n{', '.join(profile.skills)}\n{' '.join(profile.education)}"
                    ss.resume = (profile, llm.embed([profile_text])[0] if JOB_VECTORS else None)
                    ss.resume_hash = h
            except (ResumeError, LLMError) as exc:
                st.error(str(exc))
                ss.resume, ss.resume_hash = None, None

    if ss.resume:
        profile, rvec = ss.resume
        with st.expander("👤 پروفایل استخراج‌شده از رزومه", expanded=False):
            st.markdown(f"**مهارت‌ها:** {chips(profile.skill_ids, 'ok') or '—'}", unsafe_allow_html=True)
            st.markdown(f"**سابقه‌ی کار:** {profile.years_experience if profile.years_experience is not None else 'نامشخص'} سال · "
                        f"**شهر:** {profile.location or 'نامشخص'} · **تحصیلات:** {'، '.join(profile.education) or '—'}")
            st.json(profile.model_dump(exclude={"skills"}), expanded=False)

        cities = sorted({j.location for j in JOBS if j.location}, key=lambda c: -sum(j.location == c for j in JOBS))[:15]
        f1, f2, f3, f4 = st.columns([1.2, 1, 1.4, 1])
        method = f1.radio("روش رتبه‌بندی", ["hybrid", "baseline"],
                          format_func={"hybrid": "ترکیبی (معنایی + مهارت)", "baseline": "پایه (هم‌پوشانی کلمات)"}.get)
        city = f2.selectbox("شهر", ["همه"] + cities)
        levels = f3.multiselect("سطح", list(SENIORITY_FA), format_func=SENIORITY_FA.get)
        remote_ok = f4.checkbox("دورکاری هم باشد", value=True)
        filters = {"city": None if city == "همه" else city, "remote_ok": remote_ok, "seniority": levels or None}
        results = rank(profile, JOBS, tax, method=method, filters=filters, k=10,
                       job_vectors=JOB_VECTORS or None, resume_vector=rvec)
        st.caption(f"{len(results)} شغل برتر از {len(JOBS)} آگهی · آخرین به‌روزرسانی آگهی‌ها: {JOBS_META.get('last_updated', '—')[:16].replace('T', ' ')}")
        if not results:
            st.warning("با این فیلترها شغلی پیدا نشد؛ فیلترها را کم‌تر کنید.")

        gap: dict[str, int] = {}
        for rank_i, r in enumerate(results, 1):
            j = JOB_BY_ID[r.job_id]
            for c in r.missing_skills:
                gap[c] = gap.get(c, 0) + 1
            with st.container(border=True):
                a, b = st.columns([4, 1])
                a.markdown(f"**{rank_i}. {j.title}**  \n<span class='job-meta'>{j.company or ''} · {j.location or ''}"
                           f"{' · دورکاری' if j.remote else ''} · {SOURCE_FA.get(j.source, j.source)}"
                           f"{' · ' + j.date_posted if j.date_posted else ''}</span>", unsafe_allow_html=True)
                b.metric("تطابق", f"{round(r.score * 100)}٪")
                st.markdown(f"✅ مهارت‌های منطبق: {chips(r.matched_skills, 'ok') or '—'}", unsafe_allow_html=True)
                st.markdown(f"❌ مهارت‌های لازم که ندارید: {chips(r.missing_skills, 'miss') or '—'}", unsafe_allow_html=True)
                c1, c2 = st.columns([1, 1])
                c1.link_button("مشاهده‌ی آگهی اصلی ↗", j.url)
                if r.missing_skills and c2.toggle("برای این شغل چه یاد بگیرم؟", key=f"b10-{j.id}"):
                    rm = compute_roadmap_for_targets(tax, job_skill_ids(j, tax), set(profile.skill_ids), set(), label=f"job:{j.id}")
                    show_roadmap(rm, f"شغل «{j.title}»", key=f"job-{j.id}")

        if gap:
            st.divider()
            top_gap = sorted(gap, key=lambda c: -gap[c])[:5]
            st.markdown("#### 🎯 نقشه‌ی گپ بازار")
            st.markdown("مهارت‌هایی که در بیشترِ این ۱۰ شغل از شما خواسته شده ولی ندارید: "
                        + " ".join(f'<span class="chip miss">{tax.concepts[c]["name_fa"]} ({gap[c]} شغل)</span>' for c in top_gap),
                        unsafe_allow_html=True)
            if st.toggle("نقشه‌ی راه برای این مهارت‌ها", key="gap-roadmap"):
                rm = compute_roadmap_for_targets(tax, set(top_gap), set(profile.skill_ids), set(), label="market-gap")
                show_roadmap(rm, "مهارت‌های پرتقاضای بازار برای شما", key="gap")

# ---------------- evaluation & cost ----------------
with tab_eval:
    st.subheader("ارزیابی کیفیت رتبه‌بندی (بخش ۱۰.۲)")
    res_file = ROOT / "data" / "eval" / "results.json"
    if res_file.exists():
        res = json.loads(res_file.read_text(encoding="utf-8"))
        st.dataframe(res.get("table", res), width="stretch")
        if res.get("notes"):
            st.caption(res["notes"])
    else:
        st.info("نتایج هنوز تولید نشده است. اجرا: `.venv/bin/python scripts/eval_ranking.py`")
    st.subheader("هزینه و مصرف این جلسه")
    st.json(llm.usage)
    st.caption(f"منابع آگهی: {', '.join(f'{SOURCE_FA.get(s, s)} ({n})' for s, n in JOBS_META.get('per_source', {}).items())}")
