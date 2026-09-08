/* SPDX-License-Identifier: MIT */
#include "display/papercolor_lut.h"
#include "display/papercolor_photo_dither.h"

#include <array>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <vector>

namespace {

std::vector<uint8_t> load_lut(const char* path)
{
    std::ifstream input(path, std::ios::binary);
    return std::vector<uint8_t>(std::istreambuf_iterator<char>(input),
                                std::istreambuf_iterator<char>());
}

bool is_native_color(uint8_t value)
{
    return value == PAPERCOLOR_NATIVE_BLACK || value == PAPERCOLOR_NATIVE_WHITE ||
           value == PAPERCOLOR_NATIVE_YELLOW || value == PAPERCOLOR_NATIVE_RED ||
           value == PAPERCOLOR_NATIVE_BLUE || value == PAPERCOLOR_NATIVE_GREEN;
}

uint16_t make_swap565(uint8_t red5, uint8_t green6, uint8_t blue5)
{
    return static_cast<uint16_t>((green6 >> 3) | (red5 << 3) |
                                 (blue5 << 8) | ((green6 & 0x7) << 13));
}

void expand_swap565(uint16_t raw, uint8_t* rgb)
{
    const uint8_t red5 = static_cast<uint8_t>((raw >> 3) & 0x1f);
    const uint8_t green6 = static_cast<uint8_t>(((raw & 0x7) << 3) |
                                                (raw >> 13));
    const uint8_t blue5 = static_cast<uint8_t>((raw >> 8) & 0x1f);
    rgb[0] = static_cast<uint8_t>((red5 << 3) | (red5 >> 2));
    rgb[1] = static_cast<uint8_t>((green6 << 2) | (green6 >> 4));
    rgb[2] = static_cast<uint8_t>((blue5 << 3) | (blue5 >> 2));
}

void test_dither(const std::vector<uint8_t>& lut)
{
    constexpr size_t WIDTH = 64;
    constexpr size_t HEIGHT = 32;
    const size_t workspace_size =
        papercolor_dither_workspace_size(WIDTH, PAPERCOLOR_DITHER_FLOYD_STEINBERG);
    assert(workspace_size > 0);

    std::vector<uint8_t> too_small(workspace_size - 1);
    papercolor_dither_state_t state{};
    assert(!papercolor_dither_init(&state, WIDTH, PAPERCOLOR_DITHER_FLOYD_STEINBERG,
                                   lut.data(), too_small.data(), too_small.size()));

    std::vector<uint8_t> workspace(workspace_size);
    assert(papercolor_dither_init(&state, WIDTH, PAPERCOLOR_DITHER_FLOYD_STEINBERG,
                                  lut.data(), workspace.data(), workspace.size()));

    const std::array<uint8_t, 18> palette = {
        0, 0, 0, 255, 255, 255, 255, 243, 56,
        191, 0, 0, 100, 64, 255, 67, 138, 28,
    };
    const std::array<uint8_t, 6> expected = {
        PAPERCOLOR_NATIVE_BLACK, PAPERCOLOR_NATIVE_WHITE,
        PAPERCOLOR_NATIVE_YELLOW, PAPERCOLOR_NATIVE_RED,
        PAPERCOLOR_NATIVE_BLUE, PAPERCOLOR_NATIVE_GREEN,
    };
    std::vector<uint8_t> palette_row(WIDTH * 3);
    std::vector<uint8_t> native_row(WIDTH);
    for (size_t x = 0; x < WIDTH; ++x) {
        const size_t color = x % expected.size();
        for (size_t channel = 0; channel < 3; ++channel) {
            palette_row[x * 3 + channel] = palette[color * 3 + channel];
        }
    }
    assert(papercolor_dither_process_rgb888_row(&state, palette_row.data(), native_row.data()));
    for (size_t x = 0; x < WIDTH; ++x) {
        assert(native_row[x] == expected[x % expected.size()]);
    }

    papercolor_dither_reset(&state);
    std::vector<uint8_t> frame(WIDTH * HEIGHT * 3);
    for (size_t y = 0; y < HEIGHT; ++y) {
        for (size_t x = 0; x < WIDTH; ++x) {
            frame[(y * WIDTH + x) * 3] = static_cast<uint8_t>(x * 255 / (WIDTH - 1));
            frame[(y * WIDTH + x) * 3 + 1] = static_cast<uint8_t>(y * 255 / (HEIGHT - 1));
            frame[(y * WIDTH + x) * 3 + 2] = static_cast<uint8_t>((x + y) * 255 / (WIDTH + HEIGHT - 2));
        }
    }
    std::vector<uint8_t> first_output(WIDTH * HEIGHT);
    for (size_t y = 0; y < HEIGHT; ++y) {
        assert(papercolor_dither_process_rgb888_row(
            &state, frame.data() + y * WIDTH * 3, first_output.data() + y * WIDTH));
    }
    for (uint8_t value : first_output) {
        assert(is_native_color(value));
    }

    papercolor_dither_reset(&state);
    std::vector<uint8_t> second_output(WIDTH * HEIGHT);
    for (size_t y = 0; y < HEIGHT; ++y) {
        assert(papercolor_dither_process_rgb888_row(
            &state, frame.data() + y * WIDTH * 3, second_output.data() + y * WIDTH));
    }
    assert(first_output == second_output);

    // M5Canvas stores RGB565 with swapped bytes. Its direct fast path must be
    // exactly equivalent to expanding those samples to RGB888 first.
    std::vector<uint8_t> rgb_workspace(workspace_size);
    std::vector<uint8_t> swap_workspace(workspace_size);
    papercolor_dither_state_t rgb_state{};
    papercolor_dither_state_t swap_state{};
    assert(papercolor_dither_init(&rgb_state, WIDTH,
                                  PAPERCOLOR_DITHER_FLOYD_STEINBERG,
                                  lut.data(), rgb_workspace.data(),
                                  rgb_workspace.size()));
    assert(papercolor_dither_init(&swap_state, WIDTH,
                                  PAPERCOLOR_DITHER_FLOYD_STEINBERG,
                                  lut.data(), swap_workspace.data(),
                                  swap_workspace.size()));
    std::vector<uint16_t> swap_row(WIDTH);
    std::vector<uint8_t> expanded_row(WIDTH * 3);
    std::vector<uint8_t> rgb_output(WIDTH);
    std::vector<uint8_t> swap_output(WIDTH);
    for (size_t y = 0; y < HEIGHT; ++y) {
        for (size_t x = 0; x < WIDTH; ++x) {
            swap_row[x] = make_swap565(
                static_cast<uint8_t>((x + y) & 0x1f),
                static_cast<uint8_t>((x * 3 + y * 5) & 0x3f),
                static_cast<uint8_t>((x * 7 + y * 11) & 0x1f));
            expand_swap565(swap_row[x], expanded_row.data() + x * 3);
        }
        assert(papercolor_dither_process_rgb888_row(
            &rgb_state, expanded_row.data(), rgb_output.data()));
        assert(papercolor_dither_process_swap565_row(
            &swap_state, swap_row.data(), swap_output.data()));
        assert(rgb_output == swap_output);
    }

    constexpr size_t FULL_WIDTH = 400;
    constexpr size_t FULL_HEIGHT = 600;
    const size_t full_workspace_size =
        papercolor_dither_workspace_size(FULL_WIDTH, PAPERCOLOR_DITHER_BURKES);
    std::vector<uint8_t> full_workspace(full_workspace_size);
    assert(papercolor_dither_init(&state, FULL_WIDTH, PAPERCOLOR_DITHER_BURKES,
                                  lut.data(), full_workspace.data(), full_workspace.size()));
    std::vector<uint8_t> full_rgb(FULL_WIDTH * 3);
    std::vector<uint8_t> full_native(FULL_WIDTH);
    const auto started = std::chrono::steady_clock::now();
    for (size_t y = 0; y < FULL_HEIGHT; ++y) {
        for (size_t x = 0; x < FULL_WIDTH; ++x) {
            full_rgb[x * 3] = static_cast<uint8_t>(x + y);
            full_rgb[x * 3 + 1] = static_cast<uint8_t>(x * 3 + y * 5);
            full_rgb[x * 3 + 2] = static_cast<uint8_t>(x * 7 + y * 11);
        }
        assert(papercolor_dither_process_rgb888_row(&state, full_rgb.data(), full_native.data()));
    }
    const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now() - started);
    std::cout << "papercolor_burkes_host_us_per_frame=" << elapsed.count() << '\n';
    assert(elapsed.count() < 1000000);
}

}  // namespace

int main(int argc, char** argv)
{
    assert(argc == 2);
    const std::vector<uint8_t> nominal_lut = load_lut(argv[1]);
    assert(nominal_lut.size() == PAPERCOLOR_LUT_SIZE);
    test_dither(nominal_lut);
    std::array<uint8_t, PAPERCOLOR_LUT_SIZE> lut{};
    lut.fill(PAPERCOLOR_NATIVE_WHITE);
    lut[papercolor_lut_index(255, 0, 0)] = PAPERCOLOR_NATIVE_RED;
    lut[papercolor_lut_index(0, 0, 255)] = PAPERCOLOR_NATIVE_BLUE;

    assert(papercolor_lut_index(0, 0, 0) == 0);
    assert(papercolor_lut_index(255, 255, 255) == PAPERCOLOR_LUT_SIZE - 1);
    assert(papercolor_lut_lookup(nullptr, 0, 0, 0) == PAPERCOLOR_NATIVE_WHITE);
    assert(papercolor_lut_lookup(lut.data(), 255, 0, 0) == PAPERCOLOR_NATIVE_RED);

    const uint8_t rgb[] = {255, 0, 0, 0, 0, 255, 255, 255, 255};
    uint8_t packed_rgb[2]{};
    papercolor_quantize_rgb888_4bpp(rgb, 3, packed_rgb, lut.data());
    assert(packed_rgb[0] == ((PAPERCOLOR_NATIVE_RED << 4) | PAPERCOLOR_NATIVE_BLUE));
    assert(packed_rgb[1] == ((PAPERCOLOR_NATIVE_WHITE << 4) | PAPERCOLOR_NATIVE_WHITE));

    const uint8_t bgr[] = {0, 0, 255, 255, 0, 0};
    uint8_t packed_bgr[1]{};
    papercolor_quantize_bgr888_4bpp(bgr, 2, packed_bgr, lut.data());
    assert(packed_bgr[0] == ((PAPERCOLOR_NATIVE_RED << 4) | PAPERCOLOR_NATIVE_BLUE));

    constexpr size_t PIXELS = 400 * 600;
    std::vector<uint8_t> frame(PIXELS * 3);
    std::vector<uint8_t> output((PIXELS + 1) / 2);
    for (size_t index = 0; index < frame.size(); ++index) {
        frame[index] = static_cast<uint8_t>(index * 37U + 11U);
    }

    const auto started = std::chrono::steady_clock::now();
    constexpr int ITERATIONS = 50;
    for (int iteration = 0; iteration < ITERATIONS; ++iteration) {
        papercolor_quantize_bgr888_4bpp(frame.data(), PIXELS, output.data(), lut.data());
    }
    const auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now() - started);
    const auto per_frame_us = elapsed.count() / ITERATIONS;
    std::cout << "papercolor_lut_host_us_per_frame=" << per_frame_us << '\n';
    assert(per_frame_us < 100000);
    return 0;
}
