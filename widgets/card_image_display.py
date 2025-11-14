"""Card image display widget with navigation and transition animations.

Features:
- Display MTG card images with rounded corners
- Navigate between multiple printings with arrow buttons
- Smooth fade transition animations between images
- Printing counter display (e.g., "1 of 3")
"""

from __future__ import annotations

from pathlib import Path

import wx
from loguru import logger


class CardImageDisplay(wx.Panel):
    """A panel that displays MTG card images with navigation and animations."""

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
        self.corner_radius = 12

        # Image navigation state
        self.image_paths: list[Path] = []
        self.current_index: int = 0

        # Animation state
        self.animation_timer: wx.Timer | None = None
        self.animation_alpha: float = 0.0
        self.animation_target_bitmap: wx.Bitmap | None = None
        self.animation_current_bitmap: wx.Bitmap | None = None

        # Set panel size
        self.SetMinSize((width, height + 50))  # Extra space for buttons

        # Create UI components
        self._create_ui()

        # Show placeholder initially
        self.show_placeholder()

    def _create_ui(self) -> None:
        """Create the UI layout with image display and navigation buttons."""
        # Main vertical sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Image display area
        self.bitmap_ctrl = wx.StaticBitmap(self, size=(self.image_width, self.image_height))
        self.bitmap_ctrl.Bind(wx.EVT_LEFT_UP, self._on_bitmap_left_click)
        main_sizer.Add(self.bitmap_ctrl, 1, wx.EXPAND | wx.ALL, 0)

        # Navigation panel
        nav_panel = wx.Panel(self)
        nav_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left arrow button
        self.left_button = wx.Button(nav_panel, label="◀", size=(40, 30))
        self.left_button.SetToolTip("Previous printing (Left Arrow)")
        self.left_button.Bind(wx.EVT_BUTTON, self._on_previous_clicked)
        self.left_button.Enable(False)
        nav_sizer.Add(self.left_button, 0, wx.ALL, 5)

        # Counter label (e.g., "1 of 3")
        self.counter_label = wx.StaticText(nav_panel, label="", style=wx.ALIGN_CENTER)
        font = self.counter_label.GetFont()
        font.PointSize = 9
        self.counter_label.SetFont(font)
        nav_sizer.Add(self.counter_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        # Right arrow button
        self.right_button = wx.Button(nav_panel, label="▶", size=(40, 30))
        self.right_button.SetToolTip("Next printing (Right Arrow)")
        self.right_button.Bind(wx.EVT_BUTTON, self._on_next_clicked)
        self.right_button.Enable(False)
        nav_sizer.Add(self.right_button, 0, wx.ALL, 5)

        nav_panel.SetSizer(nav_sizer)
        main_sizer.Add(nav_panel, 0, wx.EXPAND | wx.ALL, 0)

        self.SetSizer(main_sizer)

        # Keyboard shortcuts
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key_down)

    def show_placeholder(self, text: str = "No image") -> None:
        """Display a placeholder with optional text.

        Args:
            text: Text to display in the placeholder
        """
        self.image_paths = []
        self.current_index = 0
        bitmap = self._create_placeholder_bitmap(text)
        self.bitmap_ctrl.SetBitmap(bitmap)
        self._update_navigation()
        self.Refresh()

    def show_images(self, image_paths: list[Path], start_index: int = 0) -> bool:
        """Display a list of card images with navigation.

        Args:
            image_paths: List of paths to image files
            start_index: Index to start at (default: 0)

        Returns:
            True if at least one image loaded successfully, False otherwise
        """
        if not image_paths:
            self.show_placeholder("No images")
            return False

        # Filter to only existing paths
        valid_paths = [p for p in image_paths if p and p.exists()]
        if not valid_paths:
            self.show_placeholder("Images not found")
            return False

        self.image_paths = valid_paths
        self.current_index = min(start_index, len(valid_paths) - 1)

        # Load first image without animation
        success = self._load_image_at_index(self.current_index, animate=False)
        self._update_navigation()

        return success

    def show_image(self, image_path: Path) -> bool:
        """Display a single card image (convenience method).

        Args:
            image_path: Path to the image file

        Returns:
            True if image loaded successfully, False otherwise
        """
        return self.show_images([image_path] if image_path else [])

    def _load_image_at_index(self, index: int, animate: bool = True) -> bool:
        """Load and display the image at the given index.

        Args:
            index: Index in image_paths list
            animate: Whether to use fade transition

        Returns:
            True if successful, False otherwise
        """
        if not 0 <= index < len(self.image_paths):
            return False

        image_path = self.image_paths[index]

        try:
            # Load the image
            img = wx.Image(str(image_path), wx.BITMAP_TYPE_ANY)
            if not img.IsOk():
                logger.debug(f"Failed to load image: {image_path}")
                return False

            # Scale to fit while maintaining aspect ratio
            img_width = img.GetWidth()
            img_height = img.GetHeight()

            scale_w = self.image_width / img_width
            scale_h = self.image_height / img_height
            scale = min(scale_w, scale_h)

            new_width = int(img_width * scale)
            new_height = int(img_height * scale)

            img = img.Scale(new_width, new_height, wx.IMAGE_QUALITY_HIGH)

            # Create bitmap with rounded corners
            bitmap = self._create_rounded_bitmap(img)

            # Display with or without animation
            if animate and self.bitmap_ctrl.GetBitmap().IsOk():
                self._start_fade_animation(bitmap)
            else:
                self.bitmap_ctrl.SetBitmap(bitmap)
                self.Refresh()

            return True

        except Exception as exc:
            logger.exception(f"Error loading image {image_path}: {exc}")
            return False

    def _start_fade_animation(self, target_bitmap: wx.Bitmap) -> None:
        """Start a fade transition animation to the target bitmap.

        Args:
            target_bitmap: The bitmap to fade to
        """
        # Cancel any existing animation
        if self.animation_timer and self.animation_timer.IsRunning():
            self.animation_timer.Stop()

        # Set up animation state
        self.animation_current_bitmap = self.bitmap_ctrl.GetBitmap()
        self.animation_target_bitmap = target_bitmap
        self.animation_alpha = 0.0

        # Create and start timer (60 FPS)
        self.animation_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_animation_tick, self.animation_timer)
        self.animation_timer.Start(16)  # ~60 FPS

    def _on_animation_tick(self, event: wx.TimerEvent) -> None:
        """Handle animation timer tick."""
        # Increment alpha (fade speed)
        self.animation_alpha += 0.15

        if self.animation_alpha >= 1.0:
            # Animation complete
            self.animation_timer.Stop()
            self.bitmap_ctrl.SetBitmap(self.animation_target_bitmap)
            self.animation_current_bitmap = None
            self.animation_target_bitmap = None
            self.Refresh()
            return

        # Create blended bitmap
        blended = self._blend_bitmaps(
            self.animation_current_bitmap, self.animation_target_bitmap, self.animation_alpha
        )

        self.bitmap_ctrl.SetBitmap(blended)
        self.Refresh()

    def _blend_bitmaps(self, bmp1: wx.Bitmap, bmp2: wx.Bitmap, alpha: float) -> wx.Bitmap:
        """Blend two bitmaps with the given alpha value.

        Args:
            bmp1: Source bitmap (fading out)
            bmp2: Target bitmap (fading in)
            alpha: Blend factor (0.0 = bmp1, 1.0 = bmp2)

        Returns:
            Blended bitmap
        """
        # Convert bitmaps to images for pixel manipulation
        img1 = bmp1.ConvertToImage()
        img2 = bmp2.ConvertToImage()

        # Ensure same size
        if img1.GetSize() != img2.GetSize():
            img1 = img1.Resize(img2.GetSize(), (0, 0))

        # Create a copy and blend manually
        result = img1.Copy()

        # Blend RGB values
        data1 = img1.GetData()
        data2 = img2.GetData()
        blended_data = bytearray(len(data1))

        for i in range(0, len(data1), 3):
            blended_data[i] = int(data1[i] * (1 - alpha) + data2[i] * alpha)
            blended_data[i + 1] = int(data1[i + 1] * (1 - alpha) + data2[i + 1] * alpha)
            blended_data[i + 2] = int(data1[i + 2] * (1 - alpha) + data2[i + 2] * alpha)

        result.SetData(bytes(blended_data))

        return wx.Bitmap(result)

    def _update_navigation(self) -> None:
        """Update navigation button states and counter label."""
        num_images = len(self.image_paths)

        if num_images <= 1:
            # Hide navigation for single or no images
            self.left_button.Enable(False)
            self.right_button.Enable(False)
            self.counter_label.SetLabel("")
        else:
            # Enable/disable buttons based on position
            self.left_button.Enable(self.current_index > 0)
            self.right_button.Enable(self.current_index < num_images - 1)

            # Update counter
            self.counter_label.SetLabel(f"{self.current_index + 1} of {num_images}")

        # Force button refresh
        self.left_button.Refresh()
        self.right_button.Refresh()

    def _on_previous_clicked(self, event: wx.CommandEvent) -> None:
        """Handle previous button click."""
        logger.debug(f"Previous button clicked, current index: {self.current_index}")
        if self.current_index > 0:
            self.current_index -= 1
            logger.debug(f"Moving to index: {self.current_index}")
            self._load_image_at_index(self.current_index, animate=True)
            self._update_navigation()
        event.Skip()

    def _on_next_clicked(self, event: wx.CommandEvent) -> None:
        """Handle next button click."""
        logger.debug(f"Next button clicked, current index: {self.current_index}")
        if self.current_index < len(self.image_paths) - 1:
            self.current_index += 1
            logger.debug(f"Moving to index: {self.current_index}")
            self._load_image_at_index(self.current_index, animate=True)
            self._update_navigation()
        event.Skip()

    def _on_key_down(self, event: wx.KeyEvent) -> None:
        """Handle keyboard navigation."""
        keycode = event.GetKeyCode()

        if keycode == wx.WXK_LEFT and self.left_button.IsEnabled():
            self._on_previous_clicked(None)
        elif keycode == wx.WXK_RIGHT and self.right_button.IsEnabled():
            self._on_next_clicked(None)
        else:
            event.Skip()

    def _on_bitmap_left_click(self, event: wx.MouseEvent) -> None:
        """Toggle to the next image when the bitmap is clicked."""
        if len(self.image_paths) > 1:
            self._on_next_clicked(event)
        else:
            event.Skip()

    def _create_rounded_bitmap(self, image: wx.Image) -> wx.Bitmap:
        """Create a bitmap with the image centered and rounded corners.

        Uses alpha channel manipulation for proper rounded corner clipping.

        Args:
            image: The wx.Image to display

        Returns:
            A wx.Bitmap with rounded corners
        """
        # Create a bitmap canvas
        bitmap = wx.Bitmap(self.image_width, self.image_height)
        dc = wx.MemoryDC(bitmap)

        # Fill background with parent color
        bg_color = self.GetParent().GetBackgroundColour()
        dc.SetBackground(wx.Brush(bg_color))
        dc.Clear()

        # Draw dark background rounded rectangle
        dc.SetPen(wx.Pen(wx.Colour(40, 40, 40), 1))
        dc.SetBrush(wx.Brush(wx.Colour(40, 40, 40)))
        dc.DrawRoundedRectangle(0, 0, self.image_width, self.image_height, self.corner_radius)

        # Center the image
        img_width = image.GetWidth()
        img_height = image.GetHeight()
        x = (self.image_width - img_width) // 2
        y = (self.image_height - img_height) // 2

        # Create a rounded corner mask and apply it to the image
        masked_image = self._apply_rounded_corners_to_image(image, self.corner_radius)

        # Draw the masked image
        dc.DrawBitmap(wx.Bitmap(masked_image), x, y, True)

        # Draw border using GraphicsContext for smooth anti-aliased edges
        gc = wx.GraphicsContext.Create(dc)
        if gc:
            gc.SetPen(wx.Pen(wx.Colour(60, 60, 60), 1))
            gc.SetBrush(wx.TRANSPARENT_BRUSH)
            path = gc.CreatePath()
            path.AddRoundedRectangle(
                0.5, 0.5, self.image_width - 1, self.image_height - 1, self.corner_radius
            )
            gc.DrawPath(path)
        else:
            # Fallback border without antialiasing
            dc.SetPen(wx.Pen(wx.Colour(60, 60, 60), 1))
            dc.SetBrush(wx.TRANSPARENT_BRUSH)
            dc.DrawRoundedRectangle(0, 0, self.image_width, self.image_height, self.corner_radius)

        dc.SelectObject(wx.NullBitmap)
        return bitmap

    def _apply_rounded_corners_to_image(self, image: wx.Image, radius: int) -> wx.Image:
        """Apply rounded corners to an image using alpha channel manipulation.

        Args:
            image: The wx.Image to process
            radius: Corner radius in pixels

        Returns:
            A new wx.Image with rounded corners
        """
        # Make a copy to avoid modifying the original
        img = image.Copy()

        # Ensure image has alpha channel
        if not img.HasAlpha():
            img.InitAlpha()

        width = img.GetWidth()
        height = img.GetHeight()

        # Get alpha data as bytearray for modification
        alpha_data = bytearray(img.GetAlpha())

        # Helper function to check if a point is inside the rounded rectangle
        def is_inside_rounded_rect(px, py):
            # Check if point is in corner regions
            # Top-left corner
            if px < radius and py < radius:
                dx = radius - px
                dy = radius - py
                return (dx * dx + dy * dy) <= (radius * radius)
            # Top-right corner
            elif px >= width - radius and py < radius:
                dx = px - (width - radius - 1)
                dy = radius - py
                return (dx * dx + dy * dy) <= (radius * radius)
            # Bottom-left corner
            elif px < radius and py >= height - radius:
                dx = radius - px
                dy = py - (height - radius - 1)
                return (dx * dx + dy * dy) <= (radius * radius)
            # Bottom-right corner
            elif px >= width - radius and py >= height - radius:
                dx = px - (width - radius - 1)
                dy = py - (height - radius - 1)
                return (dx * dx + dy * dy) <= (radius * radius)
            # Not in any corner region - always inside
            return True

        # Apply rounded corner mask to alpha channel
        for y in range(height):
            for x in range(width):
                idx = y * width + x
                if not is_inside_rounded_rect(x, y):
                    alpha_data[idx] = 0  # Make transparent
                # else: keep existing alpha value

        # Set the modified alpha data
        img.SetAlpha(bytes(alpha_data))

        return img

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
        dc.SetPen(wx.Pen(wx.Colour(80, 80, 80), 2))
        dc.SetBrush(wx.Brush(wx.Colour(50, 50, 50)))
        dc.DrawRoundedRectangle(
            5, 5, self.image_width - 10, self.image_height - 10, self.corner_radius
        )

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

    def __del__(self):
        """Cleanup when widget is destroyed."""
        if self.animation_timer and self.animation_timer.IsRunning():
            self.animation_timer.Stop()
