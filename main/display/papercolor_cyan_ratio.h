/* SPDX-License-Identifier: MIT */
#pragma once
#include "display/papercolor_gamut.h"

namespace papercolor_gamut {
inline float cyan_ratio_smoothstep(float t)
{
    if (t <= 0) return 0;
    if (t >= 1) return 1;
    return t*t*(3-2*t);
}

// Experimental generalization of IMG_9955's cyan B direction. Transfer at most
// 1/16 of chromatic coverage from green to blue without changing white/black.
// The source hue window ends well inside the green/blue mask; the chroma fade
// vanishes before the existing neutral guard. Widths are policy choices, not
// measured physical calibration. Exact native pigments remain fixed points.
inline Point balance_cyan_ratio(Point original, Point projected)
{
    const float g = original.y-original.x, b = original.z-original.x;
    const float maximum = g > b ? g : b, minimum = g < b ? g : b;
    if (minimum <= 0 || maximum <= 24) return projected;
    const float hue = cyan_ratio_smoothstep((minimum/maximum-0.75f)/0.25f);
    const float chroma = cyan_ratio_smoothstep((maximum-24)/104);
    if (hue == 0) return projected;
    const Point white{255,255,255}, green{67,138,28}, blue{100,64,255};
    const float det = dot(white,cross(green,blue));
    const float a = dot(white,cross(projected,blue))/det;
    const float c = dot(white,cross(green,projected))/det;
    if (a <= 0 || c <= 0) return projected;
    const float total = a+c;
    const float smaller = a < c ? a : c;
    const float available = cyan_ratio_smoothstep(smaller/(total*0.125f));
    // smoothstep(t)/t <= 9/8, so even in the donor fade this transfer
    // consumes at most 9/16 of the smaller pigment; no hull clipping needed.
    const float transfer = total*0.0625f*hue*chroma*available;
    return add(projected,mul(sub(blue,green),transfer));
}
} // namespace papercolor_gamut
