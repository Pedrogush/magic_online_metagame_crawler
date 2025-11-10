import pytest
import wx

from tests.ui.conftest import prepare_card_manager, pump_ui_events


@pytest.mark.usefixtures("wx_app")
def test_deck_selector_loads_archetypes_and_mainboard_stats(
    deck_selector_factory,
):
    frame = deck_selector_factory()
    try:
        frame.fetch_archetypes()
        pump_ui_events(wx.GetApp(), iterations=8)
        assert frame.archetype_list.GetCount() == 2

        frame.archetype_list.SetSelection(0)
        frame.on_archetype_selected(None)
        pump_ui_events(wx.GetApp(), iterations=8)

        assert frame.deck_list.GetCount() == 1
        frame.deck_list.SetSelection(0)
        frame.on_deck_selected(None)

        frame.on_load_deck_clicked(None)
        pump_ui_events(wx.GetApp(), iterations=12)

        assert "8 card" in frame.main_table.count_label.GetLabel()
        assert "Mainboard: 8 cards" in frame.stats_summary.GetLabel()
        assert frame.copy_button.IsEnabled()
    finally:
        frame.Destroy()


@pytest.mark.usefixtures("wx_app")
def test_builder_search_populates_results(
    deck_selector_factory,
):
    frame = deck_selector_factory()
    try:
        prepare_card_manager(frame)
        frame._show_left_panel("builder", force=True)
        name_ctrl = frame.builder_inputs["name"]
        name_ctrl.ChangeValue("Mountain")
        frame.on_builder_search(None)
        pump_ui_events(wx.GetApp(), iterations=4)

        assert frame.builder_results_ctrl.GetItemCount() >= 1
        assert "Mountain" in frame.builder_results_ctrl.GetItemText(0)
    finally:
        frame.Destroy()


@pytest.mark.usefixtures("wx_app")
def test_notes_persist_across_frames(
    deck_selector_factory,
):
    first_frame = deck_selector_factory()
    try:
        first_frame.current_deck = {"href": "manual", "name": "Manual Deck"}
        first_frame.deck_notes_text.ChangeValue("Important note")
        first_frame._save_current_notes()
    finally:
        first_frame.Destroy()

    second_frame = deck_selector_factory()
    try:
        second_frame.current_deck = {"href": "manual", "name": "Manual Deck"}
        second_frame._load_notes_for_current()
        assert second_frame.deck_notes_text.GetValue() == "Important note"
    finally:
        second_frame.Destroy()
