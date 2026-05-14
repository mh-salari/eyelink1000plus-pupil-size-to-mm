"""Convert EyeLink 1000 Plus pupil-size readings (arbitrary units) to millimetres.

EyeLink reports pupil size in arbitrary units that depend on the tracking mode
configured on the Host PC. This package converts those units to millimetres using
a one-time per-eye calibration recorded against a printed black circle of known
diameter (an "artificial eye"). See the project README for the full step-by-step
workflow, and ``docs/FAQ How can I convert pupil size to mm?.md`` for the SR
Research FAQ this procedure is based on.
"""

from .core import (
    MM_FIELD,
    RAW_FIELD,
    VALID_MODES,
    augment_gaze_samples,
    load_calibration,
    units_to_mm,
)

__all__ = [
    "MM_FIELD",
    "RAW_FIELD",
    "VALID_MODES",
    "augment_gaze_samples",
    "load_calibration",
    "units_to_mm",
]
