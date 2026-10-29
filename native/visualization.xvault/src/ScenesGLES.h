// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
// Only backdrop and emblem are shaded per pixel. Audio contours use native
// curve geometry so low-power Fire TV GPUs keep full display resolution.
constexpr const char* sceneGLSL=R"glsl(
uniform vec4 screen, audio, transition;
uniform sampler2D emblem;
vec3 base(vec2 p){return vec3(.012,.018,.032)+vec3(.014,.018,.025)*exp(-dot(p,p)*2.5);}
vec3 wordmark(vec2 p,float halfWidth,float intensity){
 vec2 uv=vec2(p.x/(halfWidth*2.0)+.5,p.y/(halfWidth*.674)+.5);
 if(any(lessThan(uv,vec2(0)))||any(greaterThan(uv,vec2(1))))return vec3(0);
 vec4 c=texture(emblem,uv);
 return c.rgb*c.a*intensity;
}
)glsl";
