"""PythonNET integration helpers for MTGOSDK access."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Dict

from loguru import logger

try:
    import pythonnet  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    pythonnet = None  # type: ignore

AppDomain = None  # type: ignore
FileLoadException = Exception  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[1]

_LOAD_LOCK = threading.RLock()
_SDK_MODULE = None
_CLR = None
_LOAD_ERROR: Exception | None = None


def is_available() -> bool:
    """Return True if MTGOSDK is ready for use via pythonnet."""
    _ensure_loaded()
    return _SDK_MODULE is not None


def is_initialized() -> bool:
    return _SDK_MODULE is not None


def availability_error() -> Exception | None:
    """Return the last initialization error, if any."""
    _ensure_loaded()
    return _LOAD_ERROR


def initialize(force: bool = False) -> bool:
    """Attempt to load MTGOSDK runtime immediately."""
    global _SDK_MODULE, _LOAD_ERROR, _CLR
    if force:
        with _LOAD_LOCK:
            _SDK_MODULE = None
            _LOAD_ERROR = None
            _CLR = None
    _ensure_loaded()
    return _SDK_MODULE is not None


def get_game_state(self_name: str | None = None) -> Dict[str, Any]:
    """Return live game state snapshot using MTGOSDK."""
    sdk = _require_sdk()
    EventManager = sdk.API.Play.EventManager  # type: ignore[attr-defined]
    Match = sdk.API.Play.Match  # type: ignore[attr-defined]
    Tournament = sdk.API.Play.Tournaments.Tournament  # type: ignore[attr-defined]

    def _find_active_match():
        try:
            joined_events = list(EventManager.JoinedEvents)  # type: ignore[call-overload]
        except TypeError:
            joined_events = EventManager.JoinedEvents
        for evt in joined_events:
            if isinstance(evt, Match) and not evt.IsComplete:
                return evt
            if isinstance(evt, Tournament):
                rounds = evt.Rounds
                if rounds is None:
                    continue
                for round_obj in rounds:
                    matches = round_obj.Matches
                    if matches is None:
                        continue
                    for candidate in matches:
                        if not candidate.IsComplete:
                            return candidate
        return None

    active_match = _find_active_match()
    active_game = None
    if active_match is not None:
        try:
            active_game = active_match.CurrentGame
        except AttributeError:
            active_game = None
        if active_game is None:
            games = getattr(active_match, "Games", None)
            if games is not None:
                try:
                    games_list = list(games)
                except TypeError:
                    games_list = games
                if games_list:
                    active_game = games_list[-1]

    players_payload: list[dict[str, Any]] | None = None
    if active_game is not None:
        players_payload = []
        try:
            players = list(active_game.Players)
        except TypeError:
            players = active_game.Players
        if players:
            for player in players:
                name = getattr(player, "Name", None)
                clock = getattr(player, "ChessClock", None)
                seconds_value = 0.0
                if clock is not None:
                    seconds_attr = getattr(clock, "TotalSeconds", 0.0)
                    try:
                        seconds_value = float(seconds_attr)
                    except (TypeError, ValueError):
                        seconds_value = 0.0
                is_self = False
                if self_name and name:
                    is_self = name.lower() == self_name.lower()
                players_payload.append(
                    {
                        "name": name,
                        "clockSeconds": max(0, int(round(seconds_value))),
                        "isSelf": is_self,
                    }
                )

    parent_event = None
    if active_match is not None:
        try:
            parent_event = EventManager.FindParentEvent(EventManager.JoinedEvents, active_match)
        except Exception:
            parent_event = None

    payload: Dict[str, Any] = {}
    if parent_event is not None:
        payload["eventInfo"] = {
            "id": str(getattr(parent_event, "Id", "")),
            "description": getattr(parent_event, "Description", None),
            "isCompleted": bool(getattr(parent_event, "IsCompleted", False)),
            "format": str(getattr(parent_event, "Format", None)),
        }

    if active_match is not None:
        payload["match"] = {
            "id": str(getattr(active_match, "Id", "")),
            "state": str(getattr(active_match, "State", "")),
            "isComplete": bool(getattr(active_match, "IsComplete", False)),
            "challengeText": getattr(active_match, "ChallengeText", None),
        }

    if active_game is not None:
        payload["game"] = {
            "id": str(getattr(active_game, "Id", "")),
            "status": str(getattr(active_game, "Status", "")),
            "isReplay": bool(getattr(active_game, "IsReplay", False)),
            "players": players_payload,
        }

    if players_payload is not None:
        payload["players"] = players_payload

    payload["matches"] = _gather_event_matches(include_completed=False)
    return payload


def accept_pending_trades() -> Dict[str, Any]:
    """Attempt to accept or ready the active trade session."""
    sdk = _require_sdk()
    TradeManager = sdk.API.Trade.TradeManager  # type: ignore[attr-defined]
    DLRWrapper = sdk.Core.Reflection.DLRWrapper  # type: ignore[attr-defined]

    trade = getattr(TradeManager, "CurrentTrade", None)
    if trade is None:
        return {"accepted": False, "reason": "No active trade"}

    try:
        raw_trade = DLRWrapper.Unbind(trade)
    except Exception:
        raw_trade = trade

    invoked = False
    for method_name in ("AcceptTrade", "Accept", "ConfirmTrade", "ApproveTrade", "FinalizeTrade"):
        invoked |= _try_invoke(raw_trade, method_name)
    for method_name in ("SetLocalReadyState", "SetReady", "SetAccepted"):
        invoked |= _try_invoke(raw_trade, method_name, True)

    if not invoked:
        return {"accepted": False, "reason": "No known trade acceptors found"}

    partner = getattr(getattr(trade, "TradePartner", None), "Name", None)
    return {"accepted": True, "partner": partner}


def list_decks_grouped() -> list[dict[str, Any]]:
    """Return deck summaries grouped by format."""
    sdk = _require_sdk()
    CollectionManager = sdk.API.Collection.CollectionManager  # type: ignore[attr-defined]
    DeckRegion = sdk.API.Collection.DeckRegion  # type: ignore[attr-defined]

    groups: dict[str, list[dict[str, Any]]] = {}
    for deck in CollectionManager.Decks:
        fmt = getattr(getattr(deck, "Format", None), "Name", "Unknown") or "Unknown"
        entry = groups.setdefault(fmt, [])
        entry.append(
            {
                "id": str(getattr(deck, "Id", "")),
                "name": getattr(deck, "Name", ""),
                "format": fmt,
                "main": int(deck.GetRegionCount(DeckRegion.MainDeck)),
                "side": int(deck.GetRegionCount(DeckRegion.Sideboard)),
                "timestamp": str(getattr(deck, "Timestamp", "")),
            }
        )

    return [
        {
            "format": fmt,
            "decks": sorted(block, key=lambda x: x["name"].lower()),
        }
        for fmt, block in sorted(groups.items(), key=lambda item: item[0].lower())
    ]


def get_collection_snapshot() -> list[dict[str, Any]]:
    """Return the MTGO collection grouped by binder."""
    sdk = _require_sdk()
    CollectionManager = sdk.API.Collection.CollectionManager  # type: ignore[attr-defined]
    logger.debug("MTGOSDK: querying collection binders")
    binders_payload: list[dict[str, Any]] = []
    for binder in CollectionManager.Binders:
        logger.debug("Processing binder {}", getattr(binder, "Name", "<unknown>"))
        cards = []
        try:
            items = list(binder.Items)
        except TypeError:
            items = binder.Items
        for card in items:
            cards.append(
                {
                    "name": getattr(card, "Name", ""),
                    "quantity": int(getattr(card, "Quantity", 0)),
                    "cardId": str(getattr(card, "Id", "")),
                    "set": getattr(card, "Set", None),
                }
            )
            binders_payload.append(
                {
                    "name": getattr(binder, "Name", ""),
                    "itemCount": int(getattr(binder, "ItemCount", len(cards))),
                    "cards": cards,
                }
            )
        logger.debug("Binder {} contains %d cards", binders_payload[-1]["name"], len(cards))
    return binders_payload


def get_binder_by_name(name: str) -> dict[str, Any] | None:
    sdk = _require_sdk()
    CollectionManager = sdk.API.Collection.CollectionManager  # type: ignore[attr-defined]
    target = name.strip().lower()
    for binder in CollectionManager.Binders:
        binder_name = getattr(binder, "Name", "") or ""
        display_name = binder_name.strip().lower()
        if display_name != target:
            continue
        logger.debug(f"Found binder {binder_name}")
        cards = []
        try:
            items = list(binder.Items)
        except TypeError:
            items = binder.Items
        for card in items:
            cards.append(
                {
                    "name": getattr(card, "Name", ""),
                    "quantity": int(getattr(card, "Quantity", 0)),
                    "cardId": str(getattr(card, "Id", "")),
                    "set": getattr(card, "Set", None),
                }
            )
        logger.debug(f"Binder {binder_name} export contains {len(cards)} cards")
        return {
            "name": binder_name,
            "itemCount": int(getattr(binder, "ItemCount", len(cards))),
            "cards": cards,
        }
    logger.debug(f"Binder {name} not found")
    available = [getattr(b, "Name", "") for b in CollectionManager.Binders]
    logger.debug(f"Available binders: {available}")
    return None


def _try_invoke(target: Any, method_name: str, *args: Any) -> bool:
    method = getattr(target, method_name, None)
    if method is None:
        return False
    try:
        method(*args)
        return True
    except Exception:
        return False


def _require_sdk():
    _ensure_loaded()
    if _SDK_MODULE is None:
        error = _LOAD_ERROR or RuntimeError("Unknown initialization failure")
        raise RuntimeError(f"MTGOSDK runtime unavailable: {error}") from error
    return _SDK_MODULE


def _ensure_loaded() -> None:
    global _SDK_MODULE, _CLR, _LOAD_ERROR
    if _SDK_MODULE is not None or _LOAD_ERROR is not None:
        return
    global AppDomain, FileLoadException
    if pythonnet is None:
        _LOAD_ERROR = ModuleNotFoundError("pythonnet is not installed")
        return

    with _LOAD_LOCK:
        if _SDK_MODULE is not None or _LOAD_ERROR is not None:
            return

        try:
            pythonnet.load("coreclr")
            import clr  # type: ignore
            from System import AppDomain as _AppDomain  # type: ignore
            from System.IO import FileLoadException as _FileLoadException  # type: ignore
        except Exception as exc:  # pragma: no cover
            _LOAD_ERROR = exc
            logger.debug("Failed to load pythonnet coreclr: {}", exc)
            return

        _CLR = clr
        AppDomain = _AppDomain
        FileLoadException = _FileLoadException

        def add_ref(dll_path: Path | None, name: str) -> None:
            if dll_path and dll_path.exists():
                try:
                    clr.AddReference(str(dll_path))
                    return
                except FileLoadException as exc:
                    if "already loaded" not in str(exc):
                        raise
            try:
                clr.AddReference(name)
            except Exception as exc:
                raise RuntimeError(f"Failed to load assembly '{name}'") from exc

        for assembly_name in ("WindowsBase", "PresentationCore", "PresentationFramework", "System.Xaml"):
            add_ref(_find_reference_dll(assembly_name), assembly_name)

        win32_path = _locate_sdk_dll("MTGOSDK.Win32.dll")
        sdk_path = _locate_sdk_dll("MTGOSDK.dll")
        if sdk_path is None:
            _LOAD_ERROR = FileNotFoundError("MTGOSDK.dll not found. Run dotnet publish or set MTGOSDK_LIB_DIR.")
            return

        add_ref(win32_path, "MTGOSDK.Win32")
        add_ref(sdk_path, "MTGOSDK")

        try:
            import MTGOSDK as sdk  # type: ignore
        except Exception as exc:  # pragma: no cover
            _LOAD_ERROR = exc
            logger.debug("Failed to import MTGOSDK: {}", exc)
            return

        _SDK_MODULE = sdk


def _find_reference_dll(name: str) -> Path | None:
    candidates = []
    dotnet_root = Path(r"C:\Program Files\dotnet")
    reference_root = Path(r"C:\Program Files (x86)\Reference Assemblies\Microsoft\Framework\.NETFramework")
    for base in (
        dotnet_root / "shared" / "Microsoft.WindowsDesktop.App",
        dotnet_root / "shared" / "Microsoft.NETCore.App",
    ):
        for version in ("9.0.10", "9.0.2", "8.0.13", "6.0.36"):
            candidate = base / version / f"{name}.dll"
            candidates.append(candidate)
    for version in ("v4.8.1", "v4.8", "v4.7.2", "v4.7.1", "v4.6.2", "v4.6"):
        candidates.append(reference_root / version / f"{name}.dll")
        candidates.append(reference_root / version / "Facades" / f"{name}.dll")
    env_dir = os.environ.get("MTGOSDK_REF_DIR")
    if env_dir:
        candidates.insert(0, Path(env_dir) / f"{name}.dll")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _locate_sdk_dll(filename: str) -> Path | None:
    env_dir = os.environ.get("MTGOSDK_LIB_DIR")
    candidate_dirs = []
    if env_dir:
        candidate_dirs.append(Path(env_dir))
    repo_candidates = [
        REPO_ROOT / "dotnet" / "MTGOBridge" / "bin" / "Release" / "net9.0-windows7.0" / "win-x64" / "publish",
        REPO_ROOT / "dotnet" / "MTGOBridge" / "bin" / "Debug" / "net9.0-windows7.0" / "win-x64" / "publish",
        REPO_ROOT / "dotnet" / "MTGOBridge" / "bin" / "Release" / "net9.0-windows7.0",
        REPO_ROOT / "dotnet" / "MTGOBridge" / "bin" / "Debug" / "net9.0-windows7.0",
        REPO_ROOT / "vendor" / "mtgosdk" / "MTGOSDK" / "lib" / "net9.0-windows7.0",
        REPO_ROOT / "vendor" / "mtgosdk" / "MTGOSDK.Win32" / "lib" / "netstandard2.0",
    ]
    candidate_dirs.extend(repo_candidates)
    for directory in candidate_dirs:
        candidate = Path(directory) / filename
        if candidate.exists():
            return candidate
    return None


def get_match_history(limit: int = 50) -> list[dict[str, Any]]:
    """Return match history from MTGO events and leagues."""
    history = _gather_event_matches(include_completed=True, include_event_info=True)
    if limit and limit > 0:
        history = history[:limit]
    return history


def list_active_matches() -> list[dict[str, Any]]:
    """Return currently active matches with basic metadata."""
    return _gather_event_matches(include_completed=False, include_event_info=False)


def _serialize_match(match: Any, round_number: int | None) -> dict[str, Any]:
    players = [_serialize_player(player) for player in _safe_iter(getattr(match, "Players", None))]
    opponent = getattr(match, "Opponent", None)
    if opponent is not None and not players:
        players.append(_serialize_player(opponent))

    return {
        "id": str(getattr(match, "Id", "")),
        "round": round_number,
        "table": getattr(match, "TableNumber", None),
        "state": str(getattr(match, "State", getattr(match, "Status", ""))),
        "isComplete": bool(getattr(match, "IsComplete", False)),
        "result": str(getattr(match, "Result", getattr(match, "MatchResult", ""))),
        "challengeText": getattr(match, "ChallengeText", None),
        "lastUpdated": str(_first_not_none(
            getattr(match, "UpdatedAt", None),
            getattr(match, "Timestamp", None),
            getattr(match, "LastUpdated", None),
        )),
        "players": players,
    }


def _serialize_player(player: Any) -> dict[str, Any]:
    name = getattr(player, "Name", getattr(player, "DisplayName", None))
    if not name:
        name = getattr(player, "UserName", None)
    clock = getattr(player, "ChessClock", None)
    seconds_value = None
    if clock is not None:
        total = getattr(clock, "TotalSeconds", None)
        try:
            seconds_value = int(round(float(total))) if total is not None else None
        except (TypeError, ValueError):
            seconds_value = None
    return {
        "name": name,
        "team": getattr(player, "TeamId", getattr(player, "Team", None)),
        "result": str(getattr(player, "Result", getattr(player, "MatchResult", ""))),
        "isWinner": bool(getattr(player, "IsWinner", False)),
        "isSelf": bool(getattr(player, "IsSelf", False)),
        "clockSeconds": seconds_value,
    }


def _safe_iter(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    try:
        iterator = iter(value)
    except TypeError:
        return [value]
    else:
        return [item for item in iterator]


def _first_not_none(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _gather_event_matches(
    include_completed: bool,
    include_event_info: bool = False,
) -> list[dict[str, Any]]:
    sdk = _require_sdk()
    EventManager = sdk.API.Play.EventManager  # type: ignore[attr-defined]

    results: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for evt in _safe_iter(EventManager.JoinedEvents):
        matches: list[dict[str, Any]] = []
        rounds = _safe_iter(getattr(evt, "Rounds", None))
        if rounds:
            for idx, round_obj in enumerate(rounds, start=1):
                for match in _safe_iter(getattr(round_obj, "Matches", None)):
                    matches.append(_serialize_match(match, round_number=getattr(round_obj, "Number", idx)))
        else:
            for match in _safe_iter(getattr(evt, "Matches", None)):
                matches.append(_serialize_match(match, round_number=None))
            single = getattr(evt, "Match", None)
            if single is not None:
                matches.append(_serialize_match(single, round_number=None))

        if not include_completed:
            matches = [m for m in matches if not m.get("isComplete")]

        for match in _safe_iter(getattr(evt, "ActiveMatches", None)):
            matches.append(_serialize_match(match, round_number=getattr(match, "RoundNumber", None)))

        if not matches:
            attrs = [attr for attr in dir(evt) if not attr.startswith("_")]
            logger.debug(f"Event {event_id} has no matches; available attrs: {attrs}")
            continue

        event_id = str(getattr(evt, "Id", ""))

        if include_event_info:
            filtered_matches: list[dict[str, Any]] = []
            for match in matches:
                match_id = match.get("id") or ""
                pair = (event_id, str(match_id))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                filtered_matches.append(match)
            if not filtered_matches:
                logger.debug("Event %s had no matches after filtering", event_id)
                continue
            event_entry = {
                "eventId": event_id,
                "description": getattr(evt, "Description", None),
                "format": str(getattr(getattr(evt, "Format", None), "Name", getattr(evt, "Format", ""))),
                "type": evt.__class__.__name__,
                "state": str(getattr(evt, "State", getattr(evt, "Status", ""))),
                "isCompleted": bool(getattr(evt, "IsCompleted", False)),
                "lastUpdated": str(
                    _first_not_none(
                        getattr(evt, "UpdatedAt", None),
                        getattr(evt, "Timestamp", None),
                        getattr(evt, "LastUpdated", None),
                    )
                ),
                "matches": filtered_matches,
            }
            results.append(event_entry)
        else:
            for match in matches:
                match = dict(match)
                match_id = match.get("id") or ""
                pair = (event_id, str(match_id))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                match["eventId"] = event_id
                match["eventDescription"] = getattr(evt, "Description", None)
                match["format"] = str(getattr(getattr(evt, "Format", None), "Name", getattr(evt, "Format", "")))
                results.append(match)
        logger.debug(f"Event {event_id} contributed {len(matches)} matches")

    # Fallback to global active matches in case JoinedEvents misses leagues
    for match in _safe_iter(getattr(EventManager, "ActiveMatches", None)):
        serialized = _serialize_match(match, round_number=getattr(match, "RoundNumber", None))
        event = getattr(match, "ParentEvent", getattr(match, "Event", None))
        event_id = str(getattr(event, "Id", getattr(match, "EventId", "")))
        pair = (event_id, serialized.get("id", ""))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        if include_event_info:
            serialized_event = {
                "eventId": event_id,
                "description": getattr(event, "Description", None) if event else None,
                "format": str(getattr(getattr(event, "Format", None), "Name", getattr(event, "Format", ""))) if event else None,
                "type": event.__class__.__name__ if event else None,
                "state": str(getattr(event, "State", getattr(event, "Status", ""))) if event else None,
                "isCompleted": bool(getattr(event, "IsCompleted", False)) if event else False,
                "lastUpdated": None,
                "matches": [serialized],
            }
            results.append(serialized_event)
        else:
            serialized["eventId"] = event_id
            serialized["eventDescription"] = getattr(event, "Description", None) if event else None
            serialized["format"] = str(getattr(getattr(event, "Format", None), "Name", getattr(event, "Format", ""))) if event else None
            results.append(serialized)
        logger.debug(f"Active match {serialized.get('id')} appended from fallback")

    return results


def get_available_binder_names() -> list[str]:
    sdk = _require_sdk()
    CollectionManager = sdk.API.Collection.CollectionManager  # type: ignore[attr-defined]
    return [getattr(b, "Name", "") for b in CollectionManager.Binders]
