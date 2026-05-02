"""Touchstone reference implementation.

Model-independent verification for AI-coupled work. Implements the
Touchstone Standard (see STANDARDS/touchstone-1.0.md).

Public API:

    from clarethium_touchstone import measure, align, profile

    # Output profiling (Standard Section 5)
    result = measure(text, source=source_text)

    # Specification compliance (Standard Section 6)
    result = align(text, spec=spec_text)

    # Combined profile (both, with optional source)
    result = profile(text, source=source_text, spec=spec_text)

For individual layer functions see the ``measure`` and ``align`` modules.

The Standard is the canonical reference. The library is the reference
implementation. Where library behavior diverges from the Standard,
the Standard takes precedence.
"""

from clarethium_touchstone._version import __version__
from clarethium_touchstone.align import align
from clarethium_touchstone.measure import measure
from clarethium_touchstone.profile import profile

__all__ = [
    "__version__",
    "align",
    "measure",
    "profile",
]
