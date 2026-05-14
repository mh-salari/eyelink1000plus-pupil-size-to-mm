"""CLI for the EyeLink 1000 Plus pupil-size → mm calibration.

Three subcommands:

  - ``record``   record one artificial-eye EDF (per side) on the EyeLink Host PC.
  - ``compute``  compute the per-eye unit-to-mm constant from a syelink JSON.
  - ``convert``  augment a recording JSON with per-sample ``<eye>_pupil_mm`` fields.

See the project README for the full step-by-step workflow.
"""

import argparse
from pathlib import Path


def _add_record_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "record",
        help="Record one artificial-eye EDF (per side) for unit-to-mm calibration.",
        description=__doc__,
    )
    p.add_argument("--eye", required=True, choices=("L", "R"), help="Which artificial eye is mounted.")
    p.add_argument(
        "--setup",
        type=Path,
        required=True,
        help="Path to the setup JSON. Run `export-setup <path>` first if you don't have one.",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./data"),
        help="Directory the EDF is written into (default: ./data).",
    )
    p.add_argument(
        "--known-mm",
        type=float,
        default=7.0,
        help="Known diameter of the printed dot, in mm (default: 7).",
    )
    p.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Recording duration in seconds (default: 10).",
    )
    p.add_argument(
        "--dummy",
        action="store_true",
        help="Dry-run without a connected EyeLink (uses pyelink's dummy host).",
    )
    p.set_defaults(handler=_handle_record)


def _handle_record(args: argparse.Namespace) -> None:
    # Lazy: importing .record drags in pyelink + pyglet; keep `compute` and `convert`
    # invocations cheap by only paying that cost when `record` actually runs.
    from .record import load_setup, record_artificial_eye  # noqa: PLC0415

    setup = load_setup(args.setup)
    record_artificial_eye(
        eye_flag=args.eye,
        output_dir=args.output_dir,
        setup=setup,
        known_mm=args.known_mm,
        duration_s=args.duration,
        dummy=args.dummy,
    )


def _add_export_setup_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "export-setup",
        help="Write an example setup JSON you can edit for your own monitor/camera geometry.",
    )
    p.add_argument(
        "output",
        type=Path,
        help="Where to write the example setup (e.g. ./setup.json).",
    )
    p.set_defaults(handler=_handle_export_setup)


def _handle_export_setup(args: argparse.Namespace) -> None:
    from .record import export_default_setup  # noqa: PLC0415  (same lazy rationale as record)

    export_default_setup(args.output)


def _add_compute_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "compute",
        help="Compute the per-eye unit-to-mm constant from an artificial-eye JSON.",
    )
    p.add_argument("--eye", required=True, choices=("left", "right"), help="Which eye this recording covers.")
    p.add_argument("--input", type=Path, required=True, help="Path to the syelink-converted JSON.")
    p.add_argument(
        "--output",
        type=Path,
        default=Path("./data/pupil_units_per_mm.json"),
        help="Calibration JSON to merge into (default: ./data/pupil_units_per_mm.json).",
    )
    p.add_argument(
        "--known-mm",
        type=float,
        default=7.0,
        help="Known diameter of the printed dot, in mm (default: 7).",
    )
    p.add_argument(
        "--mode",
        choices=("area", "diameter"),
        default="area",
        help="EyeLink pupil-size recording mode set on the Host PC (default: area).",
    )
    p.set_defaults(handler=_handle_compute)


def _handle_compute(args: argparse.Namespace) -> None:
    from .compute import compute_for_eye  # noqa: PLC0415  (defer until subcommand dispatch)

    compute_for_eye(
        input_json=args.input,
        eye_flag=args.eye,
        output_json=args.output,
        known_mm=args.known_mm,
        mode=args.mode,
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
        default=Path("./data/pupil_units_per_mm.json"),
        help="Calibration JSON produced by `compute` (default: ./data/pupil_units_per_mm.json).",
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
    from .convert import convert_recording  # noqa: PLC0415  (defer until subcommand dispatch)

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
