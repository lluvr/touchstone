"""Shared pytest fixtures for the Touchstone test suite.

The reference test suite (per Standard Section 8) lives under
``tests/reference/`` once extracted from the operator's research
vault. These reference cases are versioned with the Standard.

Synthetic and unit tests live alongside this file as ``test_*.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REFERENCE_ROOT = Path(__file__).parent / "reference"


@pytest.fixture
def reference_root() -> Path:
    """Path to the reference test suite directory."""
    return REFERENCE_ROOT


@pytest.fixture
def sample_source() -> str:
    """A small synthetic source text for unit tests."""
    return (
        "Acme Corp reported revenue of $143.8B in fiscal year 2024, "
        "up 12% year-over-year. CEO Maria Chen attributed growth to "
        "expansion in the European market and a 23% increase in "
        "enterprise contracts. Operating margin improved to 18.4%."
    )


@pytest.fixture
def sample_grounded_output() -> str:
    """A small output that is well-grounded in sample_source."""
    return (
        "Acme Corp's fiscal year 2024 revenue reached $143.8B, "
        "representing 12% growth. CEO Maria Chen credited European "
        "market expansion and growth in enterprise contracts (up 23%). "
        "Operating margin: 18.4%."
    )


@pytest.fixture
def sample_overclaiming_output() -> str:
    """A small output that overclaims beyond sample_source."""
    return (
        "Acme Corp's fiscal year 2024 revenue reached $143.8B, "
        "representing dramatic 12% growth that signals continued "
        "dominance. Industry analysts predict revenue will exceed "
        "$200B by 2027 driven by accelerating AI adoption. CEO Maria "
        "Chen's strategic vision has positioned the company as the "
        "clear leader in next-generation enterprise solutions."
    )


@pytest.fixture
def sample_spec() -> str:
    """A small synthetic specification for align tests."""
    return (
        "Write a brief financial summary that:\n"
        "1. States revenue figure for fiscal year 2024\n"
        "2. Reports year-over-year growth percentage\n"
        "3. Names the CEO\n"
        "4. Identifies one key driver of growth\n"
        "5. Reports operating margin\n"
    )
