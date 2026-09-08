# PaperColor display baseline tools

The firmware emits one `DisplayMetrics` record for every instrumented display
operation. During a serial-capable debug session, capture the output with:

```bash
./tools/idf.sh monitor | tee papercolor-display.log
```

The production firmware exposes a composite USB device: the existing photo
storage volume plus a CDC diagnostics port. Read the last 16 records without
changing the Mac's network connection:

```bash
python3 tools/color_lab/read_display_metrics_usb.py \
  --csv baseline.csv \
  --summary baseline-summary.json
```

The same records are also available over the read-only HTTP fallback:

```text
GET http://<device-address>/api/display/metrics
```

The endpoint is read-only. Records are returned oldest-to-newest and live in
RAM only, so a reboot starts a fresh capture.

Convert the captured records to CSV and a per-source P50/P95 summary:

```bash
python3 tools/color_lab/collect_display_metrics.py papercolor-display.log \
  --csv baseline.csv \
  --summary baseline-summary.json
```

Run the host-side parser tests:

```bash
python3 -m unittest discover -s tools/color_lab -p 'test_*.py'
./tools/color_lab/run_host_tests.sh
```

Generate the nominal 32 KiB perceptual LUT:

```bash
python3 tools/color_lab/generate_lut.py \
  tools/color_lab/profiles/nominal.json \
  --output artifacts/color_lut/nominal-5bit.lut \
  --metadata artifacts/color_lut/nominal-5bit.json
```

Compare it with the current RGB-nearest-color baseline on the complete 5-bit
grid:

```bash
python3 tools/color_lab/evaluate_lut.py \
  tools/color_lab/profiles/nominal.json \
  artifacts/color_lut/nominal-5bit.lut \
  --output artifacts/color_lut/nominal-evaluation.json
```

The nominal profile reproduces the current M5GFX palette as a controlled
reference. The evaluation above proves the algorithm and packing pipeline, not
the appearance of the physical panel. Color-improvement claims must use a new profile populated from
measured panel patches; changing the distance metric alone is not considered
calibration.

Firmware integration is guarded by
`CONFIG_PAPERCOLOR_EXPERIMENTAL_LUT` and defaults to off. Enable it only for
controlled A/B builds. The disabled path calls the existing `pushSprite()`
implementation and does not change page rendering.

The enabled build exposes four internal render modes without changing the web
page: `legacy` is the exact upstream path, `ui` is perceptual nearest-color,
`photo-balanced` is serpentine Floyd-Steinberg, and `photo-detail` is
serpentine Burkes. Full-screen local and EZData photos currently select
`photo-balanced`; home, QR, and other UI screens remain in `ui` mode. Both
photo modes diffuse error in a fixed-point linear-light approximation and use
two bounded scanline buffers plus 4,096-byte inverse and 512-byte forward
transfer tables. The 600-pixel unrotated Canvas backing width therefore uses
19,104 bytes. The workspace uses internal RAM only when a 96 KiB reserve and a
large-enough contiguous block remain; otherwise it falls back to PSRAM, and it
is released before the physical panel refresh begins.

The M5Canvas byte-swapped RGB565 fast path is tested against the RGB888 path
for byte-identical native-color output. Only the two measured per-pixel source
files are compiled with `-O2`; the rest of the application keeps the project's
debuggable `-Og` profile. On the C151 sample, the final full-frame
`photo-balanced` preparation time is 638,422 us, below the 1 s device budget.

Build the enabled variant in an independent directory:

```bash
./tools/idf.sh \
  -B build-lut \
  -D SDKCONFIG=build-lut/sdkconfig \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;tools/color_lab/lut-sdkconfig.defaults' \
  build
```

For a device that already contains photos, flash only the app target so the
FAT storage partition is not rewritten:

```bash
./tools/idf.sh -B build-lut -p /dev/cu.usbmodemXXXX app-flash
```

The current `panel_us` value includes color quantization, SPI transfer, power
sequencing and the physical BUSY interval. Splitting those phases requires the
planned, reproducible M5GFX fork; this first instrumentation step deliberately
does not modify the detached upstream submodule.

Experimental firmware also includes a `PaperColorPipeline` line in the USB
metrics response. Its `prepare_us` measures scanline read, quantization and
the pre-refresh image transfer, while `workspace_bytes` records the temporary
dither memory. The physical refresh remains part of `panel_us`.
