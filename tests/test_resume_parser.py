import io
from datetime import date

import pytest

from core.resume_parser import ResumeError, experience_years, extract_text


def _docx(paragraphs):
    from docx import Document

    d = Document()
    for p in paragraphs:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _pdf(text):
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), text)
    return doc.tobytes()


def test_docx_text_is_extracted_and_normalized():
    text = extract_text(_docx(["تحلیلگر داده", "مهارت‌ها: اكسل، SQL، آمار توصیفی و ساخت داشبورد",
                               "سوابق: کارآموز تحلیل داده در یک فروشگاه اینترنتی از ۱۴۰۲ تا ۱۴۰۳"]), "cv.docx")
    assert "تحلیلگر داده" in text and "اکسل" in text  # Arabic kaf normalized


def test_pdf_text_is_extracted():
    text = "Python developer, 3 years, Django, PostgreSQL, Docker. Built REST APIs for an online shop."
    assert "Python developer" in extract_text(_pdf(text), "resume.PDF")


@pytest.mark.parametrize("data, name, needle", [
    (b"not a real pdf", "cv.pdf", "خوانده"),
    (b"x", "cv.doc", "DOCX"),
    (b"x", "cv.png", "PDF"),
    (b"x" * (6 * 1024 * 1024), "cv.pdf", "۵"),
])
def test_bad_files_give_persian_errors(data, name, needle):
    with pytest.raises(ResumeError, match=needle):
        extract_text(data, name)


def test_scanned_pdf_without_text_is_reported():
    import pymupdf

    doc = pymupdf.open()
    doc.new_page()
    with pytest.raises(ResumeError, match="اسکن"):
        extract_text(doc.tobytes(), "scan.pdf")


TODAY = date(2026, 10, 29)


def test_years_merge_overlaps_and_handle_present():
    roles = [{"start": "2020-01", "end": "2022-01"}, {"start": "2021-01", "end": "2023-01"}, {"start": "2024-01", "end": "present"}]
    assert experience_years(roles, today=TODAY) == pytest.approx(3.0 + 2.83, abs=0.05)


def test_years_accept_jalali_and_persian_words():
    roles = [{"start": "1401/01", "end": "تاکنون"}]  # 1401/01 ≈ March 2022
    assert experience_years(roles, today=TODAY) == pytest.approx(4.6, abs=0.15)


def test_years_unknown_dates_give_none():
    assert experience_years([{"start": None, "end": None}], today=TODAY) is None
    assert experience_years([], today=TODAY) is None


def test_years_accept_month_first_dates():
    # MM/YYYY, as many English resumes write it: 12/2022 → 03/2026 is 3.25 years, not 4.
    roles = [{"start": "12/2022", "end": "09/2023"}, {"start": "09/2023", "end": "10/2024"}, {"start": "10/2024", "end": "03/2026"}]
    assert experience_years(roles, today=TODAY) == pytest.approx(3.25, abs=0.05)
