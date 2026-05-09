"""Record an artificial eye to derive PUPIL_UNITS_PER_MM for the EyeLink 1000 Plus.

Procedure (per SR Research FAQ, thread-154 "How can I convert pupil size to mm?"):

  1. Mount the artificial eye on the head-rest at the same position a participant's
     eye would occupy. The camera distance must match the experimental rig
     (see camera_to_screen_distance below) — the calibration constant is only
     valid for that distance.

  2. Run this script. It enables pupil-only tracking at runtime via
     tracker.send_command(...), so no FINAL.INI editing or Host-PC reboot is
     needed; the settings revert automatically when the connection closes.
     During camera setup, press the "Pupil" button on the Host PC to switch
     from PUPIL-CR to PUPIL-only mode and lock onto the artificial eye, then
     exit the setup screen to start the timed recording.

  3. After recording: convert the EDF with syelink, then run
     compute_pupil_units_per_mm.py on the resulting JSON to derive
     PUPIL_UNITS_PER_MM.
"""

import pyelink as el

KNOWN_DIAMETER_MM = 7.0
RECORD_DURATION_S = 10.0

settings = el.Settings(
    backend="pyglet",
    fullscreen=True,
    # host_ip="dummy",  # uncomment to dry-run without a connected EyeLink
    display_index=0,
    enable_long_filenames=True,
    filename=f"pupil_calib_{KNOWN_DIAMETER_MM:.0f}mm",
    filepath="./data/",
    eye_tracked="BOTH",
    # Physical geometry (mm) — ASUS VG248 lab setup, 35 mm EyeLink lens.
    # Must match the rig the calibration constant will be applied to.
    screen_res=(1920, 1080),
    screen_width=531.36,
    screen_height=298.98,
    screen_distance_top_bottom=(905.0, 920.0),
    camera_to_screen_distance=925.0,
)

print("Connecting to EyeLink and creating window...")
tracker = el.EyeLink(settings, record_raw_data=True)

# Enable pupil-only tracking (no corneal reflection required). Runtime-only;
# reverts when the connection closes, so no FINAL.INI changes to clean up.
print("Configuring tracker for pupil-only mode...")
tracker.send_command("force_corneal_reflection = OFF")
tracker.send_command("allow_pupil_without_cr = ON")
tracker.send_command("elcl_hold_if_no_corneal = OFF")
tracker.send_command("elcl_search_if_no_corneal = OFF")
tracker.send_command("elcl_use_pcr_matching = OFF")

print("\n=== Camera setup ===")
print("On the Host PC, press the 'Pupil' button to switch from PUPIL-CR to")
print("PUPIL-only mode. Frame the artificial eye and confirm a stable pupil")
print("lock with no corneal reflection. Exit setup to start recording.")
tracker.camera_setup()

tracker.send_message("PUPIL_CALIB_START")
print(f"\n=== Recording artificial eye for {RECORD_DURATION_S:.0f} s ===")
tracker.start_recording()
tracker.wait(RECORD_DURATION_S)
tracker.stop_recording()
tracker.send_message("PUPIL_CALIB_END")

print("\n=== Recording complete ===")
tracker.end_experiment()
