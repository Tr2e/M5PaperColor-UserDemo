// Host-only experiment: constrain the target's neutral-white budget before
// quantization. This is NOT measured calibration and is not linked by firmware.
#ifdef ESP_PLATFORM
#error "The white-budget candidate is offline-only until physical validation"
#endif
#include "display/papercolor_gamut.h"

namespace papercolor_gamut {
inline Point project_with_white_budget(Point p, const Point* vertices, size_t count)
{
#ifdef PAPERCOLOR_PRIMARY_BUDGET_ONLY
    // Keep all two-pigment/neutral targets unchanged. Restrict only the existing
    // black + white + one chromatic-pigment sectors, without per-color offsets.
    if (count != 3) return project(p, vertices, count);
#endif
    // In the existing nominal RGB model, white adds equally to all channels.
    // Permit at most the neutral component of the already-compensated target.
    // This is a testable rendering-policy choice, not a physical mixing law.
    float neutral = p.x < p.y ? p.x : p.y;
    neutral = neutral < p.z ? neutral : p.z;
    const float budget = neutral / 255.0f;
    if (budget >= 1.0f || count > 6) return project(p, vertices, count);
    Point restricted[10];
    size_t n = 0;
    bool has_white = false;
    for (size_t i = 0; i < count; ++i) {
        const auto v = vertices[i];
        if (v.x == 255 && v.y == 255 && v.z == 255) {
            has_white = true;
        } else {
            restricted[n++] = v;
        }
    }
    if (!has_white || n == 0) return project(p, vertices, count);
    const size_t pigments = n;
    if (budget > 0) {
        for (size_t i = 0; i < pigments; ++i) {
            restricted[n++] = add(mul(restricted[i], 1 - budget),
                                  {neutral, neutral, neutral});
        }
    }
    // The clipped simplex is the convex hull of the non-white vertices and
    // their intersections with the white-weight budget plane.
    return project(p, restricted, n);
}
}

// Reuse the exact current parser, hue guards, source compensation, Q4 error
// diffusion and LUT selection. Override only the gamut target for host A/B.
// The gamut header is already included above, so its implementation is intact.
#define project project_with_white_budget
#include "display/papercolor_photo_dither.cpp"
#undef project
