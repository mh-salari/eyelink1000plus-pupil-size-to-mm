# eyelink1000plus-pupil-size-to-mm

[![PyPI version](https://img.shields.io/pypi/v/eyelink1000plus-pupil-size-to-mm)](https://pypi.org/project/eyelink1000plus-pupil-size-to-mm/)
[![Downloads](https://static.pepy.tech/badge/eyelink1000plus-pupil-size-to-mm)](https://pepy.tech/project/eyelink1000plus-pupil-size-to-mm)
[![License](https://img.shields.io/pypi/l/eyelink1000plus-pupil-size-to-mm)](https://github.com/mh-salari/eyelink1000plus-pupil-size-to-mm/blob/main/LICENSE)
<!-- TODO: enable Zenodo-GitHub integration and add the DOI badge after the first GitHub release tag. -->

Convert EyeLink 1000 Plus pupil-size readings (arbitrary units) into millimetres.

The EyeLink 1000 Plus records pupil size in arbitrary units whose scale depends on the camera distance and the tracking threshold the Host PC chose for that recording. To report pupil size in physical units, you record a printed circle of known diameter (an *artificial eye*) at the camera-to-eye distance your participants will sit at, derive a per-eye unit-to-mm constant from that recording, and apply the constant to every participant recording made with the same physical setup. The procedure follows SR Research's [FAQ How can I convert pupil size to mm?](docs/FAQ%20How%20can%20I%20convert%20pupil%20size%20to%20mm%3F.md) (a copy is shipped under `docs/`).

Two conversion formulas are supported, matching the Host PC's `pupil_size_diameter` setting at recording time:

| Host PC mode                | Formula                            |
|-----------------------------|------------------------------------|
| `pupil_size_diameter = NO`  | `mm = sqrt(units) / constant`      |
| `pupil_size_diameter = YES` | `mm = units / constant`            |

The Host PC mode used for the artificial-eye recording must match the mode used for participant recordings. Mismatching modes silently under-reads small pupils.

---

## Installation

From PyPI:

```bash
pip install eyelink1000plus-pupil-size-to-mm
```

With uv:

```bash
uv add eyelink1000plus-pupil-size-to-mm
```

For a local checkout, install editable:

```bash
pip install -e .
# or
uv add --editable .
```

The `record` subcommand drives an EyeLink 1000 Plus through SR Research's `pylink` C bindings, which are not on PyPI. Install them separately:

```bash
uv pip install --extra-index-url https://pypi.sr-support.com sr-research-pylink
```

You also need the **EyeLink Developers Kit** (native C libraries) from <https://www.sr-research.com/support/thread-13.html>.

After install, the `eyelink1000plus-pupil-size-to-mm` command is available on your `PATH`. The `record` subcommand requires a connected EyeLink Host PC; `compute`, `convert`, and `export-setup` are pure post-processing and have no EyeLink-side dependencies.

---

## Step-by-step workflow

### 0. Prepare the artificial eye

Print a black filled circle of known diameter on plain paper with a laser printer. SR Research's FAQ uses 7–8 mm; the CLI defaults to 7 mm. Measure the printed dot with calipers to confirm the actual diameter — laser-printer rendering can be a few percent off, and the unit-to-mm constant inherits that error linearly.

Mount the paper on the head-rest at the same camera-to-eye distance you use for participants. Mount it at the lateral position of the eye you are calibrating (the constant is per-eye).

### 1. Describe your physical setup

Generate a one-time `setup.json` describing your monitor and camera-to-screen geometry:

```bash
eyelink1000plus-pupil-size-to-mm export-setup ./setup.json
```

Open `setup.json` and replace every value with your own:

```json
{
  "_comment": "Example setup ... Replace every value with the geometry of your own setup before recording.",
  "screen_res": [1920, 1080],
  "screen_width_mm": 531.36,
  "screen_height_mm": 298.98,
  "screen_distance_top_mm": 905.0,
  "screen_distance_bottom_mm": 920.0,
  "camera_to_screen_distance_mm": 925.0
}
```

`export-setup` refuses to overwrite an existing file, so editing `setup.json` after generating it is safe.

### 2. Record the artificial eye (left, then right)

Pupil-only tracking is enabled at the start of the recording via runtime commands, so **no `FINAL.INI` edits or Host-PC reboots are needed** — the settings revert when the connection closes.

```bash
eyelink1000plus-pupil-size-to-mm record \
    --eye L \
    --setup ./setup.json \
    --output-dir ./data \
    --known-mm 7 \
    --duration 10
```

On the Host PC's camera-setup screen, select the **Pupil** button to switch from PUPIL-CR to PUPIL-only mode. Frame the artificial eye and confirm a stable pupil lock with no corneal reflection, then exit setup to start the timed recording.

Repeat for the right eye:

```bash
eyelink1000plus-pupil-size-to-mm record --eye R --setup ./setup.json --output-dir ./data
```

Two EDFs are produced: `data/pupil_calib_7mm_left.edf` and `data/pupil_calib_7mm_right.edf`.

### 3. Convert each EDF to JSON

[`syelink`](https://github.com/mh-salari/syelink) parses SR Research ASCII files into JSON:

```bash
syelink convert ./data/pupil_calib_7mm_left.edf  --json
syelink convert ./data/pupil_calib_7mm_right.edf --json
```

Any tool that produces a JSON with a `gaze_samples` list containing per-sample `left_pupil` / `right_pupil` fields will work — see the JSON schema notes below.

### 4. Compute the per-eye unit-to-mm constant

Run `compute` once per eye. Both runs merge into the same `pupil_units_per_mm.json` without overwriting each other:

```bash
eyelink1000plus-pupil-size-to-mm compute \
    --eye left \
    --mode area \
    --known-mm 7 \
    --input  ./data/pupil_calib_7mm_left.json \
    --output ./data/pupil_units_per_mm.json

eyelink1000plus-pupil-size-to-mm compute \
    --eye right \
    --mode area \
    --known-mm 7 \
    --input  ./data/pupil_calib_7mm_right.json \
    --output ./data/pupil_units_per_mm.json
```

`--mode` must match the Host PC's `pupil_size_diameter` setting at recording time (`area` for the EyeLink default; `diameter` if the Host PC has `pupil_size_diameter = YES`). If the two `compute` runs disagree on `--mode`, the second run fails fast.

### 5. Apply the calibration to a participant recording

```bash
eyelink1000plus-pupil-size-to-mm convert \
    --input ./data/some_recording.json \
    --calibration ./data/pupil_units_per_mm.json
```

`convert` adds `left_pupil_mm` and `right_pupil_mm` to every sample (in place) for whichever eyes have raw pupil data. To restrict to a subset, pass `--eyes left_eye right_eye` (the default auto-detects from the sample data).

The same `pupil_units_per_mm.json` is reused for every recording made with the same physical setup; you only re-derive it if the camera-to-eye distance or the Host PC's `pupil_size_diameter` setting changes.

---

## CLI reference

```text
eyelink1000plus-pupil-size-to-mm export-setup OUTPUT
eyelink1000plus-pupil-size-to-mm record       --eye {L,R} --setup PATH [--output-dir DIR] [--known-mm MM] [--duration S] [--dummy]
eyelink1000plus-pupil-size-to-mm compute      --eye {left,right} --input JSON [--output JSON] [--known-mm MM] [--mode {area,diameter}]
eyelink1000plus-pupil-size-to-mm convert      --input JSON [--calibration JSON] [--eyes left_eye right_eye]
```

Each subcommand supports `--help` for the full option listing.

---

## Library API

For programmatic use, the three pure functions are re-exported from the package root:

```python
from pathlib import Path

from eyelink1000plus_pupil_size_to_mm import (
    augment_gaze_samples,
    load_calibration,
    units_to_mm,
)

mode, constants = load_calibration(
    Path("pupil_units_per_mm.json"),
    eyes=["left_eye", "right_eye"],
)

# One value:
mm = units_to_mm(value=1234.0, mode=mode, constant=constants["left_eye"])

# A whole sample list, in place; returns the count of samples that got a non-None mm value:
n = augment_gaze_samples(samples, eyes=["left_eye", "right_eye"], mode=mode, constants=constants)
```

The CLI subcommands are thin wrappers around three callables that mirror them: `eyelink1000plus_pupil_size_to_mm.record.record_artificial_eye`, `…compute.compute_for_eye`, and `…convert.convert_recording`.

---

## Input/output JSON schema

`compute` and `convert` operate on JSON files with this minimal shape (additional fields are passed through untouched):

```json
{
  "gaze_samples": [
    {
      "left_pupil":  1234.0,
      "right_pupil": 1187.0
    }
  ]
}
```

`convert` augments each sample with `left_pupil_mm` and/or `right_pupil_mm`, in place. The output is written back to the same file. Re-running `convert` on an already-augmented JSON simply recomputes the mm values from the original `*_pupil` fields and is safe.

The calibration JSON written by `compute` has this shape:

```json
{
  "mode": "area",
  "left_eye": {
    "constant": 11.2949,
    "calibration_file": "...",
    "known_diameter_mm": 7.0,
    "n_samples": 8123,
    "mean_units": 6256.4,
    "sd_units": 88.1
  },
  "right_eye": { "constant": 11.6730, "...": "..." }
}
```

---

## Reference

SR Research's procedural FAQ this tool implements is shipped under [`docs/`](docs/) for offline reference. The original is at <https://www.sr-research.com/support/printthread.php?tid=154>.

---

## Acknowledgments

This project has received funding from the European Union's Horizon Europe research and innovation funding program under grant agreement No 101072410, Eyes4ICU project.

<p align="center">
<img src="https://raw.githubusercontent.com/mh-salari/eyelink1000plus-pupil-size-to-mm/main/resources/Funded_by_EU_Eyes4ICU.png" alt="Funded by EU Eyes4ICU" width="500">
</p>
