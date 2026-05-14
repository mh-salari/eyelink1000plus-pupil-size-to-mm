---
title: "FAQ How can I convert pupil size to mm?"
source: "https://www.sr-research.com/support/printthread.php?tid=154"
author: SR-SUPPORT
published: 2020-09-03
created: 2026-05-14
description: SR Research FAQ on converting EyeLink pupil-size readings (arbitrary units) to millimetres via a one-time artificial-eye calibration.
tags:
  - clippings
---

**How can I convert pupil size to mm?** — [SR-SUPPORT](https://www.sr-research.com/support/user-5.html), 2020-09-03

For publication, some journals require pupil size data to be reported in millimetres (mm) to allow for comparisons across studies. EyeLink systems record pupil size in arbitrary units, which are based on the number of thresholded pixels that make up the pupil area in the EyeLink camera image. These units are influenced by factors like camera distance and the tracking threshold (which is automatically adjusted when operating in remote mode), not just the true size of the pupil. For these reasons, SR Research recommends against using Remote Mode for any research focused on pupil size as it may introduce confounds unrelated to actual physiological changes in pupil diameter.

The arbitrary units can be reliably converted to millimetres for head-fixed data by performing a one-time pupil-size calibration with an artificial eye or a printed black circle of a known diameter. If the camera distance is kept the same across participants, this calibration only needs to be performed once.

Video tutorial: [Converting Pupil Size Data into Millimeter](https://www.sr-research.com/support/thread-7304.html).

---

## How to calibrate pupil size with an artificial eye

1. Using a laser printer, print a black dot of a known size (e.g. 8 mm diameter) on a piece of paper. This will serve as your artificial eye.
2. Attach the paper to the head support so the dot is at the same distance from the camera as a participant's eye would be.
3. Configure the Host PC for pupil-only recording if necessary (see the next section).
4. Record a short EDF file of the eye tracker measuring the artificial eye. Either:
   - Run a short trial and quit after a few seconds of recording (in Experiment Builder, exit with `Ctrl+C` on Windows or `Cmd+C` on macOS).
   - Manually record on the Host PC via the "Output / Record" screen — start, record for a few seconds, stop.
5. Open the recorded EDF file in Data Viewer (or convert it to ASCII) and find the average pupil size reported by the tracker. The next calculation depends on whether the recording was in pupil-diameter or pupil-area mode.

### Pupil-diameter recordings

Simple linear ratio. If an 8 mm dot records as 1260 units and a participant's pupil records as 1000 units, the participant's pupil diameter is:

```
8 / 1260 = x / 1000
x = (8 * 1000) / 1260 = 6.35 mm
```

### Pupil-area recordings

Area scales as the square of the diameter, so take the square root before the linear conversion. If an 8 mm dot records as 7070 area units and a participant's pupil records as 6000 area units, the participant's pupil diameter is:

```
8 / sqrt(7070) = x / sqrt(6000)
x = (8 * sqrt(6000)) / sqrt(7070) = 7.37 mm
```

---

## Host PC settings for pupil-only calibration

To track a printed artificial eye (a black dot), you must temporarily enable Pupil-Only tracking on the Host PC. This lets the system track a "pupil" without requiring a corneal reflection.

**Important:** these changes are for calibration only. Back up `FINAL.INI` before editing, and remove these lines after the calibration is done to restore normal Pupil-CR tracking.

### EyeLink 1000, EyeLink 1000 Plus, EyeLink Portable Duo — exit the Host software

- **EyeLink 1000 Plus** / **EyeLink Portable Duo**: press `Ctrl+Alt+Q` to exit to the file manager.
- **EyeLink 1000**: reboot the Host PC to Windows and navigate to the EyeLink drive (typically `D:` or `E:`).

Navigate to the `/elcl/exe/` directory and open `FINAL.INI`.

### EyeLink 1000 and EyeLink 1000 Plus

Append to `FINAL.INI`:

```ini
##################################################
##
## force_corneal_reflection = <Value>
;; Hides "Pupil" mode button on Camera Setup screen
;; Pupil Only mode should only be used in EyeLink 1000 when the participant's head is completely fixed.
;; Default Value: OFF
force_corneal_reflection = OFF

## allow_pupil_without_cr = <switch>
;; Allows pupil without a CR nearby to be detected
;; in pupil search (after pupil loss or on startup).
;; This command is overridden in P-CR mode.
allow_pupil_without_cr = ON

## elcl_hold_if_no_corneal = <switch>
;; If true, eye window is frozen until both pupil and CR are present.
;; Default Value: OFF
elcl_hold_if_no_corneal = OFF

## elcl_search_if_no_corneal = <switch>
;; If corneal missing for long period, assumes false target and searches for pupil/CR candidate.
;; Default Value: OFF
elcl_search_if_no_corneal = OFF

## elcl_use_pcr_matching = <switch>
;; Selects enhanced pupil-CR matching during pupil identification.
;; If used, pupil and CR are selected as best matching pair.
;; This can be used even if CR is not being used for tracking.
;; Default Value: ON
elcl_use_pcr_matching = OFF

##################################################
```

### EyeLink Portable Duo

Append the same block, plus uncomment the `corneal_mode = OFF` line at the end:

```ini
##################################################
##
## force_corneal_reflection = <Value>
;; Hides "Pupil" mode button on Camera Setup screen
;; Pupil Only mode should only be used in EyeLink 1000 when the participant's head is completely fixed.
;; Default Value: OFF
force_corneal_reflection = OFF

## allow_pupil_without_cr = <switch>
;; Allows pupil without a CR nearby to be detected
;; in pupil search (after pupil loss or on startup).
;; This command is overridden in P-CR mode.
allow_pupil_without_cr = ON

## elcl_hold_if_no_corneal = <switch>
;; If true, eye window is frozen until both pupil and CR are present.
;; Default Value: OFF
elcl_hold_if_no_corneal = OFF

## elcl_search_if_no_corneal = <switch>
;; If corneal missing for long period, assumes false target and searches for pupil/CR candidate.
;; Default Value: OFF
elcl_search_if_no_corneal = OFF

## elcl_use_pcr_matching = <switch>
;; Selects enhanced pupil-CR matching during pupil identification.
;; If used, pupil and CR are selected as best matching pair.
;; This can be used even if CR is not being used for tracking.
;; Default Value: ON
elcl_use_pcr_matching = OFF

## Portable Duo users: uncomment the following line (remove the leading #)
corneal_mode = OFF

##################################################
```

Save the file, then restart the Host PC for the changes to take effect.
