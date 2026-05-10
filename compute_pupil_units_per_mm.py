"""Compute per-eye PUPIL_UNITS_PER_MM from an artificial-eye recording.

Reads the JSON produced by syelink for a single-eye artificial-eye calibration
session, averages the pupil values across the recording (filtering blinks /
zero samples), and writes the per-eye calibration constant to
``psa-mechanisms/data/pupil_units_per_mm.json`` per the SR Research FAQ
(thread-154).

Run once per eye::

    uv run python compute_pupil_units_per_mm.py --eye left  data/pupil_calib_7mm_left.json
    uv run python compute_pupil_units_per_mm.py --eye right data/pupil_calib_7mm_right.json

Both runs share the output JSON; the second run merges its per-eye block in
without overwriting the first eye's calibration. Mode must match between
runs (the file's existing ``mode`` is checked on the second call).

For AREA recording mode (default — matches the EyeLink default
``pupil_size_diameter = NO``)::

    PUPIL_SQRT_AREA_UNITS_PER_MM = sqrt(mean(area_units)) / known_diameter_mm
    Apply later as:  mm = sqrt(area_units) / PUPIL_SQRT_AREA_UNITS_PER_MM

For DIAMETER recording mode::

    PUPIL_UNITS_PER_MM = mean(units) / known_diameter_mm
    Apply later as:  mm = units / PUPIL_UNITS_PER_MM
"""

import argparse
import json
import math
from pathlib import Path
from statistics import mean, stdev

KNOWN_DIAMETER_MM = 7.0
DATA_DIR = Path(__file__).parent / "data"
OUTPUT_FILE = Path(__file__).resolve().parents[1] / "data" / "pupil_units_per_mm.json"

EYE_TO_RAW = {"left_eye": "left_pupil", "right_eye": "right_pupil"}
EYE_FROM_FLAG = {"left": "left_eye", "right": "right_eye"}


def collect_pupil_units(samples: list[dict], eye: str) -> list[float]:
    """Return raw pupil values for ``eye`` with blinks / null / zero filtered."""
    raw_field = EYE_TO_RAW[eye]
    return [v for s in samples if (v := s.get(raw_field)) is not None and v > 0]


def compute_constant(vals: list[float], known_mm: float, mode: str) -> float:
    """Return the calibration constant for ``vals`` in ``mode``."""
    m = mean(vals)
    return math.sqrt(m) / known_mm if mode == "area" else m / known_mm


def load_existing(output_file: Path) -> dict:
    """Return the existing JSON, or a fresh skeleton if the file doesn't exist yet."""
    if output_file.exists():
        return json.loads(output_file.read_text(encoding="utf-8"))
    return {"mode": None}


def main() -> None:
    """Parse one calibration JSON and merge its per-eye constant into pupil_units_per_mm.json."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--eye",
        choices=("left", "right"),
        required=True,
        help="Which artificial eye this recording covers.",
    )
    parser.add_argument(
        "json",
        type=Path,
        nargs="?",
        default=None,
        help="Path to syelink-converted JSON "
        "(default: data/pupil_calib_<known-mm>mm_<eye>.json)",
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

    eye = EYE_FROM_FLAG[args.eye]
    json_path = args.json or DATA_DIR / f"pupil_calib_{args.known_mm:.0f}mm_{args.eye}.json"
    if not json_path.exists():
        raise SystemExit(f"JSON file not found: {json_path}")

    data = json.loads(json_path.read_text())
    vals = collect_pupil_units(data["gaze_samples"], eye)
    if not vals:
        raise SystemExit(f"no valid {eye} pupil samples in {json_path}")

    constant = compute_constant(vals, args.known_mm, args.mode)
    m = mean(vals)
    sd = stdev(vals) if len(vals) > 1 else 0.0

    print(f"\nFile : {json_path}")
    print(f"Eye  : {eye}")
    print(f"Mode : {args.mode}")
    print(f"Known: {args.known_mm} mm")
    if args.mode == "area":
        print(
            f"  n={len(vals):6d}  mean={m:9.1f} area-units  sd={sd:7.1f}  "
            f"sqrt(mean)={math.sqrt(m):7.2f}  →  PUPIL_SQRT_AREA_UNITS_PER_MM = {constant:.4f}"
        )
    else:
        print(f"  n={len(vals):6d}  mean={m:8.2f} units  sd={sd:6.2f}  →  PUPIL_UNITS_PER_MM = {constant:.2f}")

    payload = load_existing(OUTPUT_FILE)
    if payload.get("mode") not in (None, args.mode):
        raise SystemExit(
            f"existing {OUTPUT_FILE.name} has mode={payload['mode']!r} but --mode={args.mode!r}. "
            f"Recompute both eyes in the same mode or delete the file to start over.",
        )
    payload["mode"] = args.mode
    payload[eye] = {
        "constant": round(constant, 4),
        "calibration_file": str(json_path),
        "known_diameter_mm": args.known_mm,
        "n_samples": len(vals),
        "mean_units": round(m, 4),
        "sd_units": round(sd, 4),
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote: {OUTPUT_FILE}  (eye={eye})")


if __name__ == "__main__":
    main()
