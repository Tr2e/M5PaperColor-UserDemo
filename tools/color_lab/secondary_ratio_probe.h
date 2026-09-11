/* SPDX-License-Identifier: MIT */
#pragma once
#ifdef ESP_PLATFORM
#error "Diagnostic target perturbation is host-only, never a production color policy"
#endif
#include "display/papercolor_gamut.h"
#include <cassert>
#include <stdint.h>

namespace papercolor_diagnostic {
inline papercolor_gamut::Point secondary_ratio_target(const uint8_t original[3],
    papercolor_gamut::Point target, float offset)
{
    using namespace papercolor_gamut;
    const bool magenta=original[0]==255 && original[1]==0 && original[2]==255;
    const bool cyan=original[0]==0 && original[1]==255 && original[2]==255;
    if ((!magenta && !cyan) || offset==0) return target;
    const Point white{255,255,255}, blue{100,64,255};
    const Point pigment=magenta ? Point{191,0,0} : Point{67,138,28};
    const float det=dot(white,cross(pigment,blue));
    const float a=dot(white,cross(target,blue))/det;
    const float b=dot(white,cross(pigment,target))/det;
    const float delta=(a+b)*offset;
    assert(a+delta>=0 && b-delta>=0);
    // Transfer only colored coverage. White, black and total coverage are
    // unchanged before Q4 rounding. This samples two diagnostic sources only;
    // it is not a continuous mapping suitable for arbitrary photographs.
    return add(target,mul(sub(pigment,blue),delta));
}
}
