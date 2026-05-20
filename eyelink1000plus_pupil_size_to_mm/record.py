"""Record an artificial eye for the EyeLink 1000 Plus pupil-size calibration.

Records one eye at a time. All parameters come from the ``setup`` dict; see
``REQUIRED_SETUP_KEYS`` for the schema. ``export_default_setup()`` writes an
example JSON (also exposed via the ``export-setup`` CLI subcommand).
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

PACKAGE_NAME = "eyelink1000plus-pupil-size-to-mm"


def _tool_version() -> str:
    """Return the installed package version, or 'unknown' if not installed."""
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return "unknown"


EYE_OPTIONS = {"L": ("LEFT", "left"), "R": ("RIGHT", "right")}

# Runtime Host-PC commands to enable pupil-only tracking on the EyeLink 1000 /
# 1000 Plus. ``corneal_mode = NO`` is required on EL1000 Plus despite the FAQ
# listing it for Portable Duo only — without it the Host PC's Pupil button
# stays disabled.
PUPIL_ONLY_COMMANDS: tuple[str, ...] = (
    "force_corneal_reflection = OFF",
    "allow_pupil_without_cr = ON",
    "elcl_hold_if_no_corneal = OFF",
    "elcl_search_if_no_corneal = OFF",
    "elcl_use_pcr_matching = OFF",
    "corneal_mode = NO",
)

PUPIL_SIZE_MODES = ("AREA", "DIAMETER")
EL_CONFIGURATIONS = ("MTABLER", "BTABLER", "RTABLER", "RBTABLER", "AMTABLER", "ARTABLER", "BTOWER")

REQUIRED_SETUP_KEYS: tuple[str, ...] = (
    "output_dir",
    "screen_res",
    "screen_width_mm",
    "screen_height_mm",
    "screen_distance_top_mm",
    "screen_distance_bottom_mm",
    "camera_to_screen_distance_mm",
    "artificial_pupil_diameter_mm",
    "duration_s",
    "el_configuration",
    "camera_lens_focal_length_mm",
    "sampling_rate_hz",
    "pupil_size_mode",
)

# Example setup written by ``export-setup``. Users must replace every value
# with their own monitor, camera, and hardware config before recording.
DEFAULT_SETUP: dict[str, object] = {
    "_comment": (
        "Example setup for the ASUS VG248 lab with the 35 mm EyeLink 1000 Plus lens. "
        "Replace every value with your own monitor, camera, and hardware config before recording."
    ),
    "output_dir": "./data",
    "screen_res": [1920, 1080],
    "screen_width_mm": 531.36,
    "screen_height_mm": 298.98,
    "screen_distance_top_mm": 905.0,
    "screen_distance_bottom_mm": 920.0,
    "camera_to_screen_distance_mm": 925.0,
    "artificial_pupil_diameter_mm": 7.0,
    "duration_s": 10.0,
    "el_configuration": "MTABLER",
    "camera_lens_focal_length_mm": 35,
    "sampling_rate_hz": 1000,
    "pupil_size_mode": "AREA",
}


def export_default_setup(output_path: Path) -> None:
    """Write the example setup JSON to ``output_path``. Refuses to overwrite."""
    if output_path.exists():
        raise SystemExit(f"refusing to overwrite existing {output_path}.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(DEFAULT_SETUP, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote example setup to {output_path}")
    print("Edit it to match your monitor, camera, and hardware config before recording.")


def load_setup(path: Path) -> dict[str, object]:
    """Read a setup JSON and verify every required key is present."""
    if not path.exists():
        raise SystemExit(
            f"setup file not found: {path}.\n"
            f"Run `eyelink1000plus-pupil-size-to-mm export-setup {path}` to generate an example, "
            f"then edit it for your setup.",
        )
    cfg = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_SETUP_KEYS if k not in cfg]
    if missing:
        raise SystemExit(f"setup file {path} is missing required keys: {missing}")
    return cfg


def _validate_setup(setup: dict[str, object]) -> None:
    missing = [k for k in REQUIRED_SETUP_KEYS if k not in setup]
    if missing:
        raise SystemExit(f"setup is missing required keys: {missing}")
    mode = str(setup["pupil_size_mode"]).upper()
    if mode not in PUPIL_SIZE_MODES:
        raise SystemExit(f"pupil_size_mode {mode!r} not in {PUPIL_SIZE_MODES}")
    config = str(setup["el_configuration"]).upper()
    if config not in EL_CONFIGURATIONS:
        raise SystemExit(f"el_configuration {config!r} not in {EL_CONFIGURATIONS}")


def record_artificial_eye(
    eye_flag: str,
    setup: dict[str, object],
    *,
    dummy: bool = False,
    filename: str | None = None,
    extra_commands: Sequence[str] = (),
) -> Path:
    """Record one artificial-eye EDF for the named side.

    ``setup`` must contain every key in ``REQUIRED_SETUP_KEYS``. ``filename`` is
    auto-derived from ``artificial_pupil_diameter_mm`` and the side if not
    given; pyelink prompts the operator (replace/rename) if the EDF already
    exists. ``extra_commands`` are sent to the Host PC after the pupil-only
    commands and the pupil-size-mode command, before Camera Setup — use this
    for lab-specific overrides such as ``remote_camera_position``.

    Returns the path to the recorded EDF.
    """
    # Deferred: pyelink pulls in pyglet/display backend; keeps `compute` and
    # `convert` import-cheap.
    import pyelink as el  # noqa: PLC0415

    if eye_flag not in EYE_OPTIONS:
        raise SystemExit(f"invalid eye {eye_flag!r}; choose L or R")
    _validate_setup(setup)

    eye_tracked, eye_tag = EYE_OPTIONS[eye_flag]
    diameter_mm = float(setup["artificial_pupil_diameter_mm"])
    duration_s = float(setup["duration_s"])
    pupil_size_mode = str(setup["pupil_size_mode"]).upper()
    el_configuration = str(setup["el_configuration"]).upper()

    if filename is None:
        filename = f"pupil_calib_{diameter_mm:.0f}mm_{eye_tag}"

    output_dir = Path(setup["output_dir"]).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Recording artificial {eye_tag} eye → {output_dir / (filename + '.edf')}")

    settings_kwargs: dict[str, object] = {
        "backend": "pyglet",
        "fullscreen": True,
        "display_index": 0,
        "enable_long_filenames": True,
        "filename": filename,
        "filepath": str(output_dir),
        "eye_tracked": eye_tracked,
        "screen_res": tuple(setup["screen_res"]),
        "screen_width": setup["screen_width_mm"],
        "screen_height": setup["screen_height_mm"],
        "screen_distance_top_bottom": (
            setup["screen_distance_top_mm"],
            setup["screen_distance_bottom_mm"],
        ),
        "camera_to_screen_distance": setup["camera_to_screen_distance_mm"],
        "el_configuration": el_configuration,
        "camera_lens_focal_length": int(setup["camera_lens_focal_length_mm"]),
        "sample_rate": int(setup["sampling_rate_hz"]),
    }
    if dummy:
        settings_kwargs["host_ip"] = "dummy"

    settings = el.Settings(**settings_kwargs)

    print("Connecting to EyeLink and creating window...")
    tracker = el.EyeLink(settings, record_raw_data=True)

    print("Configuring tracker for pupil-only mode...")
    for cmd in PUPIL_ONLY_COMMANDS:
        tracker.send_command(cmd)

    print(f"Setting pupil-size recording mode: {pupil_size_mode}")
    tracker.send_command(f"pupil_size_diameter = {pupil_size_mode}")

    for cmd in extra_commands:
        print(f"  extra: {cmd}")
        tracker.send_command(cmd)

    print("\n=== Camera setup ===")
    print("Frame the artificial eye, set the pupil threshold, and exit setup to start recording.")
    tracker.camera_setup()

    tracker.send_message("PUPIL_CALIB_START")
    print(f"\n=== Recording artificial eye for {duration_s:.0f} s ===")
    tracker.start_recording()
    tracker.wait(duration_s)
    tracker.stop_recording()
    tracker.send_message("PUPIL_CALIB_END")

    print("\n=== Recording complete ===")
    tracker.end_experiment()

    sidecar_path = output_dir / f"{filename}.setup.json"
    sidecar = {
        "eye_flag": eye_flag,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool_version": _tool_version(),
        "filename": filename,
        "setup": setup,
    }
    sidecar_path.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote setup sidecar: {sidecar_path}")

    return output_dir / f"{filename}.edf"
