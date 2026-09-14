/* SPDX-License-Identifier: MIT */
#pragma once

#ifdef ESP_PLATFORM
#error "Warm-ratio diagnostic probe is host-only"
#endif

#include "display/papercolor_gamut.h"

#include <stdint.h>

namespace papercolor_diagnostic {

inline papercolor_gamut::Point warm_ratio_target(
    const uint8_t original[3], papercolor_gamut::Point projected, int mode)
{
    using namespace papercolor_gamut;
    const bool orange = original[0] == 255 && original[1] == 101 && original[2] == 49;
    const bool red_orange = original[0] == 206 && original[1] == 48 && original[2] == 0;
    if ((!orange && !red_orange) || (mode != 1 && mode != 2)) {
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
    const float transfer = (yellow_weight + red_weight) * 0.0625f * (mode == 1 ? 1.0f : -1.0f);
    return add(projected, mul(sub(red, yellow), transfer));
}

}  // namespace papercolor_diagnostic
