#include "display/papercolor_stacked_painter.h"
#include <cassert>
#include <cstdio>
#include <vector>

static void test(int w, int h, int stride, PaperColorOilRect rect)
{
    std::vector<uint16_t> source(stride * h, 0x1234), first(stride * h, 0x5678), second(first);
    for (int y = 0; y < h; ++y) for (int x = 0; x < w; ++x)
        source[y * stride + x] = papercolor_oil_encode_swap565(x * 17 % 256, y * 13 % 256, (x ^ y) % 256);
    const auto original = source;
    const auto untouched = first;
    const size_t needed = papercolor_stacked_workspace_size(rect.width, rect.height);
    std::vector<uint32_t> storage((needed + 3) / 4 + 2, 0xa5a5a5a5);
    void* workspace = storage.data() + 1;
    size_t callbacks = 0;
    PaperColorStackedOptions options{};
    options.cooperate = [](void* context) { ++*static_cast<size_t*>(context); };
    options.cooperate_context = &callbacks;
    PaperColorStackedStats stats{};
    stats.workspace_bytes = 123;
    assert(!papercolor_stacked_render_swap565(source.data(), first.data(), w, h, stride, rect, options, workspace, needed - 1, &stats));
    assert(!papercolor_stacked_render_swap565(source.data(), first.data(), w, h, stride, {-1, 0, 1, 1}, options, workspace, needed, &stats));
    assert(!papercolor_stacked_render_swap565(source.data(), first.data(), w, h, stride, {0, 0, w + 1, h}, options, workspace, needed, &stats));
    assert(!papercolor_stacked_render_swap565(source.data(), first.data(), w, h, w - 1, rect, options, workspace, needed, &stats));
    assert(!papercolor_stacked_render_swap565(source.data(), source.data(), w, h, stride, rect, options, workspace, needed, &stats));
    assert(!papercolor_stacked_render_swap565(source.data(), first.data(), w, h, stride, rect, options, source.data(), needed, &stats));
    assert(!papercolor_stacked_render_swap565(source.data(), first.data(), w, h, stride, rect, options, static_cast<char*>(workspace) + 1, needed, &stats));
    assert(!papercolor_stacked_render_swap565(nullptr, first.data(), w, h, stride, rect, options, workspace, needed, &stats));
    assert(first == untouched && source == original && stats.workspace_bytes == 123 && callbacks == 0);
    assert(papercolor_stacked_render_swap565(source.data(), first.data(), w, h, stride, rect, options, workspace, needed, &stats));
    assert(callbacks > 0 && stats.workspace_bytes == needed);
    assert(papercolor_stacked_render_swap565(source.data(), second.data(), w, h, stride, rect, options, workspace, needed));
    assert(first == second && source == original);
    assert(storage.front() == 0xa5a5a5a5 && storage.back() == 0xa5a5a5a5);
    for (int y = 0; y < h; ++y) for (int x = 0; x < stride; ++x)
        if (x < rect.x || x >= rect.x + rect.width || y < rect.y || y >= rect.y + rect.height)
            assert(first[y * stride + x] == source[y * stride + x]);
    // Rendering the same rectangle packed must have identical local coordinates,
    // independent of frame offset/padding (as used by rotated Canvas geometry).
    std::vector<uint16_t> packed(rect.width * rect.height), output(packed.size());
    for (int y = 0; y < rect.height; ++y) for (int x = 0; x < rect.width; ++x)
        packed[y * rect.width + x] = source[(y + rect.y) * stride + x + rect.x];
    assert(papercolor_stacked_render_swap565(packed.data(), output.data(), rect.width, rect.height, rect.width,
        {0, 0, rect.width, rect.height}, options, workspace, needed));
    for (int y = 0; y < rect.height; ++y) for (int x = 0; x < rect.width; ++x)
        assert(output[y * rect.width + x] == first[(y + rect.y) * stride + x + rect.x]);
}

int main()
{
    assert(!papercolor_stacked_workspace_size(0, 1));
    assert(!papercolor_stacked_workspace_size(601, 400));
    test(600, 400, 600, {0, 0, 600, 400});
    test(400, 600, 403, {11, 20, 370, 560});
    test(23, 19, 27, {3, 2, 12, 8});
    test(1, 1, 1, {0, 0, 1, 1});
    test(1, 17, 3, {0, 2, 1, 13});
    test(17, 1, 19, {1, 0, 13, 1});
    std::puts("stacked firmware core: workspace guards, rect/stride parity, determinism, callbacks, failures: pass");
}
