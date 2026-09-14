/* SPDX-License-Identifier: MIT */
#include "display/papercolor_neutral_dither_ab_chart.h"
#include <cassert>
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>
int main(int argc,char** argv){if(argc!=2)return 2;std::ifstream f(argv[1],std::ios::binary);
 std::vector<uint8_t>d((std::istreambuf_iterator<char>(f)),{});using namespace papercolor_neutral_dither_ab_chart;
 if(!valid_payload(d.data(),d.size()))return 3;assert(!valid_payload(nullptr,d.size()));assert(!valid_payload(d.data(),d.size()-1));
 const uint8_t first=d[0];for(uint8_t bad:{4,7,15}){d[0]=(bad<<4)|(first&15);assert(!valid_payload(d.data(),d.size()));d[0]=(first&240)|bad;assert(!valid_payload(d.data(),d.size()));}d[0]=first;
 uint8_t n=255;assert(!sample(-1,0,d.data(),d.size(),n));assert(!sample(400,599,d.data(),d.size(),n));assert(!sample(0,600,d.data(),d.size(),n));
 for(int y=0;y<HEIGHT;++y)for(int x=0;x<WIDTH;++x){uint8_t c=255;sample(x,y,d.data(),d.size(),c);std::cout.put(char(c));}}
