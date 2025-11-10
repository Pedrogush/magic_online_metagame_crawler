"""Archetype classification backed by the MTGOArchetypeParser + MTGOFormatData datasets."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import NamedTuple

from loguru import logger

VENDOR_ROOT = Path("vendor/mtgo_format_data")
COLOR_ORDER = ("W", "U", "B", "R", "G")
COLOR_PREFIX = {
    "W": "MonoWhite",
    "U": "MonoBlue",
    "B": "MonoBlack",
    "R": "MonoRed",
    "G": "MonoGreen",
    "WU": "Azorius",
    "WB": "Orzhov",
    "WR": "Boros",
    "WG": "Selesnya",
    "UB": "Dimir",
    "UR": "Izzet",
    "UG": "Simic",
    "BR": "Rakdos",
    "BG": "Golgari",
    "RG": "Gruul",
    "WUB": "Esper",
    "WUR": "Jeskai",
    "WUG": "Bant",
    "WBR": "Mardu",
    "WBG": "Abzan",
    "WRG": "Naya",
    "UBR": "Grixis",
    "UBG": "Sultai",
    "URG": "Temur",
    "BRG": "Jund",
    "WUBR": "WUBR",
    "WBRG": "WBRG",
    "WUBG": "WUBG",
    "WURG": "WURG",
    "UBRG": "UBRG",
    "WUBRG": "5Color",
}
COLORLESS_CODE = "C"
_PASCAL_RE = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])|(?<=[^A-Z])(?=[A-Z])|(?<=[A-Za-z])(?=[^A-Za-z])")
_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_COMMA_RE = re.compile(r",(?=\s*[}\]])")


class DeckEntry(NamedTuple):
    name: str
    count: int


@dataclass(frozen=True)
class Condition:
    type: str
    cards: tuple[str, ...]


@dataclass
class ArchetypeSpecific:
    name: str
    include_color: bool
    conditions: tuple[Condition, ...]
    variants: tuple[ArchetypeSpecific, ...] = ()

    @cached_property
    def complexity(self) -> int:
        return len(self.conditions)


@dataclass
class ArchetypeGeneric:
    name: str
    include_color: bool
    common_cards: tuple[str, ...]

    @cached_property
    def complexity(self) -> int:
        return 2 ** 31 - 1


@dataclass
class FormatBundle:
    name: str
    lands: dict[str, str]
    non_lands: dict[str, str]
    specifics: tuple[ArchetypeSpecific, ...]
    generics: tuple[ArchetypeGeneric, ...]

    def classify(self, mainboard: dict[str, DeckEntry], sideboard: dict[str, DeckEntry]) -> tuple[str | None, float]:
        color = determine_color_identity(mainboard, sideboard, self.lands, self.non_lands)
        matches: list[tuple[ArchetypeSpecific, ArchetypeSpecific | None]] = []
        for archetype in self.specifics:
            if not conditions_met(archetype.conditions, mainboard, sideboard):
                continue
            matched_variant: ArchetypeSpecific | None = None
            for variant in archetype.variants:
                if conditions_met(variant.conditions, mainboard, sideboard):
                    matched_variant = variant
                    matches.append((archetype, variant))
            if matched_variant is None:
                matches.append((archetype, None))

        if matches:
            archetype, variant = select_best_match(matches)
            chosen = variant or archetype
            return format_name(chosen.name, chosen.include_color, color), 1.0

        generic_match = best_generic_match(
            self.generics,
            mainboard,
            sideboard,
            color,
        )
        if generic_match:
            archetype, score = generic_match
            return format_name(archetype.name, archetype.include_color, color), score

        return None, 0.0


def determine_color_identity(
    mainboard: dict[str, DeckEntry],
    sideboard: dict[str, DeckEntry],
    lands: dict[str, str],
    non_lands: dict[str, str],
) -> str:
    colors_in_lands = dict.fromkeys(COLOR_ORDER, 0)
    colors_in_nonlands = dict.fromkeys(COLOR_ORDER, 0)

    for zone in (mainboard, sideboard):
        for entry in zone.values():
            if color_hint := lands.get(entry.name):
                for symbol in color_hint:
                    colors_in_lands[symbol] += entry.count
            if color_hint := non_lands.get(entry.name):
                for symbol in color_hint:
                    colors_in_nonlands[symbol] += entry.count

    produced = "".join(symbol for symbol in COLOR_ORDER if colors_in_lands[symbol] > 0 and colors_in_nonlands[symbol] > 0)
    return produced or COLORLESS_CODE


def conditions_met(conditions: tuple[Condition, ...], mainboard: dict[str, DeckEntry], sideboard: dict[str, DeckEntry]) -> bool:
    for condition in conditions:
        cards = condition.cards
        if not cards:
            continue
        if condition.type == "InMainboard":
            if cards[0] not in mainboard:
                return False
        elif condition.type == "InSideboard":
            if cards[0] not in sideboard:
                return False
        elif condition.type == "InMainOrSideboard":
            if cards[0] not in mainboard and cards[0] not in sideboard:
                return False
        elif condition.type == "OneOrMoreInMainboard":
            if not any(card in mainboard for card in cards):
                return False
        elif condition.type == "OneOrMoreInSideboard":
            if not any(card in sideboard for card in cards):
                return False
        elif condition.type == "OneOrMoreInMainOrSideboard":
            if not any(card in mainboard or card in sideboard for card in cards):
                return False
        elif condition.type == "TwoOrMoreInMainboard":
            if sum(1 for card in cards if card in mainboard) < 2:
                return False
        elif condition.type == "TwoOrMoreInSideboard":
            if sum(1 for card in cards if card in sideboard) < 2:
                return False
        elif condition.type == "TwoOrMoreInMainOrSideboard":
            if sum(1 for card in cards if card in mainboard or card in sideboard) < 2:
                return False
        elif condition.type == "DoesNotContain":
            if any(card in mainboard or card in sideboard for card in cards):
                return False
        elif condition.type == "DoesNotContainMainboard":
            if any(card in mainboard for card in cards):
                return False
        elif condition.type == "DoesNotContainSideboard":
            if any(card in sideboard for card in cards):
                return False
        else:
            logger.debug("Unknown archetype condition type '%s'", condition.type)
            return False
    return True


def select_best_match(matches: list[tuple[ArchetypeSpecific, ArchetypeSpecific | None]]) -> tuple[ArchetypeSpecific, ArchetypeSpecific | None]:
    return min(
        matches,
        key=lambda pair: pair[0].complexity + (pair[1].complexity if pair[1] else 0),
    )


def best_generic_match(
    generics: tuple[ArchetypeGeneric, ...],
    mainboard: dict[str, DeckEntry],
    sideboard: dict[str, DeckEntry],
    color: str,
) -> tuple[ArchetypeGeneric, float] | None:
    combined_counts = dict(mainboard)
    for name, entry in sideboard.items():
        if name in combined_counts:
            combined_counts[name] = DeckEntry(name, combined_counts[name].count + entry.count)
        else:
            combined_counts[name] = entry

    weight_entries: list[tuple[ArchetypeGeneric, int]] = []
    for generic in generics:
        score = 0
        for card in generic.common_cards:
            if card in combined_counts:
                score += combined_counts[card].count
        weight_entries.append((generic, score))

    max_weight = max((weight for _, weight in weight_entries), default=0)
    if max_weight == 0:
        return None

    winners = [item for item in weight_entries if item[1] == max_weight]
    winners.sort(key=lambda pair: len(pair[0].common_cards))
    chosen_generic, chosen_weight = winners[0]

    # mimic similarity from the C# implementation
    denominator = max(1, len(mainboard) + len(sideboard))
    similarity = chosen_weight / denominator
    if similarity <= 0.1:
        return None
    return chosen_generic, similarity


def format_name(raw_name: str, include_color: bool, color_code: str) -> str:
    name = raw_name.replace("Generic", "")
    if include_color:
        prefix = COLOR_PREFIX.get(color_code, "")
        if prefix:
            name = f"{prefix}{name}"
    name = _PASCAL_RE.sub(" ", name)
    return _WHITESPACE_RE.sub(" ", name).strip()


def normalize(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


class FormatLoader:
    FALLBACK_VENDOR_ROOT = Path(__file__).resolve().parent.parent / "resources" / "mtgo_format_data"

    def __init__(self, vendor_root: Path) -> None:
        if vendor_root.exists():
            self.vendor_root = vendor_root
        elif self.FALLBACK_VENDOR_ROOT.exists():
            self.vendor_root = self.FALLBACK_VENDOR_ROOT
        else:
            raise FileNotFoundError(f"MTGO format data not found at {vendor_root}")
        self._index = self._discover_formats()
        self._cache: dict[str, FormatBundle] = {}

    def _discover_formats(self) -> dict[str, Path]:
        if not self.vendor_root.exists():
            raise FileNotFoundError(f"MTGO format data not found at {self.vendor_root}")
        mapping: dict[str, Path] = {}
        for entry in self.vendor_root.iterdir():
            if entry.is_dir() and entry.name not in {".git"}:
                mapping[normalize(entry.name)] = entry
        return mapping

    def get(self, fmt: str) -> FormatBundle | None:
        key = normalize(fmt)
        if key in self._cache:
            return self._cache[key]
        path = self._index.get(key)
        if not path:
            logger.debug("No MTGO format data for format '%s'", fmt)
            return None
        bundle = self._load_bundle(path)
        self._cache[key] = bundle
        return bundle

    def _load_bundle(self, path: Path) -> FormatBundle:
        color_file = self.vendor_root / "card_colors.json"
        override_file = path / "color_overrides.json"
        archetype_dir = path / "Archetypes"
        fallback_dir = path / "Fallbacks"

        lands, nonlands = load_colors(color_file, override_file)
        specifics = load_specific_archetypes(archetype_dir)
        generics = load_generic_archetypes(fallback_dir)
        return FormatBundle(
            name=path.name,
            lands=lands,
            non_lands=nonlands,
            specifics=specifics,
            generics=generics,
        )


def read_json(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    cleaned = _TRAILING_COMMA_RE.sub("", text)
    return json.loads(cleaned)


def load_colors(primary_file: Path, override_file: Path) -> tuple[dict[str, str], dict[str, str]]:
    lands: dict[str, str] = {}
    nonlands: dict[str, str] = {}

    def apply(data: dict[str, list[dict[str, str]]]) -> None:
        for card in data.get("Lands") or []:
            lands[card["Name"]] = card["Color"]
        for card in data.get("NonLands") or []:
            nonlands[card["Name"]] = card["Color"]

    apply(read_json(primary_file))
    if override_file.exists():
        apply(read_json(override_file))

    return lands, nonlands


def load_specific_archetypes(directory: Path) -> tuple[ArchetypeSpecific, ...]:
    archetypes: list[ArchetypeSpecific] = []
    for path in sorted(directory.glob("*.json")):
        payload = read_json(path)
        archetypes.append(parse_specific(payload))
    return tuple(archetypes)


def parse_specific(payload: dict) -> ArchetypeSpecific:
    conditions = tuple(
        Condition(type=entry["Type"], cards=tuple(entry.get("Cards", [])))
        for entry in payload.get("Conditions", [])
    )
    variants = tuple(parse_specific(entry) for entry in payload.get("Variants", []) or [])
    return ArchetypeSpecific(
        name=payload["Name"],
        include_color=payload.get("IncludeColorInName", False),
        conditions=conditions,
        variants=variants,
    )


def load_generic_archetypes(directory: Path) -> tuple[ArchetypeGeneric, ...]:
    archetypes: list[ArchetypeGeneric] = []
    for path in sorted(directory.glob("*.json")):
        payload = read_json(path)
        archetypes.append(
            ArchetypeGeneric(
                name=payload["Name"],
                include_color=payload.get("IncludeColorInName", False),
                common_cards=tuple(payload.get("CommonCards", [])),
            )
        )
    return tuple(archetypes)


class ArchetypeClassifier:
    """Assign archetype names to MTGO decklists by reusing MTGOArchetypeParser datasets."""

    def __init__(self, vendor_root: Path | None = None) -> None:
        self.loader = FormatLoader(vendor_root or VENDOR_ROOT)

    def assign_archetypes(self, decks: Iterable[dict], fmt: str | None) -> None:
        if not fmt:
            logger.debug("Skipping archetype classification because format is empty.")
            return

        bundle = self.loader.get(fmt)
        if not bundle:
            return

        fmt_norm = normalize(fmt)
        for deck in decks:
            deck_format = normalize(deck.get("format") or fmt)
            if deck_format != fmt_norm:
                continue
            mainboard = {card["name"]: DeckEntry(card["name"], int(card.get("count", 0) or 0)) for card in deck.get("mainboard", []) if card.get("name")}
            sideboard = {card["name"]: DeckEntry(card["name"], int(card.get("count", 0) or 0)) for card in deck.get("sideboard", []) if card.get("name")}
            if not mainboard:
                continue
            name, score = bundle.classify(mainboard, sideboard)
            if name:
                deck["archetype"] = name
                deck["archetype_score"] = round(score, 3)
            else:
                deck.setdefault("archetype", deck.get("deck_name") or deck.get("event_name") or "Unknown")


__all__ = ["ArchetypeClassifier"]
