/* SPDX-License-Identifier: MIT */
#include "display/papercolor_portrait_warm_refinement.h"

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
    const Point projected = add(mul(Point{255, 255, 255}, 0.35f),
        add(mul(Point{255, 243, 56}, 0.25f), mul(Point{191, 0, 0}, 0.25f)));
    const Point skin{148, 129, 112};
    const auto before = weights(projected);
    const auto b = weights(refine_portrait_warm_ratio(skin, projected, 0.0625f));
    const auto c = weights(refine_portrait_warm_ratio(skin, projected, 0.125f));
    for (const auto after : {b, c}) {
        assert(std::fabs(after.white - before.white) < 1e-5f);
        assert(std::fabs((after.yellow + after.red) -
                         (before.yellow + before.red)) < 1e-5f);
        assert(after.yellow < before.yellow && after.red > before.red);
    }
    assert(c.red > b.red && c.yellow < b.yellow);

    for (Point source : {Point{255, 101, 49}, Point{255, 0, 0},
                         Point{96, 96, 96}, Point{72, 55, 45},
                         Point{0, 255, 0}, Point{255, 0, 255}}) {
        assert(distance(refine_portrait_warm_ratio(source, projected),
                        projected) < 1e-8f);
    }

    float max_local = 0.0f;
    for (int r = 0; r <= 255; r += 17) {
        for (int g = 0; g <= 255; g += 5) {
            for (int b0 = 0; b0 <= 255; b0 += 17) {
                for (int axis = 0; axis < 3; ++axis) {
                    Point low{float(r), float(g), float(b0)};
                    Point high = low;
                    (&low.x)[axis] -= 0.001f;
                    (&high.x)[axis] += 0.001f;
                    const float step = std::sqrt(distance(
                        refine_portrait_warm_ratio(low, projected),
                        refine_portrait_warm_ratio(high, projected)));
                    if (step > max_local) max_local = step;
                    assert(step < 0.05f);
                }
            }
        }
    }
    std::printf("portrait warm helper: weights, guards and fine neighborhoods pass; max local %.7f\n",
                max_local);
}
