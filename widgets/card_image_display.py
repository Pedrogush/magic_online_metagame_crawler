"""Simple card image display widget with rounded corners.

Clean implementation without any legacy code.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import wx
from loguru import logger


class CardImageDisplay(wx.Panel):
    """A panel that displays MTG card images with rounded corners."""

    def __init__(self, parent: wx.Window, width: int = 260, height: int = 360):
        """Initialize the card image display.

        Args:
            parent: Parent window
            width: Image display width in pixels
            height: Image display height in pixels
        """
        super().__init__(parent)

        self.image_width = width
        self.image_height = height

        # Set panel size
        self.SetMinSize((width, height))
        self.SetSize((width, height))

        # Create the static bitmap that will hold the image
        self.bitmap_ctrl = wx.StaticBitmap(self, size=(width, height))

        # Layout
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.bitmap_ctrl, 1, wx.EXPAND | wx.ALL, 0)
        self.SetSizer(sizer)

        # Show placeholder initially
        self.show_placeholder()

    def show_placeholder(self, text: str = "No image") -> None:
        """Display a placeholder with optional text.

        Args:
            text: Text to display in the placeholder
        """
        bitmap = self._create_placeholder_bitmap(text)
        self.bitmap_ctrl.SetBitmap(bitmap)
        self.Refresh()

    def show_image(self, image_path: Path) -> bool:
        """Display a card image from file.

        Args:
            image_path: Path to the image file

        Returns:
            True if image loaded successfully, False otherwise
        """
        if not image_path or not image_path.exists():
            logger.debug(f"Image path does not exist: {image_path}")
            self.show_placeholder("Image not found")
            return False

        try:
            # Load the image
            img = wx.Image(str(image_path), wx.BITMAP_TYPE_ANY)
            if not img.IsOk():
                logger.debug(f"Failed to load image: {image_path}")
                self.show_placeholder("Invalid image")
                return False

            # Scale to fit while maintaining aspect ratio
            img_width = img.GetWidth()
            img_height = img.GetHeight()

            # Calculate scaling to fit within our dimensions
            scale_w = self.image_width / img_width
            scale_h = self.image_height / img_height
            scale = min(scale_w, scale_h)

            new_width = int(img_width * scale)
            new_height = int(img_height * scale)

            # Scale the image
            img = img.Scale(new_width, new_height, wx.IMAGE_QUALITY_HIGH)

            # Create bitmap with rounded corners
            bitmap = self._create_rounded_bitmap(img)

            # Display
            self.bitmap_ctrl.SetBitmap(bitmap)
            self.Refresh()

            return True

        except Exception as exc:
            logger.exception(f"Error loading image {image_path}: {exc}")
            self.show_placeholder("Load error")
            return False

    def _create_rounded_bitmap(self, image: wx.Image) -> wx.Bitmap:
        """Create a bitmap with the image centered and rounded corners.

        Args:
            image: The wx.Image to display

        Returns:
            A wx.Bitmap with rounded corners
        """
        # Create a bitmap canvas
        bitmap = wx.Bitmap(self.image_width, self.image_height)
        dc = wx.MemoryDC(bitmap)

        # Fill background
        bg_color = self.GetParent().GetBackgroundColour()
        dc.SetBackground(wx.Brush(bg_color))
        dc.Clear()

        # Draw rounded rectangle background
        corner_radius = 12
        dc.SetPen(wx.Pen(wx.Colour(60, 60, 60), 1))
        dc.SetBrush(wx.Brush(wx.Colour(40, 40, 40)))
        dc.DrawRoundedRectangle(0, 0, self.image_width, self.image_height, corner_radius)

        # Center the image
        img_width = image.GetWidth()
        img_height = image.GetHeight()
        x = (self.image_width - img_width) // 2
        y = (self.image_height - img_height) // 2

        # Draw the image
        dc.DrawBitmap(wx.Bitmap(image), x, y, True)

        dc.SelectObject(wx.NullBitmap)
        return bitmap

    def _create_placeholder_bitmap(self, text: str) -> wx.Bitmap:
        """Create a placeholder bitmap with text.

        Args:
            text: Text to display

        Returns:
            A wx.Bitmap for the placeholder
        """
        bitmap = wx.Bitmap(self.image_width, self.image_height)
        dc = wx.MemoryDC(bitmap)

        # Background
        bg_color = self.GetParent().GetBackgroundColour()
        dc.SetBackground(wx.Brush(bg_color))
        dc.Clear()

        # Draw rounded rectangle
        corner_radius = 12
        dc.SetPen(wx.Pen(wx.Colour(80, 80, 80), 2))
        dc.SetBrush(wx.Brush(wx.Colour(50, 50, 50)))
        dc.DrawRoundedRectangle(5, 5, self.image_width - 10, self.image_height - 10, corner_radius)

        # Draw text
        dc.SetTextForeground(wx.Colour(150, 150, 150))
        font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        dc.SetFont(font)

        text_width, text_height = dc.GetTextExtent(text)
        text_x = (self.image_width - text_width) // 2
        text_y = (self.image_height - text_height) // 2
        dc.DrawText(text, text_x, text_y)

        dc.SelectObject(wx.NullBitmap)
        return bitmap
