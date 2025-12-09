"""Internationalization (i18n) module for multilingual support."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from loguru import logger

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ["en", "pt_br"]


class I18n:
    def __init__(self, language: str = DEFAULT_LANGUAGE):
        self._language = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        self._translations: dict[str, Any] = {}
        self._load_translations()

    def _load_translations(self) -> None:
        locale_file = LOCALES_DIR / f"{self._language}.json"
        if not locale_file.exists():
            logger.warning(f"Translation file not found: {locale_file}")
            if self._language != DEFAULT_LANGUAGE:
                fallback = LOCALES_DIR / f"{DEFAULT_LANGUAGE}.json"
                if fallback.exists():
                    locale_file = fallback
                    logger.info(f"Falling back to {DEFAULT_LANGUAGE}")

        try:
            with open(locale_file, encoding="utf-8") as f:
                self._translations = json.load(f)
        except Exception as exc:
            logger.error(f"Failed to load translations from {locale_file}: {exc}")
            self._translations = {}

    def t(self, key: str, **kwargs: Any) -> str:
        keys = key.split(".")
        value = self._translations

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
                break

        if value is None:
            logger.warning(f"Translation key not found: {key}")
            return key

        if isinstance(value, str) and kwargs:
            try:
                return value.format(**kwargs)
            except KeyError as exc:
                logger.warning(f"Missing format parameter for key {key}: {exc}")
                return value

        return str(value)

    def get_language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        if language in SUPPORTED_LANGUAGES:
            self._language = language
            self._load_translations()
        else:
            logger.warning(f"Unsupported language: {language}")


_global_i18n: I18n | None = None


def init_i18n(language: str = DEFAULT_LANGUAGE) -> I18n:
    global _global_i18n
    _global_i18n = I18n(language)
    return _global_i18n


def get_i18n() -> I18n:
    global _global_i18n
    if _global_i18n is None:
        _global_i18n = I18n()
    return _global_i18n


def t(key: str, **kwargs: Any) -> str:
    return get_i18n().t(key, **kwargs)


__all__ = ["I18n", "init_i18n", "get_i18n", "t", "SUPPORTED_LANGUAGES", "DEFAULT_LANGUAGE"]
