/* SPDX-License-Identifier: MIT */
#ifndef PAPERCOLOR_TEST_PHOTO_IMPLEMENTATION
#define PAPERCOLOR_TEST_PHOTO_IMPLEMENTATION "display/papercolor_photo_dither.cpp"
#endif
#include PAPERCOLOR_TEST_PHOTO_IMPLEMENTATION
#include <cassert>
#include <cstdio>

int main()
{
    papercolor_dither_state_t state{};
    // Exercise the full interval, both endpoints, and former R/B=1/2 step.
    // Quantization still makes small steps; this is not a C1 continuity claim.
    int32_t previous[3]{};
    for (unsigned r=70;r<=140;++r) {
        const uint8_t rgb[]={static_cast<uint8_t>(r),50,200};
        assert(candidate_mask(rgb[0],rgb[1],rgb[2])==MASK_RED_BLUE);
        int32_t comp[3],target[3];
        compensated_photo_target(MASK_RED_BLUE,rgb,comp);
        reachable_photo_target(&state,MASK_RED_BLUE,rgb,target);
        assert(comp[1]==50);
        if (r<=80) assert(comp[0]==int(r) && comp[2]==200);
        if (r>=125) {
            assert(comp[0]==int(r)+(200-int(r))*3/4);
            assert(comp[2]==200-(200-int(r))/5);
        }
        if (r>70) {
            int32_t squared=0;
            for (unsigned c=0;c<3;++c) squared+=(target[c]-previous[c])*(target[c]-previous[c]);
            assert(squared<96*96); // under six nominal RGB units per input step
        }
        for (unsigned c=0;c<3;++c) previous[c]=target[c];
    }
    const uint8_t blue[]={100,64,255},purple[]={102,51,153};
    int32_t comp[3];
    compensated_photo_target(MASK_RED_BLUE,blue,comp);
    assert(comp[0]==100 && comp[1]==64 && comp[2]==255);
    compensated_photo_target(MASK_RED_BLUE,purple,comp);
    assert(comp[0]==140 && comp[1]==51 && comp[2]==143);
    std::puts("purple smooth/full activation interval/endpoints/native-blue/purple control: pass");
}
