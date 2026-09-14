/* SPDX-License-Identifier: MIT */
#pragma once

#include "display/papercolor_gamut.h"

namespace papercolor_gamut {

inline float deep_purple_smoothstep(float value)
{
    if (value <= 0.0f) return 0.0f;
    if (value >= 1.0f) return 1.0f;
    return value * value * (3.0f - 2.0f * value);
}

// Generalize IMG_9961's patch-09 B choice within a smooth mid/deep-purple
// window. Convert at most half of the current white target into the existing
// red/blue mixture, preserving its hue ratio and black coverage. The source
// lightness window keeps the same-hue darker patch 18 unchanged and fades
// before the lighter patch 17; hue and saturation fades protect magenta and
// near-neutral colors.
inline Point refine_deep_purple_white(Point original, Point projected)
{
    const float red_chroma = original.x - original.y;
    const float blue_chroma = original.z - original.y;
    if (red_chroma <= 0.0f || blue_chroma <= red_chroma || original.z <= 0.0f) {
        return projected;
    }

    const float ratio = red_chroma / blue_chroma;
    const float hue_enter = deep_purple_smoothstep((ratio - 0.32f) / 0.12f);
    const float hue_leave = 1.0f - deep_purple_smoothstep((ratio - 0.52f) / 0.10f);
    const float light_enter = deep_purple_smoothstep((original.z - 116.0f) / 36.0f);
    const float light_leave =
        1.0f - deep_purple_smoothstep((original.z - 176.0f) / 32.0f);
    const float saturation = blue_chroma / original.z;
    const float saturation_fade =
        deep_purple_smoothstep((saturation - 0.35f) / 0.25f);
    const float window = hue_enter * hue_leave * light_enter * light_leave * saturation_fade;
    if (window <= 0.0f) {
        return projected;
    }

    const Point white{255, 255, 255};
    const Point red{191, 0, 0};
    const Point blue{100, 64, 255};
    const float determinant = dot(white, cross(red, blue));
    const float white_weight = dot(projected, cross(red, blue)) / determinant;
    const float red_weight = dot(white, cross(projected, blue)) / determinant;
    const float blue_weight = dot(white, cross(red, projected)) / determinant;
    if (white_weight <= 0.0f || red_weight <= 0.0f || blue_weight <= 0.0f) {
        return projected;
    }

    const float total = red_weight + blue_weight;
    const float smaller = red_weight < blue_weight ? red_weight : blue_weight;
    const float availability = deep_purple_smoothstep(smaller / (total * 0.15f));
    const float removed = white_weight * 0.5f * window * availability;
    const Point mixture = mul(
        add(mul(red, red_weight), mul(blue, blue_weight)), 1.0f / total);
    return add(projected, mul(sub(mixture, white), removed));
}

}  // namespace papercolor_gamut
