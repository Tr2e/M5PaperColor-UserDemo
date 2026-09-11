// Host-only inspection of the actual firmware's pre-diffusion target mapping.
// Include the implementation so private helpers are inspected without adding
// diagnostics or a public API to firmware. Link papercolor_lut.cpp, not a second
// copy of papercolor_photo_dither.cpp.
#ifdef ESP_PLATFORM
#error "Target probe must never be built into firmware"
#endif
#if !defined(CONFIG_PAPERCOLOR_PRIMARY_WHITE_BUDGET) || !CONFIG_PAPERCOLOR_PRIMARY_WHITE_BUDGET
#error "This audit requires the accepted 21b0370 primary-white-budget config"
#endif
#include "display/papercolor_photo_dither.cpp"
#include <iomanip>
#include <iostream>

int main()
{
    papercolor_dither_state_t state{};
    std::cout << std::setprecision(9);
    std::cout << "rgb565,r,g,b,mask,comp_r,comp_g,comp_b,target_r,target_g,target_b,"
                 "uncompensated_r,uncompensated_g,uncompensated_b\n";
    for (unsigned packed = 0; packed < 65536; ++packed) {
        const uint16_t swapped = static_cast<uint16_t>((packed >> 8) | (packed << 8));
        uint8_t rgb[3];
        Swap565Source{&swapped}.sample(0, rgb);
        const auto mask = candidate_mask(rgb[0], rgb[1], rgb[2]);
        int32_t compensated[3], target[3];
        compensated_photo_target(mask, rgb, compensated);
        reachable_photo_target(&state, mask, rgb, target);
        papercolor_gamut::Point vertices[6];
        size_t count = 0;
        for (auto native : NATIVE_CANDIDATES) {
            if (mask_allows(mask, native)) {
                vertices[count++] = {float(NATIVE_SRGB[native][0]),
                                     float(NATIVE_SRGB[native][1]),
                                     float(NATIVE_SRGB[native][2])};
            }
        }
        // Diagnostic ablation only: same hull/white budget, no source compensation.
        const auto raw = papercolor_gamut::project_primary_white_budget(
            {float(rgb[0]), float(rgb[1]), float(rgb[2])}, vertices, count);
        std::cout << packed;
        for (auto value : rgb) std::cout << ',' << unsigned(value);
        std::cout << ',' << unsigned(mask);
        for (auto value : compensated) std::cout << ',' << value;
        for (auto value : target) std::cout << ',' << value / float(RGB_SCALE);
        for (auto value : {raw.x, raw.y, raw.z})
            std::cout << ',' << int(value * RGB_SCALE + 0.5f) / float(RGB_SCALE);
        std::cout << '\n';
    }
}
