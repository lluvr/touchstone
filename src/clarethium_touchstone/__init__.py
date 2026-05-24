"""Touchstone reference implementation.

Model-independent verification for AI-coupled work. Implements
Section 5 (Output Measurement) of the Touchstone Standard. See
``STANDARDS/touchstone-1.0.md`` for the canonical reference.

Public API (v0.1):

    from clarethium_touchstone import measure, assess_derivation_regime

    result = measure(text, source=source_text)

    # Standalone Layer 11 regime classifier - useful for UIs that
    # display "trust this signal" hints before measurement begins.
    assessment = assess_derivation_regime(source_num_count=14)

The ``measure()`` orchestrator runs every measurement layer whose
preconditions are met. Layer functions are also accessible
individually from ``clarethium_touchstone.measure``.

Standard Section 6 (Specification Compliance) is reserved for
Standard 1.1; the ``align()`` API is not part of v0.1.

The Standard is the canonical reference. The library is the reference
implementation. Where library behaviour diverges from the Standard,
the Standard takes precedence.
"""

from clarethium_touchstone._version import __version__
from clarethium_touchstone.measure import (
    EXTERNAL_ENTITIES_DEFAULT,
    assess_derivation_regime,
    measure,
)
from clarethium_touchstone.verifier import (
    VERIFIER_MODES,
    UnsupportedSpan,
    Verifier,
    VerifierMode,
    VerifierResult,
)

__all__ = [
    "EXTERNAL_ENTITIES_DEFAULT",
    "VERIFIER_MODES",
    "UnsupportedSpan",
    "Verifier",
    "VerifierMode",
    "VerifierResult",
    "__version__",
    "assess_derivation_regime",
    "measure",
]
