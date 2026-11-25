"""Contracts between the public workflow and the withheld CAD capabilities."""

from abc import ABC, abstractmethod
from pathlib import Path

from ..contracts import (CODE_CORE_CAPABILITY_HIDDEN, CODE_UNSUPPORTED_REPLAY_INPUT,
                         ReplayRejection)


class CoreBoundaryError(ReplayRejection):
    """A request crossed the replay boundary. The CLI reports rejection (exit 1)."""

    def __init__(self, detail="This capability requires the private CAD engine.", *,
                 code=CODE_CORE_CAPABILITY_HIDDEN, data=None):
        if code not in (CODE_CORE_CAPABILITY_HIDDEN, CODE_UNSUPPORTED_REPLAY_INPUT):
            raise ValueError("Invalid core boundary code")
        super().__init__(code, detail, data)


class CoreEnginePort(ABC):
    """The public package supplies a fixed-fixture implementation only."""

    @abstractmethod
    def inspect_drawing_source(self, path: Path) -> dict:
        """Inspect one permitted drawing-source identity."""

    @abstractmethod
    def run_cognition_gate(self, expected: dict) -> list:
        """Supply cognition results for the permitted task snapshot."""

    @abstractmethod
    def solve_parameter_bridge(self, expected: dict, parameters: dict) -> dict:
        """Resolve one permitted parameter snapshot against its task contract."""

    @abstractmethod
    def construct_brep_and_measure(self, path: Path) -> dict:
        """Read measurements for a permitted job through the private boundary."""

    @abstractmethod
    def render_concept_views(self, deliverable_spec: dict) -> list:
        """Provide view descriptors for a permitted task snapshot."""

    @abstractmethod
    def emit_and_verify_sheets(self, deliverable_spec: dict) -> dict:
        """Supply the permitted sheet delivery and its readback specification."""

    @abstractmethod
    def inspect_evidence_media(self, path: Path, data: bytes, locator: dict) -> None:
        """Accept a known media location by returning, or raise CoreBoundaryError."""
