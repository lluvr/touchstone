"""Combined output profile + alignment.

When both source and spec are provided, ``profile()`` returns both
a ``MeasureResult`` and an ``AlignResult`` in a single call along
with a small combined summary.
"""

from __future__ import annotations

from clarethium_touchstone._version import __standard_version__, __version__
from clarethium_touchstone.types import CombinedProfile


def profile(
    text: str,
    *,
    source: str | None = None,
    spec: str | None = None,
    comparisons: list[str] | None = None,
    topic: str | None = None,
    use_semantic: bool = False,
    p_detection_mode: str = "conservative",
) -> CombinedProfile:
    """Run measure() and align() on ``text``, return combined profile.

    At least one of ``source`` or ``spec`` should be provided.

    Args:
        text: The output to profile.
        source: Source material for measurement layers 4-6, 8, 11.
        spec: Specification for compliance verification layers 1-5.
        comparisons: Alternative output versions for Layer 3 instability.
        topic: Topic string for optional Layer 1a heading defaultness.
        use_semantic: Enable Layer 5 semantic alignment (requires API).
        p_detection_mode: ``conservative`` or ``liberal`` for Layer 11.

    Returns:
        A ``CombinedProfile`` containing both measurement and alignment
        results plus a combined summary.

    Raises:
        NotImplementedError: Library extraction in progress.
    """
    raise NotImplementedError(
        "Library extraction in progress. The Touchstone Standard 1.0 is "
        "the canonical reference; see STANDARDS/touchstone-1.0.md."
    )


__all__ = ["profile"]


LIBRARY_VERSION = __version__
STANDARD_VERSION = __standard_version__
