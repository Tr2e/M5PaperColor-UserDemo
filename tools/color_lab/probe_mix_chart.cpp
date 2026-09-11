// Host artifact generator: emit the actual diagnostic fill codes, 255 elsewhere.
#include "display/papercolor_mix_chart.h"
#include <iostream>
int main()
{
    for (int y=0; y<600; ++y) for (int x=0; x<400; ++x) {
        uint8_t code=255;
        papercolor_mix_chart::sample(x,y,code);
        std::cout.put(static_cast<char>(code));
    }
}
