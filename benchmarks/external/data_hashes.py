"""Compute and verify SHA-256 hashes for the source pair files.

Every snapshot in ``benchmarks/external/*/results/`` (substrate, MiniCheck,
AlignScore, judges) is derived from a pair file under
``/tmp/alignscore_corpora/``. Those pair files are NOT in the repo (they
are derived from the corpus runners under ``benchmarks/external/<corpus>/``,
running in ``.venv-external`` / ``.venv-alignscore``). For reproducibility
to be auditable, the pair files must be cryptographically pinned: any
future regeneration that doesn't match the recorded SHA-256 invalidates
the downstream snapshots that referenced them.

This script does two operations:

- ``--write``: read every pair file in the standard set, compute SHA-256,
  size, and row count, and write the manifest to
  ``benchmarks/external/data_hashes_2026-05-19.json``. Also patches every
  ``subsample_n400_indices_*.json`` file under each corpus's ``results/``
  to include a ``source_sha256`` field tying that subsample back to the
  exact source pair file it was sampled from.
- ``--verify``: re-read the pair files and compare against the manifest;
  exit non-zero if any hash differs.

Run::

    python -m benchmarks.external.data_hashes --write
    python -m benchmarks.external.data_hashes --verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

CORPORA_PAIRS = {
    "ragtruth_summary": "/tmp/alignscore_corpora/ragtruth_summary.json",
    "ragtruth_qa": "/tmp/alignscore_corpora/ragtruth_qa.json",
    "ragtruth_data2txt": "/tmp/alignscore_corpora/ragtruth_data2txt.json",
    "summeval": "/tmp/alignscore_corpora/summeval.json",
    "halueval_summarization": "/tmp/alignscore_corpora/halueval.json",
}

# Subsample pair files derived from the above by subsample_pairs.py.
SUBSAMPLE_PAIRS = {
    "ragtruth_summary": "/tmp/alignscore_corpora/ragtruth_summary_n400.json",
    "summeval": "/tmp/alignscore_corpora/summeval_n400.json",
    "halueval_summarization": "/tmp/alignscore_corpora/halueval_n400.json",
}

# subsample_n400_indices_*.json file path under each corpus's results/.
SUBSAMPLE_INDICES_GLOB = "benchmarks/external/{corpus}/results/subsample_n400_indices_*.json"


def _sha256_and_meta(path: Path) -> dict:
    digest = hashlib.sha256()
    n_bytes = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
            n_bytes += len(chunk)
    # Row count (the pair files are JSON arrays of {context, output, label}).
    rows = json.loads(path.read_text())
    return {
        "path": str(path),
        "sha256": digest.hexdigest(),
        "size_bytes": n_bytes,
        "n_rows": len(rows),
    }


def write_manifest() -> dict:
    manifest = {
        "source_pair_files": {},
        "subsample_pair_files": {},
        "notes": (
            "SHA-256 pins for the source and subsample pair files used to "
            "generate every snapshot in benchmarks/external/*/results/. The "
            "source files live in /tmp/alignscore_corpora/ and are derived "
            "from each corpus's runner under benchmarks/external/<corpus>/ "
            "via .venv-external or .venv-alignscore. The subsample files "
            "are derived from the source files by "
            "benchmarks/external/subsample_pairs.py with --n-total 400."
        ),
    }
    for corpus, path_str in CORPORA_PAIRS.items():
        p = Path(path_str)
        if not p.exists():
            print(f"WARN: source pair file missing: {p}", file=sys.stderr)
            continue
        manifest["source_pair_files"][corpus] = _sha256_and_meta(p)
    for corpus, path_str in SUBSAMPLE_PAIRS.items():
        p = Path(path_str)
        if not p.exists():
            print(f"WARN: subsample pair file missing: {p}", file=sys.stderr)
            continue
        manifest["subsample_pair_files"][corpus] = _sha256_and_meta(p)

    # Patch each subsample_n400_indices_*.json file with the source_sha256
    # of the corpus's source pair file.
    for corpus in SUBSAMPLE_PAIRS:
        if corpus not in manifest["source_pair_files"]:
            continue
        source_sha = manifest["source_pair_files"][corpus]["sha256"]
        subsample_sha = manifest["subsample_pair_files"][corpus]["sha256"]
        for idx_path in Path().glob(SUBSAMPLE_INDICES_GLOB.format(corpus=corpus)):
            doc = json.loads(idx_path.read_text())
            doc["source_sha256"] = source_sha
            doc["subsample_sha256"] = subsample_sha
            idx_path.write_text(json.dumps(doc, indent=2))
            print(f"  patched {idx_path}")

    out_path = Path("benchmarks/external/data_hashes_2026-05-19.json")
    out_path.write_text(json.dumps(manifest, indent=2))
    print(f"Wrote {out_path}")
    print()
    print("Source pair files:")
    for corpus, meta in manifest["source_pair_files"].items():
        print(
            f"  {corpus:25s}  sha256={meta['sha256'][:16]}...  n={meta['n_rows']}  size={meta['size_bytes']:,}"
        )
    print("Subsample pair files:")
    for corpus, meta in manifest["subsample_pair_files"].items():
        print(f"  {corpus:25s}  sha256={meta['sha256'][:16]}...  n={meta['n_rows']}")
    return manifest


def verify_manifest() -> int:
    manifest_path = Path("benchmarks/external/data_hashes_2026-05-19.json")
    if not manifest_path.exists():
        print(f"ERROR: manifest missing at {manifest_path}", file=sys.stderr)
        return 2
    manifest = json.loads(manifest_path.read_text())
    drift = 0
    for section_name, expected_section in (
        ("source_pair_files", manifest["source_pair_files"]),
        ("subsample_pair_files", manifest["subsample_pair_files"]),
    ):
        for corpus, expected in expected_section.items():
            p = Path(expected["path"])
            if not p.exists():
                print(f"ERROR: {section_name}.{corpus} path missing: {p}", file=sys.stderr)
                drift += 1
                continue
            actual = _sha256_and_meta(p)
            if actual["sha256"] != expected["sha256"]:
                print(
                    f"DRIFT: {section_name}.{corpus} sha256 mismatch: "
                    f"expected {expected['sha256'][:16]}..., got {actual['sha256'][:16]}...",
                    file=sys.stderr,
                )
                drift += 1
            else:
                print(f"OK    {section_name}.{corpus}  sha256 matches  n={actual['n_rows']}")
    return 0 if drift == 0 else 1


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--verify", action="store_true")
    args = p.parse_args()
    if args.write:
        write_manifest()
    else:
        sys.exit(verify_manifest())


if __name__ == "__main__":
    main()
