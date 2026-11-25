"""Compatibility entry for the original fixed replay engine."""

from .replay_stub import (CONCEPT_FIXTURE_DIR, DRAWING_FIXTURE_DIR,
                          SUPPORTED_DRAWING_EXTENSIONS, ReplayStubEngine,
                          parse_dxf_text)

ReplayEngine = ReplayStubEngine

__all__ = ["ReplayEngine", "parse_dxf_text"]
