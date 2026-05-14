"""Compute the per-eye pupil-units-per-mm constant from an artificial-eye JSON.

Reads the syelink-converted JSON of a single-eye artificial-eye recording, averages
the pupil values (filtering blinks / zero samples), and merges the per-eye constant
into the calibration JSON used downstream by ``convert``.
"""

import json
import math
from pathlib import Path
from statistics import mean, stdev

EYE_TO_RAW = {"left_eye": "left_pupil", "right_eye": "right_pupil"}
EYE_FROM_FLAG = {"left": "left_eye", "right": "right_eye"}
SCHEMA_KEYS = {"mode", "left_eye", "right_eye"}
VALID_MODES = ("area", "diameter")


def collect_pupil_units(samples: list[dict], eye_key: str) -> list[float]:
    """Return raw pupil values for ``eye_key`` (``left_eye``/``right_eye``)."""
    raw_field = EYE_TO_RAW[eye_key]
    return [v for s in samples if (v := s.get(raw_field)) is not None and v > 0]


def compute_constant(vals: list[float], known_mm: float, mode: str) -> float:
    """Return the calibration constant for ``vals`` in ``mode``."""
    m = mean(vals)
    return math.sqrt(m) / known_mm if mode == "area" else m / known_mm


def load_existing(output_file: Path) -> dict:
    """Return only the current-schema keys from the existing JSON (or a fresh skeleton)."""
    if not output_file.exists():
        return {"mode": None}
    raw = json.loads(output_file.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if k in SCHEMA_KEYS}


def compute_for_eye(
    input_json: Path,
    eye_flag: str,
    output_json: Path,
    known_mm: float,
    mode: str,
) -> None:
    """Compute the constant for one eye, merge into the calibration JSON.

    ``eye_flag`` is ``"left"`` / ``"right"`` (matching the recording side).
    ``mode`` is ``"area"`` (EyeLink default) or ``"diameter"``.
    """
    if mode not in VALID_MODES:
        raise SystemExit(f"invalid mode {mode!r}; choose from {VALID_MODES}")
    if eye_flag not in EYE_FROM_FLAG:
        raise SystemExit(f"invalid eye {eye_flag!r}; choose left or right")
    if not input_json.exists():
        raise SystemExit(f"input JSON not found: {input_json}")

    eye_key = EYE_FROM_FLAG[eye_flag]
    data = json.loads(input_json.read_text(encoding="utf-8"))
    vals = collect_pupil_units(data["gaze_samples"], eye_key)
    if not vals:
        raise SystemExit(f"no valid {eye_key} pupil samples in {input_json}")

    constant = compute_constant(vals, known_mm, mode)
    m = mean(vals)
    sd = stdev(vals) if len(vals) > 1 else 0.0

    print(f"\nFile : {input_json}")
    print(f"Eye  : {eye_key}")
    print(f"Mode : {mode}")
    print(f"Known: {known_mm} mm")
    if mode == "area":
        print(
            f"  n={len(vals):6d}  mean={m:9.1f} area-units  sd={sd:7.1f}  "
            f"sqrt(mean)={math.sqrt(m):7.2f}  →  PUPIL_SQRT_AREA_UNITS_PER_MM = {constant:.4f}"
        )
    else:
        print(f"  n={len(vals):6d}  mean={m:8.2f} units  sd={sd:6.2f}  →  PUPIL_UNITS_PER_MM = {constant:.2f}")

    payload = load_existing(output_json)
    if payload.get("mode") not in {None, mode}:
        raise SystemExit(
            f"existing {output_json.name} has mode={payload['mode']!r} but --mode={mode!r}. "
            f"Recompute both eyes in the same mode or delete the file to start over.",
        )
    payload["mode"] = mode
    payload[eye_key] = {
        "constant": round(constant, 4),
        "calibration_file": str(input_json),
        "known_diameter_mm": known_mm,
        "n_samples": len(vals),
        "mean_units": round(m, 4),
        "sd_units": round(sd, 4),
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote: {output_json}  (eye={eye_key})")
