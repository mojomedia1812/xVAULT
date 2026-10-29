// Original xVAULT scenes. SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
constexpr const char* sceneShader=R"hlsl(
cbuffer Scene : register(b0) {
  float4 screen; // width, height, elapsed seconds, mode
  float4 audio; // bass, mids, treble, transient envelope
  float4 transition; // previous mode, mix, viewport x, viewport y
  float4 memory[32]; // actual recent smoothed audio levels, newest first
};
Texture2D emblem : register(t0);
SamplerState emblemSampler : register(s0);
static const float PI=3.141592654;
static const float3 rose=float3(.94,.69,.78), mint=float3(.63,.87,.80), lavender=float3(.76,.74,.96);
static const float3 red=float3(.86,.20,.27), silver=float3(.66,.73,.82);
float2 rotate(float2 p,float angle) {
  float s=sin(angle),c=cos(angle);return float2(c*p.x-s*p.y,s*p.x+c*p.y);
}
float light(float distance,float pixels) {
  float w=pixels/max(screen.y,1.0);return exp(-distance*distance/(w*w));
}
float3 base(float2 p) {
  return float3(.012,.018,.032)+float3(.014,.018,.025)*exp(-dot(p,p)*2.5);
}
float3 wordmark(float2 p,float halfWidth,float intensity) {
  float2 uv=float2(p.x/(halfWidth*2)+.5,p.y/(halfWidth*.674)+.5);
  if(any(uv<0)||any(uv>1))return 0;
  // Sample the real xVAULT wordmark from the shipped icon, preserving its colours.
  float4 c=emblem.SampleLevel(emblemSampler,uv,0);
  return c.rgb*c.a*intensity;
}
float3 resonance(float2 p) {
  float2 q=p;float r=length(q),a=atan2(q.y,q.x),t=screen.z;
  float opening=.025*audio.x+.018*audio.w;
  float3 c=base(p);
  c+=red*.09*exp(-r*r*12)*(audio.x+.15);
  for(int i=0;i<6;i++) {
    float fi=float(i),radius=.17+fi*.029+opening*(fi*.35+1);
    float rot=t*(.025+fi*.004)*(i%2==0?1:-1);
    float arc=smoothstep(.12,.28,abs(sin(a*1.5+rot+fi*.8)));
    float radial=r-radius;
    c+=lerp(silver,red,fi/7)*arc*(light(radial,2.8)*.42+light(radial,11)*.08);
    float gates=pow(saturate(cos((a+rot)*12)),24.0);
    c+=red*light(radial,5)*gates*(.16+.6*audio.z);
  }
  float surface=saturate(1-r/.165);
  c+=silver*.045*surface*(.7+.3*sin(a*3+t*.15));
  c+=wordmark(p,.135,.34+audio.y*.25);
  float pressure=frac(t*.13); // audio controls visibility of the pressure front
  c+=rose*light(r-(.25+pressure*.20),8)*audio.w*(1-pressure)*.22;
  return c;
}
float3 liquid(float2 p) {
  float t=screen.z;
  float2 q=p;
  q.x+=.015*audio.x*sin(p.y*15+t*.55);
  q.y+=.020*audio.y*sin(p.x*10-t*.35)+.005*audio.z*sin(p.x*37+t);
  float radius=length(float2(q.x*.77,q.y*1.25));
  float edge=.28+.016*sin(atan2(q.y,q.x)*3+t*.16)*audio.x;
  float body=1-smoothstep(edge-.025,edge+.015,radius);
  float glint=.5+.5*sin(q.x*11+q.y*8+t*.20+audio.y);
  float3 c=base(p)+body*lerp(float3(.025,.031,.045),silver*.16,glint*glint);
  c+=lerp(red,lavender,saturate(q.x+0.5))*light(radius-edge,7)*(.22+.2*audio.z);
  c+=mint*light(radius-edge+.012,12)*.035;
  c+=wordmark(q,.31,.50+glint*.22);
  for(int i=0;i<7;i++) {
    float f=float(i),a=f*2.4+t*.06;
    float orbit=.30+.045*audio.x*sin(f+t*.3);
    float2 pos=float2(cos(a)*orbit*1.22,sin(a)*orbit*.65);
    float d=length(p-pos);
    c+=lerp(silver,rose,frac(f*.37))*light(d,3.5+audio.z*3)*audio.w*.18;
  }
  return c;
}
float3 archive(float2 p) {
  float3 c=base(p);
  for(int i=23;i>=0;i--) {
    float f=float(i),depth=f/24,scale=1-depth*.65;
    float2 centre=float2(-.15+depth*.37,-.12+depth*.34);
    float2 q=(p-centre)/scale;
    float a=atan2(q.y*1.7,q.x),r=length(float2(q.x,q.y*1.7));
    float contour=.33+memory[i].x*.045*sin(a*3)+memory[i].y*.025*cos(a*7)+memory[i].z*.012*sin(a*15);
    float fade=pow(1-depth,.8);
    float3 tone=lerp(red,silver,depth);
    c+=tone*light((r-contour)*scale,2.5+depth*2)*fade*(.19+.17*memory[i].x);
  }
  c+=wordmark(p-float2(-.15,-.12),.215,.44);
  return c;
}
float3 weave(float2 p) {
  float t=screen.z,unfold=.3+.7*audio.y;
  float3 c=base(p);
  for(int i=0;i<12;i++) {
    float f=float(i),o=(f-5.5)*.008;
    float wave=.026*sin(p.x*10+t*.25+f*.35)*audio.x;
    float y1=p.x*.48*unfold+o+wave;
    float y2=-p.x*.48*unfold+o-wave;
    float window=exp(-pow(abs(p.x)/.47,6));
    float3 color=i%3==0?rose:i%3==1?mint:lavender;
    float pulse=.6+.4*sin(p.x*7-t*(.45+audio.z)+f*.6);
    c+=color*(light(p.y-y1,2.8)+light(p.y-y2,2.8))*window*pulse*.09;
  }
  float visibility=.32+.12*sin(t*.17)+audio.y*.15;
  c+=wordmark(p,.34,visibility);
  return c;
}
float3 eclipse(float2 p) {
  float t=screen.z;
  float2 centre=float2(.018*sin(t*.08),.012*cos(t*.07));
  float r=length(p-centre),a=atan2(p.y-centre.y,p.x-centre.x);
  float radius=.265;
  float aperture=.008+.020*audio.x;
  float3 c=base(p);
  c+=lerp(red,rose,saturate(sin(a+t*.06)*.5+.5))*(light(r-radius,18+audio.x*24)*.23);
  float2 rear=centre+float2(aperture*1.2,-aperture*.5);
  c+=silver*light(length(p-rear)-radius,4)*(.18+.20*audio.y);
  float disk=1-smoothstep(radius-.003,radius+.003,r);
  c=lerp(c,float3(.018,.022,.030)+silver*.025*(.5+.5*cos(a)),disk);
  c+=red*light(r-radius,3)*(.17+.12*audio.z);
  for(int i=0;i<3;i++) {
    float2 q=rotate(p-centre,.32*float(i)+t*.025);
    float gap=light(q.y-(float(i)-1)*.055,3);
    float inside=1-smoothstep(radius-.02,radius,r);
    c+=lerp(red,silver,float(i)/3)*gap*inside*(.055+.10*audio.y);
  }
  c+=wordmark(p-centre,.17,.27+.12*audio.y);
  return c;
}
float3 gravity(float2 p) {
  float t=screen.z;
  float pull=1-.08*audio.x-.045*audio.w;
  float3 c=base(p);
  for(int i=0;i<3;i++) {
    float f=float(i),rotation=.42+f*.91+.045*sin(t*.1+f);
    float2 q=rotate(p,rotation);
    float radius=(.31+f*.025)*pull;
    float r=length(float2(q.x,q.y/(.38+f*.06)));
    float front=.5+.5*smoothstep(-.1,.1,q.y);
    float3 color=i==0?rose:i==1?mint:lavender;
    c+=color*light(r-radius,5)*(.12+.10*front);
    for(int j=0;j<3;j++) {
      float a=t*(.10+f*.025)+float(j)*2.094+f;
      float2 pos=rotate(float2(cos(a)*radius,sin(a)*radius*(.38+f*.06)),-rotation);
      c+=color*light(length(p-pos),4+3*audio.z)*(.16+.18*audio.z);
    }
  }
  float r=length(p);
  c*=.3+.7*smoothstep(.07,.16,r);
  c+=red*light(r-.105,9)*(.09+.12*audio.x);
  c+=wordmark(p,.13,.36+.12*audio.y);
  return c;
}
float3 scene(int mode,float2 p) {
  if(mode==1)return resonance(p);
  if(mode==2)return liquid(p);
  if(mode==3)return archive(p);
  if(mode==4)return weave(p);
  if(mode==5)return eclipse(p);
  if(mode==6)return gravity(p);
  return base(p);
}
)hlsl";
