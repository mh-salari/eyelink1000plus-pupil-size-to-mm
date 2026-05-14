"""Core conversion logic: load calibration JSON, map raw pupil units to mm.

Two tracking modes are supported, selected by the ``mode`` field of the
calibration JSON written by the ``compute`` subcommand:

  - ``"area"``     (Host PC ``pupil_size_diameter = NO``):  ``mm = sqrt(units) / constant``
  - ``"diameter"`` (Host PC ``pupil_size_diameter = YES``): ``mm = units / constant``

The Host PC tracking mode and the artificial-eye calibration recording must use
the same mode; mismatched modes silently break small-pupil readings.
"""

import json
import math
from pathlib import Path

# Map canonical eye keys to the raw EDF field names and the mm field names we add.
RAW_FIELD = {"left_eye": "left_pupil", "right_eye": "right_pupil"}
MM_FIELD = {"left_eye": "left_pupil_mm", "right_eye": "right_pupil_mm"}

VALID_MODES = ("area", "diameter")


def load_calibration(calibration_path: Path | str, eyes: list[str]) -> tuple[str, dict[str, float]]:
    """Return ``(mode, {eye: constant})`` for each tracked eye.

    ``calibration_path`` points to the JSON written by the ``compute`` subcommand.
    Expected shape::

        {
          "mode": "area" | "diameter",
          "left_eye":  {"constant": <float>, ...},
          "right_eye": {"constant": <float>, ...}
        }

    Fail-fast on missing file, unknown mode, or missing per-eye block.
    """
    path = Path(calibration_path)
    if not path.exists():
        raise SystemExit(
            f"missing {path}. Run the `compute` subcommand first (once per eye).",
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    mode = payload.get("mode")
    if mode not in VALID_MODES:
        raise SystemExit(f"unknown or missing mode in {path}: {mode!r} (expected one of {VALID_MODES}).")
    constants: dict[str, float] = {}
    for eye in eyes:
        block = payload.get(eye)
        if not block:
            raise SystemExit(
                f"no {eye} calibration in {path}. "
                f"Run `compute --eye {eye.split('_')[0]}` first.",
            )
        constants[eye] = float(block["constant"])
    return mode, constants


def units_to_mm(value: float | None, mode: str, constant: float) -> float | None:
    """Convert one raw EyeLink pupil unit to mm under the given calibration mode.

    ``None`` stays ``None`` (missing sample); ``0`` units becomes ``0.0`` mm.
    """
    if value is None:
        return None
    if mode == "area":
        return math.sqrt(value) / constant if value > 0 else 0.0
    return value / constant


def augment_gaze_samples(
    samples: list[dict],
    eyes: list[str],
    mode: str,
    constants: dict[str, float],
) -> int:
    """Add ``<eye>_pupil_mm`` to every gaze sample in place for each eye in ``eyes``.

    Each eye uses its own per-eye calibration constant. Untracked eyes get no mm
    field at all. Returns the number of samples with at least one non-None mm value
    across the tracked eyes.
    """
    n_with_mm = 0
    for s in samples:
        any_mm = False
        for eye in eyes:
            mm = units_to_mm(s.get(RAW_FIELD[eye]), mode, constants[eye])
            s[MM_FIELD[eye]] = mm
            if mm is not None:
                any_mm = True
        if any_mm:
            n_with_mm += 1
    return n_with_mm
