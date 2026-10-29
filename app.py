"""دستیار مسیر شغلی — Streamlit app. Run: ./run.sh  (or .venv/bin/streamlit run app.py)"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import streamlit as st

from core.config import ConfigError, load_settings
from core.conversation import ConversationState, apply_skill_selection, known_sets, next_turn
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
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
SAMPLE_RESUME = "r1_data_analyst_fa"  # synthetic, from data/eval/resumes


def fa(x) -> str:
    return str(x).translate(FA_DIGITS)


JALALI_MONTHS = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور", "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]


def fa_date(iso: str | None, with_time: bool = False) -> str:
    """'2026-10-29T09:19:22+00:00' → '۷ آبان ۱۴۰۵ · ۱۲:۴۹' (Tehran time)."""
    if not iso:
        return ""
    from datetime import datetime, timedelta, timezone

    import jdatetime

    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return fa(iso)
    if dt.tzinfo:
        dt = dt.astimezone(timezone(timedelta(hours=3, minutes=30)))
    j = jdatetime.date.fromgregorian(date=dt.date())
    text = f"{j.day} {JALALI_MONTHS[j.month - 1]} {j.year}"
    return fa(text + (f" · {dt:%H:%M}" if with_time else ""))


def age_fa(iso: str | None) -> str | None:
    if not iso:
        return None
    from datetime import date

    try:
        days = (date.today() - date.fromisoformat(iso[:10])).days
    except ValueError:
        return None
    return "امروز" if days <= 0 else f"{fa(days)} روز پیش"


def is_llm_error(exc: Exception) -> bool:
    # a Streamlit module reload can leave an LLM object raising the previous LLMError class
    return isinstance(exc, LLMError) or type(exc).__name__ == "LLMError"


st.set_page_config(page_title="دستیار مسیر شغلی", page_icon="🧭", layout="wide", initial_sidebar_state="collapsed")
st.markdown(
    """
<link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root { --ink:#15232B; --muted:#5A6A77; --line:#DCE4E7; --card:#FFFFFF; --bg:#F4F6F7;
        --teal:#0E6B62; --teal-d:#0B4A44; --teal-soft:#E2F0EE; --saffron:#B97C06; --saffron-soft:#FBF0D8;
        --ok:#1E6A33; --ok-soft:#DCF0E1; --bad:#982E21; --bad-soft:#FAE2DE; --grey-soft:#ECEFF2; }
html, body, .stApp, [class*="st-"], .stMarkdown, .stChatMessage, input, textarea, button, label, p, h1, h2, h3 {
  font-family: Vazirmatn, Tahoma, sans-serif !important; }
.stApp, .main { direction: rtl; text-align: right; }
.stApp { background: var(--bg); color: var(--ink); }
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display: none; }
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stToolbar"] { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; height: 0; }
.block-container { padding-top: 1.4rem; padding-bottom: 2rem; max-width: 1320px; }
[data-testid="stChatInput"] textarea { direction: rtl; text-align: right; }
.hero { background: var(--teal-d); color:#fff; border-radius: 18px; padding: 20px 26px; display:flex; flex-wrap:wrap;
        align-items:center; justify-content:space-between; gap:18px; }
.hero h1 { font-size: 1.6rem; font-weight: 800; margin: 0; color:#fff; line-height:1.5; padding:0; }
.hero p { margin: 2px 0 0; color: #C7E2DE; font-size: 0.95rem; }
.stats { display:flex; gap:10px; flex-wrap:wrap; }
.stat { background: rgba(255,255,255,0.09); border:1px solid rgba(255,255,255,0.16); border-radius: 12px; padding: 8px 14px; min-width: 92px; text-align:center; }
.stat b { display:block; font-size: 1.2rem; color:#fff; font-weight:700; }
.stat span { font-size: 0.76rem; color:#C7E2DE; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { height: 44px; padding: 0 16px; border-radius: 10px 10px 0 0; font-weight: 600; color: var(--muted); }
.stTabs [aria-selected="true"] { color: var(--teal) !important; background: var(--card); }
.stTabs [data-baseweb="tab-highlight"] { background: var(--teal); height: 3px; }
div[data-testid="stVerticalBlockBorderWrapper"] { background: var(--card); border-color: var(--line) !important; border-radius: 14px; }
[data-testid="stExpander"] { background: var(--card); border-radius: 12px; border-color: var(--line); }
[data-testid="stChatMessage"] { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 8px 12px; }
.panel-title { font-size: 1.08rem; font-weight: 700; color: var(--ink); margin: 0 0 4px; }
.panel-sub { color: var(--muted); font-size: 0.9rem; margin: 0 0 10px; }
.eyebrow { font-size: 0.78rem; font-weight: 600; color: var(--saffron); letter-spacing: .02em; }
.map-head { display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:14px; margin-bottom: 6px; }
.map-head h2 { font-size: 1.3rem; font-weight: 800; margin: 2px 0 0; color: var(--ink); padding:0; }
.kpis { display:flex; gap:8px; flex-wrap:wrap; }
.kpi { background: var(--teal-soft); border-radius: 12px; padding: 8px 14px; text-align:center; min-width: 96px; }
.kpi b { display:block; font-size: 1.25rem; color: var(--teal-d); font-weight: 800; }
.kpi span { font-size: 0.76rem; color: var(--muted); }
.kpi.warm { background: var(--saffron-soft); } .kpi.warm b { color: #7A5204; }
.legend { display:flex; gap:16px; font-size: 0.82rem; color: var(--muted); margin: 4px 0 2px; }
.legend i { display:inline-block; width:12px; height:12px; border-radius:4px; margin-left:6px; vertical-align:-1px; }
.summary { background: var(--grey-soft); border-radius: 12px; padding: 12px 16px; line-height: 2; font-size: 0.93rem; white-space: pre-line; }
.stage { border: 1px solid var(--line); border-radius: 12px; padding: 12px 16px; margin: 10px 0; background: var(--card); }
.stage-h { font-weight: 700; color: var(--teal-d); margin-bottom: 6px; }
.stage-h small { color: var(--muted); font-weight: 500; margin-right: 6px; }
.concept { padding: 6px 0; border-top: 1px dashed var(--line); }
.concept:first-of-type { border-top: 0; }
.concept b { font-weight: 600; }
.res { display:inline-block; margin: 3px 0 0 8px; font-size: 0.86rem; }
.res a { color: var(--teal); text-decoration: none; } .res a:hover { text-decoration: underline; }
.tag { display:inline-block; font-size: 0.7rem; font-weight: 700; border-radius: 6px; padding: 0 6px; margin-left: 4px; }
.tag.fa { background: var(--saffron-soft); color: #7A5204; } .tag.en { background: var(--grey-soft); color: var(--muted); }
.empty { background: var(--card); border: 1px dashed #C3D1D5; border-radius: 16px; padding: 24px; }
.empty h3 { margin: 0 0 4px; font-size: 1.08rem; font-weight: 700; padding:0; }
.steps { display:flex; gap:10px; flex-wrap:wrap; margin-top: 12px; }
.step { flex:1; min-width: 140px; background: var(--teal-soft); border-radius: 12px; padding: 12px; font-size: 0.9rem; }
.step b { color: var(--teal); display:block; margin-bottom: 2px; }
.chip { display:inline-block; padding:3px 11px; margin:3px 2px; border-radius:999px; font-size:0.83rem; font-weight:500; }
.chip.ok { background:var(--ok-soft); color:var(--ok); } .chip.miss { background:var(--bad-soft); color:var(--bad); }
.chip.heard { background:var(--grey-soft); color:#45505E; }
.label { font-size: 0.82rem; color: var(--muted); margin: 8px 0 2px; }
.job-title { font-size: 1.04rem; font-weight: 700; color: var(--ink); line-height: 1.6; }
.job-meta { color: var(--muted); font-size: 0.86rem; }
.score { display:flex; flex-direction:column; align-items:center; justify-content:center; width: 74px; height: 62px; border-radius: 14px; font-weight: 800; margin-right:auto; }
.score b { font-size: 1.3rem; line-height: 1.1; } .score span { font-size: 0.7rem; font-weight: 500; }
.score.hi { background: var(--ok-soft); color: var(--ok); } .score.mid { background: var(--saffron-soft); color: #7A5204; } .score.lo { background: var(--grey-soft); color: #45505E; }
.rank { display:inline-flex; align-items:center; justify-content:center; width: 26px; height: 26px; border-radius: 8px; background: var(--saffron-soft); color: #7A5204; font-weight: 800; font-size: 0.85rem; margin-left: 8px; }
.insight { background: var(--saffron-soft); border: 1px solid #EED9A8; border-radius: 14px; padding: 14px 18px; margin-bottom: 10px; }
.insight b { color: #6E4A03; }
.profile-row { display:flex; gap:8px; flex-wrap:wrap; margin: 6px 0; }
.pfact { background: var(--grey-soft); border-radius: 10px; padding: 6px 10px; font-size: 0.85rem; }
.pfact b { display:block; font-size: 0.72rem; color: var(--muted); font-weight: 500; }
.tile { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; }
.tile .v { font-size: 1.5rem; font-weight: 800; color: var(--teal-d); } .tile .k { font-size: 0.8rem; color: var(--muted); }
.fine { color: var(--muted); font-size: 0.8rem; line-height: 1.9; border-top: 1px solid var(--line); padding-top: 12px; margin-top: 26px; }
.stButton > button, .stDownloadButton > button, .stLinkButton > a { border-radius: 10px; font-weight: 600; }
[data-testid="stGraphVizChart"] { direction: ltr; background: var(--card); border:1px solid var(--line); border-radius: 14px; padding: 6px; }
[data-testid="stFileUploaderDropzone"] { background: var(--teal-soft); border-color: #B9D9D4; }
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


def sample_resume():
    f = ROOT / "data" / "eval" / "profiles.json"
    if not f.exists():
        return None
    item = json.loads(f.read_text(encoding="utf-8")).get(SAMPLE_RESUME)
    return (ResumeProfile(**item["profile"]), np.array(item["vector"], dtype=np.float32)) if item else None


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
ss.setdefault("audio_hash", None)
ss.setdefault("skill_ver", 0)
llm: LLM = ss.llm


def name(cid: str) -> str:
    return tax.concepts[cid]["name_fa"]


def chips(ids, kind):
    return " ".join(f'<span class="chip {kind}">{name(c)}</span>' for c in ids if c in tax.concepts)


def html(markup: str):
    st.markdown(markup, unsafe_allow_html=True)


# ---------------- roadmap view (shared by Module A, B-10 and the market-gap roadmap) ----------------
def roadmap_view(rm, goal: str, key: str, profile=None):
    total = sum(len(s) for s in rm.stages)
    summary = summarize(rm, tax, goal=goal)
    html(f"""<div class="map-head"><div><div class="eyebrow">نقشه‌ی راه یادگیری</div><h2>{goal}</h2></div>
<div class="kpis"><div class="kpi warm"><b>{fa(total)}</b><span>مهارت برای یادگیری</span></div>
<div class="kpi"><b>{fa(len(rm.stages))}</b><span>مرحله</span></div>
<div class="kpi"><b>{fa(len(rm.known))}</b><span>مهارتی که دارید</span></div></div></div>""")
    if total == 0:
        st.success(summary)
        return
    names = ["🗺️ گراف", "📚 مراحل و منابع"] + (["✏️ مهارت‌های من"] if profile is not None else [])
    tabs = st.tabs(names)
    with tabs[0]:
        html('<div class="legend"><span><i style="background:#FDE7C8;border:1px solid #B8650A"></i>باید یاد بگیرید</span>'
             '<span>مسیر از راست به چپ: هر ستون یک مرحله · فلش یعنی «پیش‌نیاز است برای»</span></div>')
        st.graphviz_chart(roadmap_dot(rm, tax), width="stretch")
    res = resources()
    with tabs[1]:
        html(f'<div class="summary">{summary}</div>')
        blocks = []
        for i, stage in enumerate(rm.stages, 1):
            rows = []
            for c in stage:
                items = res.get(c, [])
                # one Persian course first (reachable in Iran without VPN), then one official source
                picks = [r for r in items if r.get("lang") == "fa"][:1] + [r for r in items if r.get("lang") != "fa"][:1]
                links = "".join(
                    f'<span class="res"><span class="tag {r.get("lang", "en")}">{"فارسی" if r.get("lang") == "fa" else "EN"}</span>'
                    f'<a href="{r["url"]}" target="_blank">{r["title"]}</a></span>' for r in picks
                ) or '<span class="res" style="color:#8A97A3">منبع تأییدشده‌ای ثبت نشده</span>'
                rows.append(f'<div class="concept"><b>{name(c)}</b><br>{links}</div>')
            blocks.append(f'<div class="stage"><div class="stage-h">مرحله‌ی {fa(i)} <small>· {fa(len(stage))} مهارت</small></div>{"".join(rows)}</div>')
        html("".join(blocks))
    if profile is not None:
        with tabs[2]:
            heard = [c.concept_id for c in profile.claims if c.proficiency == "heard"]
            html('<div class="panel-sub">آنچه از گفتگو فهمیدم. اگر اشتباه است، همین‌جا اصلاح کنید یا در چت بنویسید (مثلاً «من اکسل بلد نیستم»).</div>')
            if heard:
                html(f'<div class="label">فقط اسمش را شنیده‌اید (دانسته حساب نمی‌شود)</div>{chips(heard, "heard")}')
            options = rm.known + [c for stage in rm.stages for c in stage]
            picked = st.multiselect("مهارت‌هایی که بلدم", options, default=rm.known, key=f"skills-{ss.skill_ver}", format_func=name)
            if set(picked) != set(rm.known):  # A-08 without the LLM (idea from Amir's prototype)
                apply_skill_selection(profile, set(picked), set(rm.known), tax)
                ss.skill_ver += 1
                st.rerun()
    a, b = st.columns(2)
    a.download_button("⬇️ دانلود نقشه‌ی راه (HTML)", roadmap_html(rm, tax, goal, summary, res),
                      file_name="roadmap.html", mime="text/html", key=f"dl-{key}", width="stretch")
    if profile is not None and b.button("🔊 خواندن خلاصه با صدا", key=f"tts-{key}", width="stretch"):
        try:
            with st.spinner("در حال ساختن صدا…"):
                st.audio(llm.speak(summary), format="audio/mpeg", autoplay=True)
        except Exception as exc:  # never show a traceback (NF-06)
            st.error(str(exc) if is_llm_error(exc) else "ساختن صدا انجام نشد. لطفاً دوباره امتحان کنید.")


# ---------------- header ----------------
html(f"""<div class="hero"><div><h1>🧭 دستیار مسیر شغلی</h1>
<p>نقشه‌ی راه یادگیری از روی یک مدل صریح مهارت‌ها، و شغل‌های مناسب شما از روی رزومه</p></div>
<div class="stats"><div class="stat"><b>{fa(len(JOBS))}</b><span>آگهی واقعی</span></div>
<div class="stat"><b>{fa(len(JOBS_META.get("per_source", {})) or 5)}</b><span>سایت کاریابی</span></div>
<div class="stat"><b>{fa(len(tax.roles))}</b><span>نقش شغلی</span></div>
<div class="stat"><b>{fa(len(tax.concepts))}</b><span>مهارت</span></div></div></div>""")
_, reset_col = st.columns([6, 1])
if reset_col.button("🔄 شروع دوباره", help="گفتگو، رزومه و همه‌ی داده‌های این جلسه پاک می‌شود", width="stretch"):
    for k in ("conv", "chat", "resume", "resume_hash", "audio_hash"):
        ss.pop(k, None)
    st.rerun()

tab_path, tab_jobs, tab_eval = st.tabs(["🗺️ مسیر شغلی", "💼 تطبیق رزومه با شغل", "📊 ارزیابی و هزینه"])

# ---------------- Module A ----------------
with tab_path:
    chat_col, map_col = st.columns([1, 1.45], gap="large")
    with chat_col:
        with st.container(border=True):
            html('<div class="panel-title">💬 گفتگو</div>')
            asked = ss.conv.questions_asked
            st.progress(1.0 if ss.conv.done else min(asked / 6, 1.0),
                        text="پروفایل کامل شد ✓  حالا می‌توانید اصلاح کنید" if ss.conv.done else f"سؤال {fa(asked)} از ۶")
            with st.container(height=380, border=False):
                for m in ss.chat:
                    st.chat_message(m["role"], avatar="🧑" if m["role"] == "user" else "🧭").markdown(m["content"])
            hint = "اصلاح کنید، مثلاً «من اکسل بلد نیستم»" if ss.conv.done else "پیامتان را بنویسید…"
            msg = st.chat_input(hint)
            voice = st.audio_input("🎤 یا با صدا بگویید", key="voice")  # A-10 (idea from Amir's prototype)
            if voice is not None:
                data = voice.getvalue()
                h = hashlib.sha256(data).hexdigest()
                if h != ss.audio_hash:
                    ss.audio_hash = h
                    try:
                        with st.spinner("در حال تبدیل صدا به متن…"):
                            msg = llm.transcribe(data, "voice.wav") or msg
                    except Exception as exc:  # never show a traceback (NF-06)
                        st.error(str(exc) if is_llm_error(exc) else "تبدیل صدا به متن انجام نشد. لطفاً پیام را تایپ کنید.")
            if msg:
                ss.chat.append({"role": "user", "content": msg})
                with st.spinner("در حال فکر کردن…"):
                    reply, ss.conv = next_turn(ss.conv, msg, llm, tax)
                ss.chat.append({"role": "assistant", "content": reply})
                st.rerun()
    with map_col:
        p = ss.conv.profile
        if ss.conv.done and p.target_role is None:
            with st.container(border=True):
                html('<div class="panel-title">نقش هدفتان را انتخاب کنید</div><div class="panel-sub">از گفتگو نقش مشخصی پیدا نشد.</div>')
                role = st.selectbox("نقش", list(tax.roles), format_func=lambda r: tax.roles[r]["name_fa"])
                level = st.segmented_control("سطح هدف", ["junior", "mid", "senior"], format_func=LEVEL_FA.get, default="junior")
                if st.button("ساختن نقشه‌ی راه", type="primary"):
                    p.target_role, p.target_level = role, level or "junior"
                    st.rerun()
        elif ss.conv.done:
            known, not_known = known_sets(p, tax)
            rm = compute_roadmap(tax, p.target_role, p.target_level or "junior", known, not_known)
            order = ["junior", "mid", "senior"]
            if p.current_level in order and order.index(p.current_level) >= order.index(rm.target_level) and rm.target_level != "senior":
                st.info(f"سطح هدف ({LEVEL_FA[rm.target_level]}) از سطح فعلی شما بالاتر نیست؛ در چت بنویسید «می‌خوام {LEVEL_FA[order[order.index(rm.target_level) + 1]]} بشم» تا نقشه‌ی سطح بعد را ببینید.")
            with st.container(border=True):
                roadmap_view(rm, f"{tax.roles[p.target_role]['name_fa']} · {LEVEL_FA[rm.target_level]}", key="path", profile=p)
        else:
            html("""<div class="empty"><h3>نقشه‌ی راه شما اینجا ساخته می‌شود</h3>
<div class="panel-sub">در گفتگو بگویید چه شغلی می‌خواهید. حداکثر ۶ سؤال کوتاه می‌پرسم.</div>
<div class="steps"><div class="step"><b>۱. هدف</b>نقش و سطحی که می‌خواهید</div>
<div class="step"><b>۲. پیشینه</b>آنچه واقعاً بلدید، نه فقط شنیده‌اید</div>
<div class="step"><b>۳. نقشه</b>گراف مرحله‌به‌مرحله با منابع فارسی و رسمی</div></div></div>""")

# ---------------- Module B ----------------
with tab_jobs:
    side, main = st.columns([1, 2.2], gap="large")
    with side:
        with st.container(border=True):
            html('<div class="panel-title">📄 رزومه‌ی شما</div>'
                 '<div class="panel-sub">🔒 رزومه فقط در همین جلسه و در حافظه پردازش می‌شود، ذخیره یا لاگ نمی‌شود و فقط برای استخراج به سرویس هوش مصنوعی می‌رود. فقط رزومه‌ی خودتان را بارگذاری کنید.</div>')
            consent = st.checkbox("موافقم", key="consent")
            up = st.file_uploader("PDF یا DOCX، فارسی یا انگلیسی", type=["pdf", "docx"], disabled=not consent)
            if st.button("یا رزومه‌ی نمونه (مصنوعی) را امتحان کنید", width="stretch"):
                ss.resume, ss.resume_hash = sample_resume(), "sample"
            if up and consent:
                data = up.getvalue()
                h = hashlib.sha256(data).hexdigest()
                if h != ss.resume_hash:
                    try:
                        with st.spinner("در حال خواندن رزومه…"):
                            profile = parse_resume(data, up.name, llm, tax)
                            text = f"{' '.join(r.get('title', '') for r in profile.previous_roles)}\n{', '.join(profile.skills)}\n{' '.join(profile.education)}"
                            ss.resume = (profile, llm.embed([text])[0] if JOB_VECTORS else None)
                            ss.resume_hash = h
                    except Exception as exc:  # ResumeError / LLMError carry Persian messages (NF-06)
                        st.error(str(exc) if isinstance(exc, ResumeError) or is_llm_error(exc) else "خواندن رزومه انجام نشد.")
                        ss.resume, ss.resume_hash = None, None

        filters, method = {}, "hybrid"
        if ss.resume:
            profile, rvec = ss.resume
            with st.container(border=True):
                html('<div class="panel-title">👤 پروفایل استخراج‌شده</div>')
                years = fa(profile.years_experience) + " سال" if profile.years_experience is not None else "نامشخص"
                lang_fa = {"fa": "فارسی", "en": "انگلیسی"}.get(profile.language, "ترکیبی")
                html(f"""<div class="profile-row"><div class="pfact"><b>سابقه</b>{years}</div>
<div class="pfact"><b>شهر</b>{profile.location or "نامشخص"}</div>
<div class="pfact"><b>زبان رزومه</b>{lang_fa}</div></div>
<div class="label">مهارت‌ها</div>{chips(profile.skill_ids, "ok") or "—"}
<div class="label">تحصیلات</div><div style="font-size:.88rem">{"<br>".join(profile.education) or "—"}</div>""")
            with st.container(border=True):
                html('<div class="panel-title">⚙️ فیلترها</div>')
                method = st.segmented_control("روش رتبه‌بندی", ["hybrid", "baseline"], default="hybrid",
                                              format_func={"hybrid": "ترکیبی", "baseline": "پایه"}.get,
                                              help="ترکیبی: شباهت معنایی + پوشش مهارت + سطح + شهر. پایه: فقط هم‌پوشانی مهارت‌ها") or "hybrid"
                cities = sorted({j.location for j in JOBS if j.location}, key=lambda c: -sum(j.location == c for j in JOBS))[:15]
                city = st.selectbox("شهر", ["همه‌ی شهرها"] + cities)
                levels = st.pills("سطح", list(SENIORITY_FA), format_func=SENIORITY_FA.get, selection_mode="multi")
                remote_ok = st.toggle("آگهی‌های دورکاری هم باشد", value=True)
                fresh_only = st.toggle("فقط آگهی‌های ۶۰ روز اخیر", value=True, help="آگهی‌های قدیمی احتمالاً بسته شده‌اند. آگهی‌هایی که سایت حذف کرده با بررسی دوره‌ای کنار گذاشته می‌شوند")
                filters = {"city": None if city == "همه‌ی شهرها" else city, "remote_ok": remote_ok, "seniority": levels or None,
                           "max_age_days": 60 if fresh_only else None}

    with main:
        if not ss.resume:
            html("""<div class="empty"><h3>شغل‌های مناسب شما اینجا نمایش داده می‌شود</h3>
<div class="panel-sub">رزومه را از ستون کناری بارگذاری کنید. ۱۰ شغل برتر از میان آگهی‌های واقعی جابینجا، جاب‌ویژن، کاربوم، ایران‌تلنت و کوئرا رتبه‌بندی می‌شود.</div>
<div class="steps"><div class="step"><b>۱. پروفایل</b>مهارت‌ها و سابقه از رزومه استخراج می‌شود</div>
<div class="step"><b>۲. تطبیق</b>هر شغل با مهارت‌های منطبق و جاافتاده</div>
<div class="step"><b>۳. نقشه</b>برای هر شغل: چه چیزی یاد بگیرم؟</div></div></div>""")
        else:
            profile, rvec = ss.resume
            results = rank(profile, JOBS, tax, method=method, filters=filters, k=10,
                           job_vectors=JOB_VECTORS or None, resume_vector=rvec)
            gap: dict[str, int] = {}
            for r in results:
                for c in r.missing_skills:
                    gap[c] = gap.get(c, 0) + 1
            if gap:
                top_gap = sorted(gap, key=lambda c: -gap[c])[:5]
                with st.container(border=False):
                    html('<div class="insight"><b>🎯 نقشه‌ی گپ بازار:</b> این مهارت‌ها در بیشترِ ۱۰ شغل برتر از شما خواسته شده ولی ندارید<br>'
                         + " ".join(f'<span class="chip miss">{name(c)} · {fa(gap[c])} شغل</span>' for c in top_gap) + "</div>")
                    if st.toggle("نمایش نقشه‌ی راه برای این مهارت‌ها", key="gap-roadmap"):
                        with st.container(border=True):
                            rm = compute_roadmap_for_targets(tax, set(top_gap), set(profile.skill_ids), set(), label="market-gap")
                            roadmap_view(rm, "مهارت‌های پرتقاضای بازار برای شما", key="gap")
            updated = fa_date(JOBS_META.get("last_updated"), with_time=True) or "—"
            html(f'<div class="panel-sub">{fa(len(results))} شغل برتر از {fa(len(JOBS))} آگهی · آخرین به‌روزرسانی آگهی‌ها: {updated}</div>')
            if not results:
                st.warning("با این فیلترها شغلی پیدا نشد؛ فیلترها را کم‌تر کنید.")
            for rank_i, r in enumerate(results, 1):
                j = JOB_BY_ID[r.job_id]
                pct = round(r.score * 100)
                band = "hi" if pct >= 70 else "mid" if pct >= 50 else "lo"
                with st.container(border=True):
                    a, b = st.columns([6, 1])
                    meta = " · ".join(x for x in [j.company, j.location, "دورکاری" if j.remote else None,
                                                  SOURCE_FA.get(j.source, j.source), age_fa(j.date_posted)] if x)
                    a.markdown(f"<div class='job-title'><span class='rank'>{fa(rank_i)}</span>{j.title}</div>"
                               f"<div class='job-meta'>{meta}</div>", unsafe_allow_html=True)
                    b.markdown(f"<div class='score {band}'><b>{fa(pct)}٪</b><span>تطابق</span></div>", unsafe_allow_html=True)
                    html(f'<div class="label">✅ مهارت‌های منطبق</div>{chips(r.matched_skills, "ok") or "—"}'
                         f'<div class="label">❌ مهارت‌های لازم که ندارید</div>{chips(r.missing_skills, "miss") or "—"}')
                    c1, c2 = st.columns([1, 1.4])
                    c1.link_button("مشاهده‌ی آگهی اصلی ↗", j.url, width="stretch")
                    if r.missing_skills and c2.toggle("برای این شغل چه یاد بگیرم؟", key=f"b10-{j.id}"):
                        rm = compute_roadmap_for_targets(tax, job_skill_ids(j, tax), set(profile.skill_ids), set(), label=f"job:{j.id}")
                        roadmap_view(rm, f"شغل «{j.title}»", key=f"job-{j.id}")

# ---------------- evaluation & cost dashboard (the single place cost is shown, NF-05) ----------------
with tab_eval:
    left, right = st.columns([1.1, 1], gap="large")
    with left:
        with st.container(border=True):
            html('<div class="panel-title">📈 کیفیت رتبه‌بندی</div>'
                 '<div class="panel-sub">P@5 و nDCG@10 روی ۳ رزومه‌ی مصنوعی با برچسب انسانی (RFP بخش ۱۰.۲)</div>')
            res_file = ROOT / "data" / "eval" / "results.json"
            if res_file.exists():
                res = json.loads(res_file.read_text(encoding="utf-8"))
                rows = {r["method"]: r for r in res.get("table", [])}
                cols = st.columns(max(1, len(rows)))
                for col, (m, r) in zip(cols, rows.items()):
                    label = {"hybrid": "ترکیبی", "baseline": "پایه"}.get(m, m)
                    col.markdown(f'<div class="tile"><div class="k">{label}</div>'
                                 f'<div class="v">{r["P@5"]:.2f}</div><div class="k">P@5 · nDCG@10 {r["nDCG@10"]:.2f}</div></div>',
                                 unsafe_allow_html=True)
                st.dataframe(res.get("table", []), width="stretch", hide_index=True)
                if res.get("notes"):
                    st.caption(res["notes"])
            else:
                st.info("نتایج بعد از برچسب‌زنی تولید می‌شود: `scripts/eval_ranking.py score`")
        with st.container(border=True):
            html('<div class="panel-title">🗂️ داده‌ها</div>')
            per_source = JOBS_META.get("per_source", {})
            st.dataframe([{"منبع": SOURCE_FA.get(s, s), "آگهی": n} for s, n in per_source.items()], width="stretch", hide_index=True)
            st.caption(f"تاکسونومی: {fa(len(tax.roles))} نقش و {fa(len(tax.concepts))} مهارت · منابع آموزشی تأییدشده: "
                       f"{fa(sum(map(len, resources().values())))} لینک")
    with right:
        with st.container(border=True):
            u = llm.usage
            html('<div class="panel-title">💰 هزینه‌ی این جلسه</div><div class="panel-sub">هر درخواست به مدل‌ها شمارش و با قیمت‌های متیس محاسبه می‌شود.</div>')
            t1, t2 = st.columns(2)
            t1.markdown(f'<div class="tile"><div class="k">هزینه</div><div class="v">${u["cost_usd"]:.4f}</div></div>', unsafe_allow_html=True)
            t2.markdown(f'<div class="tile"><div class="k">درخواست به مدل</div><div class="v">{fa(u["calls"])}</div></div>', unsafe_allow_html=True)
            tok_in, tok_out, secs = fa(f"{u['prompt_tokens']:,}"), fa(f"{u['completion_tokens']:,}"), fa(f"{u['seconds']:.1f}")
            t3, t4 = st.columns(2)
            t3.markdown(f'<div class="tile"><div class="k">توکن ورودی / خروجی</div><div class="v" style="font-size:1.1rem">{tok_in} / {tok_out}</div></div>', unsafe_allow_html=True)
            t4.markdown(f'<div class="tile"><div class="k">زمان پاسخ مدل</div><div class="v">{secs} ث</div></div>', unsafe_allow_html=True)
            budget = llm.settings.session_budget_usd
            st.progress(min(u["cost_usd"] / budget, 1.0), text=f"از سقف بودجه‌ی جلسه (${budget})")
            prices = llm.settings.prices

            def price_str(model):
                pr = prices.get(model)
                if pr is None:
                    return "نامشخص"
                if isinstance(pr, dict):
                    return f"${pr.get('per_second', 0)} بر ثانیه"
                return f"${pr[0]} / ${pr[1]}"

            st.dataframe([
                {"کاربرد": "گفتگو و استخراج", "مدل": llm.settings.chat_model, "قیمت (ورودی / خروجی به‌ازای ۱M توکن)": price_str(llm.settings.chat_model)},
                {"کاربرد": "embedding", "مدل": llm.settings.embed_model, "قیمت (ورودی / خروجی به‌ازای ۱M توکن)": price_str(llm.settings.embed_model)},
                {"کاربرد": "صدا به متن", "مدل": llm.settings.stt_model, "قیمت (ورودی / خروجی به‌ازای ۱M توکن)": price_str(llm.settings.stt_model)},
                {"کاربرد": "متن به صدا", "مدل": llm.settings.tts_model, "قیمت (ورودی / خروجی به‌ازای ۱M توکن)": price_str(llm.settings.tts_model)},
            ], width="stretch", hide_index=True)
            st.caption("هزینه‌ی متن به صدا فقط بر اساس متن ورودی برآورد می‌شود (سرویس توکن خروجی صوتی را گزارش نمی‌دهد).")
            if u["unpriced_models"]:
                st.caption("قیمت این مدل‌ها در صفحه‌ی متیس نیامده و در هزینه صفر حساب شده: " + "، ".join(u["unpriced_models"]))

html('<div class="fine">🔒 رزومه و گفتگو فقط در همین جلسه نگه داشته می‌شود و جایی ذخیره نمی‌شود. · آگهی‌ها با رعایت robots.txt از سایت‌های عمومی جمع‌آوری شده‌اند و هر کارت به آگهی اصلی لینک می‌دهد. · '
     'نقشه‌ی راه با کد و از روی تاکسونومی محاسبه می‌شود؛ مدل زبانی فقط گفتگو می‌کند و اطلاعات استخراج می‌کند. · پروژه‌ی هکاتون بوت‌کمپ ماشین‌لرنینگ رهنما کالج</div>')
