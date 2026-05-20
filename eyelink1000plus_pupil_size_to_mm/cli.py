"""CLI for the EyeLink 1000 Plus pupil-size → mm calibration.

Subcommands:

  - ``record``        record one artificial-eye EDF (per side) on the EyeLink Host PC.
  - ``export-setup``  write an example setup JSON you can edit for your lab.
  - ``compute``       compute the per-eye unit-to-mm constant from a syelink JSON.
  - ``convert``       augment a recording JSON with per-sample ``<eye>_pupil_mm`` fields.

``record`` accepts the setup either as a JSON file (``--setup file.json``) or
as individual CLI flags (``--screen-res ...``, ``--artificial-pupil-diameter-mm
...``, etc.); the two paths are mutually exclusive. See the project README for
the full step-by-step workflow.
"""

import argparse
from pathlib import Path

# Flag-name ↔ setup-key mapping for the one-liner CLI path. ``dest`` matches the
# setup-dict key, so the handler can read flag values back via ``getattr(args, key)``.
_SETUP_FLAGS: tuple[tuple[str, dict], ...] = (
    ("output_dir", {"type": Path, "help": "Directory the EDF is written into."}),
    (
        "screen_res",
        {
            "type": int,
            "nargs": 2,
            "metavar": ("WIDTH", "HEIGHT"),
            "help": "Display resolution in pixels.",
        },
    ),
    ("screen_width_mm", {"type": float, "help": "Display width in mm."}),
    ("screen_height_mm", {"type": float, "help": "Display height in mm."}),
    (
        "screen_distance_top_mm",
        {"type": float, "help": "Eye-to-top-of-screen distance in mm."},
    ),
    (
        "screen_distance_bottom_mm",
        {"type": float, "help": "Eye-to-bottom-of-screen distance in mm."},
    ),
    (
        "camera_to_screen_distance_mm",
        {"type": float, "help": "EyeLink camera-to-screen distance in mm."},
    ),
    (
        "artificial_pupil_diameter_mm",
        {"type": float, "help": "Diameter of the artificial pupil (printed dot) in mm."},
    ),
    ("duration_s", {"type": float, "help": "Recording duration in seconds."}),
    (
        "el_configuration",
        {
            "choices": ("MTABLER", "BTABLER", "RTABLER", "RBTABLER", "AMTABLER", "ARTABLER", "BTOWER"),
            "help": "EyeLink physical configuration.",
        },
    ),
    (
        "camera_lens_focal_length_mm",
        {"type": int, "help": "EyeLink camera lens focal length in mm (typically 25, 35, or 50)."},
    ),
    (
        "sampling_rate_hz",
        {"type": int, "choices": (250, 500, 1000, 2000), "help": "EyeLink sampling rate in Hz."},
    ),
    (
        "pupil_size_mode",
        {"choices": ("AREA", "DIAMETER"), "help": "Pupil-size recording mode (must match participant recordings)."},
    ),
)


def _add_record_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "record",
        help="Record one artificial-eye EDF (per side) for unit-to-mm calibration.",
        description=__doc__,
    )
    p.add_argument("--side", required=True, choices=("L", "R"), help="Which artificial-eye position is mounted.")
    p.add_argument(
        "--setup",
        type=Path,
        default=None,
        help="Path to a setup JSON. Mutually exclusive with the individual --... flags below.",
    )
    p.add_argument(
        "--dummy",
        action="store_true",
        help="Dry-run without a connected EyeLink (uses pyelink's dummy host).",
    )
    p.add_argument(
        "--filename",
        default=None,
        help="Override the output EDF stem (default: pupil_calib_<diameter>mm_<side>).",
    )
    for flag, kwargs in _SETUP_FLAGS:
        p.add_argument(f"--{flag.replace('_', '-')}", dest=flag, default=None, **kwargs)
    p.set_defaults(handler=_handle_record)


def _build_setup_from_flags(args: argparse.Namespace) -> dict[str, object]:
    return {flag: getattr(args, flag) for flag, _ in _SETUP_FLAGS}


def _handle_record(args: argparse.Namespace) -> None:
    # Deferred: importing .record drags in pyelink + pyglet; keep `compute`
    # and `convert` import-cheap.
    from .record import load_setup, record_artificial_eye  # noqa: PLC0415

    flag_values = {flag: getattr(args, flag) for flag, _ in _SETUP_FLAGS}
    flags_given = [flag for flag, v in flag_values.items() if v is not None]

    if args.setup is not None and flags_given:
        raise SystemExit(
            f"--setup is mutually exclusive with individual setup flags; got --setup and also {sorted(flags_given)}.",
        )
    if args.setup is None:
        missing = [flag for flag, v in flag_values.items() if v is None]
        if missing:
            raise SystemExit(
                f"either pass --setup <json> or all individual flags. Missing: {sorted(missing)}",
            )
        setup: dict[str, object] = _build_setup_from_flags(args)
    else:
        setup = load_setup(args.setup)

    record_artificial_eye(
        eye_flag=args.side,
        setup=setup,
        dummy=args.dummy,
        filename=args.filename,
    )


def _add_export_setup_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "export-setup",
        help="Write an example setup JSON you can edit for your own monitor/camera/hardware config.",
    )
    p.add_argument(
        "output",
        type=Path,
        help="Where to write the example setup (e.g. ./setup.json).",
    )
    p.set_defaults(handler=_handle_export_setup)


def _handle_export_setup(args: argparse.Namespace) -> None:
    from .record import export_default_setup  # noqa: PLC0415

    export_default_setup(args.output)


def _add_compute_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "compute",
        help="Compute the per-eye unit-to-mm constant from an artificial-eye JSON.",
    )
    p.add_argument("--eye", required=True, choices=("left", "right"), help="Which eye this recording covers.")
    p.add_argument("--input", type=Path, required=True, help="Path to the syelink-converted JSON.")
    p.add_argument("--output", type=Path, required=True, help="Calibration JSON to merge into.")
    p.add_argument(
        "--setup-json",
        type=Path,
        default=None,
        help="Setup sidecar written by `record`. Mutually exclusive with --known-mm and --mode.",
    )
    p.add_argument(
        "--known-mm",
        type=float,
        default=None,
        help="Known diameter of the printed dot, in mm. Required if --setup-json is not given.",
    )
    p.add_argument(
        "--mode",
        choices=("area", "diameter"),
        default=None,
        help="EyeLink pupil-size recording mode used on the Host PC. Required if --setup-json is not given.",
    )
    p.set_defaults(handler=_handle_compute)


def _handle_compute(args: argparse.Namespace) -> None:
    from .compute import compute_for_eye  # noqa: PLC0415

    if args.setup_json is not None and (args.known_mm is not None or args.mode is not None):
        raise SystemExit("--setup-json is mutually exclusive with --known-mm and --mode")
    if args.setup_json is None and (args.known_mm is None or args.mode is None):
        raise SystemExit("provide either --setup-json, or both --known-mm and --mode")

    compute_for_eye(
        input_json=args.input,
        eye_flag=args.eye,
        output_json=args.output,
        known_mm=args.known_mm,
        mode=args.mode,
        setup_json=args.setup_json,
    )


def _add_convert_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "convert",
        help="Add per-sample <eye>_pupil_mm to a recording JSON.",
    )
    p.add_argument("--input", type=Path, required=True, help="Path to the recording JSON.")
    p.add_argument(
        "--calibration",
        type=Path,
        required=True,
        help="Calibration JSON produced by `compute`.",
    )
    p.add_argument(
        "--eyes",
        nargs="+",
        choices=("left_eye", "right_eye"),
        default=None,
        help="Which eyes to convert; default auto-detects from sample data.",
    )
    p.set_defaults(handler=_handle_convert)


def _handle_convert(args: argparse.Namespace) -> None:
    from .convert import convert_recording  # noqa: PLC0415

    convert_recording(
        input_json=args.input,
        calibration_json=args.calibration,
        eyes=args.eyes,
    )


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``eyelink1000plus-pupil-size-to-mm`` CLI."""
    parser = argparse.ArgumentParser(
        prog="eyelink1000plus-pupil-size-to-mm",
        description="EyeLink 1000 Plus pupil-size calibration (arbitrary units → mm).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    _add_record_parser(sub)
    _add_compute_parser(sub)
    _add_convert_parser(sub)
    _add_export_setup_parser(sub)

    args = parser.parse_args(argv)
    args.handler(args)
