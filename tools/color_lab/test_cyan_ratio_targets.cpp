/* SPDX-License-Identifier: MIT */
#include "display/papercolor_cyan_ratio.h"
#include <cassert>
#include <cmath>
#include <cstdio>
using namespace papercolor_gamut;
static Point weights(Point p) {
    const Point white{255,255,255},green{67,138,28},blue{100,64,255};
    const float d=dot(white,cross(green,blue));
    return {dot(p,cross(green,blue))/d,dot(white,cross(p,blue))/d,dot(white,cross(green,p))/d};
}
int main() {
    const Point w{255,255,255},g{67,138,28},b{100,64,255};
    // Independent convex mixtures include zero donors, white/black faces and
    // very small pigment amounts. Transfer must preserve both neutral axes.
    unsigned checked=0;
    for (int iw=0;iw<=10;++iw) for (int ig=0;ig<=10-iw;++ig)
    for (int ib=0;ib<=10-iw-ig;++ib) {
        const Point p=add(mul(w,iw/10.f),add(mul(g,ig/10.f),mul(b,ib/10.f)));
        for (Point source : {Point{0,255,255},Point{64,180,190},Point{0,255,200},Point{120,150,150}}) {
            auto old=weights(p),now=weights(balance_cyan_ratio(source,p));
            assert(std::fabs(old.x-now.x)<2e-6f);
            assert(std::fabs((old.x+old.y+old.z)-(now.x+now.y+now.z))<2e-6f);
            assert(now.y>=-2e-6f && now.z>=-2e-6f);
            assert(now.y<=old.y+2e-6f && now.z>=old.z-2e-6f);
            ++checked;
        }
    }
    const auto p=add(mul(w,.23f),add(mul(g,.38f),mul(b,.39f)));
    auto old=weights(p),now=weights(balance_cyan_ratio({0,255,255},p));
    assert(std::fabs(now.y/(now.y+now.z)-old.y/(old.y+old.z)+.0625f)<1e-6f);
    for (Point source : {Point{255,0,255},Point{153,51,204},Point{76,38,115},Point{0,173,254},
                         Point{0,0,255},Point{67,138,28},Point{0,255,0},Point{96,96,96},Point{120,140,140}})
        assert(distance(balance_cyan_ratio(source,p),p)==0);
    for (auto vertex : {w,g,b,Point{0,0,0}})
        assert(distance(balance_cyan_ratio({0,255,255},vertex),vertex)<1e-8f);
    // Evaluate real-valued source neighborhoods across window start, hue tie,
    // chroma endpoints and both sides of every 8-bit source grid coordinate.
    // This isolates the new helper from pre-existing source/mask discontinuities.
    float max_local=0;
    for (int r=0;r<=255;r+=17) for (int green=0;green<=255;++green)
    for (int blue=0;blue<=255;blue+=17) for (int axis=0;axis<3;++axis) {
        Point a{float(r),float(green),float(blue)},c=a;
        if(axis==0){a.x-=.001f;c.x+=.001f;}
        if(axis==1){a.y-=.001f;c.y+=.001f;}
        if(axis==2){a.z-=.001f;c.z+=.001f;}
        const float step=std::sqrt(distance(balance_cyan_ratio(a,p),balance_cyan_ratio(c,p)));
        if(step>max_local)max_local=step;
        assert(step<.02f);
    }
    // Availability tends to zero continuously at a single pigment target.
    for(float epsilon : {1e-2f,1e-4f,1e-6f}) {
        const auto edge=add(mul(g,epsilon),mul(b,1-epsilon));
        assert(std::sqrt(distance(balance_cyan_ratio({0,255,255},edge),edge))<300*epsilon);
    }
    std::printf("cyan helper: %u feasible mixtures, neutral coverage/vertices/protected colors and fine source neighborhoods pass; max local %.7f\n",checked,max_local);
}
