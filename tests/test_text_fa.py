from core.text_fa import fa_normalize, skill_key


def test_pdf_presentation_forms_become_normal_letters():
    # Copied from a real LuaTeX PDF: glyph-shaped Arabic presentation forms (U+FExx/U+FBxx).
    assert fa_normalize("ﻣﺴﺎﺑﻘﻪ") == "مسابقه"
    assert fa_normalize("ﺗﯿﻢ") == "تیم"


def test_presentation_form_skill_resolves_like_typed_text():
    assert skill_key("ﺍﮐﺴﻞ") == skill_key("اکسل")
