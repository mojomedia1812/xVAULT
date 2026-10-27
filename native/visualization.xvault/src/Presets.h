// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <array>
#include <atomic>

namespace visuals {
inline constexpr std::array<const char*,7> presetNames={
  "Pastelllinien", "Resonance", "Liquid Emblem", "Klangarchiv", "Lichtgewebe", "Eclipse", "Gravity"
};
class Presets {
  std::atomic<int> active{0};
public:
  int get() const {return active.load();}
  bool select(int index) {
    if(index<0||index>=static_cast<int>(presetNames.size()))return false;
    active.store(index);return true;
  }
  int next() const {return (get()+1)%static_cast<int>(presetNames.size());}
  int previous() const {return (get()+static_cast<int>(presetNames.size())-1)%static_cast<int>(presetNames.size());}
};
}
