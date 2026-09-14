#include "display/papercolor_chromatic_dither_ab_chart.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>
int main(int argc,char**argv){if(argc!=2)return 2;std::ifstream f(argv[1],std::ios::binary);
 std::vector<uint8_t>d((std::istreambuf_iterator<char>(f)),{});if(!papercolor_chromatic_dither_ab_chart::valid_payload(d.data(),d.size()))return 3;
 for(int y=0;y<600;++y)for(int x=0;x<400;++x){uint8_t n=255;papercolor_chromatic_dither_ab_chart::sample(x,y,d.data(),d.size(),n);std::cout.put(char(n));}
 return std::cout?0:4;}
