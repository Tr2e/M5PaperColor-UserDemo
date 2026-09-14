// SPDX-License-Identifier: MIT
#include "papercolor_oil_painter.h"

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <limits>

namespace {

constexpr int kAnalysisLongestSide = 300;

struct AnalysisSize {
    int width;
    int height;
    size_t pixels;
};

AnalysisSize analysis_size(int width, int height)
{
    if (width <= 0 || height <= 0 || width > 4096 || height > 4096) return {};
    const int longest = std::max(width, height);
    const int aw = std::max(1, width * kAnalysisLongestSide / longest);
    const int ah = std::max(1, height * kAnalysisLongestSide / longest);
    return {aw, ah, static_cast<size_t>(aw) * static_cast<size_t>(ah)};
}

uint32_t next_random(uint32_t& state)
{
    state ^= state << 13;
    state ^= state >> 17;
    state ^= state << 5;
    return state;
}

int clamp_channel(int value)
{
    return std::max(0, std::min(255, value));
}

uint16_t swap_word(uint16_t value)
{
    return static_cast<uint16_t>((value >> 8) | (value << 8));
}

uint8_t luminance(uint16_t pixel)
{
    uint8_t red, green, blue;
    papercolor_oil_decode_swap565(pixel, &red, &green, &blue);
    return static_cast<uint8_t>((77 * red + 150 * green + 29 * blue + 128) >> 8);
}

uint16_t adjusted_color(uint16_t pixel, const PaperColorOilOptions& options)
{
    uint8_t red, green, blue;
    papercolor_oil_decode_swap565(pixel, &red, &green, &blue);
    const int gray = (77 * red + 150 * green + 29 * blue + 128) >> 8;
    const auto adjust = [&](int channel) {
        const int saturated = gray + (channel - gray) * options.saturation_percent / 100;
        return static_cast<uint8_t>(clamp_channel(128 + (saturated - 128) * options.contrast_percent / 100));
    };
    return papercolor_oil_encode_swap565(adjust(red), adjust(green), adjust(blue));
}

uint16_t blend565(uint16_t under, uint16_t over, int alpha)
{
    const uint16_t a = swap_word(under);
    const uint16_t b = swap_word(over);
    const int inverse = 255 - alpha;
    const int red = (((a >> 11) & 31) * inverse + ((b >> 11) & 31) * alpha + 127) / 255;
    const int green = (((a >> 5) & 63) * inverse + ((b >> 5) & 63) * alpha + 127) / 255;
    const int blue = ((a & 31) * inverse + (b & 31) * alpha + 127) / 255;
    return swap_word(static_cast<uint16_t>((red << 11) | (green << 5) | blue));
}

void draw_stroke(uint16_t* destination, int stride, PaperColorOilRect rect,
                 int center_x, int center_y, int radius, uint8_t direction,
                 uint16_t color, int opacity)
{
    const int major = radius * 2;
    const int minor = std::max(1, radius);
    const int extent = major + 1;
    const int left = std::max(rect.x, center_x - extent);
    const int right = std::min(rect.x + rect.width - 1, center_x + extent);
    const int top = std::max(rect.y, center_y - extent);
    const int bottom = std::min(rect.y + rect.height - 1, center_y + extent);
    const int major2 = major * major;
    const int minor2 = minor * minor;
    const int64_t limit = static_cast<int64_t>(major2) * minor2;

    for (int y = top; y <= bottom; ++y) {
        for (int x = left; x <= right; ++x) {
            const int dx = x - center_x;
            const int dy = y - center_y;
            int u, v;
            switch (direction) {
                case 1: u = (dx + dy) * 181 / 256; v = (dx - dy) * 181 / 256; break;
                case 2: u = dy; v = dx; break;
                case 3: u = (dy - dx) * 181 / 256; v = (dx + dy) * 181 / 256; break;
                default: u = dx; v = dy; break;
            }
            const int64_t distance = static_cast<int64_t>(u) * u * minor2 +
                                     static_cast<int64_t>(v) * v * major2;
            if (distance > limit) continue;
            const int alpha = distance > limit * 3 / 4 ? opacity / 3 :
                              distance > limit / 2 ? opacity * 2 / 3 : opacity;
            const size_t index = static_cast<size_t>(y) * stride + x;
            destination[index] = blend565(destination[index], color, alpha);
        }
    }
}

}  // namespace

uint16_t papercolor_oil_encode_swap565(uint8_t red, uint8_t green, uint8_t blue)
{
    const uint16_t rgb565 = static_cast<uint16_t>(((red >> 3) << 11) |
                                                   ((green >> 2) << 5) | (blue >> 3));
    return swap_word(rgb565);
}

void papercolor_oil_decode_swap565(uint16_t pixel, uint8_t* red, uint8_t* green, uint8_t* blue)
{
    const uint16_t rgb565 = swap_word(pixel);
    const uint8_t r5 = static_cast<uint8_t>((rgb565 >> 11) & 31);
    const uint8_t g6 = static_cast<uint8_t>((rgb565 >> 5) & 63);
    const uint8_t b5 = static_cast<uint8_t>(rgb565 & 31);
    if (red) *red = static_cast<uint8_t>((r5 << 3) | (r5 >> 2));
    if (green) *green = static_cast<uint8_t>((g6 << 2) | (g6 >> 4));
    if (blue) *blue = static_cast<uint8_t>((b5 << 3) | (b5 >> 2));
}

size_t papercolor_oil_workspace_size(int content_width, int content_height)
{
    const AnalysisSize size = analysis_size(content_width, content_height);
    return size.pixels * (sizeof(uint16_t) + 2 * sizeof(uint8_t));
}

bool papercolor_oil_render_swap565(const uint16_t* source, uint16_t* destination,
                                   int width, int height, int stride,
                                   PaperColorOilRect rect,
                                   const PaperColorOilOptions& options,
                                   void* workspace, size_t workspace_size,
                                   PaperColorOilStats* stats)
{
    if (!source || !destination || !workspace || width <= 0 || height <= 0 ||
        stride < width || width > 4096 || height > 4096 ||
        rect.x < 0 || rect.y < 0 || rect.width <= 0 || rect.height <= 0 ||
        rect.x > width - rect.width || rect.y > height - rect.height ||
        options.coarse_radius < 2 || options.coarse_radius > 32 ||
        options.medium_radius < 2 || options.medium_radius > options.coarse_radius ||
        options.detail_radius < 1 || options.detail_radius > options.medium_radius ||
        options.saturation_percent < 50 || options.saturation_percent > 150 ||
        options.contrast_percent < 50 || options.contrast_percent > 150) return false;

    const AnalysisSize size = analysis_size(rect.width, rect.height);
    const size_t needed = papercolor_oil_workspace_size(rect.width, rect.height);
    if (!size.pixels || !needed || workspace_size < needed ||
        static_cast<size_t>(stride) > std::numeric_limits<size_t>::max() /
                                          static_cast<size_t>(height)) return false;
    const size_t frame_pixels = static_cast<size_t>(height) * stride;
    if (frame_pixels > std::numeric_limits<size_t>::max() / sizeof(uint16_t)) return false;
    const size_t frame_bytes = frame_pixels * sizeof(uint16_t);
    const uintptr_t src_begin = reinterpret_cast<uintptr_t>(source);
    const uintptr_t dst_begin = reinterpret_cast<uintptr_t>(destination);
    const uintptr_t work_begin = reinterpret_cast<uintptr_t>(workspace);
    if (src_begin > UINTPTR_MAX - frame_bytes || dst_begin > UINTPTR_MAX - frame_bytes ||
        work_begin > UINTPTR_MAX - workspace_size ||
        (src_begin < dst_begin + frame_bytes && dst_begin < src_begin + frame_bytes) ||
        (src_begin < work_begin + workspace_size && work_begin < src_begin + frame_bytes) ||
        (dst_begin < work_begin + workspace_size && work_begin < dst_begin + frame_bytes)) return false;

    auto* colors = static_cast<uint16_t*>(workspace);
    auto* luma = reinterpret_cast<uint8_t*>(colors + size.pixels);
    auto* directions = luma + size.pixels;

    // Downsample with a five-point local average to suppress sensor/JPEG noise.
    for (int ay = 0; ay < size.height; ++ay) {
        const int cy = rect.y + (2 * ay + 1) * rect.height / (2 * size.height);
        for (int ax = 0; ax < size.width; ++ax) {
            const int cx = rect.x + (2 * ax + 1) * rect.width / (2 * size.width);
            const int sx = std::max(1, rect.width / size.width);
            const int sy = std::max(1, rect.height / size.height);
            const int offsets_x[5] = {0, -sx, sx, 0, 0};
            const int offsets_y[5] = {0, 0, 0, -sy, sy};
            int red = 0, green = 0, blue = 0;
            for (int sample = 0; sample < 5; ++sample) {
                const int x = std::max(rect.x, std::min(rect.x + rect.width - 1, cx + offsets_x[sample]));
                const int y = std::max(rect.y, std::min(rect.y + rect.height - 1, cy + offsets_y[sample]));
                uint8_t r, g, b;
                papercolor_oil_decode_swap565(source[static_cast<size_t>(y) * stride + x], &r, &g, &b);
                red += r; green += g; blue += b;
            }
            const uint16_t color = papercolor_oil_encode_swap565(red / 5, green / 5, blue / 5);
            const size_t index = static_cast<size_t>(ay) * size.width + ax;
            colors[index] = adjusted_color(color, options);
            luma[index] = luminance(color);
        }
        if (options.cooperate && (ay & 15) == 0) options.cooperate(options.cooperate_context);
    }

    const auto brightness_at = [&](int x, int y) {
        x = std::max(0, std::min(size.width - 1, x));
        y = std::max(0, std::min(size.height - 1, y));
        return static_cast<int>(luma[static_cast<size_t>(y) * size.width + x]);
    };
    for (int y = 0; y < size.height; ++y) {
        for (int x = 0; x < size.width; ++x) {
            const int gx = brightness_at(x + 1, y - 1) + 2 * brightness_at(x + 1, y) +
                           brightness_at(x + 1, y + 1) - brightness_at(x - 1, y - 1) -
                           2 * brightness_at(x - 1, y) - brightness_at(x - 1, y + 1);
            const int gy = brightness_at(x - 1, y + 1) + 2 * brightness_at(x, y + 1) +
                           brightness_at(x + 1, y + 1) - brightness_at(x - 1, y - 1) -
                           2 * brightness_at(x, y - 1) - brightness_at(x + 1, y - 1);
            const int ax = std::abs(gx), ay = std::abs(gy);
            uint8_t direction = 0;
            if (ax * 2 < ay) direction = 0;       // vertical edge -> horizontal brush
            else if (ay * 2 < ax) direction = 2;  // horizontal edge -> vertical brush
            else direction = (gx ^ gy) < 0 ? 1 : 3;
            const uint8_t strength = static_cast<uint8_t>(std::min(63, (ax + ay) / 8));
            directions[static_cast<size_t>(y) * size.width + x] =
                static_cast<uint8_t>(direction | (strength << 2));
        }
        if (options.cooperate && (y & 15) == 0) options.cooperate(options.cooperate_context);
    }

    // No failure path after this point. Preserve padding and all pixels outside
    // the photo rectangle, then paint only the photo area.
    std::memcpy(destination, source, frame_bytes);
    for (int y = rect.y; y < rect.y + rect.height; ++y) {
        const int ay = std::min(size.height - 1, (y - rect.y) * size.height / rect.height);
        const int by = std::min(size.height - 1, ay + 1);
        const int fy = ((y - rect.y) * size.height % rect.height) * 256 / rect.height;
        for (int x = rect.x; x < rect.x + rect.width; ++x) {
            const int ax = std::min(size.width - 1, (x - rect.x) * size.width / rect.width);
            const int bx = std::min(size.width - 1, ax + 1);
            const int fx = ((x - rect.x) * size.width % rect.width) * 256 / rect.width;
            const uint16_t top = blend565(colors[static_cast<size_t>(ay) * size.width + ax],
                                          colors[static_cast<size_t>(ay) * size.width + bx], fx);
            const uint16_t bottom = blend565(colors[static_cast<size_t>(by) * size.width + ax],
                                             colors[static_cast<size_t>(by) * size.width + bx], fx);
            const size_t pixel = static_cast<size_t>(y) * stride + x;
            destination[pixel] = blend565(blend565(top, bottom, fy), source[pixel], 38);
        }
        if (options.cooperate && (y & 15) == 0) options.cooperate(options.cooperate_context);
    }

    uint32_t random = options.seed ? options.seed : 1;
    const uint8_t radii[3] = {options.coarse_radius, options.medium_radius, options.detail_radius};
    uint32_t counts[3] = {};
    for (int layer = 0; layer < 3; ++layer) {
        const int radius = radii[layer];
        const int step = std::max(2, radius * 3 / 2);
        for (int y = rect.y + step / 2; y < rect.y + rect.height; y += step) {
            for (int x = rect.x + step / 2; x < rect.x + rect.width; x += step) {
                const int jitter = std::max(1, step / 4);
                const int cx = std::max(rect.x, std::min(rect.x + rect.width - 1,
                    x + static_cast<int>(next_random(random) % (2 * jitter + 1)) - jitter));
                const int cy = std::max(rect.y, std::min(rect.y + rect.height - 1,
                    y + static_cast<int>(next_random(random) % (2 * jitter + 1)) - jitter));
                const int ax = std::min(size.width - 1, (cx - rect.x) * size.width / rect.width);
                const int ay = std::min(size.height - 1, (cy - rect.y) * size.height / rect.height);
                const size_t index = static_cast<size_t>(ay) * size.width + ax;
                const uint8_t field = directions[index];
                if (layer == 2 && (field >> 2) < 10) continue;
                const int opacity = layer == 0 ? 205 : layer == 1 ? 190 : 165;
                const uint16_t stroke_color = layer == 2
                    ? adjusted_color(source[static_cast<size_t>(cy) * stride + cx], options)
                    : colors[index];
                draw_stroke(destination, stride, rect, cx, cy, radius,
                            field & 3, stroke_color, opacity);
                ++counts[layer];
            }
            if (options.cooperate) options.cooperate(options.cooperate_context);
        }
    }
    if (stats) {
        *stats = {counts[0], counts[1], counts[2], needed};
    }
    return true;
}
