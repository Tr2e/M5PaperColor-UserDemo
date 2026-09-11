# Portrait photo regression (Kodak 04)

## 2026-09-09 repeat flash

User explicitly selected the red-hat portrait test. Reused the verified original
test binary (SHA-256 `9bf3b6d063cff88f280a1e11ddd2765d8bb22ce16c3f1f77b8a4a7c132247d16`);
no new compensation is included. Selected `/dev/cu.usbmodem83301` by USB serial
`44:1B:F6:C1:34:10`, then verified the same MAC on the open esptool connection
before writing. App-only flash at `0x10000`: 3,867,008 bytes in 32.1 s,
`Hash of data verified`, exit 0. After the requested RTS reset the device still
enumerates as `303A:1001`; release Boot and press Reset manually. Portrait startup
and new physical acceptance remain pending. The other connected device, serial
`44:1B:F6:C1:8A:00` at `/dev/cu.usbmodem83401`, was not accessed.
The earlier restoration described below is historical; the device now contains
the portrait test image. The normal rollback image remains under
`.cache/firmware/accepted-21b0370/`.

## Source and scope

- Source page: https://r0k.us/graphics/kodak/kodim04.html
- Download: https://r0k.us/graphics/kodak/kodak/kodim04.png
- Source credit: Bob Clemens, Kodak PhotoCD PCD0992, image P008630,
  "portrait of girl in red".
- Repository copy: `artifacts/color_calibration/kodim04.png`, original 512x768 PNG.
- SHA-256: `e3b946107c5d3441c022f678d0c3caf1e224d81b1604ba840a4f88e562de61aa`.
- The hosting site's https://r0k.us/graphics/kodak/index.html states its
  understanding that Kodak released the suite for unrestricted usage. This is
  the mirror's statement, not an independently verified commercial license.
  Retain attribution; this copy is a development regression reference, not a
  newly commissioned or calibrated photograph.

This 2:3 portrait is chosen to stress red textiles/lips, continuous skin tones,
blond hair, shadow detail, pale pink/mauve fabric and black/white necklace/teeth.
It does not test vivid cyan, sky or vegetation comprehensively. Use the earlier
color chart for those hue checkpoints. The source itself has photographic
lighting/color rendering; compare reproduction of these source pixels, not
assumed "true" skin color. Phone photos do not provide absolute Delta-E.

## Display path and isolation

`CONFIG_PAPERCOLOR_REFERENCE_PHOTO_ON_BOOT` defaults off and requires the tested
primary-budget pipeline. The native pigment chart is disabled for this build.
At ordinary startup the reference replaces the initial home render. A returns
home; normal homepage, photo uploads, stored photo selection and settings are
not modified by the reference helper. RTC wake and first-run flows are untouched.
The reference repeats on normal reboot while this test build is installed.

An independent PSRAM Canvas uses the normal 600x400 RGB565 backing store,
portrait rotation 1 and the same M5GFX PNG decoder/scale as local photos. It
decodes the unmodified 512x768 source to 400x600 (scale 0.78125), without crop,
host resizing, exposure changes or pre-dither. It calls the current
`papercolor_push_canvas(..., PhotoBalanced)`; color mapping, LUT and FS code
are unchanged from commit 21b0370. Failure to allocate/decode falls back to home.
Startup runs before the app task and HTTP server are created. The reference
does not write the filesystem/NVS or touch the global Canvas. Its temporary
Canvas is released on return. Metrics source is `reference_photo`.

Build in a separate directory, preserving the validated normal firmware:

```sh
./tools/idf.sh -B /private/tmp/papercolor-reference-photo-build \
  -D SDKCONFIG=/private/tmp/papercolor-reference-photo-sdkconfig \
  -D 'SDKCONFIG_DEFAULTS=sdkconfig.defaults;tools/color_lab/reference-photo-sdkconfig.defaults' build
```

Flash **app-flash only**, never `flash` / storage partition generation output.
The source PNG lives in the application image; existing device photos remain.
Rollback normal firmware is `/private/tmp/papercolor-primary-budget-build/paper_color.bin`,
SHA-256 `a55fbe03ddb32fc8581d7788cfc385283e848e9db3125d9ae3bd73d23265fed7`.

## Physical acceptance criteria

Photograph the complete panel straight-on, under even diffuse light without
glare, retaining some white bezel. Inspect face/neck for abrupt hue bands, red
hat/lips for unintended white speckles and lost shading, hair/hat mesh for
detail, teeth/necklace for neutral highlights, and fabric for pink/purple hue.
Textured photos can legitimately use white pixels: do not apply the pure-red
solid-patch zero-white criterion indiscriminately to photographic highlights.

Read USB metrics after display; compare photo processing and total refresh
separately. This is a different source from the chart, so timing differences
are not a controlled algorithm-speed A/B. The refresh-call timer includes
preparation; render success is not an independent hardware BUSY measurement.

## Build verification

ESP-IDF build passed. Binary size: 3,867,008 bytes (0x3b0180); SHA-256:
`9bf3b6d063cff88f280a1e11ddd2765d8bb22ce16c3f1f77b8a4a7c132247d16`.
Compared with the validated primary-budget sdkconfig, the only configuration
addition is `CONFIG_PAPERCOLOR_REFERENCE_PHOTO_ON_BOOT=y`. Color code and H5
source have no changes relative to 21b0370. Host LUT/dither tests, H5 source
preview tests, and compilation of the disabled reference helper passed.
The normal rollback binary hash was rechecked and remains intact.
Source PNG metadata contains sRGB intent 0 and gamma 0.45455.

After the user entered download mode, app-only flash completed successfully to
USB serial 44:1B:F6:C1:34:10. Wrote 3,867,008 bytes at 0x10000 in 32.2 seconds;
esptool verified the data hash. No storage/configuration/partition-table write.
IMG_9914.HEIC confirms the portrait rendered. USB reference_photo reports success,
total 21.309969 s and refresh call 19.616249 s. A subsequent home_full record
overwrote the pipeline snapshot with UI preparation (0.241975 s), so the photo's
own preparation time is unavailable; do not substitute the UI value.

Visual comparison: recognizable composition and red hues, but muddy gray/yellow
skin, muted pink/purple fabric, and dither texture competing with hair/hat detail.
This is qualitative phone-photo evidence, not absolute calibration. User paused
further optimization and requested normal firmware at 21b0370. That exact
previously verified application binary was restored with data hash verification;
no storage/configuration write. Post-restore startup awaits Reset confirmation.
This test addition has not been committed or pushed. Resume from the repository
root `TODO_COLOR_CALIBRATION.md` only when the user asks to continue.
