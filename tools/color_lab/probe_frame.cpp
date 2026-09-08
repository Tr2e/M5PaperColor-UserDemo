// Pipe a 400x600 RGB888 chart to stdin; receive 400x600 native codes on stdout.
// Quantize and rotate like the portrait Canvas's 600x400 RGB565 backing buffer.
#include "display/papercolor_photo_dither.h"
#include <fstream>
#include <iostream>
#include <vector>
#include <iterator>

int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    std::ifstream file(argv[1], std::ios::binary);
    std::vector<uint8_t> lut((std::istreambuf_iterator<char>(file)), {});
    std::vector<uint8_t> input(400 * 600 * 3), output(400 * 600);
    if (lut.size() != 32768 || !std::cin.read(reinterpret_cast<char*>(input.data()), input.size())) return 3;
    std::vector<int32_t> work(papercolor_dither_workspace_size(600, PAPERCOLOR_DITHER_FLOYD_STEINBERG) / 4);
    papercolor_dither_state_t state{};
    if (!papercolor_dither_init(&state, 600, PAPERCOLOR_DITHER_FLOYD_STEINBERG,
                                lut.data(), work.data(), work.size() * 4)) return 4;
    std::vector<uint16_t> row(600);
    std::vector<uint8_t> codes(600);
    for (size_t y = 0; y < 400; ++y) {
        for (size_t x = 0; x < 600; ++x) {
            const size_t i = ((599 - x) * 400 + y) * 3;
            const uint8_t r = input[i] >> 3, g = input[i + 1] >> 2, b = input[i + 2] >> 3;
            row[x] = (g >> 3) | (r << 3) | (b << 8) | ((g & 7) << 13);
        }
        if (!papercolor_dither_process_swap565_row(&state, row.data(), codes.data())) return 5;
        for (size_t x = 0; x < 600; ++x) output[(599 - x) * 400 + y] = codes[x];
    }
    std::cout.write(reinterpret_cast<const char*>(output.data()), output.size());
}
