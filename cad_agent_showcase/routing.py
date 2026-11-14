# -*- coding: utf-8 -*-
"""Route a declared input record to the concept or drawing entry."""

import os

from .contracts import (STATE_CONCEPT_DRAFT, STATE_DRAWING_INSPECTED,
                        STATE_STOPPED, ENTRY_CONCEPT, ENTRY_DRAWING)

SUPPORTED_DRAWING_EXTENSIONS = (".dxf",)


def route_input(record):
    """Return ``entry`` and initial state for a declared input record.

    The router never guesses: an unknown kind or extension stops explicitly.
    """
    if not isinstance(record, dict):
        return {"entry": None, "status": STATE_STOPPED, "code": "UNSUPPORTED_FORMAT",
                "detail": "input record is not an object"}
    kind = record.get("kind")
    if kind == "concept":
        return {"entry": ENTRY_CONCEPT, "status": STATE_CONCEPT_DRAFT,
                "code": "OK", "detail": None}
    if kind == "drawing":
        path = record.get("path") or ""
        extension = os.path.splitext(path)[1].lower()
        if extension not in SUPPORTED_DRAWING_EXTENSIONS:
            return {"entry": None, "status": STATE_STOPPED,
                    "code": "UNSUPPORTED_FORMAT",
                    "detail": "supported drawing extension: %s" % ",".join(
                        SUPPORTED_DRAWING_EXTENSIONS)}
        return {"entry": ENTRY_DRAWING, "status": STATE_DRAWING_INSPECTED,
                "code": "OK", "detail": None}
    return {"entry": None, "status": STATE_STOPPED, "code": "UNSUPPORTED_FORMAT",
            "detail": "unknown input kind: %r" % (kind,)}
