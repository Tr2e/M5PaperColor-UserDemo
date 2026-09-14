// SPDX-License-Identifier: MIT
// Device adapter of the accepted host prototype. Large buffers are caller-owned;
// seeded ordering and floating-point expressions preserve the approved look.
#include "papercolor_stacked_painter.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>
#include <new>

namespace {
struct Color { int r, g, b; };
struct Stroke { int x, y, radius; Color color; uint32_t seed; int priority = 0; int order = 0; };
uint32_t random_word(uint32_t& random_state)
{
    random_state ^= random_state << 13;
    random_state ^= random_state >> 17;
    random_state ^= random_state << 5;
    return random_state;
}
int clamp(int n, int lo, int hi) { return std::max(lo, std::min(hi, n)); }
Color decode(uint16_t word)
{
    uint8_t r, g, b;
    papercolor_oil_decode_swap565(word, &r, &g, &b);
    return {r, g, b};
}
uint16_t encode(Color c)
{
    return papercolor_oil_encode_swap565(clamp(c.r, 0, 255), clamp(c.g, 0, 255), clamp(c.b, 0, 255));
}
int difference(Color a, Color b)
{
    return std::max({std::abs(a.r - b.r), std::abs(a.g - b.g), std::abs(a.b - b.b)});
}
int light(Color c) { return (77 * c.r + 150 * c.g + 29 * c.b) / 256; }
float unit(uint32_t seed)
{
    seed ^= seed >> 16; seed *= 0x7feb352dU;
    seed ^= seed >> 15; seed *= 0x846ca68bU; seed ^= seed >> 16;
    return static_cast<float>(seed & 65535U) / 65535.0f;
}
float noise(float x, uint32_t seed)
{
    const int i = static_cast<int>(std::floor(x));
    float t = x - i;
    t = t * t * (3 - 2 * t);
    const float a = unit(seed + static_cast<uint32_t>(i) * 2654435761U);
    const float b = unit(seed + static_cast<uint32_t>(i + 1) * 2654435761U);
    return (a + (b - a) * t) * 2 - 1;
}
Color mix(Color a, Color b, float amount)
{
    return {static_cast<int>(a.r + (b.r - a.r) * amount + 0.5f),
            static_cast<int>(a.g + (b.g - a.g) * amount + 0.5f),
            static_cast<int>(a.b + (b.b - a.b) * amount + 0.5f)};
}

class Painter {
public:
    int width, height, aw, ah;
    uint16_t *reference, *detail, *output;
    Color* ground;
    Stroke* marks;
    uint32_t random_state;
    const PaperColorStackedOptions& options;
    uint32_t counts[5] = {};
    void cooperate() const { if (options.cooperate) options.cooperate(options.cooperate_context); }
    Painter(int w, int h, const uint16_t* source, int stride, PaperColorOilRect rect,
            void* workspace, const PaperColorStackedOptions& settings)
        : width(w), height(h), aw((w + 2) / 3), ah((h + 2) / 3),
          random_state(settings.seed ? settings.seed : 1), options(settings)
    {
        auto* memory = static_cast<uint8_t*>(workspace);
        const auto take = [&](size_t bytes) {
            void* result = memory;
            memory += (bytes + 3) & ~size_t(3);
            return result;
        };
        reference = static_cast<uint16_t*>(take(aw * ah * sizeof(uint16_t)));
        detail = static_cast<uint16_t*>(take(w * h * sizeof(uint16_t)));
        output = static_cast<uint16_t*>(take(w * h * sizeof(uint16_t)));
        const int grid_size = scaled(24);
        ground = static_cast<Color*>(take((w / grid_size + 2) * (h / grid_size + 2) * sizeof(Color)));
        marks = reinterpret_cast<Stroke*>(memory);
        const size_t capacity = static_cast<size_t>(w / 2) * (h / 2);
        for (size_t i = 0; i < capacity; ++i) {
            new (marks + i) Stroke{};
            if ((i & 255U) == 0) cooperate();
        }
        // Keep a full-resolution, mildly denoised target for small marks.
        // Edge-aware averaging avoids erasing thin highlights before rendering.
        for (int y = 0; y < h; ++y) for (int x = 0; x < w; ++x) {
            const Color center = decode(source[static_cast<size_t>(y + rect.y) * stride + x + rect.x]);
            Color sum{center.r * 4, center.g * 4, center.b * 4};
            int count = 4;
            for (int dy = -1; dy <= 1; ++dy) for (int dx = -1; dx <= 1; ++dx) {
                if (!dx && !dy) continue;
                const Color c = decode(source[static_cast<size_t>(clamp(y + dy, 0, h - 1) + rect.y) * stride + clamp(x + dx, 0, w - 1) + rect.x]);
                if (difference(c, center) > 32) continue;
                sum.r += c.r; sum.g += c.g; sum.b += c.b; ++count;
            }
            if (x == 0 && (y & 7) == 0) cooperate();
            detail[y * w + x] = encode({sum.r / count, sum.g / count, sum.b / count});
        }
        for (int y = 0; y < ah; ++y) for (int x = 0; x < aw; ++x) {
            Color sum{};
            for (int dy = -2; dy <= 2; ++dy) for (int dx = -2; dx <= 2; ++dx) {
                const Color c = decode(source[static_cast<size_t>(clamp(y * 3 + dy, 0, height - 1) + rect.y) * stride + clamp(x * 3 + dx, 0, width - 1) + rect.x]);
                sum.r += c.r; sum.g += c.g; sum.b += c.b;
            }
            if (x == 0 && (y & 7) == 0) cooperate();
            reference[y * aw + x] = encode({sum.r / 25, sum.g / 25, sum.b / 25});
        }
        // A broad underpainting. Bilinear reconstruction avoids visible 3px
        // squares and leaves real reconstruction work for the large brushes.
        const int grid = scaled(24);
        const int gw = (width + grid - 1) / grid + 1;
        const int gh = (height + grid - 1) / grid + 1;
        for (int i = 0; i < gw * gh; ++i) new (ground + i) Color{};
        for (int y = 0; y < gh; ++y) for (int x = 0; x < gw; ++x) {
            Color sum{};
            for (int dy = -2; dy <= 2; ++dy) for (int dx = -2; dx <= 2; ++dx) {
                const Color c = sample(x * grid + dx * 6, y * grid + dy * 6);
                sum.r += c.r; sum.g += c.g; sum.b += c.b;
            }
            if (x == 0) cooperate();
            ground[y * gw + x] = {sum.r / 25, sum.g / 25, sum.b / 25};
        }
        for (int y = 0; y < height; ++y) for (int x = 0; x < width; ++x) {
            if (x == 0 && (y & 7) == 0) cooperate();
            const int gx = x / grid, gy = y / grid;
            const float fx = static_cast<float>(x % grid) / grid;
            const float fy = static_cast<float>(y % grid) / grid;
            output[y * width + x] = encode(mix(
                mix(ground[gy * gw + gx], ground[gy * gw + gx + 1], fx),
                mix(ground[(gy + 1) * gw + gx], ground[(gy + 1) * gw + gx + 1], fx), fy));
        }
    }
    int scaled(int radius) const
    {
        const float scale = std::max(0.35f, std::min(width, height) / 400.0f);
        return std::max(1, static_cast<int>(std::lround(radius * scale)));
    }
    Color sample(int x, int y) const
    {
        x = clamp(x, 0, width - 1); y = clamp(y, 0, height - 1);
        const int x0 = x / 3, y0 = y / 3;
        const int x1 = std::min(aw - 1, x0 + 1), y1 = std::min(ah - 1, y0 + 1);
        return mix(mix(decode(reference[y0 * aw + x0]), decode(reference[y0 * aw + x1]), (x % 3) / 3.0f),
                   mix(decode(reference[y1 * aw + x0]), decode(reference[y1 * aw + x1]), (x % 3) / 3.0f),
                   (y % 3) / 3.0f);
    }
    Color target(int x, int y, int layer) const
    {
        if (layer >= 3)
        {
            const Color fine = decode(detail[clamp(y, 0, height - 1) * width + clamp(x, 0, width - 1)]);
            return layer == 3 ? mix(sample(x, y), fine, 0.60f) : fine;
        }
        return sample(x, y);
    }
    int contrast(int x, int y, int radius, int layer) const
    {
        const Color center = target(x, y, layer);
        int span = 0;
        for (int dy = -1; dy <= 1; ++dy) for (int dx = -1; dx <= 1; ++dx)
            span = std::max(span, difference(center, target(x + dx * radius, y + dy * radius, layer)));
        return span;
    }
    Color patch(int x, int y, int r, int layer) const
    {
        Color sum{};
        const Color center = target(x, y, layer);
        int count = 0;
        const int offset = std::max(1, r / 3);
        for (int dy = -1; dy <= 1; ++dy) for (int dx = -1; dx <= 1; ++dx) {
            const Color c = target(x + dx * offset, y + dy * offset, layer);
            if (difference(c, center) > (layer >= 3 ? 20 : 45)) continue;
            sum.r += c.r; sum.g += c.g; sum.b += c.b; ++count;
        }
        return {sum.r / count, sum.g / count, sum.b / count};
    }
    float orientation(const Stroke& mark, int layer) const
    {
        // Local structure tensor stabilizes the direction around object contours.
        float xx = 0, yy = 0, xy = 0;
        const int offset = std::max(1, mark.radius / 3);
        const int gradient_step = layer >= 3 ? 1 : 3;
        for (int dy = -1; dy <= 1; ++dy) for (int dx = -1; dx <= 1; ++dx) {
            const int x = mark.x + dx * offset, y = mark.y + dy * offset;
            const float gx = light(target(x + gradient_step, y, layer)) - light(target(x - gradient_step, y, layer));
            const float gy = light(target(x, y + gradient_step, layer)) - light(target(x, y - gradient_step, layer));
            xx += gx * gx; yy += gy * gy; xy += gx * gy;
        }
        const float energy = xx + yy;
        const float coherence = std::sqrt((xx - yy) * (xx - yy) + 4 * xy * xy) / (energy + 1);
        if (energy > 500 && coherence > 0.3f)
            return 0.5f * std::atan2(2 * xy, xx - yy) + 1.570796327f + noise(mark.x * 0.035f, mark.seed) * 0.12f;
        // A low-frequency flow for quiet areas, instead of independent rotations.
        return -0.25f + 0.55f * noise(mark.x / 85.0f, 91) + 0.40f * noise(mark.y / 95.0f, 217)
            + ((unit(mark.seed + 113) - 0.5f) * 1.1f);
    }
    void stroke(const Stroke& mark, int layer)
    {
        const float r = mark.radius * (0.80f + 0.40f * unit(mark.seed));
        const float angle = orientation(mark, layer);
        const float cosine = std::cos(angle), sine = std::sin(angle);
        const float initial_long = r * (1.25f + 0.4f * unit(mark.seed + 3));
        const float initial_wide = r * (0.65f + 0.25f * unit(mark.seed + 7));
        const int limits[] = {80, 62, 48, 26, 18};
        // Fit the footprint BEFORE painting. Never cut a completed stroke into
        // a source-shaped set of disconnected pixels with per-pixel color gates.
        const auto fit = [&](float dx, float dy, float length) {
            // Probe four axis paths, not only endpoints. This is not a full
            // two-dimensional footprint test; oblique thin edges may remain.
            const float increment = layer >= 3 ? 1.0f : 2.0f;
            for (float distance = increment; distance <= length; distance += increment)
                if (difference(mark.color, target(static_cast<int>(std::lround(mark.x + dx * distance)),
                    static_cast<int>(std::lround(mark.y + dy * distance)), layer)) > limits[layer])
                    return std::max(0.75f, distance - increment * 0.5f);
            return length;
        };
        const float forward = fit(cosine, sine, initial_long);
        const float backward = fit(-cosine, -sine, initial_long);
        const float upper = fit(-sine, cosine, initial_wide);
        const float lower = fit(sine, -cosine, initial_wide);
        const float half_length = (forward + backward) * 0.5f;
        const float center_u = (forward - backward) * 0.5f;
        const float half_width = (upper + lower) * 0.5f;
        const float center_v = (upper - lower) * 0.5f;
        const int extent = static_cast<int>(initial_long + initial_wide + 3);
        const float bend = r * 0.13f * noise(0.3f, mark.seed + 19);
        const float variation = noise(0.8f, mark.seed + 101) * 2;
        const bool quiet = contrast(mark.x, mark.y, std::max(2, mark.radius), layer) < 22;
        const float opacity = quiet ? 0.65f : 0.93f + 0.06f * unit(mark.seed + 23);
        for (int y = std::max(0, mark.y - extent); y <= std::min(height - 1, mark.y + extent); ++y) {
            if ((y & 7) == 0) cooperate();
            for (int x = std::max(0, mark.x - extent); x <= std::min(width - 1, mark.x + extent); ++x) {
                const float dx = x - mark.x, dy = y - mark.y;
                const float u = dx * cosine + dy * sine - center_u;
                float v = -dx * sine + dy * cosine - center_v;
                const float un = u / half_length;
                if (std::abs(un) > 1.2f) continue;
                v -= bend * (1 - un * un);
                // Smooth pressure variation and irregular brush tips. The mask
                // has an opaque flat center and only a narrow antialiased edge.
                const float taper = 1 - (un + 1) * 0.075f;
                const float side = taper * (1 + 0.12f * noise(un * 2 + 3, mark.seed + 29)
                                              + 0.035f * noise(un * 7 + 10, mark.seed + 31));
                const float across = v / half_width;
                const float tip = 1 + (un > 0 ? 0.12f : 0.065f) * noise(across * 3 + 4, mark.seed + 37)
                                    + 0.035f * noise(across * 11 + 20, mark.seed + 41);
                const float a = std::abs(un / tip);
                const float b = std::abs(v / (half_width * side));
                const float a2 = a * a, b2 = b * b;
                const float contour = a2 * a2 * a2 + b2 * b2;
                const float coverage = std::max(0.0f, std::min(1.0f,
                    (1 - contour) * std::min(half_width, half_length) * 0.65f + 0.5f));
                if (coverage <= 0) continue;
                const float grain = noise(across * 3 + 6, mark.seed + 53);
                const float bristles = noise(v * 0.7f + 32, mark.seed + 59);
                const int shade = quiet ? 0 : static_cast<int>(std::lround(variation + grain * 2.0f));
                const Color paint{mark.color.r + shade, mark.color.g + shade, mark.color.b + shade};
                const size_t index = static_cast<size_t>(y) * width + x;
                const float dry_tip = std::max(0.0f, un - 0.25f) * 0.20f;
                const float deposit = 1 - dry_tip * (bristles + 1) * 0.5f;
                output[index] = encode(mix(decode(output[index]), paint, opacity * coverage * deposit));
            }
        }
    }
    void render()
    {
        const int radii[] = {26, 15, 9, 4, 2};
        const int thresholds[] = {7, 12, 17, 20, 16};
        for (int layer = 0; layer < 5; ++layer) {
            const int r = scaled(radii[layer]), step = std::max(2, r * 5 / 4);
            size_t size = 0;
            for (int y = step / 2; y < height; y += step) for (int x = step / 2; x < width; x += step) {
                const int cx = clamp(x + static_cast<int>(random_word(random_state) % step) - step / 2, 0, width - 1);
                const int cy = clamp(y + static_cast<int>(random_word(random_state) % step) - step / 2, 0, height - 1);
                marks[size++] = {cx, cy, r, {}, random_word(random_state)};
                if ((size & 255U) == 0) cooperate();
            }
            for (size_t i = size; i > 1; --i) {
                std::swap(marks[i - 1], marks[random_word(random_state) % i]);
                if ((i & 255U) == 0) cooperate();
            }
            const bool fine_pass = layer >= 3;
            if (fine_pass) {
                // Spend a bounded detail budget on errors near structure first.
                // Stable sorting preserves seeded order for equal priorities.
                for (size_t i = 0; i < size; ++i) {
                    auto& mark = marks[i];
                    mark.order = static_cast<int>(i);
                    if ((i & 63U) == 0) cooperate();
                    const int error = difference(target(mark.x, mark.y, layer), decode(output[mark.y * width + mark.x]));
                    const int structure = contrast(mark.x, mark.y, 2, layer);
                    mark.priority = error * std::min(structure, 80);
                }
                size_t comparisons = 0;
                // Total-order tie breaker preserves seeded stable ordering
                // without stable_sort's hidden heap allocation.
                std::sort(marks, marks + size, [&](const Stroke& a, const Stroke& b) {
                    if ((++comparisons & 255U) == 0) cooperate();
                    return a.priority != b.priority ? a.priority > b.priority : a.order < b.order;
                });
            }
            size_t painted = 0;
            const size_t budget = fine_pass ? std::max(1, width * height / (layer == 3 ? 85 : 110)) : size;
            for (size_t i = 0; i < size; ++i) {
                auto mark = marks[i];
                if ((i & 31U) == 0) cooperate();
                if (painted >= budget) break;
                int best = -1;
                int total = 0, cx = mark.x, cy = mark.y;
                // Re-evaluate against the LIVE painting after earlier strokes.
                // Mean error prevents a lone noisy pixel from repainting a region.
                for (int dy = -1; dy <= 1; ++dy) for (int dx = -1; dx <= 1; ++dx) {
                    const int px = clamp(mark.x + dx * step / 3, 0, width - 1);
                    const int py = clamp(mark.y + dy * step / 3, 0, height - 1);
                    const int error = difference(target(px, py, layer), decode(output[py * width + px]));
                    if (error > best) { best = error; cx = px; cy = py; }
                    total += error;
                }
                if (total / 9 < thresholds[layer] && best < thresholds[layer] * 3) continue;
                if (layer > 0) { mark.x = cx; mark.y = cy; }
                // The extra detail pass is structural, not full-frame texture.
                if (fine_pass && contrast(mark.x, mark.y, 2, layer) < (layer == 3 ? 18 : 30)) continue;
                mark.color = patch(mark.x, mark.y, r, layer);
                stroke(mark, layer);
                ++painted;
            }
            counts[layer] = static_cast<uint32_t>(painted);
            cooperate();
        }
    }
};
}

size_t papercolor_stacked_workspace_size(int w, int h)
{
    if (w < 1 || h < 1 || w > 600 || h > 600) return 0;
    const auto aligned = [](size_t n) { return (n + 3) & ~size_t(3); };
    const int grid = std::max(1, static_cast<int>(std::lround(24 * std::max(0.35f, std::min(w, h) / 400.0f))));
    return aligned(((w + 2) / 3) * ((h + 2) / 3) * sizeof(uint16_t)) +
           2 * aligned(w * h * sizeof(uint16_t)) +
           aligned((w / grid + 2) * (h / grid + 2) * sizeof(Color)) +
           static_cast<size_t>(w / 2) * (h / 2) * sizeof(Stroke);
}

bool papercolor_stacked_render_swap565(const uint16_t* source, uint16_t* destination,
    int width, int height, int stride, PaperColorOilRect rect,
    const PaperColorStackedOptions& options, void* workspace, size_t workspace_size,
    PaperColorStackedStats* stats)
{
    if (!source || !destination || !workspace || width < 1 || height < 1 ||
        width > 600 || height > 600 || stride < width ||
        rect.x < 0 || rect.y < 0 || rect.width < 1 || rect.height < 1 ||
        rect.x > width - rect.width || rect.y > height - rect.height) return false;
    const size_t needed = papercolor_stacked_workspace_size(rect.width, rect.height);
    if (!needed || workspace_size < needed ||
        static_cast<size_t>(stride) > std::numeric_limits<size_t>::max() / height / sizeof(uint16_t)) return false;
    const size_t bytes = static_cast<size_t>(stride) * height * sizeof(uint16_t);
    const uintptr_t src = reinterpret_cast<uintptr_t>(source), dst = reinterpret_cast<uintptr_t>(destination);
    const uintptr_t work = reinterpret_cast<uintptr_t>(workspace);
    if ((src % alignof(uint16_t)) || (dst % alignof(uint16_t)) || (work % alignof(uint32_t)) ||
        src > UINTPTR_MAX - bytes || dst > UINTPTR_MAX - bytes || work > UINTPTR_MAX - workspace_size ||
        (src < dst + bytes && dst < src + bytes) ||
        (src < work + workspace_size && work < src + bytes) ||
        (dst < work + workspace_size && work < dst + bytes)) return false;

    Painter painter(rect.width, rect.height, source, stride, rect, workspace, options);
    painter.render();
    for (int y = 0; y < height; ++y) {
        std::memcpy(destination + static_cast<size_t>(y) * stride,
                    source + static_cast<size_t>(y) * stride, static_cast<size_t>(stride) * sizeof(uint16_t));
        if (options.cooperate) options.cooperate(options.cooperate_context);
    }
    for (int y = 0; y < rect.height; ++y) {
        std::memcpy(destination + static_cast<size_t>(y + rect.y) * stride + rect.x,
                    painter.output + y * rect.width, rect.width * sizeof(uint16_t));
        if (options.cooperate) options.cooperate(options.cooperate_context);
    }
    if (stats) {
        for (int i = 0; i < 5; ++i) stats->strokes[i] = painter.counts[i];
        stats->workspace_bytes = needed;
    }
    return true;
}
