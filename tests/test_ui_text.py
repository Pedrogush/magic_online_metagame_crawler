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


def test_get_copy_uses_fallback_table_when_missing_file(monkeypatch):
    # Simulate no loaded copy and missing files
    monkeypatch.setattr(ui_text, "_copy_cache", None)
    monkeypatch.setattr(ui_text, "DEFAULT_COPY_PATHS", [])
    assert (
        ui_text.get_copy(
            "tooltips.guide.enable_double_entries",
            default="Inline",
        )
        == ui_text.FALLBACK_COPY["tooltips"]["guide"]["enable_double_entries"]
    )
    # Unknown key still falls back to provided default
    assert ui_text.get_copy("missing.key", default="Inline") == "Inline"
