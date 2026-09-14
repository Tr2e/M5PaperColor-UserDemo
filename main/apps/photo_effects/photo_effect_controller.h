// SPDX-License-Identifier: MIT
#pragma once

#include <cstdint>

enum class PaperColorPhotoSource : uint8_t { Local, EzData };

struct PaperColorPhotoTarget {
    uint32_t generation = 0;
    bool valid = false;
};

// Called before a source overwrites the shared Canvas, or before a non-photo
// view reuses it. Releases any retained original frame.
void papercolor_photo_effect_invalidate();

// Called after a photo has been decoded into Canvas. Coordinates are in the
// Canvas's current logical rotation; the controller clips them to the screen.
void papercolor_photo_effect_register(PaperColorPhotoSource source,
                                      int draw_x, int draw_y,
                                      int draw_width, int draw_height);

bool papercolor_photo_effect_is_busy();
bool papercolor_photo_effect_try_claim_canvas();
void papercolor_photo_effect_release_canvas();

// Capture on button press, before delayed single-click confirmation. Returns
// an invalid target when another task owns Canvas or no photo is registered.
PaperColorPhotoTarget papercolor_photo_effect_capture_target();

// Runs only on the app UI task. Returns false without refreshing on failure.
// A first call paints the original Canvas; a second restores the saved source.
// Rejects a target if any intervening photo/view replacement invalidated it.
bool papercolor_photo_effect_toggle(PaperColorPhotoTarget target);
