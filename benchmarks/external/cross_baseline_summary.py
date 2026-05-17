"""Cross-baseline cross-corpus aggregation script.

Reads every snapshot under ``benchmarks/external/`` and produces a
unified summary printed to stdout (and optionally written to JSON).
The output is the single source of truth for the cross-baseline table
in the main README; running this script after any new external run
produces an updated table without manual entry.

Sources read:

- ``ragtruth_summary/results/2026-05-15.json`` (Touchstone + MiniCheck point)
- ``summeval/results/2026-05-15.json``
- ``halueval_summarization/results/2026-05-15.json``
- ``ragtruth_summary/results/alignscore_baseline_2026-05-15.json``
- ``summeval/results/alignscore_baseline_2026-05-15.json``
- ``halueval_summarization/results/alignscore_baseline_2026-05-15.json``
- ``ragtruth_summary/results/task_type_generalization_2026-05-15.json``
- ``*/results/minicheck_with_cis_2026-05-16.json`` (if present)
- ``ragtruth_summary/results/minicheck_qa_with_cis_2026-05-16.json`` (if present)
- ``ragtruth_summary/results/minicheck_data2txt_with_cis_2026-05-16.json`` (if present)

Run::

    python -m benchmarks.external.cross_baseline_summary
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BASE = Path("benchmarks/external")


def _fmt(ci_dict: dict[str, Any] | None, point: float | None = None) -> str:
    """Format an AUC + CI as ``0.7368 [0.7006, 0.7699]`` or plain point."""
    if ci_dict is not None and ci_dict.get("ci_low") is not None:
        return (
            f"{ci_dict.get('auc', point):.4f} [{ci_dict['ci_low']:.4f}, {ci_dict['ci_high']:.4f}]"
        )
    if point is not None:
        return f"{point:.4f}"
    return "—"


def _load_optional(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def aggregate() -> dict[str, Any]:
    out: dict[str, Any] = {}

    # Cross-corpus on summarization-task outputs.
    summarization: dict[str, dict[str, str]] = {}
    for corpus_dir, label in [
        ("ragtruth_summary", "RAGTruth Summary"),
        ("summeval", "SummEval"),
        ("halueval_summarization", "HaluEval summarization"),
    ]:
        original = _load_optional(BASE / corpus_dir / "results" / "2026-05-15.json")
        alignscore = _load_optional(
            BASE / corpus_dir / "results" / "alignscore_baseline_2026-05-15.json"
        )
        minicheck_cis = _load_optional(
            BASE / corpus_dir / "results" / "minicheck_with_cis_2026-05-16.json"
        )
        trivial = _load_optional(
            BASE / corpus_dir / "results" / "trivial_lexical_baselines_2026-05-17.json"
        )

        row: dict[str, str] = {}

        # Touchstone Layer 6.
        if original and "touchstone_bootstrap_95ci" in original:
            ci = original["touchstone_bootstrap_95ci"].get("touchstone_layer6_inverse_proximity")
            row["touchstone_l6"] = _fmt(ci)
        else:
            row["touchstone_l6"] = "—"

        # Touchstone Layer 10 gap.
        if original and "touchstone_bootstrap_95ci" in original:
            ci = original["touchstone_bootstrap_95ci"].get("touchstone_layer10_gap")
            row["touchstone_l10_gap"] = _fmt(ci)
        else:
            row["touchstone_l10_gap"] = "—"

        # MiniCheck (prefer CI version when available).
        if minicheck_cis and "minicheck" in minicheck_cis:
            ci = minicheck_cis["minicheck"].get("bootstrap_95ci")
            row["minicheck_flan_t5_large"] = _fmt(ci)
        elif original:
            point = (
                original.get("auc_roc_by_signal", {})
                .get("minicheck_flan_t5_large", {})
                .get("auc_roc")
            )
            row["minicheck_flan_t5_large"] = _fmt(None, point)
        else:
            row["minicheck_flan_t5_large"] = "—"

        # AlignScore.
        if alignscore and "alignscore" in alignscore:
            ci = alignscore["alignscore"].get("bootstrap_95ci")
            row["alignscore_base"] = _fmt(ci)
        else:
            row["alignscore_base"] = "—"

        # Trivial baselines (only on summarization corpora).
        if trivial and "trivial_baselines" in trivial:
            for tb_key in ["word_overlap_inv", "jaccard_content_inv", "tfidf_cosine_inv"]:
                tb = trivial["trivial_baselines"].get(tb_key)
                if tb is not None:
                    row[f"trivial_{tb_key}"] = _fmt(tb["bootstrap_95ci"])
                else:
                    row[f"trivial_{tb_key}"] = "—"
        else:
            for tb_key in ["word_overlap_inv", "jaccard_content_inv", "tfidf_cosine_inv"]:
                row[f"trivial_{tb_key}"] = "—"

        summarization[label] = row

    out["cross_corpus_summarization"] = summarization

    # Cross-task within RAGTruth (Touchstone only, plus MiniCheck where available).
    task_type = _load_optional(
        BASE / "ragtruth_summary" / "results" / "task_type_generalization_2026-05-15.json"
    )
    minicheck_qa = _load_optional(
        BASE / "ragtruth_summary" / "results" / "minicheck_qa_with_cis_2026-05-16.json"
    )
    minicheck_d2t = _load_optional(
        BASE / "ragtruth_summary" / "results" / "minicheck_data2txt_with_cis_2026-05-16.json"
    )

    cross_task: dict[str, dict[str, str]] = {}
    if task_type:
        for task in ["Summary", "QA", "Data2txt"]:
            r = task_type["results_by_task"].get(task, {})
            sigs = r.get("touchstone_signals", {})
            cross_task[task] = {
                "touchstone_l4": _fmt(sigs.get("layer4_unsourced_rate")),
                "touchstone_l5": _fmt(sigs.get("layer5_entity_unsourced_rate")),
                "touchstone_l6": _fmt(sigs.get("layer6_inverse_proximity")),
                "touchstone_l10_gap": _fmt(sigs.get("layer10_gap")),
                "touchstone_l11_p": _fmt(sigs.get("layer11_p_proportion")),
            }

    # Attach MiniCheck on QA / Data2Txt if available.
    if minicheck_qa and "QA" in cross_task:
        ci = minicheck_qa["minicheck"].get("bootstrap_95ci")
        cross_task["QA"]["minicheck_flan_t5_large"] = _fmt(ci)
    if minicheck_d2t and "Data2txt" in cross_task:
        ci = minicheck_d2t["minicheck"].get("bootstrap_95ci")
        cross_task["Data2txt"]["minicheck_flan_t5_large"] = _fmt(ci)
    # Summary MiniCheck comes from the same minicheck_with_cis file at the corpus level.
    summary_mc = _load_optional(
        BASE / "ragtruth_summary" / "results" / "minicheck_with_cis_2026-05-16.json"
    )
    if summary_mc and "Summary" in cross_task:
        ci = summary_mc["minicheck"].get("bootstrap_95ci")
        cross_task["Summary"]["minicheck_flan_t5_large"] = _fmt(ci)

    out["cross_task_ragtruth"] = cross_task

    return out


def _format_table(rows: dict[str, dict[str, str]], headers: list[str], title: str) -> str:
    """Render a small Markdown table."""
    if not rows:
        return f"### {title}\n\n(no data)\n"
    columns = ["signal"] + list(rows.keys())
    lines = [f"### {title}", ""]
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("|" + "|".join(["---"] * len(columns)) + "|")
    for h in headers:
        row = [h]
        for corpus in rows:
            row.append(rows[corpus].get(h, "—"))
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", help="Optional JSON output path.")
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Print a Markdown table summary instead of JSON.",
    )
    args = parser.parse_args()

    agg = aggregate()

    if args.markdown:
        md_lines = ["# Cross-baseline cross-corpus aggregate", ""]
        md_lines.append(
            _format_table(
                agg["cross_corpus_summarization"],
                [
                    "alignscore_base",
                    "minicheck_flan_t5_large",
                    "touchstone_l6",
                    "trivial_word_overlap_inv",
                    "trivial_jaccard_content_inv",
                    "trivial_tfidf_cosine_inv",
                    "touchstone_l10_gap",
                ],
                "Cross-corpus on summarization-task outputs (AUC, 95% bootstrap CI)",
            )
        )
        md_lines.append("")
        md_lines.append(
            _format_table(
                agg["cross_task_ragtruth"],
                [
                    "minicheck_flan_t5_large",
                    "touchstone_l4",
                    "touchstone_l5",
                    "touchstone_l6",
                    "touchstone_l10_gap",
                    "touchstone_l11_p",
                ],
                "Cross-task within RAGTruth (AUC, 95% bootstrap CI)",
            )
        )
        print("\n".join(md_lines))
    else:
        text = json.dumps(agg, indent=2)
        if args.output:
            Path(args.output).write_text(text)
            print(f"Wrote {args.output}")
        else:
            print(text)


if __name__ == "__main__":
    main()
