/* SPDX-License-Identifier: MIT */
#pragma once

#include "display/papercolor_gamut.h"

namespace papercolor_gamut {

inline float green_pair_smoothstep(float value)
{
    if (value <= 0.0f) {
        return 0.0f;
    }
    if (value >= 1.0f) {
        return 1.0f;
    }
    return value * value * (3.0f - 2.0f * value);
}

inline float pigment_availability(float first, float second)
{
    const float total = first + second;
    if (total <= 0.0f) {
        return 0.0f;
    }
    const float smaller = first < second ? first : second;
    return green_pair_smoothstep(smaller / (total * 0.15f));
}

// Generalize IMG_9959's lime B choice. The correction starts with zero slope
// at the yellow/lime mask boundary, reaches the measured comparison strength
// for green-dominant lime, and fades as either pigment becomes unavailable.
inline Point refine_lime_ratio(Point original, Point projected)
{
    const float red = original.x - original.z;
    const float green_source = original.y - original.z;
    if (red <= 0.0f || green_source <= red || green_source <= 24.0f) {
        return projected;
    }

    const Point white{255, 255, 255};
    const Point yellow{255, 243, 56};
    const Point green{67, 138, 28};
    const float determinant = dot(white, cross(green, yellow));
    const float green_weight = dot(white, cross(projected, yellow)) / determinant;
    const float yellow_weight = dot(white, cross(green, projected)) / determinant;
    if (green_weight <= 0.0f || yellow_weight <= 0.0f) {
        return projected;
    }

    const float dominance = (green_source - red) / green_source;
    const float hue = green_pair_smoothstep(dominance / 0.35f);
    const float chroma = green_pair_smoothstep((green_source - 24.0f) / 104.0f);
    const float yellow_source = green_pair_smoothstep(red / 24.0f);
    const float total = green_weight + yellow_weight;
    const float transfer = total * 0.0625f * hue * chroma * yellow_source *
                           pigment_availability(green_weight, yellow_weight);
    return add(projected, mul(sub(green, yellow), transfer));
}

inline float teal_window(Point original)
{
    const float green_source = original.y - original.x;
    const float blue_source = original.z - original.x;
    if (green_source <= 24.0f || blue_source <= 0.0f ||
        blue_source >= green_source) {
        return 0.0f;
    }

    const float ratio = blue_source / green_source;
    const float enter = green_pair_smoothstep((ratio - 0.20f) / 0.20f);
    const float leave = 1.0f - green_pair_smoothstep((ratio - 0.65f) / 0.10f);
    const float chroma = green_pair_smoothstep((green_source - 24.0f) / 80.0f);
    return enter * leave * chroma;
}

inline float teal_blue_availability(float green_weight, float blue_weight)
{
    const float total = green_weight + blue_weight;
    if (total <= 0.0f || blue_weight <= 0.0f) {
        return 0.0f;
    }
    const float blue_fraction = blue_weight / total;
    return blue_fraction >= 0.225f ? 1.0f : blue_fraction / 0.225f;
}

// Generalize IMG_9959's teal ratio B choice below the existing near-cyan
// window. White and total coverage remain fixed; the transfer fades to zero
// before balance_cyan_ratio() begins.
inline Point refine_teal_ratio(Point original, Point projected)
{
    const float window = teal_window(original);
    if (window <= 0.0f) {
        return projected;
    }

    const Point white{255, 255, 255};
    const Point green{67, 138, 28};
    const Point blue{100, 64, 255};
    const float determinant = dot(white, cross(green, blue));
    const float green_weight = dot(white, cross(projected, blue)) / determinant;
    const float blue_weight = dot(white, cross(green, projected)) / determinant;
    if (green_weight <= 0.0f || blue_weight < 0.0f) {
        return projected;
    }

    const float total = green_weight + blue_weight;
    const float availability = teal_blue_availability(green_weight, blue_weight);
    const float transfer = total * 0.0625f * window * availability;
    return add(projected, mul(sub(blue, green), transfer));
}

// Generalize IMG_9959's teal-white B choice after the ratio correction.
// Convert at most 40% of white into the same green/blue mixture, preserving
// the corrected hue ratio and black coverage. This keeps the selected B
// direction while avoiding new RGB565 boundary steps in lighter teals.
inline Point refine_teal_white(Point original, Point projected)
{
    const float chroma = original.y - original.x;
    const float saturation = original.y > 0.0f ? chroma / original.y : 0.0f;
    const float saturation_fade =
        green_pair_smoothstep((saturation - 0.40f) / 0.25f);
    const float light_teal_fade =
        1.0f - green_pair_smoothstep((original.x - 56.0f) / 24.0f);
    const float window = teal_window(original) * saturation_fade * light_teal_fade;
    if (window <= 0.0f) {
        return projected;
    }

    const Point white{255, 255, 255};
    const Point green{67, 138, 28};
    const Point blue{100, 64, 255};
    const float determinant = dot(white, cross(green, blue));
    const float white_weight = dot(projected, cross(green, blue)) / determinant;
    const float green_weight = dot(white, cross(projected, blue)) / determinant;
    const float blue_weight = dot(white, cross(green, projected)) / determinant;
    if (white_weight <= 0.0f || green_weight <= 0.0f || blue_weight < 0.0f) {
        return projected;
    }

    const float availability = teal_blue_availability(green_weight, blue_weight);
    const float removed = white_weight * 0.4f * window * availability;
    const Point mixture = mul(
        add(mul(green, green_weight), mul(blue, blue_weight)),
        1.0f / (green_weight + blue_weight));
    return add(projected, mul(sub(mixture, white), removed));
}

}  // namespace papercolor_gamut
