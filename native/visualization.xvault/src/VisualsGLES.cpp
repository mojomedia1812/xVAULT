// xVAULT-Visuals: Kodi 21 Android OpenGL ES renderer.
// SPDX-License-Identifier: GPL-2.0-or-later
#include <kodi/addon-instance/Visualization.h>
#include <GLES3/gl3.h>
#include <array>
#include <chrono>
#include <mutex>
#include <vector>
#include <random>
#include <fstream>
#include <functional>
#include "Bands.h"
#include "Presets.h"
#include "ScenesGLES.h"
namespace {
struct Vertex {float x,y,r,g,b,alpha,distance;};
struct Range {unsigned offset,count;};
// A private VAO avoids touching Kodi's vertex attributes. Restore shared state.
struct Pipeline {
  GLint program,vao,vbo,active,texture,sampler,viewport[4],srcRGB,dstRGB,srcA,dstA,eqRGB,eqA;
  GLboolean blend,depth,cull,scissor,mask[4];
  Pipeline(){
    glGetIntegerv(GL_CURRENT_PROGRAM,&program);glGetIntegerv(GL_VERTEX_ARRAY_BINDING,&vao);
    glGetIntegerv(GL_ARRAY_BUFFER_BINDING,&vbo);glGetIntegerv(GL_ACTIVE_TEXTURE,&active);
    glActiveTexture(GL_TEXTURE0);glGetIntegerv(GL_TEXTURE_BINDING_2D,&texture);glGetIntegerv(GL_SAMPLER_BINDING,&sampler);
    glGetIntegerv(GL_VIEWPORT,viewport);blend=glIsEnabled(GL_BLEND);depth=glIsEnabled(GL_DEPTH_TEST);cull=glIsEnabled(GL_CULL_FACE);scissor=glIsEnabled(GL_SCISSOR_TEST);
    glGetIntegerv(GL_BLEND_SRC_RGB,&srcRGB);glGetIntegerv(GL_BLEND_DST_RGB,&dstRGB);glGetIntegerv(GL_BLEND_SRC_ALPHA,&srcA);glGetIntegerv(GL_BLEND_DST_ALPHA,&dstA);
    glGetIntegerv(GL_BLEND_EQUATION_RGB,&eqRGB);glGetIntegerv(GL_BLEND_EQUATION_ALPHA,&eqA);glGetBooleanv(GL_COLOR_WRITEMASK,mask);
  }
  static void enable(GLenum cap,GLboolean on){if(on)glEnable(cap);else glDisable(cap);}
  ~Pipeline(){
    glUseProgram(program);glBindVertexArray(vao);glBindBuffer(GL_ARRAY_BUFFER,vbo);
    glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,texture);glBindSampler(0,sampler);glActiveTexture(active);
    glViewport(viewport[0],viewport[1],viewport[2],viewport[3]);
    glBlendFuncSeparate(srcRGB,dstRGB,srcA,dstA);glBlendEquationSeparate(eqRGB,eqA);
    enable(GL_BLEND,blend);enable(GL_DEPTH_TEST,depth);enable(GL_CULL_FACE,cull);enable(GL_SCISSOR_TEST,scissor);glColorMask(mask[0],mask[1],mask[2],mask[3]);
  }
};
const char* vertexGLSL=R"glsl(#version 300 es
precision highp float;
layout(location=0) in vec2 position;
layout(location=1) in vec4 color;
layout(location=2) in float aDistance;
out vec4 tint;
out float dist;
void main(){gl_Position=vec4(position,0,1);tint=color;dist=aDistance;}
)glsl";
const char* mobileBackground=R"glsl(
vec3 mobileBackground(vec2 p){
 if(screen.w<.5)return vec3(.018,.027,.052)+wordmark(p,.30,.38);
 float w=.135,intensity=.46;vec2 centre=vec2(0);
 if(screen.w>1.5&&screen.w<2.5)w=.31;
 if(screen.w>2.5&&screen.w<3.5){w=.215;centre=vec2(-.15,-.12);}
 if(screen.w>3.5&&screen.w<4.5)w=.34;
 if(screen.w>4.5&&screen.w<5.5)w=.17;
 if(screen.w>5.5)w=.13;
 return base(p)+wordmark(p-centre,w,intensity+.12*audio.y);
}
)glsl";
const char* fragmentEnd=R"glsl(
in vec4 tint;
in float dist;
out vec4 fragment;
void main(){
 if(dist < -900.0){
   vec2 p=vec2(gl_FragCoord.x-transition.z-screen.x*.5,screen.y*.5-(gl_FragCoord.y-transition.w))/screen.y;
   vec3 color=SCENE_FUNCTION(p);
   fragment=vec4(color,transition.y);return;
 }
 float d=abs(dist);
 if(screen.w>.5 || tint.a>.5){
   float soft=.78*exp(-d*d/20.48)+.22*exp(-d*d/128.0);
   fragment=vec4(tint.rgb,soft*tint.a);
 }else{
   float aa=max(fwidth(dist),.65);
   float core=1.0-smoothstep(.65,.65+aa,d);
   float halo=.15*exp(-d*d*.10);
   fragment=vec4(tint.rgb,clamp(core+halo,0.0,1.0)*tint.a);
 }
}
)glsl";
}
class XVaultVisualsGLES : public kodi::addon::CAddonBase, public kodi::addon::CInstanceVisualization {
  GLuint program=0,vao=0,buffer=0,emblem=0;
  std::array<GLuint,7> programs{};
  GLint uScreen=-1,uAudio=-1,uTransition=-1,uMemory=-1;
  visuals::Bands bands;std::mutex audioMutex;
  visuals::Presets presets;std::atomic<bool> locked{false};
  int renderMode=0,previousMode=0;float modeBlend=1;
  std::array<std::array<float,4>,32> history{};
  float historyClock=0,transient=0,previousBass=0;
  std::array<float,3> displayed{};
  std::vector<Vertex> vertices;std::vector<Range> ranges;
  std::chrono::steady_clock::time_point last=std::chrono::steady_clock::now();
  float elapsed=0;
  GLuint compile(GLenum type,const std::string& source){
    GLuint shader=glCreateShader(type);const char* ptr=source.c_str();glShaderSource(shader,1,&ptr,nullptr);glCompileShader(shader);
    GLint ok=0;glGetShaderiv(shader,GL_COMPILE_STATUS,&ok);
    if(!ok){char log[4096]{};glGetShaderInfoLog(shader,sizeof(log),nullptr,log);kodi::Log(ADDON_LOG_ERROR,"xVAULT-Visuals GLES shader: %s",log);glDeleteShader(shader);return 0;}
    return shader;
  }
  bool bindProgram(int mode){
    program=programs[0];
    if(!program){
    GLuint vs=compile(GL_VERTEX_SHADER,vertexGLSL);
    const char* names[]={"mobileBackground","mobileBackground","mobileBackground","mobileBackground","mobileBackground","mobileBackground","mobileBackground"};
    std::string fragment=std::string("#version 300 es\nprecision highp float;\n#define SCENE_FUNCTION ")+names[mode]+"\n"+sceneGLSL+mobileBackground+fragmentEnd;
    GLuint fs=compile(GL_FRAGMENT_SHADER,fragment);
    if(!vs||!fs){if(vs)glDeleteShader(vs);if(fs)glDeleteShader(fs);return false;}
    program=glCreateProgram();glAttachShader(program,vs);glAttachShader(program,fs);glLinkProgram(program);glDeleteShader(vs);glDeleteShader(fs);
    GLint ok=0;glGetProgramiv(program,GL_LINK_STATUS,&ok);
    if(!ok){char log[2048]{};glGetProgramInfoLog(program,sizeof(log),nullptr,log);kodi::Log(ADDON_LOG_ERROR,"xVAULT-Visuals GLES link: %s",log);glDeleteProgram(program);program=0;return false;}
      programs[0]=program;
      kodi::Log(ADDON_LOG_INFO,"xVAULT-Visuals GLES: shader ready for preset %d",mode);
    }
    uScreen=glGetUniformLocation(program,"screen");uAudio=glGetUniformLocation(program,"audio");uTransition=glGetUniformLocation(program,"transition");uMemory=glGetUniformLocation(program,"memory[0]");
    glUseProgram(program);glUniform1i(glGetUniformLocation(program,"emblem"),0);return true;
  }
  bool initGL(){
    Pipeline saved;
    int selected=0;kodi::addon::CheckSettingInt("preset",selected);presets.select(selected);renderMode=presets.get();previousMode=renderMode;
    if(!bindProgram(renderMode))return false;
    glGenVertexArrays(1,&vao);glBindVertexArray(vao);glGenBuffers(1,&buffer);glBindBuffer(GL_ARRAY_BUFFER,buffer);
    glVertexAttribPointer(0,2,GL_FLOAT,GL_FALSE,sizeof(Vertex),nullptr);glEnableVertexAttribArray(0);
    glVertexAttribPointer(1,4,GL_FLOAT,GL_FALSE,sizeof(Vertex),reinterpret_cast<void*>(8));glEnableVertexAttribArray(1);
    glVertexAttribPointer(2,1,GL_FLOAT,GL_FALSE,sizeof(Vertex),reinterpret_cast<void*>(24));glEnableVertexAttribArray(2);
    std::ifstream file(kodi::addon::GetAddonPath("resources/emblem.rgba"),std::ios::binary);
    std::vector<unsigned char> pixels(2048*690*4);file.read(reinterpret_cast<char*>(pixels.data()),pixels.size());
    if(!file){kodi::Log(ADDON_LOG_ERROR,"xVAULT-Visuals: missing emblem texture");Stop();return false;}
    glGenTextures(1,&emblem);glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,emblem);
    glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA,2048,690,0,GL_RGBA,GL_UNSIGNED_BYTE,pixels.data());
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_LINEAR);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_S,GL_CLAMP_TO_EDGE);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_WRAP_T,GL_CLAMP_TO_EDGE);
    uScreen=glGetUniformLocation(program,"screen");uAudio=glGetUniformLocation(program,"audio");uTransition=glGetUniformLocation(program,"transition");uMemory=glGetUniformLocation(program,"memory[0]");
    glUseProgram(program);glUniform1i(glGetUniformLocation(program,"emblem"),0);
    vertices.reserve(66000);ranges.reserve(4);
    kodi::Log(ADDON_LOG_INFO,"xVAULT-Visuals GLES: initialized %dx%d; seven presets",Width(),Height());return true;
  }
  float wave(float x,int band,float level) {
    const float phase=band*0.8f,t=elapsed*0.23f;
    const float s=std::sin(x*static_cast<float>(visuals::pi));
    const float envelope=0.55f+0.45f*s*s;
    float value=std::sin(x*11-t+phase)+0.32f*std::sin(x*19+t*0.7f+phase*1.4f)
      +(band==0?0.0f:band==1?0.10f:0.25f)*std::sin(x*37-t*1.3f+phase);
    const float amplitude[3]={0.20f,0.16f,0.12f};
    return Height()*0.5f-envelope*level*Height()*amplitude[band]*value;
  }
  void point(float x,float y,const std::array<float,3>& color,float alpha,float distance) {
    vertices.push_back({2*x/Width()-1,1-2*y/Height(),color[0],color[1],color[2],alpha,distance});
  }
  void line(int band,float level,const std::array<float,3>& color,float alpha) {
    const unsigned start=static_cast<unsigned>(vertices.size());
    const int steps=std::clamp(Width(),320,8192); // one sample per physical pixel
    const float radius=band<0?3.0f:32.0f; // Gaussian fades to negligible opacity before the ribbon edge.
    for(int i=0;i<=steps;i++) {
      float x=static_cast<float>(i)/steps,px=x*Width();
      float y=band<0?Height()*0.5f:wave(x,band,level);
      float slope=band<0?0:(wave(x+0.0005f,band,level)-wave(x-0.0005f,band,level))/(0.001f*Width());
      float norm=1/std::sqrt(1+slope*slope),nx=-slope*norm,ny=norm;
      point(px+nx*radius,y+ny*radius,color,alpha,radius);
      point(px-nx*radius,y-ny*radius,color,alpha,-radius);
    }
    ranges.push_back({start,static_cast<unsigned>(vertices.size())-start});
  }
  struct P {float x,y;};
  const std::array<float,3> rose{.94f,.69f,.78f},mint{.63f,.87f,.80f},lavender{.76f,.74f,.96f},red{.86f,.20f,.27f},silver{.66f,.73f,.82f};
  P rotate(P p,float a){return {std::cos(a)*p.x-std::sin(a)*p.y,std::sin(a)*p.x+std::cos(a)*p.y};}
  void curve(const std::function<P(float)>& shape,const std::array<float,3>& color,float alpha,int steps=240,const std::function<float(float)>& fade={}){
    unsigned start=vertices.size();const float radius=12;
    P before=shape(-1.0f/steps),current=shape(0);
    for(int i=0;i<=steps;i++){
      float u=float(i)/steps;P next=shape(u+1.0f/steps);
      float dx=(next.x-before.x)*Height(),dy=(next.y-before.y)*Height();float norm=std::max(.00001f,std::hypot(dx,dy));
      float nx=-dy/norm,ny=dx/norm;float px=Width()*.5f+current.x*Height(),py=Height()*.5f+current.y*Height();
      float opacity=alpha*(fade?fade(u):1);
      point(px+nx*radius,py+ny*radius,color,opacity,radius);point(px-nx*radius,py-ny*radius,color,opacity,-radius);
      before=current;current=next;
    }
    ranges.push_back({start,unsigned(vertices.size())-start});
  }
  void dot(P p,const std::array<float,3>& color,float alpha,float radius){
    curve([=](float u){float a=u*2*visuals::pi;return P{p.x+radius*std::cos(a),p.y+radius*std::sin(a)};},color,alpha,24);
  }
  void mobileScene(int mode){
    float t=elapsed,b=displayed[0],m=displayed[1],h=displayed[2];
    const float tau=2*visuals::pi;
    if(mode==1){
      for(int i=0;i<6;i++){
        float r=.17f+i*.029f+(.025f*b+.018f*transient)*(i*.35f+1),spin=t*(.025f+i*.004f)*(i%2?-1:1);
        curve([=](float u){float a=u*tau;return P{r*std::cos(a),r*std::sin(a)};},i%2?red:silver,.38f,320,
          [=](float u){return std::clamp((std::abs(std::sin(u*tau*1.5f+spin+i*.8f))-.12f)/.16f,0.f,1.f);});
      }
      for(int i=0;i<6;i++){float a=t*.05f+i*tau/6;dot({.32f*std::cos(a),.32f*std::sin(a)},red,.35f*h,.002f);}
    }else if(mode==2){
      for(int i=0;i<5;i++){
        float r=.26f+i*.009f;
        curve([=](float u){float a=u*tau;float d=r+.016f*b*std::sin(a*3+t*.16f)+.012f*m*std::sin(a*7-t*.2f);return P{d*1.25f*std::cos(a),d*.72f*std::sin(a)};},i%2?lavender:red,.13f+i*.04f,320);
      }
      for(int i=0;i<7;i++){float a=i*2.4f+t*.06f,r=.30f+.045f*b*std::sin(i+t*.3f);dot({std::cos(a)*r*1.22f,std::sin(a)*r*.65f},silver,.20f+transient*.2f,.002f);}
    }else if(mode==3){
      for(int i=23;i>=0;i--){
        float depth=float(i)/24,scale=1-depth*.65f;auto energy=history[i];
        curve([=](float u){float a=u*tau,r=.33f+energy[0]*.045f*std::sin(a*3)+energy[1]*.025f*std::cos(a*7)+energy[2]*.012f*std::sin(a*15);return P{-.15f+depth*.37f+r*std::cos(a)*scale,-.12f+depth*.34f+r*std::sin(a)/1.7f*scale};},i%4?red:silver,std::pow(1-depth,.8f)*(.19f+.17f*energy[0]),200);
      }
    }else if(mode==4){
      for(int i=0;i<12;i++)for(int sign:{-1,1}){
        auto color=i%3==0?rose:i%3==1?mint:lavender;
        curve([=](float u){float x=(u-.5f)*1.06f,w=.026f*std::sin(x*10+t*.25f+i*.35f)*b;return P{x,sign*(x*.48f*(.3f+.7f*m)+w)+(i-5.5f)*.008f};},color,.18f,180,
          [=](float u){float x=(u-.5f)*1.06f;return std::exp(-std::pow(std::abs(x)/.47f,6))*(.6f+.4f*std::sin(x*7-t*(.45f+h)+i*.6f));});
      }
    }else if(mode==5){
      P centre{.018f*std::sin(t*.08f),.012f*std::cos(t*.07f)};float open=.008f+.020f*b;
      for(int i=0;i<3;i++){
        curve([=](float u){float a=u*tau,r=.265f+i*open*.5f;return P{centre.x+r*std::cos(a),centre.y+r*std::sin(a)};},i==1?silver:red,.26f+i*.07f,360);
      }
      for(int i=0;i<3;i++)curve([=](float u){P q{(u-.5f)*.48f,(i-1)*.055f};q=rotate(q,-.32f*i-t*.025f);return P{q.x+centre.x,q.y+centre.y};},i==1?silver:red,.11f+.10f*m,120);
    }else if(mode==6){
      for(int i=0;i<3;i++){
        float rotation=.42f+i*.91f+.045f*std::sin(t*.1f+i),radius=(.31f+i*.025f)*(1-.08f*b-.045f*transient);
        auto color=i==0?rose:i==1?mint:lavender;
        curve([=](float u){float a=u*tau;return rotate({std::cos(a)*radius,std::sin(a)*radius*(.38f+i*.06f)},-rotation);},color,.27f,320);
        for(int j=0;j<3;j++){float a=t*(.10f+i*.025f)+j*2.094f+i;P p=rotate({std::cos(a)*radius,std::sin(a)*radius*(.38f+i*.06f)},-rotation);dot(p,color,.40f+.25f*h,.002f+.002f*h);}
      }
      curve([=](float u){float a=u*tau;return P{.105f*std::cos(a),.105f*std::sin(a)};},red,.16f+.12f*b,150);
    }
  }
public:
  void Stop() override {
    if(emblem)glDeleteTextures(1,&emblem);if(buffer)glDeleteBuffers(1,&buffer);if(vao)glDeleteVertexArrays(1,&vao);for(auto id:programs)if(id)glDeleteProgram(id);programs={};
    emblem=buffer=vao=program=0;
  }
  ~XVaultVisualsGLES() override {Stop();}
  bool GetPresets(std::vector<std::string>& names) override {
    names.assign(visuals::presetNames.begin(),visuals::presetNames.end());return true;
  }
  int GetActivePreset() override {return presets.get();}
  bool LoadPreset(int index) override {
    if(!presets.select(index))return false;
    kodi::addon::SetSettingInt("preset",index);
    kodi::Log(ADDON_LOG_INFO,"xVAULT-Visuals: preset %d (%s)",index,visuals::presetNames[index]);return true;
  }
  bool NextPreset() override {return LoadPreset(presets.next());}
  bool PrevPreset() override {return LoadPreset(presets.previous());}
  bool RandomPreset() override {
    static std::mt19937 rng(std::random_device{}());
    return LoadPreset((presets.get()+1+static_cast<int>(rng()%6))%7);
  }
  bool IsLocked() override {return locked.load();}
  bool LockPreset(bool value) override {locked.store(value);return true;}
  ADDON_STATUS SetSetting(const std::string& name,const kodi::addon::CSettingValue& value) override {
    if(name=="preset")return presets.select(value.GetInt())?ADDON_STATUS_OK:ADDON_STATUS_UNKNOWN;
    return ADDON_STATUS_OK;
  }
  bool Start(int channels,int rate,int,const std::string&) override {
    std::lock_guard<std::mutex> lock(audioMutex);bands.reset(channels,rate);displayed={};
    history={};historyClock=0;transient=0;previousBass=0;
    last=std::chrono::steady_clock::now();elapsed=0;return initGL();
  }
  void AudioData(const float* data,size_t count) override {
    std::lock_guard<std::mutex> lock(audioMutex);bands.process(data,count);
  }
  void Render() override {
    if(!program||Width()<=0||Height()<=0)return;
    const auto now=std::chrono::steady_clock::now();
    float dt=std::clamp(std::chrono::duration<float>(now-last).count(),0.0f,0.1f);last=now;elapsed+=dt;
    std::array<float,3> levels;
    {std::lock_guard<std::mutex> lock(audioMutex);levels=bands.levels();}
    for(int i=0;i<3;i++)displayed[i]+=(levels[i]-displayed[i])*(1-std::exp(-dt/0.065f));
    transient=std::max(transient*std::exp(-dt/0.4f),std::clamp((displayed[0]-previousBass)*7,0.0f,1.0f));previousBass=displayed[0];
    historyClock+=dt;
    if(historyClock>=.25f) {
      historyClock=0;
      for(size_t i=history.size()-1;i>0;i--)history[i]=history[i-1];
      history[0]={displayed[0],displayed[1],displayed[2],transient};
    }
    const int selected=presets.get();
    if(selected!=renderMode){previousMode=renderMode;renderMode=selected;modeBlend=0;}
    modeBlend=std::min(1.0f,modeBlend+dt/0.65f);
    vertices.clear();ranges.clear();
    const std::array<float,3> ink={0.018f,0.027f,0.052f};
    point(0,0,ink,1,-1000);point(Width(),0,ink,1,-1000);point(0,Height(),ink,1,-1000);
    point(0,Height(),ink,1,-1000);point(Width(),0,ink,1,-1000);point(Width(),Height(),ink,1,-1000);
    const std::array<std::array<float,3>,3> palette={{{0.94f,0.69f,0.78f},{0.63f,0.87f,0.80f},{0.76f,0.74f,0.96f}}};
    auto geometry=[&](int mode,float alpha){
      size_t first=vertices.size();
      if(mode==0){
        for(int i=0;i<3;i++)line(i,displayed[i],palette[i],.72f);
        line(-1,0,{.53f,.81f,.94f},.40f);
      }else mobileScene(mode);
      for(size_t i=first;i<vertices.size();i++)vertices[i].alpha*=alpha;
    };
    float fade=modeBlend*modeBlend*(3-2*modeBlend);
    bool crossfade=renderMode>0 && previousMode>0 && modeBlend<1;
    if(crossfade)geometry(previousMode,1-fade);
    geometry(renderMode,crossfade?fade:1);

    Pipeline saved;
    if(!bindProgram(renderMode))return;
    glBindVertexArray(vao);glBindBuffer(GL_ARRAY_BUFFER,buffer);
    glBufferData(GL_ARRAY_BUFFER,vertices.size()*sizeof(Vertex),vertices.data(),GL_STREAM_DRAW);
    glActiveTexture(GL_TEXTURE0);glBindTexture(GL_TEXTURE_2D,emblem);glBindSampler(0,0);
    glViewport(X(),Y(),Width(),Height());glDisable(GL_DEPTH_TEST);glDisable(GL_CULL_FACE);glDisable(GL_SCISSOR_TEST);glEnable(GL_BLEND);glColorMask(GL_TRUE,GL_TRUE,GL_TRUE,GL_TRUE);
    glBlendEquationSeparate(GL_FUNC_ADD,GL_FUNC_ADD);glBlendFuncSeparate(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA,GL_ONE,GL_ONE_MINUS_SRC_ALPHA);
    auto uniforms=[&](int mode,float alpha){
      if(!bindProgram(mode))return false;
      glUniform4f(uScreen,Width(),Height(),elapsed,mode);glUniform4f(uAudio,displayed[0],displayed[1],displayed[2],transient);
      glUniform4f(uTransition,previousMode,alpha,X(),Y());glUniform4fv(uMemory,32,history[0].data());return true;
    };
    if(crossfade){
      if(uniforms(previousMode,1))glDrawArrays(GL_TRIANGLES,0,6);
      if(uniforms(renderMode,fade))glDrawArrays(GL_TRIANGLES,0,6);
    }else if(uniforms(renderMode,1))glDrawArrays(GL_TRIANGLES,0,6);
    for(const auto& range:ranges)glDrawArrays(GL_TRIANGLE_STRIP,range.offset,range.count);
  }
};
ADDONCREATOR(XVaultVisualsGLES)
