/* SPDX-License-Identifier: MIT */
#include "display/papercolor_lut.h"
#include "display/papercolor_photo_dither.h"
#include "display/papercolor_gamut.h"
#include "display/papercolor_native_chart.h"

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

std::array<size_t, 7> assert_uniform_region_uses_only(
    papercolor_dither_state_t* state, const std::array<uint8_t, 3>& color,
    const std::array<bool, 7>& allowed, size_t width, size_t height)
{
    papercolor_dither_reset(state);
    std::vector<uint8_t> rgb(width * 3);
    std::vector<uint8_t> native(width);
    std::array<size_t, 7> counts{};
    for (size_t x = 0; x < width; ++x) {
        for (size_t channel = 0; channel < 3; ++channel) {
            rgb[x * 3 + channel] = color[channel];
        }
    }
    for (size_t y = 0; y < height; ++y) {
        assert(papercolor_dither_process_rgb888_row(state, rgb.data(), native.data()));
        for (uint8_t value : native) {
            assert(value < allowed.size());
            assert(allowed[value]);
            ++counts[value];
        }
    }
    return counts;
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

void test_native_chart()
{
    using namespace papercolor_native_chart;
    for (int i = 0; i < 6; ++i) {
        for (int y = 58 + (i / 3) * 78; y < 106 + (i / 3) * 78; ++y)
            for (int x = 12 + (i % 3) * 128; x < 132 + (i % 3) * 128; ++x) {
                uint8_t native = 255;
                assert(sample(x, y, native) && native == SOLIDS[i]);
            }
        // The exact 24-bit trigger must map back to its native code under the
        // driver's RGB-nearest no-dither transfer (unique zero-distance match).
        int zero_distance_matches = 0;
        for (uint8_t c : SOLIDS) {
            int distance = 0;
            for (int channel = 0; channel < 3; ++channel) {
                int d = RGB[c][channel] - RGB[SOLIDS[i]][channel];
                distance += d * d;
            }
            if (distance == 0) {
                assert(c == SOLIDS[i]);
                ++zero_distance_matches;
            }
        }
        assert(zero_distance_matches == 1);
    }
    for (int row = 0; row < 6; ++row) {
        for (int col = 0; col < 5; ++col) {
            int second = 0;
            for (int y = 234 + row * 50; y < 266 + row * 50; ++y)
                for (int x = 12 + col * 76; x < 84 + col * 76; ++x) {
                    uint8_t native = 255;
                    assert(sample(x, y, native));
                    assert(native == PAIRS[row][0] || native == PAIRS[row][1]);
                    second += native == PAIRS[row][1];
                }
            assert(second == 72 * 32 * col / 4);
        }
    }
    uint8_t untouched = 255;
    assert(!sample(-1, 0, untouched) && untouched == 255);
    assert(!sample(0, 0, untouched) && untouched == 255);
    assert(!sample(400, 600, untouched) && untouched == 255);
    // Portrait x/y <-> unrotated 600x400 buffer is a bijection.
    std::vector<bool> seen(WIDTH * HEIGHT);
    for (int y = 0; y < 400; ++y) for (int x = 0; x < 600; ++x) {
        const int offset = (599-x) * WIDTH + y;
        assert(!seen[offset]);
        seen[offset] = true;
    }
    std::cout << "native-chart solids/30 exact mixtures/rotation: pass\n";
}

void test_dither(const std::vector<uint8_t>& lut)
{
    constexpr size_t WIDTH = 64;
    constexpr size_t HEIGHT = 32;
    const size_t workspace_size =
        papercolor_dither_workspace_size(WIDTH, PAPERCOLOR_DITHER_FLOYD_STEINBERG);
    assert(workspace_size == (WIDTH + 4) * 3 * sizeof(int32_t) * 2);

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

    // Photo hue guards must suppress pigment contamination while retaining
    // enough legal colors for spatial mixing inside each source-color sector.
    assert_uniform_region_uses_only(
        &state, {240, 235, 232},
        {true, true, false, false, false, false, false}, WIDTH, HEIGHT);
    const auto purple_counts = assert_uniform_region_uses_only(
        &state, {102, 51, 153},
        {true, true, false, true, false, true, false}, WIDTH, HEIGHT);
    assert(purple_counts[PAPERCOLOR_NATIVE_RED] > 0);
    assert(purple_counts[PAPERCOLOR_NATIVE_BLUE] > 0);
    assert(purple_counts[PAPERCOLOR_NATIVE_RED] * 3 >
           purple_counts[PAPERCOLOR_NATIVE_BLUE] * 2);
    const auto cyan_counts = assert_uniform_region_uses_only(
        &state, {0, 173, 254},
        {true, true, false, false, false, true, true}, WIDTH, HEIGHT);
    // White is not mandatory: the reachable target may lie on the blue/green
    // edge. Check hue separation rather than the old clipping artefact.
    assert(cyan_counts[PAPERCOLOR_NATIVE_BLUE] > 0);
    assert(cyan_counts[PAPERCOLOR_NATIVE_GREEN] > 0);
    assert(cyan_counts[PAPERCOLOR_NATIVE_WHITE] * 2 < WIDTH * HEIGHT);
    const auto lime_counts = assert_uniform_region_uses_only(
        &state, {153, 255, 0},
        {true, true, true, false, false, false, true}, WIDTH, HEIGHT);
    assert(lime_counts[PAPERCOLOR_NATIVE_YELLOW] > 0);
    assert(lime_counts[PAPERCOLOR_NATIVE_GREEN] > 0);
    const auto teal_counts = assert_uniform_region_uses_only(
        &state, {51, 153, 102},
        {true, true, false, false, false, true, true}, WIDTH, HEIGHT);
    assert(teal_counts[PAPERCOLOR_NATIVE_BLUE] > 0);
    assert(teal_counts[PAPERCOLOR_NATIVE_GREEN] > 0);
    assert(teal_counts[PAPERCOLOR_NATIVE_WHITE] * 20 < WIDTH * HEIGHT);
    // A small white fraction is valid after gamut projection; the preceding
    // bound still guards against the washed-out regression.
    const auto yellow_counts = assert_uniform_region_uses_only(
        &state, {255, 204, 0},
        {true, true, true, true, false, false, false}, WIDTH, HEIGHT);
    assert(yellow_counts[PAPERCOLOR_NATIVE_YELLOW] > 0);
    assert(yellow_counts[PAPERCOLOR_NATIVE_RED] > 0);
    const auto orange_counts = assert_uniform_region_uses_only(
        &state, {255, 102, 51},
        {true, true, true, true, false, false, false}, WIDTH, HEIGHT);
    assert(orange_counts[PAPERCOLOR_NATIVE_RED] > 0);
    assert(orange_counts[PAPERCOLOR_NATIVE_YELLOW] > 0);
    assert(orange_counts[PAPERCOLOR_NATIVE_WHITE] * 10 < WIDTH * HEIGHT);
    const auto dark_red_counts = assert_uniform_region_uses_only(
        &state, {204, 51, 0},
        {true, true, true, true, false, false, false}, WIDTH, HEIGHT);
    assert(dark_red_counts[PAPERCOLOR_NATIVE_YELLOW] > 0);
    assert(dark_red_counts[PAPERCOLOR_NATIVE_RED] > 0);
    assert_uniform_region_uses_only(
        &state, {180, 85, 105},
        {true, true, false, true, false, true, false}, WIDTH, HEIGHT);

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

void test_gamut_and_saturation(const std::vector<uint8_t>& lut)
{
    using namespace papercolor_gamut;
    const Point tetra[] = {{0,0,0}, {255,0,0}, {0,255,0}, {0,0,255}};
    assert(distance(project({20,30,40}, tetra, 4), {20,30,40}) < 0.001f);
    assert(distance(project({255,255,255}, tetra, 4), {85,85,85}) < 0.01f);
    const Point line[] = {{0,0,0}, {255,255,255}, {100,100,100}};
    assert(distance(project({255,0,0}, line, 3), {85,85,85}) < 0.01f);
    // Nearest projection is idempotent, including degenerate hulls.
    const auto p = project({255,20,180}, tetra, 4);
    assert(distance(project(p, tetra, 4), p) < 0.01f);

    const Point red_sector[] = {{0,0,0}, {255,255,255}, {191,0,0}};
    assert(distance(project_primary_white_budget({255,0,0}, red_sector, 3),
                    {191,0,0}) < 0.001f);
    const auto pink = project_primary_white_budget({255,64,64}, red_sector, 3);
    assert(pink.y > 63.9f && pink.y <= 64.01f && pink.z == pink.y);
    // Multi-pigment and neutral-only hulls must remain on the baseline mapping,
    // independent of the source's saturation. No universal white suppression.
    const Point purple_sector[] = {{0,0,0}, {255,255,255}, {191,0,0}, {100,64,255}};
    const Point cyan_sector[] = {{0,0,0}, {255,255,255}, {100,64,255}, {67,138,28}};
    const Point neutral_sector[] = {{0,0,0}, {255,255,255}};
    for (int r = 0; r < 256; r += 17) for (int g = 0; g < 256; g += 17)
        for (int b = 0; b < 256; b += 17) {
            const Point source{static_cast<float>(r),static_cast<float>(g),static_cast<float>(b)};
            for (const auto* hull : {purple_sector, cyan_sector})
                assert(distance(project_primary_white_budget(source, hull, 4),
                                project(source, hull, 4)) == 0);
            assert(distance(project_primary_white_budget(source, neutral_sector, 2),
                            project(source, neutral_sector, 2)) == 0);
        }

    constexpr size_t W = 64, H = 64;
    for (auto mode : {PAPERCOLOR_DITHER_FLOYD_STEINBERG, PAPERCOLOR_DITHER_BURKES}) {
        std::vector<int32_t> workspace(papercolor_dither_workspace_size(W, mode) / sizeof(int32_t));
        papercolor_dither_state_t state{};
        assert(papercolor_dither_init(&state, W, mode, lut.data(),
                                      workspace.data(), workspace.size() * sizeof(int32_t)));
#if defined(CONFIG_PAPERCOLOR_PRIMARY_WHITE_BUDGET) && CONFIG_PAPERCOLOR_PRIMARY_WHITE_BUDGET
        const auto pure_red = assert_uniform_region_uses_only(&state, {255,0,0},
            {false,false,false,true,false,false,false}, W, H);
        assert(pure_red[PAPERCOLOR_NATIVE_RED] == W * H);
        const auto pale_red = assert_uniform_region_uses_only(&state, {255,64,64},
            {true,true,false,true,false,false,false}, W, H);
        assert(pale_red[PAPERCOLOR_NATIVE_WHITE] > W * H / 5);
        assert(pale_red[PAPERCOLOR_NATIVE_WHITE] < W * H * 3 / 10);
#endif
        for (int gray = 0; gray < 256; ++gray) {
            uint8_t rgb[3];
            expand_swap565(make_swap565(gray >> 3, gray >> 2, gray >> 3), rgb);
            assert_uniform_region_uses_only(&state, {rgb[0],rgb[1],rgb[2]},
                {true,true,false,false,false,false,false}, W, 8);
        }
        const auto magenta = assert_uniform_region_uses_only(&state, {255,0,255},
            {true,true,false,true,false,true,false}, W, H);
        assert(magenta[PAPERCOLOR_NATIVE_RED] > W * H / 10);
        assert(magenta[PAPERCOLOR_NATIVE_BLUE] > W * H / 10);
        const auto cyan = assert_uniform_region_uses_only(&state, {0,255,255},
            {true,true,false,false,false,true,true}, W, H);
        assert(cyan[PAPERCOLOR_NATIVE_GREEN] > W * H / 10);
        assert(cyan[PAPERCOLOR_NATIVE_BLUE] > W * H / 10);

        // Long saturated runs used to accumulate unrepresentable residuals.
        // Both filters must stay bounded and recover to a neutral strip.
        for (auto color : {std::array<uint8_t,3>{255,0,255}, {0,255,255}}) {
            papercolor_dither_reset(&state);
            std::vector<uint8_t> row(W * 3), output(W);
            for (size_t y = 0; y < 2048; ++y) {
                for (size_t x = 0; x < W; ++x)
                    for (size_t c = 0; c < 3; ++c) row[x * 3 + c] = color[c];
                assert(papercolor_dither_process_rgb888_row(&state, row.data(), output.data()));
                for (int32_t e : workspace) assert(e > -131000 && e < 131000);
            }
            std::fill(row.begin(), row.end(), 96);
            size_t whites = 0;
            for (size_t y = 0; y < 64; ++y) {
                assert(papercolor_dither_process_rgb888_row(&state, row.data(), output.data()));
                for (uint8_t v : output) {
                    assert(v == PAPERCOLOR_NATIVE_BLACK || v == PAPERCOLOR_NATIVE_WHITE);
                    if (y >= 32 && v == PAPERCOLOR_NATIVE_WHITE) ++whites;
                }
            }
            assert(whites > W * 32 * 35 / 100 && whites < W * 32 * 40 / 100);
        }
    }
    std::cout << "gamut/saturation/all-RGB565-grays/both-filters: pass\n";
}

}  // namespace

int main(int argc, char** argv)
{
    assert(argc == 2);
    const std::vector<uint8_t> nominal_lut = load_lut(argv[1]);
    assert(nominal_lut.size() == PAPERCOLOR_LUT_SIZE);
    test_native_chart();
    test_dither(nominal_lut);
    test_gamut_and_saturation(nominal_lut);
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
