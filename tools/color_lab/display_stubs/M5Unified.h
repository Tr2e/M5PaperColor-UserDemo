#pragma once
#include <algorithm>
#include <array>
#include <cstdint>
#include <vector>
struct RGBColor {
    uint8_t r=0,g=0,b=0;
    constexpr RGBColor()=default;
    constexpr RGBColor(uint8_t r_,uint8_t g_,uint8_t b_):r(r_),g(g_),b(b_){}
    bool operator==(const RGBColor& p) const {return r==p.r && g==p.g && b==p.b;}
    bool operator!=(const RGBColor& p) const {return !(*this==p);}
};
enum class epd_mode_t {epd_quality,epd_fastest};
struct MockDisplay {
    int width=600,height=400,starts=0,ends=0,pushes=0;
    epd_mode_t mode=epd_mode_t::epd_quality;
    std::array<int32_t,4> clip{0,0,600,400};
    std::vector<RGBColor> pixels=std::vector<RGBColor>(600*400);
    void reset(int w=600,int h=400) {width=w;height=h;starts=ends=pushes=0;clip={0,0,w,h};pixels.assign(w*h,{1,2,3});mode=epd_mode_t::epd_quality;}
    auto getEpdMode() const {return mode;}
    void setEpdMode(epd_mode_t m) {mode=m;}
    void startWrite(){++starts;}
    void endWrite(){++ends;}
    void pushImage(int x,int y,int w,int h,const RGBColor* data) {
        ++pushes;
        for(int j=0;j<h;++j) for(int i=0;i<w;++i) {
            int px=x+i,py=y+j;
            if(px>=0 && py>=0 && px<width && py<height && px>=clip[0] && py>=clip[1] && px<clip[0]+clip[2] && py<clip[1]+clip[3])
                pixels[py*width+px]=data[j*w+i];
        }
    }
};
struct MockM5 {MockDisplay Display;};
extern MockM5 M5;
namespace m5gfx {
constexpr int rgb565_2Byte=16;
class M5Canvas {
public:
    int bw,bh,depth=16,legacy_pushes=0;
    uint8_t rotation=0;
    std::array<int32_t,4> clip{},scroll{};
    std::vector<uint16_t> buffer;
    M5Canvas(int w,int h):bw(w),bh(h),buffer(w*h){setRotation(0);}
    int width()const{return (rotation&1)?bh:bw;}
    int height()const{return (rotation&1)?bw:bh;}
    uint8_t getRotation()const{return rotation;}
    void setRotation(uint8_t r){rotation=r;clip={0,0,width(),height()};scroll=clip;}
    void getClipRect(int32_t*x,int32_t*y,int32_t*w,int32_t*h)const{*x=clip[0];*y=clip[1];*w=clip[2];*h=clip[3];}
    void getScrollRect(int32_t*x,int32_t*y,int32_t*w,int32_t*h)const{*x=scroll[0];*y=scroll[1];*w=scroll[2];*h=scroll[3];}
    void setClipRect(int x,int y,int w,int h){clip={x,y,w,h};}
    void setScrollRect(int x,int y,int w,int h){scroll={x,y,w,h};}
    int getColorDepth()const{return depth;}
    void* getBuffer(){return buffer.data();}
    size_t bufferLength()const{return buffer.size()*2;}
    void pushSprite(int,int){++legacy_pushes;}
    void readRectRGB(int x,int y,int w,int h,RGBColor* out)const{
        for(int j=0;j<h;++j)for(int i=0;i<w;++i){
            uint16_t v=buffer[(y+j)*bw+x+i];v=uint16_t((v<<8)|(v>>8));
            unsigned r=v>>11,g=(v>>5)&63,b=v&31;
            out[j*w+i]={uint8_t((r<<3)|(r>>2)),uint8_t((g<<2)|(g>>4)),uint8_t((b<<3)|(b>>2))};
        }
    }
};
}
