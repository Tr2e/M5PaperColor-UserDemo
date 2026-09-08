# Calibration-chart regression fix — 2026-09-08

Based on the user's accepted, restored photo-balanced version on
`feat/papercolor-os`. No driver waveform, display transport, page navigation,
photo storage, upload composition, or UI-nearest LUT changes.

## Reproduced faults

- H5 preview used a different palette/dither from the firmware and replaced
  white with `#eef1f4`. Both upload actions already sent the original composition,
  not that preview. The overlay now renders the upload source, with an explicit
  note that physical screen colors differ. It is not a calibrated panel simulator.
- The firmware admitted colored pigments for mid/dark neutral input. The neutral
  guard now covers all brightness levels and RGB565 channel-rounding differences.
- Clipping adjusted RGB before computing diffusion residuals destroyed the error
  needed to mix saturated colors. Simply removing clipping caused unreachable
  targets to accumulate error. The existing diffuser now projects each target
  onto the allowed nominal-pigment convex hull, retains signed Q4 residuals, and
  uses direct nearest lookup outside the LUT's domain. A wide safety bound prevents
  overflow. A 32-entry cache adds 384 bytes to the state; row workspace is unchanged.
- Existing accepted source compensation is preserved, not expanded. No new
  hand-tuned per-color compensation or claimed factory calibration was added.

## Evidence

Uniform 400 × 128 RGB565-expanded patches, photo-balanced; counts rounded to
percentages of native codes, **not physical color measurements**:

| Input | Before | After |
| --- | --- | --- |
| Magenta `255,0,255` | 100% blue | 58.3% blue, 23.0% red, 18.7% white |
| Cyan `0,255,255` | 100% blue | 44.0% blue, 25.1% green, 30.9% white |
| Gray `96,96,96` | Mostly colored pigments | Black/white only |
| Gray `160,160,160` | Mostly colored pigments | Black/white only |

## Verification

- `bash tools/color_lab/run_host_tests.sh`: passed, including nominal pigment
  identity, hue masks, repeatability, RGB565 equivalence, all 256 source grays,
  saturated magenta/cyan, long-run residual bounds and recovery to gray in both
  Floyd–Steinberg and Burkes modes.
- AddressSanitizer + UndefinedBehaviorSanitizer: passed.
- `node tools/color_lab/test_preview_source.mjs`: passed, including HTML script
  syntax, source-pixel preservation, white, both selected modes, empty composition,
  and both upload routes retaining `exportToCanvas()`.
- Local browser + mock device API: loaded the 400 × 600 chart, checked desktop and
  393-pixel mobile layout, zoom (1 → 1.15), rotation (0 → 90°), reset, and mode menu.
  This did not exercise the real device's HTTP upload endpoint or iOS captive UI.
- ESP-IDF experimental-LUT build: passed. Binary SHA-256:
  `00f59bbe600c4ac9631a5b8e97dcf467058aa2792b9e45296d0012fecb86026c`.

## Pending hardware acceptance

After the user connected the device in download mode, app-only flashing completed
at `0x10000` (3,228,512 bytes), with the device data hash verified. Storage and
configuration partitions were not flashed. After the user's physical Reset, USB
enumerated as PaperColor (`303A:4002`). The runtime returned one `home_full`
record: render success, total 17.010862 s, panel stage 16.402837 s; the pipeline
was `ui`, preparation 0.243810 s, workspace 0. These are homepage timings, not
photo-balanced timings or independent visual confirmation of the panel update.
No photo record was present yet. Reopen the H5 page and display the same
calibration PNG in Dither mode.
Compare under the same lighting, especially magenta/cyan and the gray ramp; read
USB timing metrics again. Geometry changes can increase processing time; the old
0.89-second result is **not** a measurement of this build. Physical gamut and
nominal palette mismatch remain limitations; passing code tests is not proof of
absolute color accuracy. No commit or push was performed.

## Second physical review — IMG_9910.HEIC

The user's photo shows the calibration chart on the running repair build.
Compared with IMG_9908, magenta/cyan no longer appear as identical solid blue
patches, and the mid-gray patches no longer contain the earlier green/yellow
pigment mixture. This supports the specific regression fixes, not an absolute
color-calibration claim: magenta still appears blue-purple rather than vivid
magenta, cyan and lime remain muted, and the physical black appears purplish.
Camera white balance, lighting, nominal pigment values, and screen gamut prevent
assigning a calibrated color error from this photo alone.

### Pure-red white speckles: reproduced and explained

The chart's source patch 07 is exactly (255,0,0). A uniform 400 × 128 patch run
through the current RGB565-expanded photo-balanced path produces 49,751 red and
1,449 white codes: **2.8301% white**. Patch 04's nominal (191,0,0), by contrast,
produces 50,776 red and 424 black codes after RGB565 expansion (no white).
These are offline code counts, not a measured white-pixel fraction in the photo.

The code's nominal red vertex is R=(191,0,0), white W=(255,255,255). In the current
RGB-distance projection, pure source red P=(255,0,0) is outside the gamut. The
closest point on R–W is R+t(W–R), where
`t=4096/(4096+65025+65025)=0.0305339`.
It is approximately **(192.954,7.786,7.786)**, not (191,0,0). Thus the target itself
asks for white before error diffusion. Q4 rounding, LUT selection and diffusion
edge losses account for the finite-patch fraction differing slightly from t.
The repeated white pattern visible in patch 07 agrees with this mechanism; it is
not evidence of bad pixels or a second H5 quantization pass.

This is a limitation of the current nearest-RGB gamut policy: it trades a little
saturation for a tiny numeric-distance improvement. A solid-red target would
remove the white but would map bright source red to the darker nominal red.
Do not erase white codes globally: white is required for grays, pale colors and
many mixed colors, and post-quantization replacement breaks the error budget.
Any next candidate should change target mapping before diffusion, compare a
saturation-preserving policy against this accepted baseline, and retain magenta,
cyan, pale-red, gray and boundary tests. No new per-color coefficients are justified
by this uncalibrated photograph. Production code/firmware was not changed in this
review; retain the currently improved result while this tradeoff is evaluated.

### Runtime evidence after chart display

Two local-photo records returned render success:

| Record | Total | Image decode/render | Refresh call (`panel_us`) |
| --- | --- | --- | --- |
| First | 17.622453 s | 0.475245 s | 17.147186 s |
| Latest | 17.659355 s | 0.491809 s | 17.167524 s |

The latest pipeline is photo-balanced: preparation **1.009798 s**, row workspace
14,496 bytes. Important timing correction: `panel_us` spans the entire
`papercolor_push_canvas()` call, **including preparation**, not just the panel BUSY
wait. Do not add preparation to it. Subtracting preparation leaves about 16.158 s
for the remainder of the refresh call, not a separately measured waveform time.
The previous 0.894168 s preparation result is not a controlled same-image A/B
benchmark; use the same chart and conditions for future performance comparisons.
