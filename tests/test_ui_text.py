from utils import ui_text


def test_get_copy_uses_default_and_format(monkeypatch):
    monkeypatch.setattr(
        ui_text,
        "_copy_cache",
        {"tooltips": {"sample": "Value {count}"}, "messages": {"plain": "Hello"}},
    )

    assert ui_text.get_copy("tooltips.sample", "Fallback", count=3) == "Value 3"
    assert ui_text.get_copy("messages.plain", "Fallback") == "Hello"
    assert ui_text.get_copy("messages.missing", "Fallback") == "Fallback"
