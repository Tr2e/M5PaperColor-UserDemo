/* SPDX-License-Identifier: MIT */
#pragma once

#include "display/papercolor_gamut.h"

namespace papercolor_gamut {

inline float warm_ratio_smoothstep(float value)
{
    if (value <= 0.0f) return 0.0f;
    if (value >= 1.0f) return 1.0f;
    return value * value * (3.0f - 2.0f * value);
}

// Generalize IMG_9963's patch-14/15 B choices across saturated orange and
// red-orange. Transfer at most 1/16 of red/yellow chromatic coverage from
// yellow to red, preserving white, black and total coverage. Smooth source
// hue and saturation fades protect warm yellow, pure red and near-neutrals;
// pigment availability makes the transfer vanish at either gamut edge.
inline Point refine_warm_red_yellow_ratio(Point original, Point projected)
{
    const float red_chroma = original.x - original.z;
    const float green_chroma = original.y - original.z;
    if (red_chroma <= 0.0f || green_chroma <= 0.0f ||
        green_chroma >= red_chroma || original.x <= 0.0f) {
        return projected;
    }

    const float ratio = green_chroma / red_chroma;
    const float hue_enter = warm_ratio_smoothstep((ratio - 0.08f) / 0.10f);
    const float hue_leave =
        1.0f - warm_ratio_smoothstep((ratio - 0.45f) / 0.18f);
    const float saturation = red_chroma / original.x;
    const float saturation_fade =
        warm_ratio_smoothstep((saturation - 0.35f) / 0.25f);
    const float window = hue_enter * hue_leave * saturation_fade;
    if (window <= 0.0f) {
        return projected;
    }

    const Point white{255, 255, 255};
    const Point yellow{255, 243, 56};
    const Point red{191, 0, 0};
    const float determinant = dot(white, cross(yellow, red));
    const float yellow_weight = dot(white, cross(projected, red)) / determinant;
    const float red_weight = dot(white, cross(yellow, projected)) / determinant;
    if (yellow_weight <= 0.0f || red_weight <= 0.0f) {
        return projected;
    }

    const float total = yellow_weight + red_weight;
    const float smaller = yellow_weight < red_weight ? yellow_weight : red_weight;
    const float availability =
        warm_ratio_smoothstep(smaller / (total * 0.15f));
    const float transfer = total * 0.0625f * window * availability;
    return add(projected, mul(sub(red, yellow), transfer));
}

}  // namespace papercolor_gamut
