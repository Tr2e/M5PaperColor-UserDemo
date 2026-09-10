/*
 * SPDX-FileCopyrightText: 2026 M5Stack Technology CO LTD
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once

#include "hal/hal.h"

class PhotoSlideshow;
class EzdataPhotoPush;

static constexpr int PAPERCOLOR_HOME_DATE_X = 12;
static constexpr int PAPERCOLOR_HOME_DATE_Y = 72;
static constexpr int PAPERCOLOR_HOME_DATE_W = 224;
static constexpr int PAPERCOLOR_HOME_DATE_H = 164;

static constexpr int PAPERCOLOR_HOME_AUDIO_X = 205;
static constexpr int PAPERCOLOR_HOME_AUDIO_Y = 447;
static constexpr int PAPERCOLOR_HOME_AUDIO_W = 179;
static constexpr int PAPERCOLOR_HOME_AUDIO_H = 126;

/**
 * @brief Renders the static PaperColor OS home surface.
 *
 * The renderer only composes the canvas. The caller owns the physical e-paper
 * refresh so all home widgets can be committed in one refresh cycle.
 *
 * @return True when the image tile contains a decoded photo.
 */
bool papercolor_home_draw(AppMode mode, PhotoSlideshow& local_photos, EzdataPhotoPush& ezdata_photos, bool audio_muted);

/** @brief Redraws only the monochrome home action/audio-status cluster. */
void papercolor_home_draw_audio_state(bool audio_muted);

/** @brief Redraws only the monochrome RTC date panel on the home canvas. */
void papercolor_home_draw_date(void);

/** Push the composed home canvas once, with photo color mapping confined to
 * its decoded thumbnail and embedded color logo. Honors the display clip. */
void papercolor_home_push(void);
