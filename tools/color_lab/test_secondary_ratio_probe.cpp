/* SPDX-License-Identifier: MIT */
#include "secondary_ratio_probe.h"
#include <cmath>
#include <initializer_list>
#include <cstdio>
using namespace papercolor_gamut;
static void weights(Point p,Point pigment,float& white,float& a,float& b){
    const Point w{255,255,255},blue{100,64,255};const float det=dot(w,cross(pigment,blue));
    white=dot(p,cross(pigment,blue))/det;
    a=dot(w,cross(p,blue))/det;b=dot(w,cross(pigment,p))/det;
}
int main(){
    const uint8_t sources[][3]={{255,0,255},{0,255,255}};
    const Point targets[]={{157.8125f,65.6875f,154.3125f},{123.5f,136.125f,169.5625f}};
    for(int i=0;i<2;++i) for(float offset:{-0.0625f,0.0f,0.0625f}){
        const Point pigment=i==0?Point{191,0,0}:Point{67,138,28};
        const auto q=papercolor_diagnostic::secondary_ratio_target(sources[i],targets[i],offset);
        float w,a,b,v,c,d;weights(targets[i],pigment,w,a,b);weights(q,pigment,v,c,d);
        assert(std::fabs(v-w)<1e-5f);
        assert(std::fabs((v+c+d)-(w+a+b))<1e-5f);
        assert(std::fabs(c/(c+d)-a/(a+b)-offset)<1e-5f);
        assert(c>=0 && d>=0);
    }
    // Nearby arbitrary-photo colors are intentionally not a new policy.
    const uint8_t protected_colors[][3]={{254,0,255},{255,1,255},{1,255,255},
        {0,254,255},{153,51,204},{0,173,254},{0,0,255},{96,96,96}};
    for(const auto& rgb:protected_colors){
        const Point p{float(rgb[0]),float(rgb[1]),float(rgb[2])};
        const auto q=papercolor_diagnostic::secondary_ratio_target(rgb,p,0.0625f);
        assert(q.x==p.x && q.y==p.y && q.z==p.z);
    }
    std::puts("host-only ratio probe: white/black invariance, exact colored offset, protected inputs: pass");
}
