"""Record an artificial eye for the EyeLink 1000 Plus pupil-size calibration.

Records one eye at a time. Pupil-only tracking is enabled at runtime via
``tracker.send_command(...)``, so no FINAL.INI editing or Host-PC reboot is needed.

Physical setup geometry (screen resolution, screen size in mm, eye-to-screen distance,
camera-to-screen distance) is read from a JSON file. See ``export_default_setup()``
for the schema; the CLI ``export-setup`` subcommand writes an example you can edit
for your own setup.
"""

import json
from pathlib import Path

EYE_OPTIONS = {"L": ("LEFT", "left"), "R": ("RIGHT", "right")}
DEFAULT_KNOWN_DIAMETER_MM = 7.0
DEFAULT_RECORD_DURATION_S = 10.0

# Example setup (ASUS VG248 lab with the 35 mm EyeLink lens). This is NOT a universal
# default — every lab's monitor and camera-to-screen geometry differ. Use the
# ``export-setup`` CLI subcommand to write this out and edit it for your own setup.
DEFAULT_SETUP: dict[str, object] = {
    "_comment": (
        "Example setup for the ASUS VG248 lab with the 35 mm EyeLink 1000 Plus lens. "
        "Replace every value with the geometry of your own setup before recording."
    ),
    "screen_res": [1920, 1080],
    "screen_width_mm": 531.36,
    "screen_height_mm": 298.98,
    "screen_distance_top_mm": 905.0,
    "screen_distance_bottom_mm": 920.0,
    "camera_to_screen_distance_mm": 925.0,
}

REQUIRED_SETUP_KEYS = (
    "screen_res",
    "screen_width_mm",
    "screen_height_mm",
    "screen_distance_top_mm",
    "screen_distance_bottom_mm",
    "camera_to_screen_distance_mm",
)


def export_default_setup(output_path: Path) -> None:
    """Write the example setup JSON to ``output_path``. Refuses to overwrite."""
    if output_path.exists():
        raise SystemExit(f"refusing to overwrite existing {output_path}.")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(DEFAULT_SETUP, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote example setup to {output_path}")
    print("Edit it to match your monitor and camera-to-screen geometry before recording.")


def load_setup(path: Path) -> dict[str, object]:
    """Read and validate a setup JSON."""
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


def record_artificial_eye(
    eye_flag: str,
    output_dir: Path,
    setup: dict[str, object],
    known_mm: float = DEFAULT_KNOWN_DIAMETER_MM,
    duration_s: float = DEFAULT_RECORD_DURATION_S,
    *,
    dummy: bool = False,
) -> Path:
    """Record one artificial-eye EDF for the named side.

    Writes ``pupil_calib_<known_mm>mm_<eye>.edf`` (and friends) into ``output_dir``.
    The Host PC's pupil-size recording mode (area vs diameter) must match the mode
    used for participant recordings; this function does not configure it.
    Returns the path to the recorded EDF.
    """
    # Lazy import: pyelink pulls in pyglet + an X / display backend. Loading it only
    # when ``record`` actually runs keeps ``compute`` / ``convert`` import-cheap.
    import pyelink as el  # noqa: PLC0415

    if eye_flag not in EYE_OPTIONS:
        raise SystemExit(f"invalid eye {eye_flag!r}; choose L or R")
    eye_tracked, eye_tag = EYE_OPTIONS[eye_flag]
    filename = f"pupil_calib_{known_mm:.0f}mm_{eye_tag}"

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Recording artificial {eye_tag} eye → {output_dir / (filename + '.edf')}")

    settings = el.Settings(
        backend="pyglet",
        fullscreen=True,
        host_ip="dummy" if dummy else None,
        display_index=0,
        enable_long_filenames=True,
        filename=filename,
        filepath=str(output_dir),
        eye_tracked=eye_tracked,
        screen_res=tuple(setup["screen_res"]),
        screen_width=setup["screen_width_mm"],
        screen_height=setup["screen_height_mm"],
        screen_distance_top_bottom=(
            setup["screen_distance_top_mm"],
            setup["screen_distance_bottom_mm"],
        ),
        camera_to_screen_distance=setup["camera_to_screen_distance_mm"],
    )

    print("Connecting to EyeLink and creating window...")
    tracker = el.EyeLink(settings, record_raw_data=True)

    print("Configuring tracker for pupil-only mode...")
    tracker.send_command("force_corneal_reflection = OFF")
    tracker.send_command("allow_pupil_without_cr = ON")
    tracker.send_command("elcl_hold_if_no_corneal = OFF")
    tracker.send_command("elcl_search_if_no_corneal = OFF")
    tracker.send_command("elcl_use_pcr_matching = OFF")

    print("\n=== Camera setup ===")
    print("On the Host PC, select the 'Pupil' button to switch from PUPIL-CR to")
    print("PUPIL-only mode. Frame the artificial eye and confirm a stable pupil")
    print("lock with no corneal reflection. Exit setup to start recording.")
    tracker.camera_setup()

    tracker.send_message("PUPIL_CALIB_START")
    print(f"\n=== Recording artificial eye for {duration_s:.0f} s ===")
    tracker.start_recording()
    tracker.wait(duration_s)
    tracker.stop_recording()
    tracker.send_message("PUPIL_CALIB_END")

    print("\n=== Recording complete ===")
    tracker.end_experiment()
    return output_dir / f"{filename}.edf"
