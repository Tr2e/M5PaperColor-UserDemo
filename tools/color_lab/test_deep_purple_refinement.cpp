/* SPDX-License-Identifier: MIT */
#include "display/papercolor_deep_purple_refinement.h"

#include <cassert>
#include <cmath>
#include <cstdio>

using namespace papercolor_gamut;

namespace {
struct Weights { float white; float red; float blue; };

Weights weights(Point point)
{
    const Point white{255, 255, 255};
    const Point red{191, 0, 0};
    const Point blue{100, 64, 255};
    const float determinant = dot(white, cross(red, blue));
    return {dot(point, cross(red, blue)) / determinant,
            dot(white, cross(point, blue)) / determinant,
            dot(white, cross(red, point)) / determinant};
}
}  // namespace

int main()
{
    const Point white{255, 255, 255};
    const Point red{191, 0, 0};
    const Point blue{100, 64, 255};
    const Point target = add(mul(white, 0.06f), add(mul(red, 0.38f), mul(blue, 0.52f)));
    const auto before = weights(target);
    const auto after = weights(refine_deep_purple_white({99, 48, 156}, target));
    assert(std::fabs(after.white - before.white * 0.5f) < 1e-6f);
    assert(std::fabs(after.red / after.blue - before.red / before.blue) < 1e-6f);
    assert(std::fabs(after.white + after.red + after.blue -
                     before.white - before.red - before.blue) < 1e-6f);

    for (Point source : {Point{74, 36, 115}, Point{156, 48, 206},
                         Point{255, 0, 255}, Point{96, 96, 96},
                         Point{0, 173, 255}, Point{255, 0, 0}}) {
        assert(distance(refine_deep_purple_white(source, target), target) < 1e-8f);
    }
    for (Point vertex : {white, red, blue, Point{0, 0, 0}}) {
        assert(distance(refine_deep_purple_white({99, 48, 156}, vertex), vertex) < 1e-8f);
    }

    float max_step = 0.0f;
    for (int red_source = 0; red_source <= 255; red_source += 17) {
        for (int green_source = 0; green_source <= 255; green_source += 17) {
            for (int blue_source = 0; blue_source <= 255; ++blue_source) {
                for (int axis = 0; axis < 3; ++axis) {
                    Point low{float(red_source), float(green_source), float(blue_source)};
                    Point high = low;
                    (&low.x)[axis] -= 0.001f;
                    (&high.x)[axis] += 0.001f;
                    const float step = std::sqrt(distance(
                        refine_deep_purple_white(low, target),
                        refine_deep_purple_white(high, target)));
                    if (step > max_step) max_step = step;
                    assert(step < 0.05f);
                }
            }
        }
    }
    std::printf("deep-purple helper: weights, protections and fine neighborhoods pass; max local %.7f\n",
                max_step);
}
