"""Quick test of the new CardImageDisplay widget."""

import sys

import pytest

if sys.platform != "win32":
    pytest.skip("Card display test requires Windows", allow_module_level=True)

import wx  # noqa: E402
from pathlib import Path
from widgets.card_image_display import CardImageDisplay


class TestFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Card Image Display Test", size=(400, 600))

        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.Colour(34, 39, 46))

        sizer = wx.BoxSizer(wx.VERTICAL)

        # Create card image display
        self.card_display = CardImageDisplay(panel, width=260, height=360)
        sizer.Add(self.card_display, 0, wx.ALIGN_CENTER | wx.ALL, 20)

        # Buttons to test
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        placeholder_btn = wx.Button(panel, label="Show Placeholder")
        placeholder_btn.Bind(wx.EVT_BUTTON, lambda e: self.card_display.show_placeholder("Test placeholder"))
        btn_sizer.Add(placeholder_btn, 0, wx.ALL, 5)

        load_btn = wx.Button(panel, label="Load Test Image")
        load_btn.Bind(wx.EVT_BUTTON, self.on_load)
        btn_sizer.Add(load_btn, 0, wx.ALL, 5)

        sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER)

        panel.SetSizer(sizer)
        self.Centre()

    def on_load(self, event):
        # Try to load a cached image if available
        from utils.card_images import IMAGE_CACHE_DIR

        # Find any .jpg file in the cache
        cache_normal = IMAGE_CACHE_DIR / "normal"
        if cache_normal.exists():
            images = list(cache_normal.glob("*.jpg"))
            if images:
                success = self.card_display.show_image(images[0])
                if success:
                    print(f"Loaded: {images[0].name}")
                else:
                    print("Failed to load image")
                return

        self.card_display.show_placeholder("No cached images found")


if __name__ == "__main__":
    app = wx.App(False)
    frame = TestFrame()
    frame.Show()
    app.MainLoop()
