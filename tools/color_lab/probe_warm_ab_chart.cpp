/* SPDX-License-Identifier: MIT */
#include "display/papercolor_warm_ab_chart.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>

int main(int argc,char** argv)
{
    if (argc!=2) return 2;
    std::ifstream file(argv[1],std::ios::binary);
    std::vector<uint8_t> data((std::istreambuf_iterator<char>(file)),{});
    using namespace papercolor_warm_ab_chart;
    if (!valid_payload(data.data(),data.size())) return 3;
    for (int y=0;y<HEIGHT;++y) for (int x=0;x<WIDTH;++x) {
        uint8_t code=255;
        sample(x,y,data.data(),data.size(),code);
        std::cout.put(static_cast<char>(code));
    }
}
