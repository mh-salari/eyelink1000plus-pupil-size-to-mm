"""Compute PUPIL_UNITS_PER_MM from a syelink JSON of an artificial-eye recording.

Reads the JSON produced by syelink for an artificial-eye calibration session,
averages the pupil values across the recording (filtering blinks / zero
samples), and prints the calibration constant per the SR Research FAQ
(thread-154).

For DIAMETER recording mode (default):
    PUPIL_UNITS_PER_MM = mean(units) / known_diameter_mm
    Apply later as:  mm = units / PUPIL_UNITS_PER_MM

For AREA recording mode:
    PUPIL_SQRT_AREA_UNITS_PER_MM = sqrt(mean(area_units)) / known_diameter_mm
    Apply later as:  mm = sqrt(area_units) / PUPIL_SQRT_AREA_UNITS_PER_MM

Pass --mode {diameter,area} to match the Host PC's pupil-size setting.
"""

import argparse
import json
import math
from pathlib import Path
from statistics import mean, stdev

KNOWN_DIAMETER_MM = 7.0
DEFAULT_JSON = Path(__file__).parent / "data" / "pupil_calib_7mm.json"


# ---------------------------------------------------------------------------
# Sample collection
# ---------------------------------------------------------------------------


def collect_pupil_units(samples: list[dict]) -> tuple[list[float], list[float]]:
    """Return (left, right) pupil unit lists with blinks / null / zero filtered."""
    left: list[float] = []
    right: list[float] = []
    for s in samples:
        lp, rp = s.get("left_pupil"), s.get("right_pupil")
        if lp is not None and lp > 0:
            left.append(lp)
        if rp is not None and rp > 0:
            right.append(rp)
    return left, right


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _report_diameter(label: str, vals: list[float], known_mm: float) -> None:
    n = len(vals)
    m = mean(vals)
    sd = stdev(vals) if n > 1 else 0.0
    constant = m / known_mm
    print(f"  {label:5s}  n={n:6d}  mean={m:8.2f} units  sd={sd:6.2f}  →  PUPIL_UNITS_PER_MM = {constant:.2f}")


def _report_area(label: str, vals: list[float], known_mm: float) -> None:
    n = len(vals)
    m = mean(vals)
    sd = stdev(vals) if n > 1 else 0.0
    sqrt_m = math.sqrt(m)
    constant = sqrt_m / known_mm
    print(
        f"  {label:5s}  n={n:6d}  mean={m:9.1f} area-units  sd={sd:7.1f}  sqrt(mean)={sqrt_m:7.2f}  "
        f"→  PUPIL_SQRT_AREA_UNITS_PER_MM = {constant:.4f}"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse a calibration JSON and print the PUPIL_UNITS_PER_MM constant."""
    parser = argparse.ArgumentParser(description="Compute PUPIL_UNITS_PER_MM from an artificial-eye recording.")
    parser.add_argument(
        "json",
        type=Path,
        nargs="?",
        default=DEFAULT_JSON,
        help=f"Path to syelink-converted JSON (default: {DEFAULT_JSON})",
    )
    parser.add_argument(
        "--known-mm",
        type=float,
        default=KNOWN_DIAMETER_MM,
        help=f"Artificial-eye diameter in mm (default: {KNOWN_DIAMETER_MM})",
    )
    parser.add_argument(
        "--mode",
        choices=("diameter", "area"),
        default="diameter",
        help="EyeLink pupil-size recording mode set on the Host PC (default: diameter)",
    )
    args = parser.parse_args()

    if not args.json.exists():
        msg = f"JSON file not found: {args.json}"
        raise FileNotFoundError(msg)

    data = json.loads(args.json.read_text())
    left, right = collect_pupil_units(data["gaze_samples"])

    if not left and not right:
        msg = f"No valid (non-zero) pupil samples in {args.json}"
        raise RuntimeError(msg)

    print(f"\nFile : {args.json}")
    print(f"Mode : {args.mode}")
    print(f"Known: {args.known_mm} mm")
    print()

    report = _report_diameter if args.mode == "diameter" else _report_area
    if left:
        report("Left", left, args.known_mm)
    else:
        print("  Left   no valid samples")
    if right:
        report("Right", right, args.known_mm)
    else:
        print("  Right  no valid samples")
    if left and right:
        report("Both", left + right, args.known_mm)


if __name__ == "__main__":
    main()
