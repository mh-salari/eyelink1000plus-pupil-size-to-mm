"""Core conversion logic: load calibration JSON, map raw pupil units to mm.

Two host-column tracking modes are supported, selected by the ``mode`` field of
the calibration JSON written by the ``compute`` subcommand:

  - ``"area"``     (Host PC ``pupil_size_diameter = NO``):  ``mm = sqrt(units) / constant``
  - ``"diameter"`` (Host PC ``pupil_size_diameter = YES``): ``mm = units / constant``

The Host PC tracking mode and the artificial-eye calibration recording must use
the same mode; mismatched modes silently break small-pupil readings.

When pyelink writes per-sample raw fields (``<eye>_raw.pupil_width``,
``pupil_height``) into the gaze samples (``record_raw_data=True``), the same
calibration recording also yields a raw-diameter constant under the optional
top-level ``raw_diameter`` block of the calibration JSON. If that block is
present, ``augment_gaze_samples`` additionally writes
``<eye>_raw.pupil_diameter_mm = ((pupil_width + pupil_height) / 2) / raw_constant``
per sample, alongside the host-column ``<eye>_pupil_mm`` field.
"""

import json
import math
from pathlib import Path

# Map canonical eye keys to the host-column raw EDF field names and the mm field
# names we add for the host column.
RAW_FIELD = {"left_eye": "left_pupil", "right_eye": "right_pupil"}
MM_FIELD = {"left_eye": "left_pupil_mm", "right_eye": "right_pupil_mm"}

# Per-sample raw block (pyelink with record_raw_data=True): nested dict carrying
# pupil_width / pupil_height / pupil_area / cr_x / cr_y for each tracked eye.
RAW_BLOCK_FIELD = {"left_eye": "left_raw", "right_eye": "right_raw"}
RAW_WIDTH_KEY = "pupil_width"
RAW_HEIGHT_KEY = "pupil_height"
RAW_DIAMETER_MM_KEY = "pupil_diameter_mm"

VALID_MODES = ("area", "diameter")


def load_calibration(
    calibration_path: Path | str,
    eyes: list[str],
) -> tuple[str, dict[str, float], dict[str, float] | None]:
    """Return ``(mode, host_constants, raw_constants_or_None)`` for each tracked eye.

    ``calibration_path`` points to the JSON written by the ``compute`` subcommand.
    Expected shape::

        {
          "mode": "area" | "diameter",
          "left_eye":  {"constant": <float>, ...},
          "right_eye": {"constant": <float>, ...},
          "raw_diameter": {                       (optional)
            "left_eye":  {"constant": <float>, ...},
            "right_eye": {"constant": <float>, ...}
          }
        }

    The ``raw_diameter`` block is written by ``compute`` when the artificial-eye
    recording carries per-sample raw fields (pyelink ``record_raw_data=True``).
    When absent, ``raw_constants`` is ``None`` and only the host-column field
    will be added by :func:`augment_gaze_samples`.

    Fail-fast on missing file, unknown host mode, or missing per-eye host-column
    block. Raw-diameter blocks are optional per-eye; the absence of one eye in
    the raw block just disables raw-mm augmentation for that eye.
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
                f"no {eye} calibration in {path}. Run `compute --eye {eye.split('_')[0]}` first.",
            )
        constants[eye] = float(block["constant"])
    raw_block = payload.get("raw_diameter")
    raw_constants: dict[str, float] | None = None
    if raw_block:
        raw_constants = {}
        for eye in eyes:
            entry = raw_block.get(eye)
            if entry and "constant" in entry:
                raw_constants[eye] = float(entry["constant"])
        if not raw_constants:
            raw_constants = None
    return mode, constants, raw_constants


def units_to_mm(value: float | None, mode: str, constant: float) -> float | None:
    """Convert one raw EyeLink pupil unit to mm under the given calibration mode.

    ``None`` stays ``None`` (missing sample); ``0`` units becomes ``0.0`` mm.
    """
    if value is None:
        return None
    if mode == "area":
        return math.sqrt(value) / constant if value > 0 else 0.0
    return value / constant


def raw_diameter_units(raw_block: dict | None) -> float | None:
    """Return ``(pupil_width + pupil_height) / 2`` from a per-sample raw block.

    Returns ``None`` when the block is missing, either dimension is missing, or
    either dimension is non-positive (the SR Research convention for blink /
    no-detection samples).
    """
    if raw_block is None:
        return None
    w = raw_block.get(RAW_WIDTH_KEY)
    h = raw_block.get(RAW_HEIGHT_KEY)
    if w is None or h is None:
        return None
    if w <= 0 or h <= 0:
        return None
    return (float(w) + float(h)) / 2.0


def augment_gaze_samples(
    samples: list[dict],
    eyes: list[str],
    mode: str,
    constants: dict[str, float],
    raw_constants: dict[str, float] | None = None,
) -> int:
    """Add ``<eye>_pupil_mm`` to every gaze sample in place for each eye in ``eyes``.

    Each eye uses its own per-eye calibration constant. Untracked eyes get no mm
    field at all. Returns the number of samples with at least one non-None mm value
    across the tracked eyes.

    When ``raw_constants`` is provided AND the sample carries a ``<eye>_raw`` block
    with ``pupil_width`` / ``pupil_height`` (pyelink ``record_raw_data=True``),
    also writes ``<eye>_raw.pupil_diameter_mm`` per sample. The host-column
    ``<eye>_pupil_mm`` field is always written regardless.
    """
    n_with_mm = 0
    for s in samples:
        any_mm = False
        for eye in eyes:
            mm = units_to_mm(s.get(RAW_FIELD[eye]), mode, constants[eye])
            s[MM_FIELD[eye]] = mm
            if mm is not None:
                any_mm = True
            if raw_constants is not None and eye in raw_constants:
                raw_block = s.get(RAW_BLOCK_FIELD[eye])
                if isinstance(raw_block, dict):
                    diameter_units = raw_diameter_units(raw_block)
                    raw_block[RAW_DIAMETER_MM_KEY] = (
                        diameter_units / raw_constants[eye] if diameter_units is not None else None
                    )
        if any_mm:
            n_with_mm += 1
    return n_with_mm
