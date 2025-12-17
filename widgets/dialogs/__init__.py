"""Dialog windows for the MTG deck selector application."""

from widgets.dialogs.feedback_dialog import FeedbackDialog, show_feedback_dialog
from widgets.dialogs.image_download_dialog import ImageDownloadDialog, show_image_download_dialog

__all__ = [
    "FeedbackDialog",
    "ImageDownloadDialog",
    "show_feedback_dialog",
    "show_image_download_dialog",
]
