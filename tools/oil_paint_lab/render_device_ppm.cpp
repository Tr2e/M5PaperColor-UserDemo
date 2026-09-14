// Host entry point for the EXACT core linked into the firmware.
#include "display/papercolor_stacked_painter.h"
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>
int main(int argc, char** argv)
{
    if (argc != 3) return 2;
    std::ifstream in(argv[1], std::ios::binary);
    std::string magic;
    int w = 0, h = 0, maximum = 0;
    in >> magic >> w >> h >> maximum;
    in.get();
    if (!in || magic != "P6" || maximum != 255 || w < 1 || h < 1 || w > 600 || h > 600) return 2;
    std::vector<uint8_t> rgb(w * h * 3);
    in.read(reinterpret_cast<char*>(rgb.data()), rgb.size());
    if (in.gcount() != static_cast<std::streamsize>(rgb.size())) return 2;
    std::vector<uint16_t> source(w * h), result(w * h);
    for (size_t i = 0; i < source.size(); ++i)
        source[i] = papercolor_oil_encode_swap565(rgb[i * 3], rgb[i * 3 + 1], rgb[i * 3 + 2]);
    const size_t needed = papercolor_stacked_workspace_size(w, h);
    std::vector<uint32_t> workspace((needed + 3) / 4);
    PaperColorStackedStats stats{};
    if (!papercolor_stacked_render_swap565(source.data(), result.data(), w, h, w, {0, 0, w, h},
        {}, workspace.data(), needed, &stats)) return 1;
    for (size_t i = 0; i < result.size(); ++i)
        papercolor_oil_decode_swap565(result[i], &rgb[i * 3], &rgb[i * 3 + 1], &rgb[i * 3 + 2]);
    std::ofstream out(argv[2], std::ios::binary);
    out << "P6\n" << w << ' ' << h << "\n255\n";
    out.write(reinterpret_cast<const char*>(rgb.data()), rgb.size());
    for (int i = 0; i < 5; ++i) std::fprintf(stderr, "layer=%d strokes=%u\n", i, stats.strokes[i]);
    std::fprintf(stderr, "workspace_bytes=%zu\n", stats.workspace_bytes);
    return out ? 0 : 1;
}
