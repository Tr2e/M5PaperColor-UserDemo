/* SPDX-License-Identifier: MIT */
#pragma once

#include "display/papercolor_portrait_warm_refinement.h"

namespace papercolor_diagnostic {

inline papercolor_gamut::Point portrait_warm_target(
    const uint8_t original[3], papercolor_gamut::Point projected, int mode)
{
    if (mode <= 0) return projected;
    const float fraction = mode == 1 ? 0.0625f : 0.125f;
    return papercolor_gamut::refine_portrait_warm_ratio(
        {float(original[0]), float(original[1]), float(original[2])},
        projected, fraction);
}

}  // namespace papercolor_diagnostic
