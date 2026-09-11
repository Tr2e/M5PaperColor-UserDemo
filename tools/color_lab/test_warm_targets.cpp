/* SPDX-License-Identifier: MIT */
// Inspect real private mapping helpers without exporting firmware test APIs.
#ifndef PAPERCOLOR_TEST_PHOTO_IMPLEMENTATION
#define PAPERCOLOR_TEST_PHOTO_IMPLEMENTATION "display/papercolor_photo_dither.cpp"
#endif
#include PAPERCOLOR_TEST_PHOTO_IMPLEMENTATION
#include <cassert>
#include <cstdio>

int main()
{
    papercolor_dither_state_t state{};
    // One input-level changes across both former switches must not produce
    // compression jumps. Each pair stays inside the same red/yellow hull.
    const uint8_t pairs[][2][3]={{{255,102,31},{255,102,32}},
                                {{179,100,49},{180,100,49}},
                                {{255,175,49},{255,176,49}}};
    for (const auto& pair : pairs) {
        int32_t a[3],b[3];
        assert(candidate_mask(pair[0][0],pair[0][1],pair[0][2])==MASK_RED_YELLOW);
        assert(candidate_mask(pair[1][0],pair[1][1],pair[1][2])==MASK_RED_YELLOW);
        reachable_photo_target(&state,MASK_RED_YELLOW,pair[0],a);
        reachable_photo_target(&state,MASK_RED_YELLOW,pair[1],b);
        int32_t squared=0;
        for (size_t c=0;c<3;++c) squared+=(a[c]-b[c])*(a[c]-b[c]);
        // Non-expansive projection plus independent Q4 rounding: < 1.2 RGB.
        assert(squared<20*20);
    }
    const uint8_t orange[]={255,101,49}; int32_t compensated[3];
    compensated_photo_target(MASK_RED_YELLOW,orange,compensated);
    assert(compensated[0]==255 && compensated[1]==101 && compensated[2]==49);
    const uint8_t purple[]={102,51,153},cyan[]={0,174,255};
    compensated_photo_target(MASK_RED_BLUE,purple,compensated);
    assert(compensated[0]==140 && compensated[1]==51 && compensated[2]==143);
    compensated_photo_target(MASK_GREEN_BLUE,cyan,compensated);
    assert(compensated[0]==0 && compensated[1]==152 && compensated[2]==223);
    std::puts("warm targets/two former thresholds/blue compensation unchanged: pass");
}
