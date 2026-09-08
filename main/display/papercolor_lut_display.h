/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once

#include <stddef.h>
#include <stdint.h>

namespace m5gfx {
class M5Canvas;
}

enum class PaperColorRenderMode : uint8_t {
    Ui,
    PhotoBalanced,
    PhotoDetail,
    Legacy,
};

struct PaperColorPipelineStats {
    bool valid;
    PaperColorRenderMode mode;
    uint64_t prepare_us;
    size_t workspace_bytes;
};

const char* papercolor_render_mode_name(PaperColorRenderMode mode);
bool papercolor_pipeline_stats_snapshot(PaperColorPipelineStats* stats);

/**
 * Pushes a Canvas through the optional experimental LUT pipeline.
 * With CONFIG_PAPERCOLOR_EXPERIMENTAL_LUT disabled this is exactly a
 * Canvas::pushSprite() call.
 */
void papercolor_push_canvas(m5gfx::M5Canvas* canvas, int32_t x, int32_t y,
                            PaperColorRenderMode mode = PaperColorRenderMode::Ui);
