"""Public datasets that may help (v7 §9). NOTHING is downloaded by this script.

`python training/download.py list` prints the registry. `python training/download.py get NAME --yes`
only creates data/external/NAME and prints where to fetch the files: these datasets need a licence
check or a login, so the files are placed by hand (and checked with `verify`). Face and gesture
data of real staff is recorded with robot/vision_agent/record.py instead.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path("data/external")
REGISTRY = {
    "wider_face": ("Face detection (v7 6.3)", "http://shuoyang1213.me/WIDERFACE/"),
    "coco_person": ("Person detection, lower body crops (v7 8.2)", "https://cocodataset.org/#download"),
    "crowdhuman": ("Person detection in crowds (v7 8.2)", "https://www.crowdhuman.org/"),
    "hagrid": ("Hand gestures to pretrain the classifier (v7 7.3)", "https://github.com/hukenovs/hagrid"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    get = sub.add_parser("get")
    get.add_argument("name", choices=sorted(REGISTRY))
    get.add_argument("--yes", action="store_true", help="confirm that you accept the dataset licence")
    verify = sub.add_parser("verify")
    verify.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    if args.cmd == "list":
        for name, (use, url) in sorted(REGISTRY.items()):
            print(f"{name:12} {use}\n{'':12} {url}")
        return 0
    if args.cmd == "verify":
        print(sha256(args.file))
        return 0
    if not args.yes:
        print("add --yes after reading the dataset licence", file=sys.stderr)
        return 2
    target = ROOT / args.name
    target.mkdir(parents=True, exist_ok=True)
    print(f"Download manually from {REGISTRY[args.name][1]} into {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
