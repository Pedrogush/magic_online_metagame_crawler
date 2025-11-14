from __future__ import annotations

from collections.abc import Callable

from repositories.card_repository import CardRepository
from utils.card_data import CardDataManager


class DeckSelectorCardDataLoader:
    """Background loader for card data triggered by the deck selector UI."""

    def __init__(self, card_repo: CardRepository) -> None:
        self.card_repo = card_repo

    def needs_loading(self) -> bool:
        return not (self.card_repo.get_card_manager() or self.card_repo.is_card_data_loading())

    def load_async(
        self,
        worker_factory: Callable[..., any],
        on_success: Callable[[CardDataManager], None],
        on_error: Callable[[Exception], None],
    ) -> None:
        self.card_repo.set_card_data_loading(True)

        def worker():
            return self.card_repo.ensure_card_data_loaded()

        worker_factory(worker, on_success=on_success, on_error=on_error).start()


__all__ = ["DeckSelectorCardDataLoader"]
