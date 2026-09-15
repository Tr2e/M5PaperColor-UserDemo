// Isolated host experiment, forked from the accepted stacked prototype.
// Never enabled in firmware. Both study switches off must replay its pixels.
#include "display/papercolor_oil_painter.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

// Compile-time ablations for the host lab, not firmware feature switches.
#ifndef PAINT_DETAIL
#define PAINT_DETAIL 1
#endif
#ifndef PAINT_SCALE
#define PAINT_SCALE 1
#endif
#ifndef PAINT_QUIET
#define PAINT_QUIET 1
#endif
#ifndef PAINT_BACKGROUND_CONTROL
#define PAINT_BACKGROUND_CONTROL 1
#endif
#ifndef PAINT_SOFT_EDGES
#define PAINT_SOFT_EDGES 1
#endif

namespace {
struct Color { int r, g, b; };
struct Stroke { int x, y, radius; Color color; uint32_t seed; int priority = 0; };
uint32_t random_state = 0x5041494e;
uint32_t random_word()
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
    std::vector<uint16_t> reference, detail, output;
    std::vector<uint8_t> quiet_map;
    explicit Painter(int w, int h, const std::vector<uint16_t>& source)
        : width(w), height(h), aw((w + 2) / 3), ah((h + 2) / 3),
          reference(aw * ah), detail(PAINT_DETAIL ? w * h : 0), output(w * h)
    {
        // Keep a full-resolution, mildly denoised target for small marks.
        // Edge-aware averaging avoids erasing thin highlights before rendering.
        if (PAINT_DETAIL) for (int y = 0; y < h; ++y) for (int x = 0; x < w; ++x) {
            const Color center = decode(source[y * w + x]);
            Color sum{center.r * 4, center.g * 4, center.b * 4};
            int count = 4;
            for (int dy = -1; dy <= 1; ++dy) for (int dx = -1; dx <= 1; ++dx) {
                if (!dx && !dy) continue;
                const Color c = decode(source[clamp(y + dy, 0, h - 1) * w + clamp(x + dx, 0, w - 1)]);
                if (difference(c, center) > 32) continue;
                sum.r += c.r; sum.g += c.g; sum.b += c.b; ++count;
            }
            detail[y * w + x] = encode({sum.r / count, sum.g / count, sum.b / count});
        }
        for (int y = 0; y < ah; ++y) for (int x = 0; x < aw; ++x) {
            Color sum{};
            for (int dy = -2; dy <= 2; ++dy) for (int dx = -2; dx <= 2; ++dx) {
                const Color c = decode(source[clamp(y * 3 + dy, 0, height - 1) * width +
                                                clamp(x * 3 + dx, 0, width - 1)]);
                sum.r += c.r; sum.g += c.g; sum.b += c.b;
            }
            reference[y * aw + x] = encode({sum.r / 25, sum.g / 25, sum.b / 25});
        }
        // Conservative local flatness, NOT semantic background segmentation.
        // A neighbourhood maximum protects thin boundaries before interpolation.
        if (PAINT_BACKGROUND_CONTROL || PAINT_SOFT_EDGES) {
            quiet_map.resize(aw * ah);
            const int reach = scaled(9);
            for (int y = 0; y < ah; ++y) for (int x = 0; x < aw; ++x) {
                const Color center = sample(x * 3, y * 3);
                int span = 0;
                for (int dy = -2; dy <= 2; ++dy) for (int dx = -2; dx <= 2; ++dx)
                    span = std::max(span, difference(center,
                        sample(x * 3 + dx * reach / 2, y * 3 + dy * reach / 2)));
                float t = std::max(0.0f, std::min(1.0f, (36 - span) / 28.0f));
                t = t * t * (3 - 2 * t);
                quiet_map[y * aw + x] = static_cast<uint8_t>(std::lround(t * 255));
            }
        }
        // A broad underpainting. Bilinear reconstruction avoids visible 3px
        // squares and leaves real reconstruction work for the large brushes.
        const int grid = scaled(24);
        const int gw = (width + grid - 1) / grid + 1;
        const int gh = (height + grid - 1) / grid + 1;
        std::vector<Color> ground(gw * gh);
        for (int y = 0; y < gh; ++y) for (int x = 0; x < gw; ++x) {
            Color sum{};
            for (int dy = -2; dy <= 2; ++dy) for (int dx = -2; dx <= 2; ++dx) {
                const Color c = sample(x * grid + dx * 6, y * grid + dy * 6);
                sum.r += c.r; sum.g += c.g; sum.b += c.b;
            }
            ground[y * gw + x] = {sum.r / 25, sum.g / 25, sum.b / 25};
        }
        for (int y = 0; y < height; ++y) for (int x = 0; x < width; ++x) {
            const int gx = x / grid, gy = y / grid;
            const float fx = static_cast<float>(x % grid) / grid;
            const float fy = static_cast<float>(y % grid) / grid;
            Color ground_color = mix(
                mix(ground[gy * gw + gx], ground[gy * gw + gx + 1], fx),
                mix(ground[(gy + 1) * gw + gx], ground[(gy + 1) * gw + gx + 1], fx), fy);
            if (PAINT_BACKGROUND_CONTROL) {
                const float q = quietness(x, y);
                // Preserve smooth source gradations in the ground; foreground
                // still needs the original coarse-to-fine opaque construction.
                ground_color = mix(ground_color, sample(x, y), 0.80f * q * q);
            }
            output[y * width + x] = encode(ground_color);
        }
    }
    float quietness(int x, int y) const
    {
        if (quiet_map.empty()) return 0;
        x = clamp(x, 0, width - 1); y = clamp(y, 0, height - 1);
        const int x0 = x / 3, y0 = y / 3;
        const int x1 = std::min(aw - 1, x0 + 1), y1 = std::min(ah - 1, y0 + 1);
        const float fx = (x % 3) / 3.0f, fy = (y % 3) / 3.0f;
        const float top = quiet_map[y0 * aw + x0] * (1 - fx) + quiet_map[y0 * aw + x1] * fx;
        const float bottom = quiet_map[y1 * aw + x0] * (1 - fx) + quiet_map[y1 * aw + x1] * fx;
        return (top * (1 - fy) + bottom * fy) / 255.0f;
    }
    int scaled(int radius) const
    {
        const float scale = PAINT_SCALE ? std::max(0.35f, std::min(width, height) / 400.0f) : 1.0f;
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
        if (PAINT_DETAIL && layer >= 3)
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
            if (difference(c, center) > (PAINT_DETAIL && layer >= 3 ? 20 : 45)) continue;
            sum.r += c.r; sum.g += c.g; sum.b += c.b; ++count;
        }
        return {sum.r / count, sum.g / count, sum.b / count};
    }
    float orientation(const Stroke& mark, int layer) const
    {
        // Local structure tensor stabilizes the direction around object contours.
        float xx = 0, yy = 0, xy = 0;
        const int offset = std::max(PAINT_DETAIL ? 1 : 2, mark.radius / 3);
        const int gradient_step = PAINT_DETAIL && layer >= 3 ? 1 : 3;
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
            + (PAINT_QUIET ? (unit(mark.seed + 113) - 0.5f) * 1.1f : 0);
    }
    void stroke(const Stroke& mark, int layer)
    {
        const float r = mark.radius * (0.80f + 0.40f * unit(mark.seed));
        const float angle = orientation(mark, layer);
        const float cosine = std::cos(angle), sine = std::sin(angle);
        const float initial_long = r * (1.25f + 0.4f * unit(mark.seed + 3));
        const float initial_wide = r * (0.65f + 0.25f * unit(mark.seed + 7));
        const int limits[] = {80, 62, 48, PAINT_DETAIL ? 26 : 36, 18};
        // Fit the footprint BEFORE painting. Never cut a completed stroke into
        // a source-shaped set of disconnected pixels with per-pixel color gates.
        const auto fit = [&](float dx, float dy, float length) {
            if (PAINT_DETAIL) {
                // March through the footprint, not just its endpoint: a thin
                // edge may otherwise be crossed and end in a similar color.
                const float increment = layer >= 3 ? 1.0f : 2.0f;
                for (float distance = increment; distance <= length; distance += increment)
                    if (difference(mark.color, target(static_cast<int>(std::lround(mark.x + dx * distance)),
                        static_cast<int>(std::lround(mark.y + dy * distance)), layer)) > limits[layer])
                        return std::max(0.75f, distance - increment * 0.5f);
                return length;
            }
            while (length > 2.5f && difference(mark.color, sample(
                static_cast<int>(mark.x + dx * length), static_cast<int>(mark.y + dy * length))) > limits[layer])
                length *= 0.80f;
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
        const bool quiet = PAINT_QUIET && contrast(mark.x, mark.y, std::max(2, mark.radius), layer) < 22;
        const float opacity = quiet ? 0.65f : 0.93f + 0.06f * unit(mark.seed + 23);
        // Only coarse marks in low-variation regions get a wider feather.
        // Fine structural strokes retain the accepted, opaque, hard-edged mask.
        const float softness = PAINT_SOFT_EDGES && layer < 3 ? 0.85f * quietness(mark.x, mark.y) : 0;
        for (int y = std::max(0, mark.y - extent); y <= std::min(height - 1, mark.y + extent); ++y) {
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
                float coverage = std::max(0.0f, std::min(1.0f,
                    (1 - contour) * std::min(half_width, half_length) * 0.65f + 0.5f));
                if (softness > 0) {
                    float feather = std::max(0.0f, std::min(1.0f, (1 - contour) / 0.80f));
                    feather = feather * feather * (3 - 2 * feather);
                    coverage += (feather - coverage) * softness;
                }
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
        const int radii[] = {26, 15, 9, PAINT_DETAIL ? 4 : 5, 2};
        const int thresholds[] = {7, 12, 17, PAINT_DETAIL ? 20 : 23, 16};
        for (int layer = 0; layer < (PAINT_DETAIL ? 5 : 4); ++layer) {
            const int r = scaled(radii[layer]), step = std::max(2, r * 5 / 4);
            std::vector<Stroke> strokes;
            for (int y = step / 2; y < height; y += step) for (int x = step / 2; x < width; x += step) {
                const int cx = clamp(x + static_cast<int>(random_word() % step) - step / 2, 0, width - 1);
                const int cy = clamp(y + static_cast<int>(random_word() % step) - step / 2, 0, height - 1);
                strokes.push_back({cx, cy, r, {}, random_word()});
            }
            for (size_t i = strokes.size(); i > 1; --i) std::swap(strokes[i - 1], strokes[random_word() % i]);
            const bool fine_pass = PAINT_DETAIL && layer >= 3;
            if (fine_pass) {
                // Spend a bounded detail budget on errors near structure first.
                // Stable sorting preserves seeded order for equal priorities.
                for (auto& mark : strokes) {
                    const int error = difference(target(mark.x, mark.y, layer), decode(output[mark.y * width + mark.x]));
                    const int structure = contrast(mark.x, mark.y, 2, layer);
                    mark.priority = error * std::min(structure, 80);
                }
                std::stable_sort(strokes.begin(), strokes.end(), [](const Stroke& a, const Stroke& b) {
                    return a.priority > b.priority;
                });
            }
            size_t painted = 0;
            const size_t budget = fine_pass ? std::max(1, width * height / (layer == 3 ? 85 : 110)) : strokes.size();
            for (auto mark : strokes) {
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
                if (PAINT_BACKGROUND_CONTROL && layer > 0 && layer < 3) {
                    const int threshold = thresholds[layer] + static_cast<int>(6 * quietness(mark.x, mark.y));
                    if (total / 9 < threshold && best < threshold * 3) continue;
                }
                // The extra detail pass is structural, not full-frame texture.
                if (fine_pass && contrast(mark.x, mark.y, 2, layer) < (layer == 3 ? 18 : 30)) continue;
                mark.color = patch(mark.x, mark.y, r, layer);
                stroke(mark, layer);
                ++painted;
            }
            std::fprintf(stderr, "layer=%d radius=%d strokes=%zu candidates=%zu budget=%zu\n", layer, r, painted, strokes.size(), budget);
        }
    }
};
}

int main(int argc, char** argv)
{
    if (argc != 3) return 2;
    std::ifstream in(argv[1], std::ios::binary);
    int width = 0, height = 0, maximum = 0;
    std::string magic;
    in >> magic >> width >> height >> maximum;
    in.get();
    if (!in || magic != "P6" || maximum != 255 || width < 1 || height < 1 || width > 600 || height > 600) return 2;
    std::vector<uint8_t> rgb(width * height * 3);
    in.read(reinterpret_cast<char*>(rgb.data()), rgb.size());
    if (in.gcount() != static_cast<std::streamsize>(rgb.size())) return 2;
    std::vector<uint16_t> source(width * height);
    for (size_t i = 0; i < source.size(); ++i) source[i] = encode({rgb[i * 3], rgb[i * 3 + 1], rgb[i * 3 + 2]});
    Painter painter(width, height, source);
    painter.render();
    for (size_t i = 0; i < source.size(); ++i) {
        const Color color = decode(painter.output[i]);
        rgb[i * 3] = color.r; rgb[i * 3 + 1] = color.g; rgb[i * 3 + 2] = color.b;
    }
    std::ofstream out(argv[2], std::ios::binary);
    out << "P6\n" << width << ' ' << height << "\n255\n";
    out.write(reinterpret_cast<const char*>(rgb.data()), rgb.size());
    return out ? 0 : 1;
}
