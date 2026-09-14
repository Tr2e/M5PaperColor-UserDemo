#include "display/papercolor_oil_painter.h"
#include "apps/photo_effects/photo_frame_geometry.h"

#include <cassert>
#include <cstdint>
#include <cstdio>
#include <vector>

static void test_color_layout()
{
    assert(papercolor_oil_encode_swap565(255, 0, 0) == 0x00f8);
    assert(papercolor_oil_encode_swap565(0, 255, 0) == 0xe007);
    assert(papercolor_oil_encode_swap565(0, 0, 255) == 0x1f00);
    uint8_t r = 0, g = 0, b = 0;
    papercolor_oil_decode_swap565(0xe007, &r, &g, &b);
    assert(r == 0 && g == 255 && b == 0);
}

static void test_rotation_geometry()
{
    PaperColorOilRect rect{};
    assert(papercolor_photo_backing_rect(600, 400, 0, {50, 20, 500, 350}, &rect));
    assert(rect.x == 50 && rect.y == 20 && rect.width == 500 && rect.height == 350);
    assert(papercolor_photo_backing_rect(400, 600, 1, {20, 50, 350, 500}, &rect));
    assert(rect.x == 50 && rect.y == 20 && rect.width == 500 && rect.height == 350);
    assert(papercolor_photo_backing_rect(600, 400, 2, {50, 30, 500, 350}, &rect));
    assert(rect.x == 50 && rect.y == 20 && rect.width == 500 && rect.height == 350);
    assert(papercolor_photo_backing_rect(400, 600, 3, {30, 50, 350, 500}, &rect));
    assert(rect.x == 50 && rect.y == 20 && rect.width == 500 && rect.height == 350);
    assert(papercolor_photo_backing_rect(400, 600, 1, {-20, 0, 100, 600}, &rect));
    assert(rect.x == 0 && rect.y == 0 && rect.width == 600 && rect.height == 80);
    assert(!papercolor_photo_backing_rect(400, 600, 1, {500, 0, 100, 100}, &rect));
}

static void test_frame(int width, int height, int stride, PaperColorOilRect rect)
{
    const size_t pixels = static_cast<size_t>(height) * stride;
    std::vector<uint16_t> source(pixels, 0xffff);
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            source[static_cast<size_t>(y) * stride + x] =
                papercolor_oil_encode_swap565(static_cast<uint8_t>(x * 255 / width),
                                               static_cast<uint8_t>(y * 255 / height),
                                               static_cast<uint8_t>((x + y) * 127 / (width + height)));
        }
    }
    std::vector<uint16_t> first(pixels, 0x1234), second(pixels, 0x1234);
    const std::vector<uint16_t> original_source = source;
    const size_t workspace_bytes = papercolor_oil_workspace_size(rect.width, rect.height);
    std::vector<uint8_t> workspace(workspace_bytes);
    PaperColorOilStats stats{};
    PaperColorOilOptions options{};
    assert(!papercolor_oil_render_swap565(source.data(), first.data(), width, height,
                                         stride, rect, options, workspace.data(),
                                         workspace_bytes - 1, nullptr));
    assert(first[0] == 0x1234);
    assert(!papercolor_oil_render_swap565(source.data(), first.data(), width, height,
                                         stride, {-1, 0, 1, 1}, options,
                                         workspace.data(), workspace_bytes, nullptr));
    assert(first[0] == 0x1234);
    assert(!papercolor_oil_render_swap565(source.data(), source.data(), width, height,
                                         stride, rect, options, workspace.data(),
                                         workspace_bytes, nullptr));
    assert(!papercolor_oil_render_swap565(source.data(), first.data(), width, height,
                                         stride, rect, options, first.data(),
                                         workspace_bytes, nullptr));
    PaperColorOilOptions invalid_options{};
    invalid_options.saturation_percent = 151;
    assert(!papercolor_oil_render_swap565(source.data(), first.data(), width, height,
                                         stride, rect, invalid_options, workspace.data(),
                                         workspace_bytes, nullptr));
    assert(first[0] == 0x1234);
    assert(papercolor_oil_render_swap565(source.data(), first.data(), width, height,
                                        stride, rect, options, workspace.data(),
                                        workspace_bytes, &stats));
    assert(papercolor_oil_render_swap565(source.data(), second.data(), width, height,
                                        stride, rect, options, workspace.data(),
                                        workspace_bytes, nullptr));
    assert(first == second);
    assert(source == original_source);
    assert(stats.workspace_bytes == workspace_bytes);
    bool changed = false;
    for (int y = 0; y < height; ++y) {
        for (int x = 0; x < width; ++x) {
            const size_t i = static_cast<size_t>(y) * stride + x;
            const bool inside = x >= rect.x && x < rect.x + rect.width &&
                                y >= rect.y && y < rect.y + rect.height;
            if (!inside) assert(first[i] == source[i]);
            else changed |= first[i] != source[i];
        }
        for (int x = width; x < stride; ++x) {
            const size_t i = static_cast<size_t>(y) * stride + x;
            assert(first[i] == source[i]);
        }
    }
    assert(changed || (width == 1 && height == 1));
}

int main()
{
    test_color_layout();
    test_rotation_geometry();
    test_frame(600, 400, 600, {0, 0, 600, 400});
    test_frame(600, 400, 600, {60, 0, 480, 400});
    test_frame(400, 600, 401, {0, 50, 400, 500});
    test_frame(19, 13, 23, {3, 2, 12, 8});
    test_frame(1, 1, 1, {0, 0, 1, 1});
    std::puts("oil painter: byte order, determinism, rect, bounds, failures: pass");
}
