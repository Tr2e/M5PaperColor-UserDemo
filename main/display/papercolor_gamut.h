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
} // namespace papercolor_gamut
