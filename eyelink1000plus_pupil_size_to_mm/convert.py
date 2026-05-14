"""Augment a syelink-converted recording JSON with per-sample pupil mm.

Reads the calibration JSON written by ``compute`` and adds ``<eye>_pupil_mm`` to
every sample in the target JSON, for each tracked eye. Idempotent. Writes the
JSON back in place.
"""

import json
from pathlib import Path

from . import augment_gaze_samples, load_calibration

# Map raw EDF field names to canonical eye keys (matches the library's RAW_FIELD).
RAW_TO_EYE = {"left_pupil": "left_eye", "right_pupil": "right_eye"}


def detect_eyes(samples: list[dict]) -> list[str]:
    """Return ``[left_eye?, right_eye?]`` based on which raw pupil fields have non-null data."""
    eyes: list[str] = []
    for raw_field, eye_key in RAW_TO_EYE.items():
        if any(s.get(raw_field) is not None for s in samples):
            eyes.append(eye_key)
    return eyes


def convert_recording(
    input_json: Path,
    calibration_json: Path,
    eyes: list[str] | None = None,
) -> None:
    """Augment ``input_json`` in place with per-sample pupil mm.

    ``eyes`` overrides auto-detection (which scans the JSON for non-null
    ``<side>_pupil`` fields). Valid eye keys: ``"left_eye"``, ``"right_eye"``.
    """
    if not input_json.exists():
        raise SystemExit(f"input JSON not found: {input_json}")

    data = json.loads(input_json.read_text(encoding="utf-8"))
    samples = data.get("gaze_samples") or []

    if eyes is None:
        eyes = detect_eyes(samples)
        if not eyes:
            raise SystemExit(f"no left/right pupil data in {input_json}")
        print(f"detected eyes from sample data: {eyes}")
    else:
        print(f"using eyes from --eyes: {eyes}")

    mode, constants = load_calibration(calibration_json, eyes)
    summary = "  ".join(f"{eye}={constants[eye]}" for eye in eyes)
    print(f"mode={mode}  {summary}  (from {calibration_json})")

    n_with_mm = augment_gaze_samples(samples, eyes, mode, constants)

    input_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"  {n_with_mm}/{len(samples)} samples have non-null pupil_mm")
    print(f"  → {input_json}")
