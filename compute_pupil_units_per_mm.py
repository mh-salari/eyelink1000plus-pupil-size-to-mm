"""Compute PUPIL_UNITS_PER_MM from a syelink JSON of an artificial-eye recording.

Reads the JSON produced by syelink for an artificial-eye calibration session,
averages the pupil values across the recording (filtering blinks / zero
samples), and writes the calibration constant to
``psa-mechanisms/data/pupil_units_per_mm.json`` per the SR Research FAQ
(thread-154).

For AREA recording mode (default — matches the EyeLink default
``pupil_size_diameter = NO``):
    PUPIL_SQRT_AREA_UNITS_PER_MM = sqrt(mean(area_units)) / known_diameter_mm
    Apply later as:  mm = sqrt(area_units) / PUPIL_SQRT_AREA_UNITS_PER_MM

For DIAMETER recording mode:
    PUPIL_UNITS_PER_MM = mean(units) / known_diameter_mm
    Apply later as:  mm = units / PUPIL_UNITS_PER_MM

Pass --mode {area,diameter} to match the Host PC's pupil-size setting. When
both eyes have valid samples the "Both" combination (left + right pooled) is
written; otherwise the eye that has samples is used.
"""

import argparse
import json
import math
from pathlib import Path
from statistics import mean, stdev

KNOWN_DIAMETER_MM = 7.0
DEFAULT_JSON = Path(__file__).parent / "data" / "pupil_calib_7mm.json"
OUTPUT_FILE = Path(__file__).resolve().parents[1] / "data" / "pupil_units_per_mm.json"


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
# Reporting + constant computation
# ---------------------------------------------------------------------------


def _stats(vals: list[float]) -> tuple[float, float]:
    """Return ``(mean, sd)`` for a non-empty list of pupil values."""
    return mean(vals), stdev(vals) if len(vals) > 1 else 0.0


def _print_diameter(label: str, vals: list[float], known_mm: float) -> None:
    n = len(vals)
    m, sd = _stats(vals)
    constant = m / known_mm
    print(f"  {label:5s}  n={n:6d}  mean={m:8.2f} units  sd={sd:6.2f}  →  PUPIL_UNITS_PER_MM = {constant:.2f}")


def _print_area(label: str, vals: list[float], known_mm: float) -> None:
    n = len(vals)
    m, sd = _stats(vals)
    sqrt_m = math.sqrt(m)
    constant = sqrt_m / known_mm
    print(
        f"  {label:5s}  n={n:6d}  mean={m:9.1f} area-units  sd={sd:7.1f}  sqrt(mean)={sqrt_m:7.2f}  "
        f"→  PUPIL_SQRT_AREA_UNITS_PER_MM = {constant:.4f}",
    )


def _compute_constant(vals: list[float], known_mm: float, mode: str) -> float:
    """Return the calibration constant for ``vals`` in ``mode``."""
    m = mean(vals)
    if mode == "diameter":
        return m / known_mm
    return math.sqrt(m) / known_mm


def _select_canonical(left: list[float], right: list[float]) -> tuple[str, list[float]]:
    """Pick the eye(s) to write to the output file: prefer pooled, else whichever has samples."""
    if left and right:
        return "both", left + right
    if right:
        return "right", right
    return "left", left


def write_constant(
    output_file: Path,
    constant: float,
    *,
    calibration_file: Path,
    known_mm: float,
    mode: str,
    eye_used: str,
    samples: list[float],
) -> None:
    """Write the calibration constant + provenance to ``output_file``."""
    m, sd = _stats(samples)
    payload = {
        "pupil_units_per_mm" if mode == "diameter" else "pupil_sqrt_area_units_per_mm": round(constant, 4),
        "_source": {
            "method": "artificial_eye",
            "calibration_file": str(calibration_file),
            "known_diameter_mm": known_mm,
            "mode": mode,
            "eye_used": eye_used,
            "n_samples": len(samples),
            "mean_units": round(m, 4),
            "sd_units": round(sd, 4),
        },
    }
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse a calibration JSON and write the PUPIL_UNITS_PER_MM constant to data/."""
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
        choices=("area", "diameter"),
        default="area",
        help="EyeLink pupil-size recording mode set on the Host PC (default: area, "
        "the EyeLink default ``pupil_size_diameter = NO``)",
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

    report = _print_diameter if args.mode == "diameter" else _print_area
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

    eye_used, canonical_samples = _select_canonical(left, right)
    constant = _compute_constant(canonical_samples, args.known_mm, args.mode)

    write_constant(
        OUTPUT_FILE,
        constant,
        calibration_file=args.json,
        known_mm=args.known_mm,
        mode=args.mode,
        eye_used=eye_used,
        samples=canonical_samples,
    )
    print(f"\nWrote: {OUTPUT_FILE}  (eye_used={eye_used})")


if __name__ == "__main__":
    main()
