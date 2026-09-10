# Home photo color rendering

The home thumbnail and embedded color logo use the same `PhotoBalanced` mapping and Floyd–Steinberg diffusion as the photo viewer. Previously the entire home canvas used `Ui` nearest-color lookup, which caused a different color result for the same decoded image.

`papercolor_home_push()` supplies the decoded thumbnail and logo rectangles to `UiWithPhotos`. Each region owns its error rows and target cache. Other UI pixels retain nearest-color mapping. The adapter converts logical rectangles to backing-buffer coordinates, overlays native region codes during a single display transaction, and restores Canvas rotation/clip/scroll and display mode. Partial home updates honor the physical display clip. Without a decoded thumbnail, only the logo receives photo processing.

The optional experimental LUT must be enabled, just as for the existing photo viewer. `tools/color_lab/primary-budget-sdkconfig.defaults` is an existing configuration for exercising this path without the startup diagnostic chart. With the LUT disabled, the adapter retains the original `pushSprite()` behavior. This change does not alter calibration parameters or image scaling/cropping. A smaller thumbnail can still have different dot placement from a full-screen image.

## Validation

On macOS, run:

```sh
python3 tools/color_lab/run_home_photo_tests.py
```

The test links the actual display adapter, photo algorithm and LUT, substituting only M5/ESP I/O. AddressSanitizer and UndefinedBehaviorSanitizer cover same-size region/viewer pixel equivalence, unchanged UI outside regions, independent diffusion, four rotations, RGB565/RGB888 input, display clipping, Canvas state restoration, one display transaction, empty/logo-only regions and allocation failure. Two home photo regions require 4,776 workspace bytes.

The user manually verified the thumbnail/logo fix on the device and accepted it. Further color-profile calibration remains separate from this rendering-path fix.
