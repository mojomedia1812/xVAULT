// SPDX-License-Identifier: GPL-2.0-or-later
#include "../src/Bands.h"
#include "../src/Presets.h"
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>

std::array<float,3> tone(int rate,int channels,float hz) {
  visuals::Bands bands;bands.reset(channels,rate);
  std::vector<float> data(512*channels);
  for(int block=0;block<rate*2/512;block++) {
    for(int i=0;i<512;i++)for(int c=0;c<channels;c++)
      data[i*channels+c]=0.4f*std::sin(2*visuals::pi*hz*(block*512+i)/rate);
    bands.process(data.data(),data.size());
  }
  return bands.levels();
}
int main() {
  visuals::Presets presets;
  if(presets.get()!=0 || presets.previous()!=6)throw std::runtime_error("Default/wrapping preset changed");
  for(int i=0;i<7;i++) {
    if(!presets.select(i)||presets.get()!=i||!visuals::presetNames[i][0])throw std::runtime_error("Preset selection failed");
    if(presets.next()!=(i+1)%7)throw std::runtime_error("Next preset wrapping failed");
  }
  if(presets.select(-1)||presets.select(7)||presets.get()!=6)throw std::runtime_error("Invalid preset changed selection");
  for(int rate:{44100,48000,96000})for(int channels:{1,2})for(int b=0;b<3;b++) {
    auto e=tone(rate,channels,b==0?100:b==1?1000:9000);
    if(e[b]<0.65f)throw std::runtime_error("Selected tone not detected");
    for(int other=0;other<3;other++)if(other!=b && e[b]<e[other]*1.7f)
      throw std::runtime_error("Frequency bands do not separate");
  }
  visuals::Bands bands;bands.reset(2,44100);
  std::vector<float> silence(1024);bands.process(silence.data(),silence.size());
  for(auto v:bands.levels())if(v!=0)throw std::runtime_error("Silence moves the lines");
  silence[5]=std::numeric_limits<float>::quiet_NaN();silence[8]=std::numeric_limits<float>::infinity();
  bands.process(silence.data(),silence.size());
  for(auto v:bands.levels())if(!std::isfinite(v)||v<0||v>1)throw std::runtime_error("Invalid audio poisoned energy");
  bands.process(nullptr,0);bands.reset(0,0);
  std::cout<<"PASS: 7 presets, boundary selection/wrapping, 18 tone separation cases, silence, nonfinite input, reset\n";
}
