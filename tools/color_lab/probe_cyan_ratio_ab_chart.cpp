/* SPDX-License-Identifier: MIT */
#include "display/papercolor_cyan_ratio_ab_chart.h"
#include <cassert>
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>

int main(int argc,char** argv)
{
    if (argc!=2) return 2;
    std::ifstream file(argv[1],std::ios::binary);
    std::vector<uint8_t> data((std::istreambuf_iterator<char>(file)),{});
    using namespace papercolor_cyan_ratio_ab_chart;
    if (!valid_payload(data.data(),data.size())) return 3;
    assert(!valid_payload(nullptr,data.size()));
    assert(!valid_payload(data.data(),data.size()-1));
    const uint8_t first=data[0];
    for (uint8_t bad : {4,7,15}) {
        data[0]=static_cast<uint8_t>((bad<<4)|(first&15));
        assert(!valid_payload(data.data(),data.size()));
        data[0]=static_cast<uint8_t>((first&240)|bad);
        assert(!valid_payload(data.data(),data.size()));
    }
    data[0]=first;
    uint8_t sentinel=255;
    for (int x : {-1,WIDTH})
        assert(!sample(x,ROW_Y,data.data(),data.size(),sentinel) && sentinel==255);
    for (int y : {-1,HEIGHT})
        assert(!sample(COLUMN_X,y,data.data(),data.size(),sentinel) && sentinel==255);
    assert(!sample(COLUMN_X,ROW_Y,nullptr,data.size(),sentinel));
    assert(!sample(COLUMN_X,ROW_Y,data.data(),data.size()-1,sentinel));
    for (int y=0;y<HEIGHT;++y) for (int x=0;x<WIDTH;++x) {
        uint8_t code=255;
        sample(x,y,data.data(),data.size(),code);
        std::cout.put(static_cast<char>(code));
    }
}
