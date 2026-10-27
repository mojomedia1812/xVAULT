// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <algorithm>
#include <array>
#include <cmath>

namespace visuals {
constexpr double pi = 3.14159265358979323846;

// RBJ biquads: separation is done once per incoming sample, never per pixel.
struct Biquad {
  double b0=1,b1=0,b2=0,a1=0,a2=0,z1=0,z2=0;
  void configure(double rate, double hz, bool highpass) {
    hz=std::clamp(hz, 10.0, rate*0.45);
    const double w=2*pi*hz/rate, c=std::cos(w), a=std::sin(w)/std::sqrt(2.0);
    const double d=1+a;
    b0=(highpass ? 1+c : 1-c)/(2*d);
    b1=(highpass ? -(1+c) : 1-c)/d;
    b2=b0; a1=-2*c/d; a2=(1-a)/d; z1=z2=0;
  }
  double process(double v) {
    const double out=b0*v+z1;
    z1=b1*v-a1*out+z2; z2=b2*v-a2*out;
    return out;
  }
};

class Bands {
  std::array<Biquad,3> hp,lp;
  std::array<float,3> energy{};
  int channels=2, rate=44100;
public:
  void reset(int channelCount,int sampleRate) {
    channels=std::clamp(channelCount,1,16);rate=std::clamp(sampleRate,8000,384000);
    const double lows[3]={40,250,4000}, highs[3]={250,4000,16000};
    for(int i=0;i<3;i++){hp[i].configure(rate,lows[i],true);lp[i].configure(rate,highs[i],false);}
    energy={};
  }
  void process(const float* data,size_t count) {
    const size_t frames=count/channels;
    if(!frames || !data)return;
    std::array<double,3> squares{};
    for(size_t f=0;f<frames;f++) {
      double mono=0;
      for(int c=0;c<channels;c++) {
        float v=data[f*channels+c];
        if(std::isfinite(v))mono+=std::clamp(v,-4.0f,4.0f);
      }
      mono/=channels;
      for(int i=0;i<3;i++){double v=lp[i].process(hp[i].process(mono));squares[i]+=v*v;}
    }
    for(int i=0;i<3;i++) {
      const float rms=static_cast<float>(std::sqrt(squares[i]/frames));
      // Soft knee: silence stays still, loud material never hits the screen edge.
      const float target=std::clamp(1.0f-std::exp(-std::max(0.0f,rms-0.0015f)*9.0f),0.0f,1.0f);
      const float seconds=target>energy[i] ? 0.035f : 0.23f;
      const float blend=1-std::exp(-static_cast<float>(frames)/(rate*seconds));
      energy[i]+=(target-energy[i])*blend;
    }
  }
  std::array<float,3> levels() const{return energy;}
};
}
