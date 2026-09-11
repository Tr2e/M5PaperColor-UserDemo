/* SPDX-License-Identifier: MIT */
#pragma once

#include <stddef.h>
#include <stdint.h>
#include <initializer_list>

// Project an unreachable target onto the convex hull of the allowed pigments.
// All operations use the same RGB coordinate system as the existing diffuser.
// This is a numerical gamut constraint, not a measured panel calibration.
namespace papercolor_gamut {
struct Point { float x, y, z; };
inline Point sub(Point a, Point b) { return {a.x-b.x,a.y-b.y,a.z-b.z}; }
inline Point add(Point a, Point b) { return {a.x+b.x,a.y+b.y,a.z+b.z}; }
inline Point mul(Point a, float k) { return {a.x*k,a.y*k,a.z*k}; }
inline float dot(Point a, Point b) { return a.x*b.x+a.y*b.y+a.z*b.z; }
inline Point cross(Point a, Point b) {
    return {a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};
}
inline float distance(Point a, Point b) { const auto d=sub(a,b); return dot(d,d); }
inline Point segment(Point p, Point a, Point b) {
    const auto v=sub(b,a);
    const float length=dot(v,v);
    float t=length > 0 ? dot(sub(p,a),v)/length : 0;
    t=t<0 ? 0 : (t>1 ? 1 : t);
    return add(a,mul(v,t));
}
// Recognize the interior of a pigment edge before Q4 rounding. This tolerance
// covers floating-point projection roundoff (under 1/1024 nominal RGB level),
// not an artistic near-color threshold. Real white/black mixtures stay outside.
inline bool on_chromatic_segment(Point p, Point a, Point b)
{
    const auto v = sub(b,a);
    const float length = dot(v,v);
    if (length <= 0) return false;
    const float t = dot(sub(p,a),v)/length;
    if (t <= 0 || t >= 1) return false;
    const auto residual = sub(p,add(a,mul(v,t)));
    constexpr float tolerance = 1.0f/1024;
    return residual.x >= -tolerance && residual.x <= tolerance &&
           residual.y >= -tolerance && residual.y <= tolerance &&
           residual.z >= -tolerance && residual.z <= tolerance;
}
inline Point triangle(Point p, Point a, Point b, Point c) {
    const auto u=sub(b,a), v=sub(c,a), w=sub(p,a);
    const float uu=dot(u,u), uv=dot(u,v), vv=dot(v,v);
    const float denominator=uu*vv-uv*uv;
    if (denominator > 0.01f) {
        const float wu=dot(w,u), wv=dot(w,v);
        const float s=(wu*vv-wv*uv)/denominator;
        const float t=(wv*uu-wu*uv)/denominator;
        if (s>=0 && t>=0 && s+t<=1) return add(a,add(mul(u,s),mul(v,t)));
    }
    Point best=segment(p,a,b);
    for (auto q : {segment(p,b,c),segment(p,c,a)}) {
        if (distance(p,q)<distance(p,best)) best=q;
    }
    return best;
}
inline bool in_tetrahedron(Point p, Point a, Point b, Point c, Point d) {
    const auto u=sub(b,a), v=sub(c,a), w=sub(d,a), q=sub(p,a);
    const float det=dot(u,cross(v,w));
    if (det>-0.01f && det<0.01f) return false;
    const float s=dot(q,cross(v,w))/det;
    const float t=dot(u,cross(q,w))/det;
    const float r=dot(u,cross(v,q))/det;
    return s>=0 && t>=0 && r>=0 && s+t+r<=1;
}
inline Point project(Point p, const Point* vertices, size_t count) {
    if (count==1) return vertices[0];
    if (count==2) return segment(p,vertices[0],vertices[1]);
    for (size_t a=0;a<count;++a) for(size_t b=a+1;b<count;++b)
        for(size_t c=b+1;c<count;++c) for(size_t d=c+1;d<count;++d)
            if(in_tetrahedron(p,vertices[a],vertices[b],vertices[c],vertices[d])) return p;
    Point best=vertices[0];
    float best_distance=distance(p,best);
    for (size_t a=0;a<count;++a) for(size_t b=a+1;b<count;++b)
        for(size_t c=b+1;c<count;++c) {
            const auto q=triangle(p,vertices[a],vertices[b],vertices[c]);
            const float candidate_distance=distance(p,q);
            if(candidate_distance<best_distance) { best=q; best_distance=candidate_distance; }
        }
    return best;
}
// Opt-in policy for black/white plus exactly one chromatic pigment. Constrain
// neutral-white coverage using the target's existing neutral component; do not
// modify any two-pigment mixture or neutral-only target. Coordinates remain the
// accepted nominal sRGB model, not a measured physical calibration.
inline Point project_primary_white_budget(Point p, const Point* vertices, size_t count)
{
    if (count != 3) return project(p, vertices, count);
    Point restricted[4];
    size_t n = 0;
    bool has_white = false, has_black = false;
    for (size_t i = 0; i < count; ++i) {
        const auto v = vertices[i];
        if (v.x == 255 && v.y == 255 && v.z == 255) {
            has_white = true;
        } else {
            restricted[n++] = v;
            has_black |= v.x == 0 && v.y == 0 && v.z == 0;
        }
    }
    if (!has_white || !has_black || n != 2) return project(p, vertices, count);
    float neutral = p.x < p.y ? p.x : p.y;
    neutral = neutral < p.z ? neutral : p.z;
    if (neutral >= 255) return project(p, vertices, count);
    if (neutral > 0) {
        const float budget = neutral / 255.0f;
        for (size_t i = 0; i < 2; ++i) {
            restricted[n++] = add(mul(restricted[i], 1 - budget),
                                  {neutral, neutral, neutral});
        }
    }
    return project(p, restricted, n);
}

// Restore a requested full-scale primary peak without adding white or leaving
// the selected hull. The correction fades quadratically with source dominance,
// across hue-mask boundaries, and is exactly zero at secondary-hue ties.
// This is a continuous target policy, not a measured physical color profile.
inline Point preserve_fullscale_peak(Point original, Point projected, Point pigment, int channel)
{
    const float source[] = {original.x, original.y, original.z};
    const float target[] = {projected.x, projected.y, projected.z};
    const float native[] = {pigment.x, pigment.y, pigment.z};
    if (channel < 0 || channel > 2 || native[channel] != 255 ||
        source[channel] <= 0 || target[channel] >= source[channel]) return projected;
    float other = source[(channel + 1) % 3];
    if (source[(channel + 2) % 3] > other) other = source[(channel + 2) % 3];
    if (other >= source[channel]) return projected;
    const float dominance = (source[channel] - other) / source[channel];
    const float reach = (source[channel] - target[channel]) / (255 - target[channel]);
    const float amount = reach * dominance * dominance;
    return add(projected, mul(sub(pigment, projected), amount));
}

// Experimental hue policy for K/W plus red/blue or green/blue. Keep the
// projected black/white amounts and redistribute only chromatic coverage.
// Source chroma ratios are a policy, not measured pigment mixing coefficients.
inline Point balance_blue_secondary(Point original, Point projected,
                                     Point pigment, Point blue, int channel)
{
    if (channel < 0 || channel > 1) return projected;
    const Point white{255,255,255};
    const float det = dot(white, cross(pigment, blue));
    if (det > -0.01f && det < 0.01f) return projected;
    const float a = dot(white, cross(projected, blue)) / det;
    const float b = dot(white, cross(pigment, projected)) / det;
    // The fade vanishes at a single-pigment target, preserving native solids
    // and avoiding a discontinuity from special-casing exact palette colors.
    if (a <= 0 || b <= 0) return projected;
    const float rgb[] = {original.x, original.y, original.z};
    const float neutral = rgb[1-channel];
    const float ca = rgb[channel] - neutral;
    const float cb = rgb[2] - neutral;
    const float maximum = ca > cb ? ca : cb;
    const float minimum = ca < cb ? ca : cb;
    // Match the existing 12-level pigment-sector and 24-level low-chroma
    // boundaries, with zero slope at both ends of each transition.
    if (minimum <= 12 || maximum <= 24) return projected;
    const float hue = (minimum - 12) / (maximum - 12);
    const float chroma = (maximum - 24) / (255 - 24);
    const float total = a + b;
    const float blend = hue*hue*(3-2*hue) * chroma*chroma*(3-2*chroma) *
                        (4*a*b/(total*total));
    const float desired = total * ca / (ca + cb);
    const float change = (desired - a) * blend;
    return add(projected, mul(sub(pigment, blue), change));
}
// Separate white-axis experiment after hue balancing. Redistribute up to a
// quarter of existing white into the same chromatic mixture, preserving black
// and the red/blue or green/blue ratio. The strength is an A/B policy choice,
// not a fitted physical coefficient. Fade at neutral and pigment boundaries.
inline Point reduce_secondary_white(Point original, Point projected,
                                     Point pigment, Point blue, int channel)
{
    if (channel < 0 || channel > 1) return projected;
    const Point white{255,255,255};
    const float det = dot(white,cross(pigment,blue));
    if (det > -0.01f && det < 0.01f) return projected;
    const float w = dot(projected,cross(pigment,blue))/det;
    const float a = dot(white,cross(projected,blue))/det;
    const float b = dot(white,cross(pigment,projected))/det;
    if (w <= 0 || a <= 0 || b <= 0) return projected;
    const float rgb[] = {original.x,original.y,original.z};
    const float neutral = rgb[1-channel];
    const float ca = rgb[channel]-neutral, cb = rgb[2]-neutral;
    const float maximum = ca > cb ? ca : cb;
    const float minimum = ca < cb ? ca : cb;
    if (minimum <= 12 || maximum <= 24) return projected;
    const float hue = (minimum-12)/(maximum-12);
    const float chroma = (maximum-24)/(255-24);
    const float total = a+b;
    const float fade = hue*hue*(3-2*hue) * chroma*chroma*(3-2*chroma) *
                       (4*a*b/(total*total));
    const float removed = w * 0.25f * fade;
    const Point mixture = mul(add(mul(pigment,a),mul(blue,b)),1/total);
    return add(projected,mul(sub(mixture,white),removed));
}
} // namespace papercolor_gamut
