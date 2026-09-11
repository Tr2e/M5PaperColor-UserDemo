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
    const uint8_t pairs[][2][3]={{{99,50,200},{100,50,200}},
                                {{100,50,200},{100,50,201}},
                                {{180,50,180},{180,50,181}}};
    for (const auto& pair : pairs) {
        int32_t a[3],b[3];
        assert(candidate_mask(pair[0][0],pair[0][1],pair[0][2])==MASK_RED_BLUE);
        assert(candidate_mask(pair[1][0],pair[1][1],pair[1][2])==MASK_RED_BLUE);
        reachable_photo_target(&state,MASK_RED_BLUE,pair[0],a);
        reachable_photo_target(&state,MASK_RED_BLUE,pair[1],b);
        int32_t squared=0;
        for (size_t c=0;c<3;++c) squared+=(a[c]-b[c])*(a[c]-b[c]);
        assert(squared<48*48); // <3 nominal RGB after the fixed post-projection policies.
    }
    const uint8_t purple[]={102,51,153},cyan[]={0,174,255},orange[]={255,101,49};
    int32_t target[3];
    compensated_photo_target(MASK_RED_BLUE,purple,target);
    assert(target[0]==102 && target[1]==51 && target[2]==153);
    compensated_photo_target(MASK_GREEN_BLUE,cyan,target);
    assert(target[0]==0 && target[1]==152 && target[2]==223);
    compensated_photo_target(MASK_RED_YELLOW,orange,target);
    assert(target[0]==255 && target[1]==101 && target[2]==49);
    std::puts("purple former thresholds/raw source/cyan compression/warm bypass: pass");
}
