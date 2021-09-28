"""Internationalization (i18n) support for Gaphor.

Translate text in to your native language using the gettext() function.
"""
__all__ = ["gettext"]

import importlib.resources
import locale
import logging
import sys
from typing import Callable

log = logging.getLogger(__name__)

gettext: Callable[[str], str]

locale.setlocale(locale.LC_ALL, "")

if sys.platform == "win32":

    import ctypes
    import ctypes.util
    import gettext as _gettext
    import os

    if not os.getenv("LANGUAGE"):
        lang, enc = locale.getdefaultlocale()
        os.environ["LANGUAGE"] = lang  # type: ignore[assignment]
        result = ctypes.windll.kernel32.SetEnvironmentVariableW("LANGUAGE", lang)
        ctypes.cdll.msvcrt._putenv(f"LANGUAGE={lang}")
        print("Language is:", lang)

    with importlib.resources.path("gaphor", "__init__.py") as path:
        localedir = path.parent / "locale"

        lang, enc = locale.getdefaultlocale()
        # For GTK Builder UI:
        libintl = ctypes.cdll.intl
        libintl.libintl_setlocale(locale.LC_ALL, "nl-NL")
        print(dir(libintl))
        libintl.libintl_bindtextdomain("gaphor", str(localedir).replace("\\", "/"))
        libintl.libintl_textdomain("gaphor")
        libintl.libintl_bind_textdomain_codeset("gaphor", "UTF-8")
        # For Python text:
        translate = _gettext.translation("gaphor", localedir=localedir, fallback=True)
        gettext = translate.gettext
    print("gettext is", gettext)

else:

    with importlib.resources.path("gaphor", "__init__.py") as path:
        localedir = path.parent / "locale"
        locale.setlocale(locale.LC_ALL, "")
        locale.bindtextdomain("gaphor", localedir)  # type: ignore[attr-defined]
        locale.textdomain("gaphor")  # type: ignore[attr-defined]
        locale.bind_textdomain_codeset("gaphor", "UTF-8")
        gettext = locale.gettext  # type: ignore[attr-defined]
