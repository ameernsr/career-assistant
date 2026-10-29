from collectors.normalize import fa_normalize, html_to_text, strip_contacts, to_iso_date, guess_seniority


def test_fa_normalize_and_dates():
    assert fa_normalize("كارشناس ارشد ۲") == "کارشناس ارشد 2"
    assert to_iso_date("2026-10-27 15:56:40") == "2026-10-27"
    assert to_iso_date("1405/08/05") == "2026-10-27"
    assert to_iso_date("not a date") is None


def test_html_and_contacts():
    assert html_to_text("&lt;p&gt;سلام&lt;/p&gt;") == "سلام"
    cleaned = strip_contacts("رزومه به hr@acme.ir یا 09121234567 ارسال شود")
    assert "@" not in cleaned and "0912" not in cleaned


def test_seniority():
    assert guess_seniority("Senior Backend Developer") == "senior"
    assert guess_seniority("کارآموز تحلیل داده") == "intern"
