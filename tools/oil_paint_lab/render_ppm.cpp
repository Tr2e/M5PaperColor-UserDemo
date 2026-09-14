#include "display/papercolor_oil_painter.h"

#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

int main(int argc, char** argv)
{
    if (argc != 7) {
        std::fprintf(stderr, "usage: render_ppm input.ppm output.ppm x y width height\n");
        return 2;
    }
    const PaperColorOilRect rect{std::stoi(argv[3]), std::stoi(argv[4]),
                                 std::stoi(argv[5]), std::stoi(argv[6])};
    std::ifstream input(argv[1], std::ios::binary);
    std::string magic;
    int width = 0, height = 0, maximum = 0;
    input >> magic >> width >> height >> maximum;
    input.get();
    if (!input || magic != "P6" || maximum != 255 || width <= 0 || height <= 0 ||
        width > 4096 || height > 4096) return 2;
    std::vector<uint8_t> rgb(static_cast<size_t>(width) * height * 3);
    input.read(reinterpret_cast<char*>(rgb.data()), rgb.size());
    if (input.gcount() != static_cast<std::streamsize>(rgb.size())) return 2;

    std::vector<uint16_t> source(static_cast<size_t>(width) * height);
    std::vector<uint16_t> output(source.size());
    for (size_t i = 0; i < source.size(); ++i) {
        source[i] = papercolor_oil_encode_swap565(rgb[i * 3], rgb[i * 3 + 1], rgb[i * 3 + 2]);
    }
    std::vector<uint8_t> workspace(papercolor_oil_workspace_size(rect.width, rect.height));
    PaperColorOilStats stats{};
    if (!papercolor_oil_render_swap565(source.data(), output.data(), width, height, width,
                                      rect, PaperColorOilOptions{}, workspace.data(),
                                      workspace.size(), &stats)) return 1;
    for (size_t i = 0; i < output.size(); ++i) {
        papercolor_oil_decode_swap565(output[i], &rgb[i * 3], &rgb[i * 3 + 1], &rgb[i * 3 + 2]);
    }
    std::ofstream result(argv[2], std::ios::binary);
    result << "P6\n" << width << ' ' << height << "\n255\n";
    result.write(reinterpret_cast<const char*>(rgb.data()), rgb.size());
    std::fprintf(stderr, "strokes coarse=%u medium=%u detail=%u workspace=%zu\n",
                 stats.coarse_strokes, stats.medium_strokes, stats.detail_strokes,
                 stats.workspace_bytes);
    return result ? 0 : 1;
}
