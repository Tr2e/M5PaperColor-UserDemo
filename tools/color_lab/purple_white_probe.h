/* SPDX-License-Identifier: MIT */
#pragma once

#ifdef ESP_PLATFORM
#error "Purple-white diagnostic probe is host-only"
#endif

#include "display/papercolor_gamut.h"

#include <stdint.h>

namespace papercolor_diagnostic {

inline papercolor_gamut::Point purple_white_target(
    const uint8_t original[3], papercolor_gamut::Point projected, int mode)
{
    using namespace papercolor_gamut;
    const bool purple = original[0] == 99 && original[1] == 48 && original[2] == 156;
    if (!purple || (mode != 1 && mode != 2)) {
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

    const float removed = white_weight * (mode == 1 ? 0.5f : 1.0f);
    const Point mixture = mul(
        add(mul(red, red_weight), mul(blue, blue_weight)),
        1.0f / (red_weight + blue_weight));
    return add(projected, mul(sub(mixture, white), removed));
}

}  // namespace papercolor_diagnostic
