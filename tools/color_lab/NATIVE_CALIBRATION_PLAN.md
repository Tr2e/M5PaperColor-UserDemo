# Native-pigment calibration / white-budget experiment

## Baseline and scope

Keep the accepted IMG_9910 photo pipeline unchanged. Its previously flashed
binary remains `/private/tmp/papercolor-lut-build/paper_color.bin`, SHA-256
`00f59bbe600c4ac9631a5b8e97dcf467058aa2792b9e45296d0012fecb86026c`.
Do not rebuild that directory if an exact binary rollback is needed.

The only production integration in this step is a default-off, startup-only
native chart. The photo algorithm, H5, saved photos and settings are unchanged.
The chart is drawn before HTTP-server startup and before the application task,
so there is no competing page/photo renderer. It uses its own 1-bit label canvas
and restores display clipping/mode. A uses the existing return-home behavior.

## Offline candidate: not promoted

Run `python3 tools/color_lab/compare_white_budget.py` (Pillow required).
It compiles the current renderer and a host-only variant, renders the complete
400x600 calibration PNG in the actual portrait/backing-buffer orientation with
RGB565 quantization, and records code fractions in
`artifacts/color_calibration/white-budget-comparison.json`.

The candidate changes only gamut projection: under the existing nominal RGB
model, white coverage is limited to the compensated target's smallest channel
divided by 255. It changes the target before diffusion; it does not delete white
output pixels or alter FS weights. This is an experimental rendering policy, not
a measured physical mixing law, and is explicitly forbidden in ESP builds.

| Sample region | Baseline | Candidate |
| --- | --- | --- |
| Pure red | 2.982% white | 0% white, 100% red |
| Magenta | 18.791% white, 58.252% blue | 0% white, 76.879% blue |
| Pure cyan | 30.964% white, 43.954% blue | 0% white, 70.057% blue |

The host tests, sanitizer checks, deterministic frame test, gray-pigment guard
and coarse red-to-pink gradient check pass. Nevertheless the increased blue
fractions risk darker/bluer magenta and cyan; these code counts do not establish
better physical color. The candidate also costs more host CPU (roughly 90 ms vs
20 ms on the synthetic 400x600 Burkes benchmark; not ESP timing). It is therefore
**not promoted or flashed**. Do not optimize/ship this direct geometric prototype
until a better target policy is selected from measured mixtures.

## Native chart

Build separately:

```sh
./tools/idf.sh -B /private/tmp/papercolor-native-chart-build \
  -D SDKCONFIG=/private/tmp/papercolor-native-chart-sdkconfig \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;tools/color_lab/native-chart-sdkconfig.defaults' build
```

Its configuration differs from the accepted build only by
`CONFIG_PAPERCOLOR_NATIVE_CHART_ON_BOOT=y`. Normal builds default to off.
The completed diagnostic binary SHA-256 is
`f0b2092e9e4b60f158aa8e3b734eccf6a8f31c621ddf1204235966ebbd93f58c`.
Enabled ESP build and disabled host compile passed, as did the unchanged H5
source-preview test and all 10 Python tests. The original accepted binary hash
was rechecked and remains unchanged.
On a normal manual boot, the diagnostic shows:

- Six unmixed native pigments: black, white, yellow, red, blue, green.
- Six pairs: red/white, red/blue, blue/green, red/yellow, black/white, green/white.
- Five exact **second-pigment** fractions in each pair: 0, 25, 50, 75, 100 percent.

Each mixed patch is 72x32 pixels, with exact counts from a repeating 4x4 pattern.
This deliberately visible pattern is a controlled measurement stimulus, not the
candidate photo dither. The 24-bit nominal RGB triples are used only as exact
driver triggers for native codes; **do not replace these triggers with measured
colors**. Driver no-dither mode remains active through the physical transfer.
No photo LUT, compensation, RGB565 conversion or FS operates on these patches.
Host tests check six pure regions, 30 ratios, trigger uniqueness and rotation.

Flash only the application after the user enters USB download mode:

```sh
./tools/idf.sh -B /private/tmp/papercolor-native-chart-build \
  -p /dev/cu.usbmodem83401 app-flash
```

Then release Boot and press Reset. Take one straight-on photograph of the whole
chart under even light without glare. Keep lighting and camera treatment fixed
for subsequent comparisons. Do not upload this chart through H5. Press A to
return home; the accepted photo renderer remains available. This diagnostic build
shows the chart on each manual restart until a normal build is restored; it is
not a permanent page or saved preference. RTC-wake/first-boot flows remain unchanged.

## Next decision gates

1. Compare direct red with the accepted nominal-red and pure-red source patches.
   Determine the visible brightness/saturation tradeoff without photo mapping.
2. Inspect red/blue and blue/green mixtures before choosing a revised gamut policy.
   Use photo evidence for relative ranking only; reliable absolute profiles need
   measured colorimetry and controlled illumination, not raw phone JPEG RGB.
3. Fit/validate a mixing model using the known coverage patches. Keep measured
   color profiles separate from the native transfer codes and RGB trigger table.
4. Evaluate a common hue/saturation-aware target policy, with near-neutral and
   pale-color continuity tests. Retire old compensation only after A/B verification.
5. Generate efficient tables for any validated expensive mapping. Test native-code
   identity, gray purity, red/pink/dark ramps, magenta/cyan distinction, photos,
   memory bounds and same-chart ESP timings before a normal-firmware promotion.

After the user entered USB download mode, the diagnostic application was flashed
to the verified PaperColor (USB serial 44:1B:F6:C1:34:10): 3,230,704 bytes at
0x10000, data hash verified. Storage/configuration partitions were not flashed.
The offline candidate is not part of this binary. IMG_9911.HEIC now confirms the
native chart displayed. USB reports one `native_chart` render-success record:
total 17.666236 s, refresh call 17.653594 s. No photo-pipeline stats were reported,
as expected for this bypass path. This is not a separately timed BUSY interval.

## IMG_9911 observations and narrower candidate

- Unmixed red is a solid red field without the regular white speckles previously
  seen in source (255,0,0). This supports the software white-target explanation.
- Red/blue at 50% second pigment appears purple; 75% appears blue-purple. These
  are qualitative observations, not an optimal measured recipe for source magenta.
- Blue/green gives muted blue-green/teal mixtures. This image does not demonstrate
  the ability to reproduce vivid source cyan. Adding white changes brightness
  and saturation together, as the red/white and green/white rows illustrate.
- Repeated black/green native fields appear different at different photo
  positions. Lighting, reflections, camera processing and panel uniformity are
  not separated here. Do not turn phone RGB samples into a claimed absolute
  profile. Physical profile fitting remains pending controlled measurements.

A narrower candidate was tested: apply the neutral-white budget only to an
existing black/white/one-chromatic-pigment sector (three vertices), leaving
neutral-only and multi-pigment targets on the accepted mapping. No red-specific
coefficient, new FS weights, post-dither pixel replacement, driver change or
removal of the old accepted compensation was introduced.

On the full RGB565/backing-buffer chart simulation:

- Pure-red sampling region: 2.982% white becomes 0% white / 100% red.
- COLOR.PURPLE, COLOR.CYAN, MAGENTA, CYAN and all four GRAY sampling regions:
  **zero changed native-code pixels**, not merely similar percentages.
- Pink ramps still contain white and pass the coarse monotonicity check.
- The firmware implementation and independent host candidate produce identical
  complete chart and ramp bytes (SHA-256 checked by `compare_white_budget.py`).
- Baseline and candidate host tests pass; candidate AddressSanitizer and UBSan
  pass. Tests check pure red, pale red, both diffusion modes, RGB565 equivalence,
  neutral purity, long-run bounds, and unchanged mixed-color gamut targets.

This controlled A/B is opt-in, `CONFIG_PAPERCOLOR_PRIMARY_WHITE_BUDGET`, default
off. It is **not** the previously rejected universal white-budget variant, and
does not claim to fix remaining magenta/cyan accuracy. Memory layout is unchanged.

Independent candidate build (native chart disabled; normal homepage startup):

```sh
./tools/idf.sh -B /private/tmp/papercolor-primary-budget-build \
  -D SDKCONFIG=/private/tmp/papercolor-primary-budget-sdkconfig \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;tools/color_lab/primary-budget-sdkconfig.defaults' build
```

Build passed, binary SHA-256:
`a55fbe03ddb32fc8581d7788cfc385283e848e9db3125d9ae3bd73d23265fed7`.
The accepted and native-chart binary hashes were rechecked and are intact.
After the user entered download mode, the candidate was app-only flashed to
PaperColor serial 44:1B:F6:C1:34:10: 3,228,944 bytes at 0x10000; data hash
verified and app-flash completed successfully. Storage/configuration partitions
were not flashed. Startup and same-chart checks are recorded below.
H5/navigation/storage code is unchanged in this step. No commit or push.

## IMG_9912 physical verification

User supplied IMG_9912.HEIC after Reset and displaying the original calibration
chart. Compared visually with IMG_9910.HEIC, the regular white speckles in patch
07 RED (255,0,0) are no longer visible; its interior is a solid red field. This
agrees with the offline native-code result (zero white in the sampled region).
Do not equate visual inspection with a microscopic zero-defect measurement.

Purple, magenta, cyan and gray fields show no obvious new qualitative regression.
The remaining muted/blue-biased magenta, low-chroma cyan and visible mixed-color
dither texture are not fixed by this narrow change. Different framing, lighting
and phone processing preclude a colorimetric accuracy or Delta-E claim. Native
red remains darker than the source's luminous sRGB red; removing the unintended
white does not expand the panel gamut.

USB reports two render records, both successful (no failed records):

- home_full: total 18.019144 s; refresh call 16.391919 s.
- local_photo: total 17.633131 s; refresh call 17.152280 s.
- photo-balanced preparation: 0.996795 s; workspace 14,496 bytes.
- minimum internal free memory after local_photo: 136,887 bytes;
  minimum PSRAM free after: 7,105,284 bytes.

The prior IMG_9910 latest record was preparation 1.009798 s and total
17.659355 s. These single observations show essentially unchanged performance,
not a demonstrated speedup. Preparation is included in the refresh-call timer;
do not add it again or label the remaining interval an independently measured
BUSY duration. Render-success records do not independently verify hardware BUSY.

The narrow red-speckle fix passes this chart's physical checkpoint. Full photo
regression, controlled physical profile measurements and mixed-color accuracy
remain pending. Keep the current firmware for normal-photo verification; this
checkpoint does not authorize a new compensation round or declare full calibration.
