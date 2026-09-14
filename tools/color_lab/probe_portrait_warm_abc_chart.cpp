/* SPDX-License-Identifier: MIT */
#include "display/papercolor_portrait_warm_abc_chart.h"

#include <cassert>
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>

int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    std::ifstream input(argv[1], std::ios::binary);
    std::vector<uint8_t> data((std::istreambuf_iterator<char>(input)), {});
    using namespace papercolor_portrait_warm_abc_chart;
    if (!valid_payload(data.data(), data.size())) return 3;
    assert(!valid_payload(nullptr, data.size()));
    assert(!valid_payload(data.data(), data.size() - 1));
    const uint8_t first = data[0];
    for (uint8_t invalid : {4, 7, 15}) {
        data[0] = (invalid << 4) | (first & 15);
        assert(!valid_payload(data.data(), data.size()));
        data[0] = (first & 240) | invalid;
        assert(!valid_payload(data.data(), data.size()));
    }
    data[0] = first;
    for (int y = 0; y < HEIGHT; ++y) {
        for (int x = 0; x < WIDTH; ++x) {
            uint8_t code = 255;
            sample(x, y, data.data(), data.size(), code);
            std::cout.put(char(code));
        }
    }
}
