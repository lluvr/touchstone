"""Touchstone reference implementation.

Model-independent verification for AI-coupled work. Implements
Section 5 (Output Measurement) of the Touchstone Standard. See
``STANDARDS/touchstone-1.0.md`` for the canonical reference.

Public API (v0.1):

    from clarethium_touchstone import measure

    result = measure(text, source=source_text)

The ``measure()`` orchestrator runs every measurement layer whose
preconditions are met. Layer functions are also accessible
individually from ``clarethium_touchstone.measure``.

Standard Section 6 (Specification Compliance) is not part of v0.1.
The ``align()`` API is reserved for a future release; the canonical
research reference lives in the operator's vault as
``clarethium_align.py`` and is not yet packaged.

The Standard is the canonical reference. The library is the reference
implementation. Where library behaviour diverges from the Standard,
the Standard takes precedence.
"""

from clarethium_touchstone._version import __version__
from clarethium_touchstone.measure import measure

__all__ = [
    "__version__",
    "measure",
]
