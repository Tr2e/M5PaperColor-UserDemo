/* SPDX-License-Identifier: MIT */
#include "display/papercolor_photo_dither.cpp"
#include <cassert>
#include <fstream>
#include <iterator>
#include <vector>
#include <cstdio>
static uint16_t pack(const uint8_t* c) { return ((c[0]>>3)<<11)|((c[1]>>2)<<5)|(c[2]>>3); }
static uint16_t swap(uint16_t p){return (p>>8)|(p<<8);}
static void expand(uint16_t p,uint8_t* c){c[0]=((p>>11)<<3)|(p>>13);c[1]=(((p>>5)&63)<<2)|((p>>9)&3);c[2]=((p&31)<<3)|((p&31)>>2);}
int main(int argc,char**argv){
 assert(argc==2);std::ifstream f(argv[1],std::ios::binary);std::vector<uint8_t>lut((std::istreambuf_iterator<char>(f)),{});assert(lut.size()==32768);
 unsigned changed=0;
 for(unsigned p=0;p<65536;++p){
  uint16_t raw=swap(p);uint8_t actual[3],ordinary[3];expand(p,ordinary);Swap565Source{&raw}.sample(0,actual);
  const uint8_t* expected=ordinary;
  for(uint8_t code:{2,3,5,6})if(pack(NATIVE_SRGB[code])==p)expected=NATIVE_SRGB[code];
  for(int c=0;c<3;++c)assert(actual[c]==expected[c]);
  changed+=memcmp(actual,ordinary,3)!=0;
  assert(pack(actual)==p); // No neighboring-cell attraction.
 }
 assert(changed==4);
 constexpr size_t W=96,H=72;
 for(auto mode:{PAPERCOLOR_DITHER_FLOYD_STEINBERG,PAPERCOLOR_DITHER_BURKES})
 for(uint8_t code:{2,3,5,6})for(uint8_t surround:{0,1,3,5,6}){
  std::vector<int32_t>work(papercolor_dither_workspace_size(W,mode)/4);
  papercolor_dither_state_t state{};assert(papercolor_dither_init(&state,W,mode,lut.data(),work.data(),work.size()*4));
  std::vector<uint16_t>input(W);std::vector<uint8_t>out(W);
  for(size_t y=0;y<H;++y){
   for(size_t x=0;x<W;++x)input[x]=swap(pack(NATIVE_SRGB[(y>=17&&y<55&&x>=19&&x<78)?code:surround]));
   assert(papercolor_dither_process_swap565_row(&state,input.data(),out.data()));
   if(y>=17&&y<55)for(size_t x=19;x<78;++x)assert(out[x]==code);
  }
 }
 // Verify all nearest/UI entries, independent of the photo source adapter.
 std::vector<uint16_t>input(65536);std::vector<uint8_t>out(65536);papercolor_dither_state_t ui{};
 assert(papercolor_dither_init(&ui,65536,PAPERCOLOR_DITHER_NEAREST,lut.data(),nullptr,0));
 for(unsigned p=0;p<65536;++p)input[p]=swap(p);
 assert(papercolor_dither_process_swap565_row(&ui,input.data(),out.data()));
 for(unsigned p=0;p<65536;++p)assert(out[p]==lut[((p>>11)<<10)|(((p>>6)&31)<<5)|(p&31)]);
 std::puts("all 65536 cells / four representatives / no neighbor attraction / native patch boundaries in both filters / all nearest UI entries: pass");
}
