/* SPDX-License-Identifier: MIT */
#include "display/papercolor_green_pair_refinement.h"

#include <cassert>
#include <cmath>
#include <cstdio>

using namespace papercolor_gamut;

namespace {

struct Weights {
    float white;
    float first;
    float second;
};

Weights weights(Point point, Point first, Point second)
{
    const Point white{255, 255, 255};
    const float determinant = dot(white, cross(first, second));
    return {
        dot(point, cross(first, second)) / determinant,
        dot(white, cross(point, second)) / determinant,
        dot(white, cross(first, point)) / determinant,
    };
}

float total(Weights value)
{
    return value.white + value.first + value.second;
}

}  // namespace

int main()
{
    const Point white{255, 255, 255};
    const Point yellow{255, 243, 56};
    const Point green{67, 138, 28};
    const Point blue{100, 64, 255};

    const Point lime = add(mul(green, 0.40f), mul(yellow, 0.60f));
    const auto lime_before = weights(lime, green, yellow);
    const auto lime_after = weights(refine_lime_ratio({156, 255, 0}, lime), green, yellow);
    assert(std::fabs(lime_after.white - lime_before.white) < 1e-6f);
    assert(std::fabs(total(lime_after) - total(lime_before)) < 1e-6f);
    assert(std::fabs(lime_after.first - lime_before.first - 0.0625f) < 1e-6f);

    Point teal = add(mul(white, 0.04f), add(mul(green, 0.74f), mul(blue, 0.22f)));
    const auto teal_before = weights(teal, green, blue);
    teal = refine_teal_ratio({49, 154, 99}, teal);
    const auto ratio_after = weights(teal, green, blue);
    assert(std::fabs(ratio_after.white - teal_before.white) < 1e-6f);
    assert(std::fabs(total(ratio_after) - total(teal_before)) < 1e-6f);
    assert(std::fabs(ratio_after.first - teal_before.first + 0.06f) < 1e-6f);
    teal = refine_teal_white({49, 154, 99}, teal);
    const auto white_after = weights(teal, green, blue);
    assert(std::fabs(white_after.white - teal_before.white * 0.6f) < 1e-6f);
    assert(std::fabs(total(white_after) - total(teal_before)) < 1e-6f);
    assert(std::fabs(white_after.first / (white_after.first + white_after.second) -
                     ratio_after.first / (ratio_after.first + ratio_after.second)) < 1e-6f);

    for (Point source : {Point{255, 255, 0}, Point{0, 255, 0}, Point{0, 255, 255},
                         Point{0, 173, 254}, Point{255, 0, 255}, Point{96, 96, 96}}) {
        assert(distance(refine_lime_ratio(source, lime), lime) < 1e-8f);
        assert(distance(refine_teal_ratio(source, teal), teal) < 1e-8f);
        assert(distance(refine_teal_white(source, teal), teal) < 1e-8f);
    }
    for (Point vertex : {white, yellow, green, blue, Point{0, 0, 0}}) {
        assert(distance(refine_lime_ratio({156, 255, 0}, vertex), vertex) < 1e-8f);
        assert(distance(refine_teal_ratio({49, 154, 99}, vertex), vertex) < 1e-8f);
        assert(distance(refine_teal_white({49, 154, 99}, vertex), vertex) < 1e-8f);
    }

    float max_step = 0.0f;
    for (int red = 0; red <= 255; red += 17) {
        for (int green_source = 0; green_source <= 255; ++green_source) {
            for (int blue_source = 0; blue_source <= 255; blue_source += 17) {
                for (int axis = 0; axis < 3; ++axis) {
                    Point low{float(red), float(green_source), float(blue_source)};
                    Point high = low;
                    (&low.x)[axis] -= 0.001f;
                    (&high.x)[axis] += 0.001f;
                    const auto lime_low = refine_lime_ratio(low, lime);
                    const auto lime_high = refine_lime_ratio(high, lime);
                    auto teal_low = refine_teal_ratio(low, teal);
                    auto teal_high = refine_teal_ratio(high, teal);
                    teal_low = refine_teal_white(low, teal_low);
                    teal_high = refine_teal_white(high, teal_high);
                    const float lime_step = std::sqrt(distance(lime_low, lime_high));
                    const float teal_step = std::sqrt(distance(teal_low, teal_high));
                    if (lime_step > max_step) max_step = lime_step;
                    if (teal_step > max_step) max_step = teal_step;
                    assert(lime_step < 0.05f);
                    assert(teal_step < 0.05f);
                }
            }
        }
    }

    std::printf("green-pair helpers: weights, vertices, protected hues and fine neighborhoods pass; max local %.7f\n",
                max_step);
}
