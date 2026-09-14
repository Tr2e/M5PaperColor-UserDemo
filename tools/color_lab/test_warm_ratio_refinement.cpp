/* SPDX-License-Identifier: MIT */
#include "display/papercolor_warm_ratio_refinement.h"

#include <cassert>
#include <cmath>
#include <cstdio>

using namespace papercolor_gamut;

namespace {
struct Weights { float white; float yellow; float red; };

Weights weights(Point point)
{
    const Point white{255, 255, 255};
    const Point yellow{255, 243, 56};
    const Point red{191, 0, 0};
    const float determinant = dot(white, cross(yellow, red));
    return {dot(point, cross(yellow, red)) / determinant,
            dot(white, cross(point, red)) / determinant,
            dot(white, cross(yellow, point)) / determinant};
}
}  // namespace

int main()
{
    const Point white{255, 255, 255};
    const Point yellow{255, 243, 56};
    const Point red{191, 0, 0};
    const Point projected = add(mul(white, 0.1f), add(mul(yellow, 0.35f), mul(red, 0.55f)));
    for (Point source : {Point{255, 101, 49}, Point{206, 48, 0}}) {
        const auto before = weights(projected);
        const auto after = weights(refine_warm_red_yellow_ratio(source, projected));
        assert(std::fabs(after.white - before.white) < 1e-6f);
        assert(std::fabs(after.white + after.yellow + after.red - 1.0f) < 1e-6f);
        assert(std::fabs(after.red - before.red - 0.0625f * (before.yellow + before.red)) < 1e-6f);
    }

    for (Point source : {Point{255, 204, 0}, Point{255, 0, 0}, Point{96, 96, 96},
                         Point{0, 255, 0}, Point{255, 0, 255}}) {
        assert(distance(refine_warm_red_yellow_ratio(source, projected), projected) < 1e-8f);
    }
    for (Point vertex : {white, yellow, red, Point{0, 0, 0}}) {
        assert(distance(refine_warm_red_yellow_ratio({255, 101, 49}, vertex), vertex) < 1e-8f);
    }

    float max_local = 0.0f;
    for (int r = 0; r <= 255; r += 17) {
        for (int g = 0; g <= 255; ++g) {
            for (int b = 0; b <= 255; b += 17) {
                for (int axis = 0; axis < 3; ++axis) {
                    Point low{float(r), float(g), float(b)};
                    Point high = low;
                    (&low.x)[axis] -= 0.001f;
                    (&high.x)[axis] += 0.001f;
                    const float step = std::sqrt(distance(
                        refine_warm_red_yellow_ratio(low, projected),
                        refine_warm_red_yellow_ratio(high, projected)));
                    if (step > max_local) max_local = step;
                    assert(step < 0.05f);
                }
            }
        }
    }
    std::printf("warm-ratio helper: weights, protected hues, vertices and fine neighborhoods pass; max local %.7f\n", max_local);
}
