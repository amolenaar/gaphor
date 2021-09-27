"""Internationalization (i18n) support for Gaphor.

Translate text in to your native language using the gettext() function.
"""
__all__ = ["gettext"]

import importlib.resources
import locale
import logging
from typing import Callable

log = logging.getLogger(__name__)

gettext: Callable[[str], str]

try:
    with importlib.resources.path("gaphor", "__init__.py") as path:
        localedir = path.parent / "locale"
        locale.bindtextdomain("gaphor", localedir)  # type: ignore[attr-defined]
        locale.textdomain("gaphor")  # type: ignore[attr-defined]
        gettext = locale.gettext  # type: ignore[attr-defined]

except OSError as e:
    log.warning(f"No translations were found: {e}")

    def gettext(s):
        return s
