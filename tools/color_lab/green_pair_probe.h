/* SPDX-License-Identifier: MIT */
#pragma once
#ifdef ESP_PLATFORM
#error "Green-pair diagnostic probe is host-only"
#endif
#include "display/papercolor_gamut.h"
#include <stdint.h>

namespace papercolor_diagnostic {
inline papercolor_gamut::Point transfer_pair(papercolor_gamut::Point p,
    papercolor_gamut::Point first, papercolor_gamut::Point second, float offset)
{
    using namespace papercolor_gamut;
    const Point white{255,255,255};
    const float det=dot(white,cross(first,second));
    const float w=dot(p,cross(first,second))/det;
    const float a=dot(white,cross(p,second))/det;
    const float b=dot(white,cross(first,p))/det;
    const float delta=(a+b)*offset;
    if (a+delta<0 || b-delta<0) return p;
    (void)w;
    return add(p,mul(sub(first,second),delta));
}

inline papercolor_gamut::Point green_pair_target(const uint8_t original[3],
    papercolor_gamut::Point p, int mode)
{
    using namespace papercolor_gamut;
    const bool lime=original[0]==156 && original[1]==255 && original[2]==0;
    const bool teal=original[0]==49 && original[1]==154 && original[2]==99;
    const Point yellow{255,243,56},green{67,138,28},blue{100,64,255},white{255,255,255};
    if (lime && (mode==1 || mode==2))
        return transfer_pair(p,green,yellow,mode==1 ? 0.0625f : -0.0625f);
    if (teal && (mode==3 || mode==4))
        return transfer_pair(p,green,blue,mode==3 ? -0.0625f : 0.0625f);
    if (teal && (mode==5 || mode==6)) {
        const float det=dot(white,cross(green,blue));
        const float w=dot(p,cross(green,blue))/det;
        const float a=dot(white,cross(p,blue))/det;
        const float b=dot(white,cross(green,p))/det;
        if (w<=0 || a<=0 || b<=0) return p;
        const float removed=w*(mode==5 ? 0.5f : 1.0f);
        const Point mixture=mul(add(mul(green,a),mul(blue,b)),1/(a+b));
        return add(p,mul(sub(mixture,white),removed));
    }
    return p;
}
} // namespace papercolor_diagnostic
