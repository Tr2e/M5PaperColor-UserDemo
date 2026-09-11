/* SPDX-License-Identifier: MIT */
#include "display/papercolor_lut.h"
#include "display/papercolor_photo_dither.h"
#include "display/papercolor_gamut.h"
#include "display/papercolor_native_chart.h"
#include "display/papercolor_mix_chart.h"
#include "display/papercolor_white_ab_chart.h"

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
#if !defined(CONFIG_PAPERCOLOR_PURPLE_COMPENSATION_BYPASS) || !CONFIG_PAPERCOLOR_PURPLE_COMPENSATION_BYPASS
    // Preserve the legacy red-boost policy for the baseline. The opt-in bypass
    // intentionally removes it; its nominal source coverage is tested below.
    assert(purple_counts[PAPERCOLOR_NATIVE_RED] * 3 >
           purple_counts[PAPERCOLOR_NATIVE_BLUE] * 2);
#endif
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
#if defined(CONFIG_PAPERCOLOR_WARM_COMPENSATION_BYPASS) && CONFIG_PAPERCOLOR_WARM_COMPENSATION_BYPASS
    // This opt-in experiment intentionally exceeds the legacy <10% white
    // policy. Check the uncompensated projection's coverage instead; this is
    // not physical approval of the brighter/possibly paler orange.
    assert(orange_counts[PAPERCOLOR_NATIVE_WHITE] * 100 > WIDTH * HEIGHT * 10);
    assert(orange_counts[PAPERCOLOR_NATIVE_WHITE] * 100 < WIDTH * HEIGHT * 14);
#else
    assert(orange_counts[PAPERCOLOR_NATIVE_WHITE] * 10 < WIDTH * HEIGHT);
#endif
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

void test_mix_chart()
{
    using namespace papercolor_mix_chart;
    std::array<bool,128> seen{};
    for (int y=0; y<8; ++y) for (int x=0; x<16; ++x) {
        const int value=rank(x,y);
        assert(value>=0 && value<128 && !seen[value]);
        seen[value]=true;
    }
    constexpr int AREA=64*32;
    // Independently specified percentages, including complete fill edges.
    for (int panel=0; panel<2; ++panel) for (int row=0; row<4; ++row)
        for (int col=0; col<5; ++col) {
            std::array<int,7> counts{};
            for (int y=0; y<32; ++y) for (int x=0; x<64; ++x) {
                uint8_t code=255;
                assert(sample(48+68*col+x,126+218*panel+44*row+y,code));
                assert(code==1 || code==5 || code==(panel==0?3:6));
                ++counts[code];
            }
            assert(counts[1]==AREA*row/8);
            const int chromatic=AREA-counts[1];
            assert(counts[panel==0?3:6]==chromatic*(col+2)/8);
            assert(counts[5]==chromatic*(6-col)/8);
            uint8_t untouched=255;
            assert(!sample(47+68*col,126+218*panel+44*row,untouched) && untouched==255);
        }
    int sampled=0;
    for (int y=0; y<600; ++y) for (int x=0; x<400; ++x) {
        uint8_t code=255;
        if (sample(x,y,code)) {
            ++sampled;
            assert(is_native_color(code));
            if (y>=54 && y<78)
                assert(code==papercolor_native_chart::SOLIDS[(x-12)/64]);
        }
    }
    assert(sampled==40*AREA+6*56*24);
    uint8_t untouched=255;
    assert(!sample(-1,0,untouched) && !sample(0,-1,untouched));
    assert(!sample(400,599,untouched) && !sample(399,600,untouched));
    assert(untouched==255);
    std::cout << "mix-chart/40 exact ratios/solids/bounds: pass\n";
}

void test_white_ab_chart()
{
    using namespace papercolor_white_ab_chart;
    std::vector<uint8_t> data(PAYLOAD_BYTES), expected(WIDTH*HEIGHT,255);
    constexpr uint8_t colors[]={0,1,2,3,5,6};
    // Asymmetric high/low nibbles and unique row/pair phases catch swapped
    // variants, byte order, wrong row stride and padding/bounds mistakes.
    for (size_t i=0;i<data.size();++i)
        data[i]=(colors[(i*7+i/13)%6]<<4)|colors[(i*11+i/17+3)%6];
    assert(valid_payload(data.data(),data.size()));
    assert(!valid_payload(nullptr,data.size()));
    assert(!valid_payload(data.data(),data.size()-1));
    assert(!valid_payload(data.data(),data.size()+1));
    const uint8_t original=data[0];
    for (uint8_t code : {4,7,8,15}) {
        data[0]=code; assert(!valid_payload(data.data(),data.size()));
        data[0]=code<<4; assert(!valid_payload(data.data(),data.size()));
    }
    data[0]=original;
    for (int i=0;i<6;++i) for(int y=52;y<72;++y) for(int x=12+i*64;x<68+i*64;++x)
        expected[y*400+x]=colors[i];
    for (int row=0;row<6;++row) for(int col=0;col<4;++col)
        for(int y=0;y<50;++y) for(int x=0;x<88;++x) {
            const int variant=(col==0 || col==3) ? 0 : 1;
            const size_t index=((row*2+variant)*4400+y*88+x);
            expected[(118+row*74+y)*400+12+col*96+x]=
                index%2 ? data[index/2]&15 : data[index/2]>>4;
        }
    size_t filled=0;
    for(int y=0;y<600;++y) for(int x=0;x<400;++x) {
        uint8_t code=255;
        const bool sampled=sample(x,y,data.data(),data.size(),code);
        assert(code==expected[y*400+x]);
        assert(sampled==(code!=255)); filled+=sampled;
    }
    assert(filled==112320);
    uint8_t untouched=255;
    assert(!sample(-1,0,data.data(),data.size(),untouched));
    assert(!sample(0,-1,data.data(),data.size(),untouched));
    assert(!sample(400,599,data.data(),data.size(),untouched));
    assert(!sample(399,600,data.data(),data.size(),untouched));
    assert(!sample(12,118,nullptr,data.size(),untouched));
    assert(!sample(12,118,data.data(),0,untouched));
    assert(untouched==255);
    std::cout << "white-ab/24 crops/ABBA/nibbles/invalid-data/bounds: pass\n";
}

void test_pigment_boundaries(const std::vector<uint8_t>& lut)
{
#if defined(CONFIG_PAPERCOLOR_EXACT_PIGMENT_ANCHOR) && CONFIG_PAPERCOLOR_EXACT_PIGMENT_ANCHOR
    // Produce real residuals before entering solid patches, both across rows
    // and within either serpentine direction. A center-only test misses this.
    constexpr size_t W = 96, H = 72;
    const std::array<std::array<uint8_t, 3>, 4> colors = {{
        {255,243,56}, {255,0,0}, {100,64,255}, {0,255,0}}};
    const uint8_t expected[] = {2,3,5,6};
    for (auto mode : {PAPERCOLOR_DITHER_FLOYD_STEINBERG, PAPERCOLOR_DITHER_BURKES}) {
        std::vector<int32_t> work(papercolor_dither_workspace_size(W, mode) / 4);
        papercolor_dither_state_t state{};
        assert(papercolor_dither_init(&state, W, mode, lut.data(), work.data(), work.size()*4));
        std::vector<uint8_t> row(W*3), output(W);
        for (size_t pigment = 0; pigment < colors.size(); ++pigment) {
            for (auto surround : {std::array<uint8_t,3>{96,96,96}, {255,0,255}, {0,255,255}}) {
                papercolor_dither_reset(&state);
                for (size_t y = 0; y < H; ++y) {
                    for (size_t x = 0; x < W; ++x) {
                        const bool inside = y >= 17 && y < 55 && x >= 19 && x < 78;
                        const auto& color = inside ? colors[pigment] : surround;
                        for (size_t c = 0; c < 3; ++c) row[x*3+c] = color[c];
                    }
                    assert(papercolor_dither_process_rgb888_row(&state, row.data(), output.data()));
                    if (y >= 17 && y < 55)
                        for (size_t x = 19; x < 78; ++x) assert(output[x] == expected[pigment]);
                }
            }
        }
    }
    std::cout << "exact-pigment/full-boundaries/both-filters: pass\n";
#else
    (void)lut;
#endif
}

void test_chromatic_edges(const std::vector<uint8_t>& lut)
{
    using namespace papercolor_gamut;
    const Point blue{100,64,255};
    for (auto pigment : {Point{191,0,0}, Point{67,138,28}}) {
        assert(!on_chromatic_segment(pigment,pigment,blue));
        assert(!on_chromatic_segment(blue,pigment,blue));
        for (float t : {0.01f,0.25f,0.5f,0.75f,0.99f}) {
            const auto p = add(mul(pigment,1-t),mul(blue,t));
            assert(on_chromatic_segment(p,pigment,blue));
            // Even 1/4096 real white or black must remain eligible; this is
            // roundoff recognition, not snapping pale or dark mixtures.
            assert(!on_chromatic_segment(add(mul(p,4095.0f/4096),{255.0f/4096,255.0f/4096,255.0f/4096}),pigment,blue));
            assert(!on_chromatic_segment(mul(p,4095.0f/4096),pigment,blue));
        }
    }
    static_assert(sizeof(papercolor_dither_state_t{}.target_cache)==384,"cache size must not grow");
#if defined(CONFIG_PAPERCOLOR_CHROMATIC_EDGE_GUARD) && CONFIG_PAPERCOLOR_CHROMATIC_EDGE_GUARD
    constexpr size_t W=128, H=96;
    for (auto mode : {PAPERCOLOR_DITHER_FLOYD_STEINBERG,PAPERCOLOR_DITHER_BURKES}) {
        std::vector<int32_t> work(papercolor_dither_workspace_size(W,mode)/4);
        papercolor_dither_state_t state{};
        assert(papercolor_dither_init(&state,W,mode,lut.data(),work.data(),work.size()*4));
        std::vector<uint8_t> row(W*3), output(W);
        for (auto color : {std::array<uint8_t,3>{0,174,255},{90,0,165},{180,0,165}}) {
        const uint8_t pigment = color[0]==0 ? 6 : 3;
#if (defined(CONFIG_PAPERCOLOR_PURPLE_COMPENSATION_BYPASS) && CONFIG_PAPERCOLOR_PURPLE_COMPENSATION_BYPASS) || \
    (defined(CONFIG_PAPERCOLOR_PURPLE_COMPENSATION_SMOOTH) && CONFIG_PAPERCOLOR_PURPLE_COMPENSATION_SMOOTH)
        // This source is in the changed activation band. Its mapped target
        // has real black coverage; retain strict edge checks on 180,0,165.
        const bool dark_purple = color[0]==90;
#else
        const bool dark_purple = false;
#endif
        for (auto surround : {std::array<uint8_t,3>{96,96,96},{255,0,255},{0,255,255},{255,255,255},{0,0,0}}) {
            papercolor_dither_reset(&state);
            size_t green=0, count=0, blacks=0, whites=0;
            for (size_t y=0;y<H;++y) {
                for (size_t x=0;x<W;++x) {
                    const bool inside = y>=17 && y<79 && x>=19 && x<109;
                    const auto& source = inside ? color : surround;
                    for (size_t c=0;c<3;++c) row[x*3+c]=source[c];
                }
                assert(papercolor_dither_process_rgb888_row(&state,row.data(),output.data()));
                if (y>=17 && y<79) for (size_t x=19;x<109;++x) {
                    if (dark_purple) {
                        assert(output[x]==0 || output[x]==1 || output[x]==3 || output[x]==5);
                    } else {
                        assert(output[x]==5 || output[x]==pigment);
                    }
                    blacks+=output[x]==0; whites+=output[x]==1;
                    green+=output[x]==pigment; ++count;
                }
            }
#if defined(CONFIG_PAPERCOLOR_BLUE_SECONDARY_BALANCE) && CONFIG_PAPERCOLOR_BLUE_SECONDARY_BALANCE
            // Independent expected coverage from patch 10's documented target.
            if (pigment==6) assert(green>count*33/100 && green<count*36/100);
            else if (color[0]==180) assert(green>count*49/100 && green<count*51/100);
            else if (dark_purple) {
#if defined(CONFIG_PAPERCOLOR_PURPLE_COMPENSATION_SMOOTH) && CONFIG_PAPERCOLOR_PURPLE_COMPENSATION_SMOOTH
                // Independent barycentric coverage of Q4 target
                // (127.9375,38.0625,151.6875): ~4.7% K,35.8% R,59.5% B.
                assert(green>count*34/100 && green<count*37/100);
                assert(blacks>count*3/100 && blacks<count*6/100);
                assert(whites<count/100);
#else
                // Nominal target now contains ~23.4% K, 17.5% R, 59.1% B.
                // This intentionally changes the old all-chromatic result.
                assert(green>count*16/100 && green<count*19/100);
                assert(blacks>count*22/100 && blacks<count*25/100);
                assert(whites<count/100);
#endif
            } else assert(green>count*39/100 && green<count*42/100);
#endif
        }
        }
    }
    std::cout << "chromatic-edge/all-boundaries/five-surrounds/both-filters: pass\n";
#else
    (void)lut;
#endif
}

void test_purple_bypass(const std::vector<uint8_t>& lut)
{
#if defined(CONFIG_PAPERCOLOR_PURPLE_COMPENSATION_BYPASS) && CONFIG_PAPERCOLOR_PURPLE_COMPENSATION_BYPASS
    constexpr size_t W=128,H=128;
    constexpr std::array<uint8_t,3> source={102,51,153};
    for (auto mode : {PAPERCOLOR_DITHER_FLOYD_STEINBERG,PAPERCOLOR_DITHER_BURKES}) {
        std::vector<int32_t> work(papercolor_dither_workspace_size(W,mode)/4);
        papercolor_dither_state_t state{};
        assert(papercolor_dither_init(&state,W,mode,lut.data(),work.data(),work.size()*4));
        const auto counts=assert_uniform_region_uses_only(&state,source,
            {true,true,false,true,false,true,false},W,H);
        // This source lies inside the nominal K/W/R/B hull. Independently
        // recombine emitted pigments: the bypass should reproduce its nominal
        // RGB closely, while the legacy boost adds about 40 to red. This is
        // numerical conservation, not physical approval of darker purples.
        for (size_t c=0;c<3;++c) {
            int64_t sum=0;
            for (size_t code=0;code<7;++code)
                sum+=int64_t(counts[code])*papercolor_native_chart::RGB[code][c];
            const int64_t error=sum-int64_t(source[c])*W*H;
            assert(error>-4*int64_t(W*H) && error<4*int64_t(W*H));
        }
        assert(counts[0]>W*H*20/100 && counts[0]<W*H*27/100);
        assert(counts[3]>W*H*14/100 && counts[3]<W*H*20/100);
    }
    std::cout << "purple-bypass/nominal-source-conservation/both-filters: pass\n";
#else
    (void)lut;
#endif
}

void test_warm_bypass(const std::vector<uint8_t>& lut)
{
#if defined(CONFIG_PAPERCOLOR_WARM_COMPENSATION_BYPASS) && CONFIG_PAPERCOLOR_WARM_COMPENSATION_BYPASS
    constexpr size_t W=128,H=128;
    for (auto mode : {PAPERCOLOR_DITHER_FLOYD_STEINBERG,PAPERCOLOR_DITHER_BURKES}) {
        std::vector<int32_t> work(papercolor_dither_workspace_size(W,mode)/4);
        papercolor_dither_state_t state{};
        assert(papercolor_dither_init(&state,W,mode,lut.data(),work.data(),work.size()*4));
        const auto counts=assert_uniform_region_uses_only(&state,{255,101,49},
            {false,true,true,true,false,false,false},W,H);
        // Independent nominal decomposition of the uncompensated projected
        // orange; the previous branch produces only about 6% white.
        assert(counts[1]>W*H*10/100 && counts[1]<W*H*13/100);
        assert(counts[3]>W*H*53/100 && counts[3]<W*H*57/100);
    }
    std::cout << "warm-bypass/orange-coverage/both-filters: pass\n";
#else
    (void)lut;
#endif
}

void test_gamut_and_saturation(const std::vector<uint8_t>& lut)
{
    using namespace papercolor_gamut;
    // A hue-only policy must preserve known neutral coverage and stay within
    // the original two-pigment interval. Check independently constructed mixes.
    const Point white{255,255,255}, blue{100,64,255};
    for (int channel : {0,1}) {
        const Point pigment = channel == 0 ? Point{191,0,0} : Point{67,138,28};
        const Point source = channel == 0 ? Point{255,0,255} : Point{0,255,255};
        for (float w : {0.0f,0.1f,0.3f}) {
            const float a = 0.2f, b = 0.4f;
            const auto mixed = add(mul(white,w),add(mul(pigment,a),mul(blue,b)));
            const auto adjusted = balance_blue_secondary(source,mixed,pigment,blue,channel);
            const float det = dot(white,cross(pigment,blue));
            const float nw = dot(adjusted,cross(pigment,blue))/det;
            const float na = dot(white,cross(adjusted,blue))/det;
            const float nb = dot(white,cross(pigment,adjusted))/det;
            assert(nw > w-0.00001f && nw < w+0.00001f);
            assert(na+nb > a+b-0.00001f && na+nb < a+b+0.00001f);
            assert(na>a && na<=0.30001f && nb>=0.29999f);
            const auto less_white = reduce_secondary_white(source,mixed,pigment,blue,channel);
            const float rw = dot(less_white,cross(pigment,blue))/det;
            const float ra = dot(white,cross(less_white,blue))/det;
            const float rb = dot(white,cross(pigment,less_white))/det;
            assert(rw>=w*.75f-0.00001f && rw<=w+0.00001f);
            if (w>0) assert(rw<w);
            assert(ra>=a-0.00001f && rb>=b-0.00001f);
            assert(ra*b-rb*a>-0.00001f && ra*b-rb*a<0.00001f);
            assert(rw+ra+rb>w+a+b-0.00001f && rw+ra+rb<w+a+b+0.00001f);
        }
        // Exact pigment vertices and the sector boundary must be unchanged.
        assert(distance(balance_blue_secondary(source,blue,pigment,blue,channel),blue)<0.000001f);
        assert(distance(balance_blue_secondary(source,pigment,pigment,blue,channel),pigment)<0.000001f);
        const Point boundary = channel == 0 ? Point{12,0,255} : Point{0,12,255};
        const Point mixed=mul(add(pigment,blue),0.5f);
        assert(distance(balance_blue_secondary(boundary,mixed,pigment,blue,channel),mixed)==0);
        assert(distance(reduce_secondary_white(boundary,mixed,pigment,blue,channel),mixed)==0);
        const auto pale=add(mul(white,0.8f),mul(mixed,0.2f));
        assert(distance(reduce_secondary_white({240,240,240},pale,pigment,blue,channel),pale)==0);
        assert(distance(reduce_secondary_white(source,blue,pigment,blue,channel),blue)<0.000001f);
        assert(distance(reduce_secondary_white(source,pigment,pigment,blue,channel),pigment)<0.000001f);
    }
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
#if defined(CONFIG_PAPERCOLOR_PRIMARY_PEAK_PRESERVATION) && CONFIG_PAPERCOLOR_PRIMARY_PEAK_PRESERVATION
        // A full blue source must not be darkened to cancel the native blue's
        // unavoidable red/green coordinates. Test both actual diffusion modes.
        const auto pure_blue = assert_uniform_region_uses_only(&state, {0,0,255},
            {false,false,false,false,false,true,false}, W, H);
        assert(pure_blue[PAPERCOLOR_NATIVE_BLUE] == W * H);
        for (int level : {32, 64, 96, 128, 160, 192, 224}) {
            const auto blue = assert_uniform_region_uses_only(&state,
                {0,0,static_cast<uint8_t>(level)},
                {true,false,false,false,false,true,false}, W, H);
            const double coverage = double(blue[PAPERCOLOR_NATIVE_BLUE]) / (W * H);
            // Known nominal full-scale-primary mixing equation, independent
            // of the implementation's projection or correction formula.
            assert(coverage > level / 255.0 - 0.015);
            assert(coverage < level / 255.0 + 0.015);
        }
#endif
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
#if defined(CONFIG_PAPERCOLOR_BLUE_SECONDARY_BALANCE) && CONFIG_PAPERCOLOR_BLUE_SECONDARY_BALANCE
        // Both filters must realize the new chromatic balance without using
        // black or increasing white to disguise the hue change.
        assert(magenta[PAPERCOLOR_NATIVE_BLACK] == 0);
        assert(cyan[PAPERCOLOR_NATIVE_BLACK] == 0);
#if defined(CONFIG_PAPERCOLOR_SECONDARY_WHITE_REDUCTION) && CONFIG_PAPERCOLOR_SECONDARY_WHITE_REDUCTION
        assert(magenta[PAPERCOLOR_NATIVE_RED] > W * H * 38 / 100);
        assert(magenta[PAPERCOLOR_NATIVE_RED] < W * H * 41 / 100);
        assert(magenta[PAPERCOLOR_NATIVE_WHITE] > W * H * 13 / 100);
        assert(magenta[PAPERCOLOR_NATIVE_WHITE] < W * H * 15 / 100);
#if defined(CONFIG_PAPERCOLOR_CYAN_RATIO_SMOOTH) && CONFIG_PAPERCOLOR_CYAN_RATIO_SMOOTH
        assert(cyan[PAPERCOLOR_NATIVE_GREEN] > W * H * 31 / 100);
        assert(cyan[PAPERCOLOR_NATIVE_GREEN] < W * H * 34 / 100);
#else
        assert(cyan[PAPERCOLOR_NATIVE_GREEN] > W * H * 36 / 100);
        assert(cyan[PAPERCOLOR_NATIVE_GREEN] < W * H * 39 / 100);
#endif
        assert(cyan[PAPERCOLOR_NATIVE_WHITE] > W * H * 22 / 100);
        assert(cyan[PAPERCOLOR_NATIVE_WHITE] < W * H * 24 / 100);
#else
        assert(magenta[PAPERCOLOR_NATIVE_RED] > W * H * 35 / 100);
        assert(magenta[PAPERCOLOR_NATIVE_RED] < W * H * 40 / 100);
        assert(magenta[PAPERCOLOR_NATIVE_WHITE] > W * H * 17 / 100);
        assert(magenta[PAPERCOLOR_NATIVE_WHITE] < W * H * 20 / 100);
        assert(cyan[PAPERCOLOR_NATIVE_GREEN] > W * H * 32 / 100);
        assert(cyan[PAPERCOLOR_NATIVE_GREEN] < W * H * 36 / 100);
        assert(cyan[PAPERCOLOR_NATIVE_WHITE] > W * H * 29 / 100);
        assert(cyan[PAPERCOLOR_NATIVE_WHITE] < W * H * 32 / 100);
#endif
#endif

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
    test_mix_chart();
    test_white_ab_chart();
    test_dither(nominal_lut);
    test_gamut_and_saturation(nominal_lut);
    test_pigment_boundaries(nominal_lut);
    test_chromatic_edges(nominal_lut);
    test_warm_bypass(nominal_lut);
    test_purple_bypass(nominal_lut);
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
