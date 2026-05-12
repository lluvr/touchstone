"""Profile a short analytical summary against the source it was derived from.

End-to-end example showing the typical adopter call shape:

1. Get an AI-generated summary (``text``) and the source it was meant
   to ground in (``source``).
2. Call ``measure(text, source=source)``.
3. Inspect Layer 4 (source matching), Layer 10 (quality_profile.gap),
   Layer 11 (G/F/P decomposition), and the layer's scope_assessment.

The example uses inline sample text so it runs offline without any LLM
client. To swap in your own data, replace ``SOURCE`` and ``TEXT`` below.

Run from the repository root::

    pip install -e .
    python examples/verify_a_summary.py
"""

from __future__ import annotations

from clarethium_touchstone import assess_derivation_regime, measure

SOURCE = """\
Quarterly revenue grew 12% year over year to $143 million, with operating
margins reaching 25%. Headcount declined 8% to 5,000 employees over 18
months. Customer acquisition cost dropped to $1,200 from a $1,750
baseline. Retention improved from 87% to 94.2% across the major
customer segments. R&D spending was $32 million for the quarter, up
from $28 million a year earlier.
"""

# A faithful summary: every numerical claim is in the source above.
TEXT_FAITHFUL = """\
Revenue rose 12% to $143 million and operating margins reached 25%
this quarter. Headcount declined 8% to 5,000 employees over 18 months
while customer acquisition cost dropped to $1,200 from the prior
$1,750 baseline. Retention improved from 87% to 94.2% across major
segments, and R&D spending grew from $28 million a year earlier to
$32 million this quarter.
"""

# An embellished summary: introduces unsourced numbers and an external
# entity (a competitor name) the source never mentions.
TEXT_EMBELLISHED = """\
Revenue rose 12% to $143 million while operating margins reached an
industry-leading 25%, well above the SaaS-sector median of 18% per
recent analyses. Headcount declined 8% to 5,000 over 18 months,
mirroring the 7.5% reduction Salesforce reported the prior quarter.
Customer acquisition cost dropped to $1,200 from a $1,750 baseline.
Retention improved from 87% to 94.2% across major segments, the
strongest cohort retention in three years. R&D spending grew from
$28 million to $32 million, signaling that the company plans to
expand its product surface by the end of FY2027.
"""


def profile(label: str, text: str, source: str) -> None:
    """Run measure() on a text/source pair and print the load-bearing layers."""
    print(f"\n{'=' * 64}")
    print(f"  {label}")
    print(f"{'=' * 64}\n")

    result = measure(text, source=source)

    # Layer 4: source matching.
    sm = result["source_matching"]
    assert sm is not None  # source provided
    print("Layer 4 (source_matching)")
    print(f"  unsourced_rate: {sm['unsourced_rate']:.3f}")
    print(f"  numbers in source / total: {sm['n_in_source']} / {sm['n_total']}")
    print(f"  precision: {sm['precision']}")
    if sm["unsourced_details"]:
        print("  unsourced numbers:")
        for detail in sm["unsourced_details"]:
            print(f"    - {detail['value']} ({detail['type']})  context: {detail['context']!r}")

    # Layer 10: composite quality profile.
    qp = result["quality_profile"]
    print("\nLayer 10 (quality_profile)")
    print(f"  substance_index: {qp['substance_index']:.3f}")
    print(f"  presentation_index: {qp['presentation_index']:.3f}")
    print(f"  gap: {qp['gap']:.3f}  (positive = overclaiming risk)")
    print(f"  components_available: {sorted(qp['components_available'])}")

    # Layer 11: G/F/P decomposition.
    gd = result["grounding_decomposition"]
    assert gd is not None  # source provided
    props = gd["proportions"]
    print("\nLayer 11 (grounding_decomposition)")
    print(f"  G / F / P: {props['G']:.2f} / {props['F']:.2f} / {props['P']:.2f}")
    print(f"  has_projection: {gd['has_projection']}")
    sa = gd["scope_assessment"]
    print(
        f"  scope_assessment: source has {sa['source_num_count']} numbers "
        f"({sa['derivation_regime']} regime)"
    )
    if gd["recommendation"]:
        print(f"  recommendation: {gd['recommendation']}")


def main() -> int:
    print("Touchstone end-to-end example: verify a summary against its source")
    print()
    print("Library version:", _library_version())
    print("Standard version:", _standard_version())

    # Pre-measurement scope hint: how many source numbers are we working
    # with? Useful for adopter UIs that want to surface "trust this
    # signal" before any measurement runs.
    src_num_hint = _count_source_numbers()
    assessment = assess_derivation_regime(source_num_count=src_num_hint)
    print(
        f"\nSource has roughly {src_num_hint} digit-formatted numbers; "
        f"Layer 11 derivation regime: {assessment['derivation_regime']}."
    )
    print(f"User-facing note: {assessment['note_user_facing']}")

    profile("Faithful summary (every number in source)", TEXT_FAITHFUL, SOURCE)
    profile("Embellished summary (extra unsourced numbers)", TEXT_EMBELLISHED, SOURCE)

    print()
    print("Compare the two profiles:")
    print("  - faithful summary: unsourced_rate = 0; gap strongly negative")
    print("    (substance exceeds presentation).")
    print("  - embellished summary: unsourced_rate > 0 (Layer 4 catches the")
    print("    SaaS-sector median '18%' the source does not contain); gap")
    print("    is still negative but closer to 0 (substance index dropped).")
    print()
    print("Note Layer 11's scope_assessment: this source has 12-15 numerical")
    print("values, putting it in the SATURATED regime. Layer 11's primary")
    print("unsourced-numbers P-signal is disabled at this regime, so P=0 in")
    print("both cases. The user-facing note above directs consumers to the")
    print("Source Fidelity signal (Layer 4 unsourced_rate) for numerical")
    print("fabrication detection on number-dense sources. This is the")
    print("scope_assessment field doing the work it was designed to do.")
    print()
    print("In production, set thresholds per Standard §7 and pair these")
    print("signals with human review for any high-stakes decision.")
    return 0


def _library_version() -> str:
    from clarethium_touchstone import __version__

    return __version__


def _standard_version() -> str:
    from clarethium_touchstone._version import __standard_version__

    return __standard_version__


def _count_source_numbers() -> int:
    """Quick approximation of Layer 4's number-extraction count on the source."""
    import re

    return len(re.findall(r"\d+(?:\.\d+)?", SOURCE))


if __name__ == "__main__":
    raise SystemExit(main())
