// xVAULT-Visuals: pastel currents. Original native Kodi visualization.
// SPDX-License-Identifier: GPL-2.0-or-later
#include <kodi/addon-instance/Visualization.h>
#include <d3d11.h>
#include <d3dcompiler.h>
#include <wincodec.h>
#include <array>
#include <chrono>
#include <mutex>
#include <vector>
#include <random>
#include "Bands.h"
#include "Presets.h"
#include "Scenes.h"

namespace {
template<class T> void release(T*& p){if(p){p->Release();p=nullptr;}}
struct Vertex {float x,y,r,g,b,alpha,distance;};
struct Range {UINT offset,count;};
constexpr const char* shader=R"hlsl(
struct V { float2 pos:POSITION; float4 color:COLOR; float distance:TEXCOORD; };
struct P { float4 pos:SV_POSITION; float4 color:COLOR; float distance:TEXCOORD; };
P vs(V v) { P p;p.pos=float4(v.pos,0,1);p.color=v.color;p.distance=v.distance;return p; }
float4 ps(P p):SV_TARGET {
  if(p.distance < -900) {
    if(screen.w<0.5)return p.color;
    float2 pos=(p.pos.xy-transition.zw-screen.xy*.5)/screen.y;
    float3 color=scene(int(screen.w+.5),pos);
    if(transition.y<1 && transition.x>0.5)
      color=lerp(scene(int(transition.x+.5),pos),color,smoothstep(0,1,transition.y));
    return float4(color,1);
  }
  float d=abs(p.distance);
  if(p.color.a>0.5) {
    // A continuous Gaussian light profile, without a solid or sharp centre.
    // Both lobes share the same centreline: softness, not a second strand.
    float soft=0.78*exp(-d*d/20.48)+0.22*exp(-d*d/128.0);
    return float4(p.color.rgb,soft*p.color.a);
  }
  // Keep the subdued sky-blue zero reference as before.
  float aa=max(fwidth(p.distance),0.65);
  float core=1-smoothstep(0.65,0.65+aa,d);
  float halo=0.15*exp(-d*d*0.10);
  return float4(p.color.rgb,saturate(core+halo)*p.color.a);
}
)hlsl";

// Kodi shares its immediate context. Restore every pipeline state we change.
struct Pipeline {
  ID3D11DeviceContext* c;
  ID3D11VertexShader* vs=nullptr;ID3D11PixelShader* ps=nullptr;
  ID3D11InputLayout* layout=nullptr;ID3D11Buffer* vb=nullptr;
  ID3D11BlendState* blend=nullptr;ID3D11RasterizerState* raster=nullptr;
  ID3D11DepthStencilState* depth=nullptr;
  ID3D11Buffer* constant=nullptr;ID3D11ShaderResourceView* texture=nullptr;
  ID3D11SamplerState* sampler=nullptr;
  UINT stride=0,offset=0,mask=0,ref=0,viewportCount=D3D11_VIEWPORT_AND_SCISSORRECT_OBJECT_COUNT_PER_PIPELINE;
  float factors[4]{};D3D11_PRIMITIVE_TOPOLOGY topology;
  D3D11_VIEWPORT viewports[D3D11_VIEWPORT_AND_SCISSORRECT_OBJECT_COUNT_PER_PIPELINE];
  explicit Pipeline(ID3D11DeviceContext* context):c(context) {
    c->VSGetShader(&vs,nullptr,nullptr);c->PSGetShader(&ps,nullptr,nullptr);
    c->IAGetInputLayout(&layout);c->IAGetVertexBuffers(0,1,&vb,&stride,&offset);
    c->IAGetPrimitiveTopology(&topology);c->OMGetBlendState(&blend,factors,&mask);
    c->OMGetDepthStencilState(&depth,&ref);c->RSGetState(&raster);
    c->RSGetViewports(&viewportCount,viewports);
    c->PSGetConstantBuffers(0,1,&constant);c->PSGetShaderResources(0,1,&texture);c->PSGetSamplers(0,1,&sampler);
  }
  ~Pipeline() {
    c->VSSetShader(vs,nullptr,0);c->PSSetShader(ps,nullptr,0);
    c->IASetInputLayout(layout);c->IASetVertexBuffers(0,1,&vb,&stride,&offset);
    c->IASetPrimitiveTopology(topology);c->OMSetBlendState(blend,factors,mask);
    c->OMSetDepthStencilState(depth,ref);c->RSSetState(raster);c->RSSetViewports(viewportCount,viewports);
    c->PSSetConstantBuffers(0,1,&constant);c->PSSetShaderResources(0,1,&texture);c->PSSetSamplers(0,1,&sampler);
    release(vs);release(ps);release(layout);release(vb);release(blend);release(depth);release(raster);
    release(constant);release(texture);release(sampler);
  }
};
}

class XVaultVisuals : public kodi::addon::CAddonBase, public kodi::addon::CInstanceVisualization {
  ID3D11DeviceContext* context=nullptr;ID3D11Device* device=nullptr;
  ID3D11VertexShader* vs=nullptr;ID3D11PixelShader* ps=nullptr;
  ID3D11InputLayout* layout=nullptr;ID3D11Buffer* buffer=nullptr;
  ID3D11BlendState* blend=nullptr;ID3D11RasterizerState* raster=nullptr;
  ID3D11DepthStencilState* depth=nullptr;
  ID3D11Buffer* sceneBuffer=nullptr;ID3D11ShaderResourceView* emblemTexture=nullptr;
  ID3D11SamplerState* emblemSampler=nullptr;
  bool comOwned=false;
  visuals::Bands bands;std::mutex audioMutex;
  visuals::Presets presets;std::atomic<bool> locked{false};
  int renderMode=0,previousMode=0;float modeBlend=1;
  std::array<std::array<float,4>,32> history{};
  float historyClock=0,transient=0,previousBass=0;
  struct alignas(16) SceneConstants {
    float screen[4],audio[4],transition[4];
    std::array<std::array<float,4>,32> history;
  };
  std::array<float,3> displayed{};
  std::vector<Vertex> vertices;std::vector<Range> ranges;
  std::chrono::steady_clock::time_point last=std::chrono::steady_clock::now();
  float elapsed=0;
  static constexpr UINT capacity=160000;
  bool compile(const char* entry,const char* target,ID3DBlob** output) {
    ID3DBlob* errors=nullptr;
    const std::string source=std::string(sceneShader)+shader;
    HRESULT hr=D3DCompile(source.c_str(),source.size(),"xVAULT-Visuals",nullptr,nullptr,entry,target,
                         D3DCOMPILE_OPTIMIZATION_LEVEL3,0,output,&errors);
    if(FAILED(hr)) {
      kodi::Log(ADDON_LOG_ERROR,"xVAULT-Visuals: shader compilation failed (%lx)",static_cast<unsigned long>(hr));
      if(errors)kodi::Log(ADDON_LOG_ERROR,"%s",static_cast<const char*>(errors->GetBufferPointer()));
    }
    release(errors);return SUCCEEDED(hr);
  }
  bool loadEmblem() {
    HRESULT com=CoInitializeEx(nullptr,COINIT_MULTITHREADED);comOwned=SUCCEEDED(com);
    IWICImagingFactory* factory=nullptr;IWICBitmapDecoder* decoder=nullptr;
    IWICBitmapFrameDecode* frame=nullptr;IWICFormatConverter* converter=nullptr;
    ID3D11Texture2D* texture=nullptr;
    HRESULT hr=CoCreateInstance(CLSID_WICImagingFactory,nullptr,CLSCTX_INPROC_SERVER,IID_PPV_ARGS(&factory));
    std::string path=kodi::addon::GetAddonPath("resources/icon.png");
    int chars=MultiByteToWideChar(CP_UTF8,0,path.c_str(),-1,nullptr,0);
    std::vector<wchar_t> wide(chars>0?chars:1);
    if(chars>0)MultiByteToWideChar(CP_UTF8,0,path.c_str(),-1,wide.data(),chars);
    if(SUCCEEDED(hr))hr=factory->CreateDecoderFromFilename(wide.data(),nullptr,GENERIC_READ,WICDecodeMetadataCacheOnLoad,&decoder);
    if(SUCCEEDED(hr))hr=decoder->GetFrame(0,&frame);
    if(SUCCEEDED(hr))hr=factory->CreateFormatConverter(&converter);
    if(SUCCEEDED(hr))hr=converter->Initialize(frame,GUID_WICPixelFormat32bppRGBA,WICBitmapDitherTypeNone,nullptr,0,WICBitmapPaletteTypeCustom);
    UINT w=0,h=0;if(SUCCEEDED(hr))hr=converter->GetSize(&w,&h);
    if(w>4096||h>4096||!w||!h)hr=E_FAIL;
    std::vector<unsigned char> pixels;
    if(SUCCEEDED(hr)){pixels.resize(w*h*4);hr=converter->CopyPixels(nullptr,w*4,static_cast<UINT>(pixels.size()),pixels.data());}
    if(SUCCEEDED(hr)) {
      D3D11_TEXTURE2D_DESC desc{};desc.Width=w;desc.Height=h;desc.MipLevels=1;desc.ArraySize=1;
      desc.Format=DXGI_FORMAT_R8G8B8A8_UNORM;desc.SampleDesc.Count=1;desc.Usage=D3D11_USAGE_IMMUTABLE;desc.BindFlags=D3D11_BIND_SHADER_RESOURCE;
      D3D11_SUBRESOURCE_DATA data{pixels.data(),w*4,0};hr=device->CreateTexture2D(&desc,&data,&texture);
      if(SUCCEEDED(hr))hr=device->CreateShaderResourceView(texture,nullptr,&emblemTexture);
    }
    release(texture);release(converter);release(frame);release(decoder);release(factory);
    return SUCCEEDED(hr);
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
    const UINT start=static_cast<UINT>(vertices.size());
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
    ranges.push_back({start,static_cast<UINT>(vertices.size())-start});
  }
public:
  bool Init() override {
    context=static_cast<ID3D11DeviceContext*>(Device());
    if(!context)return false;
    context->GetDevice(&device);
    int saved=0;kodi::addon::CheckSettingInt("preset",saved);presets.select(saved);renderMode=presets.get();previousMode=renderMode;
    ID3DBlob *v=nullptr,*p=nullptr;
    if(!compile("vs","vs_4_0",&v)||!compile("ps","ps_4_0",&p)){release(v);release(p);return false;}
    HRESULT a=device->CreateVertexShader(v->GetBufferPointer(),v->GetBufferSize(),nullptr,&vs);
    HRESULT b=device->CreatePixelShader(p->GetBufferPointer(),p->GetBufferSize(),nullptr,&ps);
    const D3D11_INPUT_ELEMENT_DESC elements[]={
      {"POSITION",0,DXGI_FORMAT_R32G32_FLOAT,0,0,D3D11_INPUT_PER_VERTEX_DATA,0},
      {"COLOR",0,DXGI_FORMAT_R32G32B32A32_FLOAT,0,8,D3D11_INPUT_PER_VERTEX_DATA,0},
      {"TEXCOORD",0,DXGI_FORMAT_R32_FLOAT,0,24,D3D11_INPUT_PER_VERTEX_DATA,0}};
    HRESULT d=device->CreateInputLayout(elements,3,v->GetBufferPointer(),v->GetBufferSize(),&layout);
    release(v);release(p);
    if(FAILED(a)||FAILED(b)||FAILED(d))return false;
    D3D11_BUFFER_DESC bd{};bd.ByteWidth=capacity*sizeof(Vertex);bd.Usage=D3D11_USAGE_DYNAMIC;
    bd.BindFlags=D3D11_BIND_VERTEX_BUFFER;bd.CPUAccessFlags=D3D11_CPU_ACCESS_WRITE;
    if(FAILED(device->CreateBuffer(&bd,nullptr,&buffer)))return false;
    D3D11_BUFFER_DESC cb{};cb.ByteWidth=sizeof(SceneConstants);cb.Usage=D3D11_USAGE_DYNAMIC;
    cb.BindFlags=D3D11_BIND_CONSTANT_BUFFER;cb.CPUAccessFlags=D3D11_CPU_ACCESS_WRITE;
    if(FAILED(device->CreateBuffer(&cb,nullptr,&sceneBuffer))||!loadEmblem())return false;
    D3D11_SAMPLER_DESC sampler{};sampler.Filter=D3D11_FILTER_MIN_MAG_MIP_LINEAR;
    sampler.AddressU=sampler.AddressV=sampler.AddressW=D3D11_TEXTURE_ADDRESS_CLAMP;sampler.MaxLOD=D3D11_FLOAT32_MAX;
    if(FAILED(device->CreateSamplerState(&sampler,&emblemSampler)))return false;
    D3D11_BLEND_DESC bl{};bl.RenderTarget[0].BlendEnable=TRUE;
    bl.RenderTarget[0].SrcBlend=D3D11_BLEND_SRC_ALPHA;bl.RenderTarget[0].DestBlend=D3D11_BLEND_INV_SRC_ALPHA;
    bl.RenderTarget[0].BlendOp=D3D11_BLEND_OP_ADD;bl.RenderTarget[0].SrcBlendAlpha=D3D11_BLEND_ONE;
    bl.RenderTarget[0].DestBlendAlpha=D3D11_BLEND_INV_SRC_ALPHA;bl.RenderTarget[0].BlendOpAlpha=D3D11_BLEND_OP_ADD;
    bl.RenderTarget[0].RenderTargetWriteMask=D3D11_COLOR_WRITE_ENABLE_ALL;
    D3D11_RASTERIZER_DESC rs{};rs.FillMode=D3D11_FILL_SOLID;rs.CullMode=D3D11_CULL_NONE;rs.DepthClipEnable=TRUE;
    D3D11_DEPTH_STENCIL_DESC ds{};ds.DepthEnable=FALSE;ds.StencilEnable=FALSE;
    if(FAILED(device->CreateBlendState(&bl,&blend))||FAILED(device->CreateRasterizerState(&rs,&raster))
       ||FAILED(device->CreateDepthStencilState(&ds,&depth)))return false;
    vertices.reserve(capacity);ranges.reserve(4);
    kodi::Log(ADDON_LOG_INFO,"xVAULT-Visuals: native Direct3D renderer initialized at %dx%d",Width(),Height());
    return true;
  }
  void DeInit() override {
    release(sceneBuffer);release(emblemTexture);release(emblemSampler);
    release(buffer);release(layout);release(vs);release(ps);release(blend);release(raster);release(depth);release(device);
    context=nullptr;
    if(comOwned){CoUninitialize();comOwned=false;}
  }
  ~XVaultVisuals() override {DeInit();}
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
  bool AudioStart(int channels,int rate,int) override {
    std::lock_guard<std::mutex> lock(audioMutex);bands.reset(channels,rate);displayed={};
    history={};historyClock=0;transient=0;previousBass=0;
    last=std::chrono::steady_clock::now();elapsed=0;return true;
  }
  void AudioData(const float* data,size_t count) override {
    std::lock_guard<std::mutex> lock(audioMutex);bands.process(data,count);
  }
  void Render() override {
    if(!context||!buffer||Width()<=0||Height()<=0)return;
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
    if(renderMode==0) {
      for(int i=0;i<3;i++)line(i,displayed[i],palette[i],0.72f);
      line(-1,0,{0.53f,0.81f,0.94f},0.40f); // fixed sky-blue zero line
    }
    if(vertices.size()>capacity)return;
    D3D11_MAPPED_SUBRESOURCE mapped{};
    if(FAILED(context->Map(buffer,0,D3D11_MAP_WRITE_DISCARD,0,&mapped)))return;
    std::memcpy(mapped.pData,vertices.data(),vertices.size()*sizeof(Vertex));context->Unmap(buffer,0);
    SceneConstants constants{{static_cast<float>(Width()),static_cast<float>(Height()),elapsed,static_cast<float>(renderMode)},
      {displayed[0],displayed[1],displayed[2],transient},
      {static_cast<float>(previousMode),modeBlend,static_cast<float>(X()),static_cast<float>(Y())},history};
    if(FAILED(context->Map(sceneBuffer,0,D3D11_MAP_WRITE_DISCARD,0,&mapped)))return;
    std::memcpy(mapped.pData,&constants,sizeof(constants));context->Unmap(sceneBuffer,0);
    Pipeline saved(context);
    const D3D11_VIEWPORT viewport={static_cast<float>(X()),static_cast<float>(Y()),static_cast<float>(Width()),static_cast<float>(Height()),0,1};
    context->RSSetViewports(1,&viewport);context->RSSetState(raster);
    context->OMSetBlendState(blend,nullptr,0xffffffff);context->OMSetDepthStencilState(depth,0);
    context->VSSetShader(vs,nullptr,0);context->PSSetShader(ps,nullptr,0);context->IASetInputLayout(layout);
    context->PSSetConstantBuffers(0,1,&sceneBuffer);context->PSSetShaderResources(0,1,&emblemTexture);
    context->PSSetSamplers(0,1,&emblemSampler);
    UINT stride=sizeof(Vertex),offset=0;context->IASetVertexBuffers(0,1,&buffer,&stride,&offset);
    context->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);context->Draw(6,0);
    context->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLESTRIP);
    for(const auto& range:ranges)context->Draw(range.count,range.offset);
  }
};
ADDONCREATOR(XVaultVisuals)
