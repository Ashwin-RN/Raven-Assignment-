"""Extraction backends. The model is a config behind the ExtractionBackend interface."""

from .base import ExtractionBackend
from .fixture import FixtureBackend

__all__ = ["ExtractionBackend", "FixtureBackend"]
