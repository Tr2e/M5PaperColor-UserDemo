# PaperDIY calendar migration handoff

Checked on 2026-11-18. Read-only research: no device ports opened, no flashing, and no changes to the source PaperColor checkout.

## Goal and base

Migrate the existing `calendar_firmware` to PaperDIY in `/Users/tree/Documents/paperdiy`, branch `codex/paperdiy-calendar`. Parent reports that the branch at `0b59f3f` includes the current calendar changes and has been pushed. Preserve the approved content, annual schedules, source-plan hashes, fonts, and editorial arrangement. Do not substitute the old release ZIP for the current source/resources.

The first target is a working PaperDIY build with trustworthy dates, a native display path, configuration buttons, and a verified sleep/wake cycle. Hardware battery life and overnight behavior require physical measurements and must not be inferred from a successful build.

## Confirmed hardware

- Official K159 Assembly and K159-B Complete kits share the same main electronics and screen: ESP32-S3-WROOM-1-N16R8, 16 MB flash, 8 MB OPI PSRAM, ET047TC1 960x540 grayscale panel, M5PM1, two user keys, 140 mAh battery. Complete adds the enclosure.
- No independent RX8130/BM8563 calendar RTC appears in the official four-page schematic. This is a material difference from PaperColor.
- PMIC I2C: SDA GPIO41, SCL GPIO42. User key A GPIO4 and B GPIO3, active low. The separate power key is connected to M5PM1.
- EPD parallel data GPIOs: D0..D7 = 6,14,7,12,9,11,8,10. XCL=16, XLE=15, XSTL=13, CKV=18, SPV=17. GPIO46 controls boost enable. M5PM1 GPIO2 controls EPD_PWR.
- microSD: MISO40, CS47, CLK39, MOSI38, detect48. Unlike Color, do not repurpose PMIC GPIO3 as SD power: PaperDIY GPIO3 is charge-status input, active low. PMIC GPIO0/1/4 are FPC signals. The old Color GPIO shutdown sequence is not portable.
- Do not port Color's RGB/speaker/three-button assumptions. PaperDIY has two user buttons; configuration should use an explicit documented A/B gesture with onscreen feedback.

Sources: [PaperDIY Complete](https://docs.m5stack.com/en/core/PaperDIY_Complete_Kit), [official schematic](https://m5stack-doc.oss-cn-shenzhen.aliyuncs.com/1288/K159-B_PaperDIY_sche.pdf), [PaperDIY power guide](https://docs.m5stack.com/en/arduino/paperdiy/m5pm1).

## Official driver baseline (already fetched locally)

- Demo: `https://github.com/m5stack/M5PaperDIY-UserDemo`, commit `71748ca831af4c67b18d63822fda45d1a2a1a739`, local `/private/tmp/paperdiy-migration-research/official-demo`.
- M5GFX: `02107b828acb3eb782fccd747863638d64c876d7`, local `/private/tmp/paperdiy-migration-research/M5GFX`.
- M5Unified: `2fe93c0c64f12f916e73a0605c86bf1241c06a6b`, local `/private/tmp/paperdiy-migration-research/M5Unified`.
- The demo's `repos.json` pins those revisions. Its `patches/M5Unified.patch` only removes the dependency on registry `m5stack/m5gfx >=0.2.26`, because the project provides pinned local M5GFX. Apply that dependency-management fix if adopting the same project structure. Do not change the original PaperColor dependency directories.
- ESP-IDF baseline is 5.5.1; available local 5.5.x may be used after a real build check. Enable ESP32-S3, OPI PSRAM, 240 MHz, and 16 MB flash.
- These revisions already contain `board_t::board_M5PaperDIY` support. M5GFX's `src/M5GFX.cpp:2130` detects M5PM1 on GPIO41/42 and builds the native `Bus_EPD` / `Panel_EPD` path. No additional external epdiy component is used by the official demo. Do not start by pulling an unrelated PaperS3 epdiy stack.
- `M5.begin(config)` with unused mic/speaker/IMU disabled is the official initialization path. Check `M5.getBoard()` and actual display width/height, fail visibly on a different board. Official `display.setRotation(0)` uses the driver's offset rotation; confirm resulting 540x960 portrait dimensions on hardware rather than assuming the old Color rotation value.
- The official demo uses `M5.Power.M5pm1` for power/battery. Its API differs from the standalone `<M5PM1.h>` wrapper used by the old calendar. Keep API usage consistent or use a deliberate adapter.

Pinned sources: [repos.json](https://github.com/m5stack/M5PaperDIY-UserDemo/blob/71748ca831af4c67b18d63822fda45d1a2a1a739/repos.json), [M5GFX initialization](https://github.com/m5stack/M5GFX/blob/02107b828acb3eb782fccd747863638d64c876d7/src/M5GFX.cpp), [official HAL](https://github.com/m5stack/M5PaperDIY-UserDemo/blob/71748ca831af4c67b18d63822fda45d1a2a1a739/main/hal/hal.cpp).

## Rendering and screen power

Keep the existing 400x600 approved bitmap and calendar pack semantics for the first port. Fit it proportionally in 540x960 portrait: scale 1.35 produces 540x810, centered vertically with 75 pixels white margin above and below. Never stretch independently to 540x960, crop text, or silently regenerate the annual content. Because the source is 1-bit, evaluate nearest-neighbor/controlled monochrome resampling rather than adding uncontrolled grayscale or blur. Once the port works, native layout optimization can be a separately reviewed step.

Native M5GFX `Panel_EPD` supports full/partial refresh. Official HAL calls `display.setAutoDisplay(false)`, draws, then `display.display(...)` and `display.waitDisplay()` for a full refresh. Use a full clean refresh for the daily page initially. The old Color-specific comments about six-color `epd_quality` are not true for this grayscale panel; choose/test the appropriate PaperDIY mode instead of blindly keeping them.

Before sleep: finish all rendering and `waitDisplay()`; `M5.Display.sleep()` reaches `Panel_EPD::setSleep` / `Bus_EPD::powerControl(false)` and disables GPIO46 boost. Then turn off M5PM1 GPIO2 EPD_PWR using the selected driver API. Retain ESP32's L2 supply for the recommended first implementation. Verify the two enables return correctly on wake, and verify dark screen/power-cut transitions only after refresh completion.

Relevant driver files: `M5GFX/src/lgfx/v1/platforms/esp32/Panel_EPD.cpp`, `Bus_EPD.cpp`, and `M5Unified/src/utility/Power_Class.cpp` (PaperDIY case). The display code automatically switches boost off when its queued update completes, but explicitly completing/sleeping the display before deep sleep still matters.

## Time and automatic wake: choose deliberately

PaperDIY does support **M5PM1 countdown power-on**: official `timerSet(seconds, M5PM1_TIM_ACTION_POWERON)` followed by `shutdown()` has a demonstrated 3-second example. It is inaccurate to say the hardware cannot power itself on on a timer. It is equally inaccurate to treat that countdown as a battery-backed calendar RTC.

Recommended first implementation: ESP32 deep sleep with timer wake, leaving 3V3_L2 on, screen/unused peripherals off. ESP-IDF's RTC timer preserves system time in deep sleep and most resets but **not power-on resets**. Compute next UTC+8 midnight from current trusted wall-clock time, rather than adding 86400 to a saved date. Use a retained validity marker and carefully distinguish cold boot, timer wake, manual button wake, and abnormal reset. `settimeofday`/SNTP already supply system time; remove mandatory RX8130 I2C checks, alarm register writes, and RTC IRQ wiring.

For true power-off/cold boot, NVS stores a last-known timestamp but cannot establish how long power was absent. Do not silently display it as today's date. Require successful bounded network sync or explicit browser/user time setting before claiming current date. A failed sync may retain the old page with clear stale-time status, without inventing elapsed days. Keep the existing annual plan protection.

If later choosing PMIC power-off for lower current, separately verify countdown range, remaining-time semantics, timer flags, manual early power-on, temperature drift, timer continuation across shutdown/reset, and trust recovery. The source Color strategy `RX8130 absolute alarm -> PMIC shutdown` cannot be transplanted directly. Timer-driven boot plus a stored expected wake time is only an estimate unless all these cases are handled.

The original 15-day offline interval assumed an independent RTC. ESP internal RC clock drift is temperature dependent; do not promise identical midnight accuracy for 15 days without measurement. ESP-IDF documents a more stable divided internal oscillator at additional sleep current. Treat sync frequency, clock source, and power consumption as measured tradeoffs, and report any changed behavior.

Sources: [ESP-IDF system time](https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32s3/api-reference/system/system_time.html), [M5PM1 timers and shutdown](https://docs.m5stack.com/en/arduino/paperdiy/m5pm1).

## Suggested implementation and validation order

1. Build a separate PaperDIY target using the pinned official drivers and a hardware adapter; retain the original PaperColor build.
2. Reuse calendar pack, parsing, rendering, date arithmetic, annual fingerprint guard, captive portal, and bounded Wi-Fi/SNTP operations. Adapt only display, time source, sleep/wake, keys, battery indication, and board power.
3. Replace the red low-battery date warning with an explicit monochrome indication; the panel cannot display red. Preserve the existing calendar content itself.
4. Add focused host checks for 540x960 placement bounds and unchanged content; cold-boot-invalid time, timer wake, midnight/year/leap rollover, and failed sync behavior. Run the existing date/content tests unchanged wherever possible.
5. Generate a real firmware build and record fixed source/driver revisions and hashes. Enumerate and identify PaperDIY separately before flashing. Historical Color MAC is `44:1B:F6:C1:34:10` and must not be used for PaperDIY.
6. Back up the new device before first flash. Check board detection, one complete daily page, config gesture, network setup, sleep/wake over a short test interval, and physical midnight/cold-power behavior. Measure battery-side sleep current; a 140 mAh battery makes unverified always-on assumptions particularly costly.

Do not mark successful compilation or USB enumeration as proof of panel output, overnight wake, or battery life.
