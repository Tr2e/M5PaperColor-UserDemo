/* SPDX-License-Identifier: MIT */
// Link the real display adapter and photo algorithm; only M5/ESP I/O is fake.
#include <M5Unified.h>
#include <esp_heap_caps.h>
#include "display/papercolor_lut_display.h"
#include "display/papercolor_region_dither.h"
#include <cassert>
#include <cstdio>
#include <limits>

MockM5 M5;
static uint16_t pack(unsigned r,unsigned g,unsigned b){uint16_t p=((r>>3)<<11)|((g>>2)<<5)|(b>>3);return uint16_t((p<<8)|(p>>8));}
static bool inside(const PaperColorPhotoRegion&r,int x,int y){return x>=r.x&&x<r.x+r.width&&y>=r.y&&y<r.y+r.height;}
static std::vector<RGBColor> render(m5gfx::M5Canvas& c,PaperColorRenderMode mode,const PaperColorPhotoRegion* r=nullptr,size_t n=0){
    M5.Display.reset(c.bw,c.bh);
    c.setClipRect(3,4,17,19);c.setScrollRect(5,6,13,11);
    const auto rot=c.rotation;const auto clip=c.clip,scroll=c.scroll;
    papercolor_push_canvas(&c,0,0,mode,r,n);
    assert(c.rotation==rot&&c.clip==clip&&c.scroll==scroll);
    assert(M5.Display.starts==1&&M5.Display.ends==1&&M5.Display.pushes==c.bh);
    assert(M5.Display.mode==epd_mode_t::epd_quality&&mock_allocations==0&&c.legacy_pushes==0);
    return M5.Display.pixels;
}
int main(){
    // Logical layouts correspond to the SAME physical rectangles in each
    // rotation. A swapped-width/height or reflected corner bug breaks equality.
    const PaperColorPhotoRegion physical[]={{57,16,145,176},{547,306,46,78}};
    const PaperColorPhotoRegion logical[4][2]={
        {{57,16,145,176},{547,306,46,78}},
        {{16,398,176,145},{306,7,78,46}},
        {{398,208,145,176},{7,16,46,78}},
        {{208,57,176,145},{16,547,78,46}}
    };
    std::vector<RGBColor> first_mixed;
    for(unsigned rot=0;rot<4;++rot){
        m5gfx::M5Canvas c(600,400);c.setRotation(rot);
        for(int y=0;y<400;++y)for(int x=0;x<600;++x)c.buffer[y*600+x]=pack((x*19+y*3)%256,(x*7+y*11)%256,(x*3+y*23)%256);
        const auto source=c.buffer;
        const auto ui=render(c,PaperColorRenderMode::Ui);
        const auto mixed=render(c,PaperColorRenderMode::UiWithPhotos,logical[rot],2);
        if(rot==0)first_mixed=mixed;else assert(mixed==first_mixed);
        assert(c.buffer==source);
        size_t changed=0;
        for(int y=0;y<400;++y)for(int x=0;x<600;++x){
            if(!inside(physical[0],x,y)&&!inside(physical[1],x,y))assert(mixed[y*600+x]==ui[y*600+x]);
            else changed+=mixed[y*600+x]!=ui[y*600+x];
        }
        assert(changed>1000); // Demonstrates the old UI mapping differs materially.
        PaperColorPipelineStats stats{};assert(papercolor_pipeline_stats_snapshot(&stats));
        assert(stats.mode==PaperColorRenderMode::UiWithPhotos&&stats.workspace_bytes==4776);
        for(const auto&r:physical){
            m5gfx::M5Canvas crop(r.width,r.height);
            for(int y=0;y<r.height;++y)for(int x=0;x<r.width;++x)crop.buffer[y*r.width+x]=source[(r.y+y)*600+r.x+x];
            const auto viewer=render(crop,PaperColorRenderMode::PhotoBalanced);
            for(int y=0;y<r.height;++y)for(int x=0;x<r.width;++x)assert(viewer[y*r.width+x]==mixed[(r.y+y)*600+r.x+x]);
        }
        c.depth=24;
        const auto mixed888=render(c,PaperColorRenderMode::UiWithPhotos,logical[rot],2);
#if !defined(CONFIG_PAPERCOLOR_NATIVE_565_RECONSTRUCTION) || !CONFIG_PAPERCOLOR_NATIVE_565_RECONSTRUCTION
        assert(mixed888==mixed);
#endif
        // The 24-bit stub supplies ordinary bit-expanded values. With native
        // cell reconstruction these legitimately differ from 16-bit photo
        // samples. Check each format against its own real viewer path.
        const auto ui888=render(c,PaperColorRenderMode::Ui);
        for(int y=0;y<400;++y)for(int x=0;x<600;++x)
            if(!inside(physical[0],x,y)&&!inside(physical[1],x,y))assert(mixed888[y*600+x]==ui888[y*600+x]);
        for(const auto&r:physical){
            m5gfx::M5Canvas crop(r.width,r.height);crop.depth=24;
            for(int y=0;y<r.height;++y)for(int x=0;x<r.width;++x)crop.buffer[y*r.width+x]=source[(r.y+y)*600+r.x+x];
            const auto viewer=render(crop,PaperColorRenderMode::PhotoBalanced);
            for(int y=0;y<r.height;++y)for(int x=0;x<r.width;++x)assert(viewer[y*r.width+x]==mixed888[(r.y+y)*600+r.x+x]);
        }
        c.depth=16;
        for(int y=0;y<400;++y)for(int x=0;x<600;++x)
            if(!inside(physical[0],x,y)&&!inside(physical[1],x,y))c.buffer[y*600+x]=pack(255,0,255);
        const auto changed_ui=render(c,PaperColorRenderMode::UiWithPhotos,logical[rot],2);
        for(const auto&r:physical)for(int y=r.y;y<r.y+r.height;++y)for(int x=r.x;x<r.x+r.width;++x)assert(changed_ui[y*600+x]==mixed[y*600+x]);
        // A date/audio partial refresh honors the physical display clip and
        // leaves existing photo pixels untouched, including outside writes.
        M5.Display.reset();M5.Display.pixels=mixed;M5.Display.clip={364,12,164,224};
        const auto clip=M5.Display.clip;
        papercolor_push_canvas(&c,0,0,PaperColorRenderMode::UiWithPhotos,logical[rot],2);
        assert(M5.Display.clip==clip&&M5.Display.starts==1&&M5.Display.ends==1);
        for(int y=0;y<400;++y)for(int x=0;x<600;++x)
            if(!(x>=364&&x<528&&y>=12&&y<236))assert(M5.Display.pixels[y*600+x]==mixed[y*600+x]);
        // Placeholder/logo-only and empty regions keep other pixels in UI.
        const auto one=render(c,PaperColorRenderMode::UiWithPhotos,&logical[rot][1],1);
        const auto fresh_ui=render(c,PaperColorRenderMode::Ui);
        for(int y=0;y<400;++y)for(int x=0;x<600;++x)if(!inside(physical[1],x,y))assert(one[y*600+x]==fresh_ui[y*600+x]);
        assert(render(c,PaperColorRenderMode::UiWithPhotos)==fresh_ui);
    }
    PaperColorRegionDither regions[2]{};size_t bytes=0;
    for(auto bad:{PaperColorPhotoRegion{-1,0,1,1},{0,0,0,1},{399,0,2,1},{0,599,1,2},{0,0,std::numeric_limits<int32_t>::max(),1}})
        assert(!papercolor_layout_photo_regions(&bad,1,600,400,1,regions,bytes));
    const PaperColorPhotoRegion overlapping[]={{1,1,4,4},{3,3,4,4}};
    assert(!papercolor_layout_photo_regions(overlapping,2,600,400,1,regions,bytes));
    assert(!papercolor_layout_photo_regions(nullptr,1,600,400,1,regions,bytes));
    assert(!papercolor_layout_photo_regions(logical[1],3,600,400,1,regions,bytes));
    assert(!papercolor_layout_photo_regions(logical[1],2,600,400,4,regions,bytes));
    m5gfx::M5Canvas c(600,400);c.setRotation(1);c.setClipRect(1,2,3,4);c.setScrollRect(4,3,2,1);
    const auto clip=c.clip,scroll=c.scroll;M5.Display.reset();mock_fail_alloc=true;
    papercolor_push_canvas(&c,0,0,PaperColorRenderMode::UiWithPhotos,logical[1],2);
    mock_fail_alloc=false;
    assert(c.legacy_pushes==1&&c.rotation==1&&c.clip==clip&&c.scroll==scroll&&mock_allocations==0&&M5.Display.starts==0);
    std::puts("real adapter: photo/viewer equivalence, UI isolation, 4 rotations, RGB565/RGB888, clipped refresh, empty/logo-only, allocation failure: pass");
}
