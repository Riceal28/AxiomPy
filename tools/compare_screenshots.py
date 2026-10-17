"""Pixel-compare two screenshot directories and write difference images."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def _changed_ratio(image: Image.Image, threshold: int) -> float:
    gray = image.convert("L")
    changed = sum(
        1 for value in gray.getdata() if value > threshold
    )
    return changed / float(gray.width * gray.height)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument(
        "--diff",
        type=Path,
        default=Path("artifacts/ui-diff"),
    )
    parser.add_argument("--pixel-threshold", type=int, default=8)
    parser.add_argument("--max-changed-ratio", type=float, default=0.005)
    args = parser.parse_args()

    args.diff.mkdir(parents=True, exist_ok=True)
    baseline = {path.stem: path for path in args.baseline.glob("*.png")}
    candidate = {path.stem: path for path in args.candidate.glob("*.png")}
    failures: list[str] = []

    for name in sorted(baseline):
        if name not in candidate:
            failures.append(f"{name}: missing candidate")
            continue
        with Image.open(baseline[name]) as left_image:
            left = left_image.convert("RGB")
        with Image.open(candidate[name]) as right_image:
            right = right_image.convert("RGB")
        if left.size != right.size:
            failures.append(
                f"{name}: size {left.size} != {right.size}"
            )
            continue
        difference = ImageChops.difference(left, right)
        difference.save(args.diff / f"{name}.png")
        ratio = _changed_ratio(difference, args.pixel_threshold)
        rms = sum(ImageStat.Stat(difference).rms) / 3.0
        print(f"{name}: changed={ratio:.4%} rms={rms:.2f}")
        if ratio > args.max_changed_ratio:
            failures.append(
                f"{name}: changed {ratio:.2%} > "
                f"{args.max_changed_ratio:.2%}"
            )

    for name in sorted(set(candidate) - set(baseline)):
        print(f"{name}: new screenshot (not compared)")

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print(f"All {len(baseline)} screenshots matched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
