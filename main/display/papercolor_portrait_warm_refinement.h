/* SPDX-License-Identifier: MIT */
#pragma once

#include "display/papercolor_warm_ratio_refinement.h"

namespace papercolor_gamut {

// Shift a small amount of yellow coverage to red in moderately light,
// low-chroma warm mixtures. This is a portrait regression candidate motivated
// by IMG_9970; it preserves black, white and total chromatic coverage.
inline Point refine_portrait_warm_ratio(Point original, Point projected,
                                        float maximum_transfer_fraction = 0.0625f)
{
    const float red_chroma = original.x - original.z;
    const float green_chroma = original.y - original.z;
    if (red_chroma <= 0.0f || green_chroma <= 0.0f ||
        green_chroma >= red_chroma || original.x <= 0.0f ||
        maximum_transfer_fraction <= 0.0f) {
        return projected;
    }

    const float ratio = green_chroma / red_chroma;
    const float hue_enter = warm_ratio_smoothstep((ratio - 0.22f) / 0.16f);
    const float hue_leave =
        1.0f - warm_ratio_smoothstep((ratio - 0.62f) / 0.18f);
    const float saturation = red_chroma / original.x;
    const float saturation_enter =
        warm_ratio_smoothstep((saturation - 0.10f) / 0.12f);
    const float saturation_leave =
        1.0f - warm_ratio_smoothstep((saturation - 0.36f) / 0.18f);
    const float lightness = warm_ratio_smoothstep((original.x - 72.0f) / 72.0f);
    const float window =
        hue_enter * hue_leave * saturation_enter * saturation_leave * lightness;
    if (window <= 0.0f) return projected;

    const Point white{255, 255, 255};
    const Point yellow{255, 243, 56};
    const Point red{191, 0, 0};
    const float determinant = dot(white, cross(yellow, red));
    const float yellow_weight = dot(white, cross(projected, red)) / determinant;
    const float red_weight = dot(white, cross(yellow, projected)) / determinant;
    if (yellow_weight <= 0.0f || red_weight <= 0.0f) return projected;

    const float total = yellow_weight + red_weight;
    const float smaller = yellow_weight < red_weight ? yellow_weight : red_weight;
    const float availability = warm_ratio_smoothstep(smaller / (total * 0.15f));
    const float transfer =
        total * maximum_transfer_fraction * window * availability;
    return add(projected, mul(sub(red, yellow), transfer));
}

}  // namespace papercolor_gamut
