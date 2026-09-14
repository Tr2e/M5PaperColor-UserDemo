#include "oil_test_runtime.h"
#include "apps/photo_effects/photo_effect_controller.h"
#include "utility/Button_Class.hpp"

#include <cstdio>

static void register_photo(TestCanvas& canvas)
{
    papercolor_photo_effect_register(PaperColorPhotoSource::EzData,
                                      0, 0, canvas.width(), canvas.height());
}

int main()
{
    TestCanvas canvas;
    hal.Canvas = &canvas;
    assert(!papercolor_photo_effect_capture_target().valid);
    register_photo(canvas);
    const auto original = canvas.pixels;
    const auto target = papercolor_photo_effect_capture_target();
    assert(target.valid);
    assert(papercolor_photo_effect_toggle(target));
    assert(oil_test::live_allocations == 1);
    assert(papercolor_photo_effect_toggle(papercolor_photo_effect_capture_target()));
    assert(canvas.pixels == original && oil_test::live_allocations == 0);

    // Non-photo Canvas replacement (QR or error page) invalidates the original
    // snapshot and rejects both old targets and new presses on the non-photo.
    assert(papercolor_photo_effect_toggle(target));
    papercolor_photo_effect_invalidate();
    assert(oil_test::live_allocations == 0);
    canvas.pixels.assign(canvas.pixels.size(), 0);
    int pushes = oil_test::refreshes;
    assert(!papercolor_photo_effect_toggle(target));
    assert(!papercolor_photo_effect_capture_target().valid);
    assert(oil_test::refreshes == pushes);
    assert(canvas.pixels.front() == 0);

    // Use the real M5Unified click recognizer: a slideshow refresh during the
    // confirmation window must not redirect the old press onto the new photo.
    register_photo(canvas);
    m5::Button_Class button;
    button.setRawState(100, true);
    assert(button.wasPressed());
    const auto pressed_target = papercolor_photo_effect_capture_target();
    button.setRawState(140, false);
    assert(button.wasClicked() && !button.wasSingleClicked());
    button.setRawState(160, false);
    register_photo(canvas);
    button.setRawState(20640, false);  // Return after the E Ink refresh.
    assert(button.wasSingleClicked());
    assert(!papercolor_photo_effect_toggle(pressed_target));
    assert(oil_test::refreshes == pushes);

    // Neither a busy Canvas nor allocation failures may refresh or overwrite.
    const auto current = papercolor_photo_effect_capture_target();
    assert(papercolor_photo_effect_try_claim_canvas());
    assert(!papercolor_photo_effect_capture_target().valid);
    assert(!papercolor_photo_effect_toggle(current));
    assert(papercolor_photo_effect_is_busy());
    papercolor_photo_effect_release_canvas();
    const auto before_failure = canvas.pixels;
    for (int failure = 1; failure <= 2; ++failure) {
        oil_test::allocation_attempts = 0;
        oil_test::fail_allocation = failure;
        assert(!papercolor_photo_effect_toggle(current));
        assert(canvas.pixels == before_failure);
        assert(oil_test::live_allocations == 0);
        assert(!papercolor_photo_effect_is_busy());
    }
    assert(oil_test::refreshes == pushes);
    oil_test::fail_allocation = 0;
    canvas.rotation = 1;
    assert(!papercolor_photo_effect_toggle(current));
    register_photo(canvas);
    assert(papercolor_photo_effect_toggle(papercolor_photo_effect_capture_target()));
    papercolor_photo_effect_invalidate();
    assert(oil_test::live_allocations == 0 && !oil_test::refreshing);
    assert(!papercolor_photo_effect_is_busy());
    std::puts("photo effect controller: stale click, invalidation, restore, allocation failures, busy: pass");
}
