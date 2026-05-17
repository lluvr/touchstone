"""Trivial lexical baselines on the three external corpora.

The single most important methodological question for the Touchstone
report is: does Layer 6 inverse vocabulary proximity actually do
anything beyond what a 5-line bag-of-words baseline would do? Layer 6
measures content-word overlap with sentence-level segmentation; a
naive baseline measures raw word overlap without any of Touchstone's
preprocessing.

This script computes three trivial lexical baselines on each of the
three external corpora, with 95% percentile bootstrap CIs (1000
stratified resamples, fixed seed), and saves snapshot JSONs alongside
the existing Touchstone / MiniCheck / AlignScore snapshots so the
cross-baseline aggregator can include them as a row in the headline
table.

Baselines, all oriented "higher score = more likely hallucinated":

- **WordOverlapInv**: ``1 - (|out_words ∩ src_words| / |out_words|)``.
  No stopword filtering, no segmentation, raw set intersection on
  lowercased word tokens (whitespace + simple punctuation split).
- **TFIDFCosineInv**: ``1 - cosine(tfidf(output), tfidf(source))``
  where TF-IDF is computed on the union vocabulary using the
  document frequency over the corpus's full set of (output, source)
  pairs.
- **JaccardContentInv**: ``1 - jaccard(content_out, content_src)``
  with stopword filtering and a 3-character minimum on content words
  (the same filter Layer 6 applies, but Jaccard instead of mean
  per-sentence overlap).

If Layer 6 does not statistically outperform all three of these
baselines on at least one corpus, the §3.5 Layer 6 construct claim
is falsified: the layer is no more informative than packaged
lexical overlap.

Usage::

    python -m benchmarks.external.trivial_lexical_baselines
"""

from __future__ import annotations

import json
import math
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _bootstrap import auc_roc, bootstrap_auc_ci  # noqa: E402

# Minimal English stopword list. The point is to exercise the same
# preprocessing as Layer 6; a longer list would be more aggressive.
STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "of",
        "in",
        "on",
        "at",
        "to",
        "from",
        "for",
        "by",
        "with",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "he",
        "she",
        "his",
        "her",
        "their",
        "they",
        "them",
        "we",
        "us",
        "our",
        "you",
        "your",
        "i",
        "me",
        "my",
        "mine",
        "ours",
        "yours",
        "theirs",
        "not",
        "no",
        "yes",
        "if",
        "then",
        "else",
        "when",
        "where",
        "which",
        "who",
        "whom",
        "why",
        "how",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "can",
        "shall",
        "must",
        "about",
        "over",
        "under",
        "after",
        "before",
        "between",
        "into",
        "through",
        "during",
        "while",
        "until",
        "since",
        "against",
        "above",
        "below",
        "up",
        "down",
        "out",
        "off",
        "so",
        "just",
        "only",
        "also",
        "very",
        "more",
        "most",
        "less",
        "least",
        "same",
        "other",
        "another",
        "such",
        "here",
        "there",
        "now",
        "ever",
        "never",
        "always",
        "sometimes",
        "much",
        "many",
        "few",
        "several",
        "both",
        "each",
        "every",
        "all",
        "some",
        "any",
        "none",
        "either",
        "neither",
    ]
)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]*", text.lower())


def _content_tokens(text: str) -> list[str]:
    return [t for t in _tokenize(text) if len(t) >= 3 and t not in STOPWORDS]


def word_overlap_inv(text: str, source: str) -> float:
    out = set(_tokenize(text))
    src = set(_tokenize(source))
    if not out:
        return 0.0
    return 1.0 - len(out & src) / len(out)


def jaccard_content_inv(text: str, source: str) -> float:
    out = set(_content_tokens(text))
    src = set(_content_tokens(source))
    if not out and not src:
        return 0.0
    return 1.0 - len(out & src) / len(out | src)


def tfidf_cosine_inv(text: str, source: str, doc_freq: dict[str, int], n_docs: int) -> float:
    """1 - cosine of TF-IDF vectors with the supplied document frequencies."""
    out_counts = Counter(_content_tokens(text))
    src_counts = Counter(_content_tokens(source))
    if not out_counts or not src_counts:
        return 0.0

    def _tfidf(counts: Counter[str]) -> dict[str, float]:
        vec: dict[str, float] = {}
        for term, c in counts.items():
            df = doc_freq.get(term, 1)
            idf = math.log((n_docs + 1) / (df + 1)) + 1.0
            vec[term] = float(c) * idf
        return vec

    a = _tfidf(out_counts)
    b = _tfidf(src_counts)
    shared = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in shared)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    if na == 0 or nb == 0:
        return 0.0
    return 1.0 - dot / (na * nb)


def compute_doc_freq(pairs: list[dict[str, Any]]) -> tuple[dict[str, int], int]:
    """Build a document-frequency table over the union of outputs and sources."""
    docs: list[set[str]] = []
    for p in pairs:
        docs.append(set(_content_tokens(p["output"])))
        docs.append(set(_content_tokens(p["context"])))
    df: dict[str, int] = {}
    for d in docs:
        for term in d:
            df[term] = df.get(term, 0) + 1
    return df, len(docs)


CORPORA = [
    ("ragtruth_summary", "RAGTruth Summary", "/tmp/alignscore_corpora/ragtruth_summary.json"),
    ("summeval", "SummEval", "/tmp/alignscore_corpora/summeval.json"),
    ("halueval_summarization", "HaluEval summarization", "/tmp/alignscore_corpora/halueval.json"),
]


def _bootstrap_one(scores: list[float], labels: list[int], name: str) -> dict[str, Any]:
    point = auc_roc(scores, labels)
    ci = bootstrap_auc_ci(scores, labels, n_resamples=1000, seed=0)
    print(
        f"    {name:30s} AUC = {point:.4f}  95% CI [{ci['ci_low']:.4f}, {ci['ci_high']:.4f}]"
        f"  (n_pos={ci['n_pos']}, n_neg={ci['n_neg']})",
        flush=True,
    )
    return ci


def main() -> None:
    base = Path("benchmarks/external")
    for corpus_dir, label, pair_path in CORPORA:
        print(f"\n=== {label} ===", flush=True)
        path = Path(pair_path)
        if not path.exists():
            print(f"  skip: pair JSON missing at {path}", flush=True)
            continue
        pairs = json.loads(path.read_text())
        print(f"  n = {len(pairs)} pairs", flush=True)

        labels = [int(p["label"]) for p in pairs]

        # WordOverlapInv.
        t0 = time.perf_counter()
        scores_wo = [word_overlap_inv(p["output"], p["context"]) for p in pairs]
        elapsed_wo = time.perf_counter() - t0
        print(f"  computed word_overlap_inv in {elapsed_wo:.2f}s", flush=True)
        ci_wo = _bootstrap_one(scores_wo, labels, "WordOverlapInv")

        # JaccardContentInv.
        t0 = time.perf_counter()
        scores_jc = [jaccard_content_inv(p["output"], p["context"]) for p in pairs]
        elapsed_jc = time.perf_counter() - t0
        print(f"  computed jaccard_content_inv in {elapsed_jc:.2f}s", flush=True)
        ci_jc = _bootstrap_one(scores_jc, labels, "JaccardContentInv")

        # TFIDFCosineInv (needs corpus-wide doc frequency).
        df, n_docs = compute_doc_freq(pairs)
        t0 = time.perf_counter()
        scores_tf = [tfidf_cosine_inv(p["output"], p["context"], df, n_docs) for p in pairs]
        elapsed_tf = time.perf_counter() - t0
        print(f"  computed tfidf_cosine_inv in {elapsed_tf:.2f}s", flush=True)
        ci_tf = _bootstrap_one(scores_tf, labels, "TFIDFCosineInv")

        snapshot = {
            "experiment": f"Trivial lexical baselines on {label}",
            "corpus": corpus_dir,
            "n_total_pairs": len(pairs),
            "trivial_baselines": {
                "word_overlap_inv": {
                    "description": "1 - |out_words ∩ src_words| / |out_words|, lowercased word tokens, no stopword filtering",
                    "bootstrap_95ci": ci_wo,
                    "runtime_seconds": round(elapsed_wo, 4),
                },
                "jaccard_content_inv": {
                    "description": "1 - jaccard(content_out, content_src), stopword-filtered, 3-char minimum",
                    "bootstrap_95ci": ci_jc,
                    "runtime_seconds": round(elapsed_jc, 4),
                },
                "tfidf_cosine_inv": {
                    "description": "1 - cosine(tfidf(output), tfidf(source)), document frequencies over corpus union",
                    "bootstrap_95ci": ci_tf,
                    "runtime_seconds": round(elapsed_tf, 4),
                },
            },
            "per_example_scores": {
                "word_overlap_inv": [round(s, 6) for s in scores_wo],
                "jaccard_content_inv": [round(s, 6) for s in scores_jc],
                "tfidf_cosine_inv": [round(s, 6) for s in scores_tf],
            },
            "per_example_label_hallucinated": labels,
        }

        out_path = base / corpus_dir / "results" / "trivial_lexical_baselines_2026-05-17.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(snapshot, indent=2))
        print(f"  wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
