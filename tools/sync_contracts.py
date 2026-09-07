"""Refresh the vendored firmware contracts from a bl-benchlab-firmware checkout.

The contracts in ``benchlab_pycore/contracts/`` are copied verbatim from the
firmware repo's ``protocol/`` directory. They are generated there from the
firmware headers and frozen at release time, so this is a copy, never an edit.

Usage::

    python tools/sync_contracts.py --from ../bl-benchlab-firmware
    python tools/sync_contracts.py --from ../bl-benchlab-firmware --check

``--check`` compares bytes and exits non-zero on drift without writing
anything, which is what CI runs. Byte comparison rather than text avoids
false positives from line-ending normalisation.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

DEST = Path(__file__).resolve().parent.parent / "benchlab_pycore" / "contracts"


def _source_files(protocol_dir: Path) -> list[Path]:
    """The files to vendor: every contract named by index.json, plus the
    index and schema themselves.

    Driven by index.json rather than a glob so that a contract the index does
    not know about is not silently picked up.
    """
    index_path = protocol_dir / "index.json"
    if not index_path.exists():
        sys.exit(f"error: {index_path} not found -- is --from a firmware checkout?")

    index = json.loads(index_path.read_text(encoding="utf-8"))
    files = [index_path, protocol_dir / "schema.json"]
    for entry in index["contracts"]:
        path = protocol_dir / entry["file"]
        if not path.exists():
            sys.exit(f"error: {path} is named by index.json but missing")
        files.append(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--from", dest="source", required=True,
        help="path to a bl-benchlab-firmware checkout (or its protocol/ dir)",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="report drift and exit non-zero instead of writing",
    )
    args = parser.parse_args()

    source = Path(args.source).resolve()
    protocol_dir = source if source.name == "protocol" else source / "protocol"

    files = _source_files(protocol_dir)
    DEST.mkdir(parents=True, exist_ok=True)

    drifted: list[str] = []
    for src in files:
        dst = DEST / src.name
        if not dst.exists() or dst.read_bytes() != src.read_bytes():
            drifted.append(src.name)
            if not args.check:
                shutil.copyfile(src, dst)

    # A contract deleted upstream should not linger here.
    expected = {f.name for f in files}
    for stale in sorted(p for p in DEST.glob("*.json") if p.name not in expected):
        drifted.append(f"{stale.name} (not in index.json)")
        if not args.check:
            stale.unlink()

    if args.check:
        if drifted:
            print("Vendored contracts differ from " + str(protocol_dir) + ":")
            for name in drifted:
                print(f"  {name}")
            print("\nRefresh with: python tools/sync_contracts.py --from " + str(source))
            return 1
        print(f"Vendored contracts match {protocol_dir} ({len(files)} files).")
        return 0

    if drifted:
        print(f"Updated {len(drifted)} file(s) in {DEST}:")
        for name in drifted:
            print(f"  {name}")
    else:
        print(f"Already up to date ({len(files)} files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
