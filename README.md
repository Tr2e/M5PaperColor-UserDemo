# PaperColor User Demo

### SKU: C151

## Related Link

- [C151 Document & Datasheet](https://docs.m5stack.com/en/products/sku/C151).

## PaperColor OS Home

After the first-boot guide, the firmware opens a portrait home surface instead
of immediately entering the photo viewer. The home screen combines the current
mode, battery, validated SHT40 environment readings, connectivity/storage
status, an RTC-backed local date, and a compact hardware capability overview.

The lower-left image tile is the entry point to the existing image viewer:

- With no image, it displays a functional placeholder.
- With an image, it renders a centered **AspectFill** thumbnail: the tile is
  completely filled, the image is never distorted, and overflow is cropped.
- Press **B** on the home screen to open the image viewer.
- Press **C** on the home screen to toggle system mute. The state is persisted
  across reboots and acknowledged by sound only, without an E Ink refresh;
  inside the image viewer, **C** remains the previous-image key.
- In the viewer, press **C/B** for previous/next and press **A** to return home.
- Hold **A** for five seconds to open the existing Wi-Fi configuration QR view;
  press **A** again to return home.

The non-image dashboard is deliberately black and white, while photos and the
PaperColor web-panel wordmark keep their native color. SHT40 acquisition and
CRC validation finish before the home surface is composed and committed in a
single refresh.

The RTC panel shows the local calendar date rather than a continuously changing
clock. Connect to the PaperColor AP and use the prominent **SYNC TIME** action in
the web page's top status bar to send the browser's current Unix time and
timezone to the RX8130 RTC. A manual sync and the automatic midnight rollover
request a fast date-region update from the main UI task.

## IDF Build

#### Tool Chains

[ESP-IDF v5.5.4](https://docs.espressif.com/projects/esp-idf/en/v5.5.4/esp32s3/index.html)

#### Clone Submodules


```bash
git submodule update --init --recursive
```

#### Build

```bash
idf.py build
```

The repository also provides a wrapper that reuses the ESP-IDF checkout and
toolchain already used by the local PaperMono project:

```bash
./tools/idf.sh build
```

It first uses `PAPERCOLOR_IDF_PATH`, then an already active `IDF_PATH`, and
finally the sibling `../stopwatch/esp-idf` checkout used by PaperMono. The
project pins `IDF_TARGET` to `esp32s3`, so a fresh checkout does not need a
separate `idf.py set-target` step.

#### Flash

```bash
idf.py flash
```

## Acknowledgments

This project references the following open-source libraries and resources:

- https://github.com/m5stack/M5GFX
- https://github.com/m5stack/M5Unified
- https://github.com/m5stack/M5PM1
- https://components.espressif.com/components?q=esp_tinyusb
- https://components.espressif.com/components/espressif/qrcode
- https://components.espressif.com/components/espressif/mdns

## License


- [MIT](LICENSE)
