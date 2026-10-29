"""Add Persian course links (Maktabkhooneh, Faradars) to data/resource_candidates.json — real URLs only.

Both sites publish sitemaps whose URLs contain the course title, so for each taxonomy concept we pick the most
general matching course (whole-word alias match, prefers «مقدماتی/مبانی/جامع», penalises courses about many other
topics). Nothing is guessed: every URL comes from the site's own sitemap, and verify_links.py still checks each one.

    .venv/bin/python scripts/find_persian_courses.py && .venv/bin/python scripts/verify_links.py
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from collectors.base import Fetcher, sitemap_urls  # noqa: E402
from core.taxonomy import load_taxonomy  # noqa: E402

CANDIDATES = ROOT / "data" / "resource_candidates.json"
SITES = {
    "مکتب‌خونه": ("https://maktabkhooneh.org/sitemap/course.xml", r"maktabkhooneh\.org/course/", r"-mk\d+/?$"),
    "فرادرس": ("https://faradars.org/sitemap_product1.xml", r"faradars\.org/videos/", r"-f[a-z]{2,6}\d+/?$"),
}
GENERAL = re.compile(r"مقدماتی|مبانی|جامع|پایه|صفر|introduction|intro|basics|beginner|fundamental|complete|tutorial", re.I)


def slug_text(url: str, code_rx: str) -> str:
    slug = unquote(url.rstrip("/").rsplit("/", 1)[-1])
    return re.sub(code_rx.replace("/?$", "$"), "", slug).replace("-", " ").strip()


def main() -> None:
    tax = load_taxonomy()
    fetcher = Fetcher("course_sitemaps", verbose=False)
    candidates = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    hosts = ("maktabkhooneh.org", "faradars.org")
    for cid in candidates:  # idempotent: drop previous picks from these sites
        candidates[cid] = [r for r in candidates[cid] if not any(h in r["url"] for h in hosts)]
    added = 0
    for site, (sitemap, url_rx, code_rx) in SITES.items():
        urls = [u for u in sitemap_urls(fetcher, sitemap, url_rx, 20000) if fetcher.allowed(u)]
        best: dict[str, tuple[float, str, str]] = {}
        for url in urls:
            text = slug_text(url, code_rx)
            found = tax.find_in_text(text)
            for cid in found:
                score = 2 * bool(GENERAL.search(text)) - (len(found) - 1) - 0.05 * len(text.split())
                if cid not in best or score > best[cid][0]:
                    best[cid] = (score, url, text)
        for cid, (_, url, text) in best.items():
            candidates.setdefault(cid, []).append({"title": f"{site}: {text}", "url": url, "lang": "fa"})
            added += 1
        print(f"{site}: {len(urls)} courses in sitemap → a course for {len(best)} concepts")
    CANDIDATES.write_text(json.dumps(candidates, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"added {added} Persian course candidates → {CANDIDATES.relative_to(ROOT)} (now run scripts/verify_links.py)")


if __name__ == "__main__":
    main()
