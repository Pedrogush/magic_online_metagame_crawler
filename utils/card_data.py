import io
import json
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger

try:
    from curl_cffi import requests
except ImportError as exc:
    requests = None
    _HTTP_IMPORT_ERROR = exc
else:
    _HTTP_IMPORT_ERROR = None


ATOMIC_META_URL = "https://mtgjson.com/api/v5/AtomicCards.meta.json"
ATOMIC_DATA_URL = "https://mtgjson.com/api/v5/AtomicCards.json.zip"


class CardDataManager:
    def __init__(self, data_dir: Path | str = Path("data")):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.data_dir / "atomic_cards_index.json"
        self.meta_path = self.data_dir / "atomic_cards_meta.json"
        self._cards: Optional[List[Dict[str, Any]]] = None
        self._cards_by_name: Optional[Dict[str, Dict[str, Any]]] = None

    def ensure_latest(self, force: bool = False) -> None:
        if requests is None:
            if not self.index_path.exists():
                raise RuntimeError(
                    "curl_cffi is required to download MTGJSON data. "
                    "Install it with: pip install curl_cffi"
                ) from _HTTP_IMPORT_ERROR
            logger.warning("curl_cffi missing; using cached MTGJSON data only")
            self._load_index()
            return

        remote_meta = self._fetch_remote_meta()
        local_meta = self._load_json(self.meta_path) or {}
        remote_sha = remote_meta.get("sha512") if remote_meta else None
        local_sha = local_meta.get("sha512")
        missing_index = not self.index_path.exists()
        needs_refresh = force or missing_index or (remote_sha and remote_sha != local_sha)

        if needs_refresh:
            if requests is None:
                if missing_index:
                    raise RuntimeError(
                        "curl_cffi is required to download MTGJSON data. "
                        "Install it with: pip install curl_cffi"
                    ) from _HTTP_IMPORT_ERROR
                logger.warning("curl_cffi missing; continuing with cached MTGJSON data")
            else:
                try:
                    if remote_meta:
                        logger.info("Refreshing MTGJSON AtomicCards dataset")
                    else:
                        logger.info("Fetching MTGJSON AtomicCards dataset (meta unavailable)")
                    self._download_and_rebuild(remote_meta or {})
                except Exception as exc:
                    if missing_index:
                        raise RuntimeError("Card data download failed and no cache is available") from exc
                    logger.warning(f"Failed to refresh MTGJSON data, using cache: {exc}")
        self._load_index()

    def search_cards(
        self,
        query: str = "",
        format_filter: Optional[str] = None,
        type_filter: Optional[str] = None,
        color_identity: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        self._require_cards()
        query = (query or "").strip().lower()
        fmt = (format_filter or "").strip().lower()
        type_filter = (type_filter or "").strip().lower()
        color_identity = [c.upper() for c in (color_identity or [])]
        results: List[Dict[str, Any]] = []
        for card in self._cards or []:
            name_lower = card["name_lower"]
            type_line = (card.get("type_line") or "").lower()
            oracle_text = (card.get("oracle_text") or "").lower()
            if query:
                haystacks = (
                    name_lower,
                    type_line,
                    oracle_text,
                )
                if not any(query in h for h in haystacks if h):
                    continue
            if fmt and card.get("legalities", {}).get(fmt) != "Legal":
                continue
            if type_filter and type_filter not in type_line:
                continue
            if color_identity:
                identity = card.get("color_identity", [])
                if not all(c in identity for c in color_identity):
                    continue
            results.append(card)
            if limit and len(results) >= limit:
                break
        return results

    def get_card(self, name: str) -> Optional[Dict[str, Any]]:
        self._require_cards()
        return (self._cards_by_name or {}).get(name.lower())

    def available_formats(self) -> List[str]:
        self._require_cards()
        seen = set()
        formats: List[str] = []
        for card in self._cards or []:
            for fmt, state in (card.get("legalities") or {}).items():
                if state != "Legal" or fmt in seen:
                    continue
                seen.add(fmt)
                formats.append(fmt)
        return sorted(formats)

    def _require_cards(self) -> None:
        if self._cards is None:
            raise RuntimeError("Card data not loaded; call ensure_latest first")

    def _fetch_remote_meta(self) -> Optional[Dict[str, Any]]:
        try:
            resp = requests.get(ATOMIC_META_URL, impersonate="chrome", timeout=60)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning(f"Failed to fetch MTGJSON meta: {exc}")
            return None

    def _download_and_rebuild(self, remote_meta: Dict[str, Any]) -> None:
        resp = requests.get(ATOMIC_DATA_URL, impersonate="chrome", timeout=300)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            with zf.open("AtomicCards.json") as source:
                raw = json.load(source)
        index = self._build_index(raw.get("data", {}))
        self.index_path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
        if remote_meta:
            self.meta_path.write_text(json.dumps(remote_meta, ensure_ascii=False), encoding="utf-8")
        self._cards = index["cards"]
        self._cards_by_name = index["cards_by_name"]

    def _load_index(self) -> None:
        data = self._load_json(self.index_path)
        if not data:
            raise RuntimeError("Card data index missing or invalid")
        self._cards = data["cards"]
        self._cards_by_name = data["cards_by_name"]

    def _load_json(self, path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning(f"Invalid JSON at {path}: {exc}")
            return None

    def _build_index(self, atomic_cards: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        cards: Dict[str, Dict[str, Any]] = {}
        for variations in atomic_cards.values():
            if not isinstance(variations, list):
                continue
            for printing in variations:
                if printing.get("isToken") or printing.get("layout") == "token":
                    continue
                face_name = printing.get("faceName") or printing.get("name")
                if not face_name:
                    continue
                key = face_name.lower()
                existing = cards.get(key)
                candidate = self._simplify_printing(printing, face_name)
                if not existing:
                    cards[key] = candidate
                else:
                    existing["legalities"] = self._merge_legalities(
                        existing.get("legalities"), candidate.get("legalities")
                    )
        card_list = sorted(cards.values(), key=lambda c: c["name_lower"])
        return {
            "cards": card_list,
            "cards_by_name": {card["name_lower"]: card for card in card_list},
        }

    def _simplify_printing(self, printing: Dict[str, Any], face_name: str) -> Dict[str, Any]:
        legalities = printing.get("legalities") or {}
        mana_value = printing.get("manaValue")
        if isinstance(mana_value, str):
            try:
                mana_value = float(mana_value)
            except ValueError:
                pass
        simplified = {
            "name": face_name,
            "name_lower": face_name.lower(),
            "mana_cost": printing.get("manaCost"),
            "mana_value": mana_value,
            "type_line": printing.get("type"),
            "oracle_text": printing.get("text"),
            "power": printing.get("power"),
            "toughness": printing.get("toughness"),
            "loyalty": printing.get("loyalty"),
            "colors": printing.get("colors") or [],
            "color_identity": printing.get("colorIdentity") or [],
            "legalities": {k.lower(): v for k, v in legalities.items()},
        }
        return simplified

    def _merge_legalities(
        self,
        base: Optional[Dict[str, Any]],
        incoming: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        merged: Dict[str, Any] = {}
        for source in (base or {}), (incoming or {}):
            for fmt, state in source.items():
                if state == "Legal":
                    merged[fmt] = state
        return merged


__all__ = ["CardDataManager"]
