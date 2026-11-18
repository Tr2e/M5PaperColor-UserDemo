#include "calendar_engine.h"
#include <cassert>
#include <fstream>
#include <iterator>
#include <vector>
#include <cstdio>
#include <cstring>

int main(int argc,char** argv) {
    assert(argc>=2);std::ifstream input(argv[1],std::ios::binary);
    std::vector<uint8_t> data{std::istreambuf_iterator<char>(input),{}};
    tr2e::CalendarPack pack;
    if(argc==3 && !std::strcmp(argv[2],"--reject")) {
        assert(!pack.open(data.data(),data.size()));return 0;
    }
    assert(pack.open(data.data(),data.size()));
    assert(tr2e::ordinal({2028,2,29})+1==tr2e::ordinal({2028,3,1}));
    assert(!tr2e::ordinal({2027,2,29}));assert(!tr2e::ordinal({2100,2,29}));
    assert(tr2e::ordinal({2026,12,31})+1==tr2e::ordinal({2027,1,1}));
    tr2e::Entry e;assert(pack.entry({2026,12,31},e));assert(pack.entry({2027,1,1},e));
    assert(!pack.entry({2025,12,31},e));assert(!pack.entry({2100,1,1},e));
    assert(pack.planHash(2026)!=0 && pack.planHash(2027)!=0);
    // Updating typography/resources must not invalidate the current-year NVS
    // assignment lock. This is the approved 2026 source-date FNV fingerprint.
    assert(pack.planHash(2026)==189380513U);
    assert(pack.planHash(2026)!=pack.planHash(2027));assert(pack.planHash(2100)==0);
    tr2e::SyncState state;auto today=tr2e::ordinal({2026,12,25});
    using tr2e::Boot;using tr2e::Reset;using tr2e::classifyBoot;
    assert(classifyBoot(Reset::PowerOn,true,false,false)==Boot::Manual);
    assert(classifyBoot(Reset::External,true,false,false)==Boot::Manual);
    assert(classifyBoot(Reset::PowerOn,true,true,false)==Boot::Manual);
    assert(classifyBoot(Reset::DeepSleep,true,true,true)==Boot::Manual);
    assert(classifyBoot(Reset::PowerOn,false,true,false)==Boot::Rtc);
    assert(classifyBoot(Reset::DeepSleep,false,false,true)==Boot::Rtc);
    assert(classifyBoot(Reset::PowerOn,false,false,false)==Boot::Manual);
    assert(classifyBoot(Reset::Recovery,true,true,false)==Boot::Recovery);
    assert(classifyBoot(Reset::DeepSleep,false,false,false)==Boot::Recovery);
    assert(tr2e::shouldSync(tr2e::Boot::Manual,today,state));
    tr2e::recordAttempt(state,today,true);
    assert(tr2e::shouldSync(classifyBoot(Reset::PowerOn,true,true,false),today+1,state));
    for(unsigned i=1;i<15;++i) assert(!tr2e::shouldSync(tr2e::Boot::Rtc,today+i,state));
    assert(tr2e::shouldSync(tr2e::Boot::Rtc,today+15,state));
    tr2e::recordAttempt(state,today+15,false);
    assert(state.last_success_day==today);
    assert(!tr2e::shouldSync(tr2e::Boot::Rtc,today+16,state));
    assert(!tr2e::shouldSync(tr2e::Boot::Recovery,today+31,state));
    assert(tr2e::shouldSync(tr2e::Boot::Manual,0,state));
    assert(!tr2e::shouldSync(tr2e::Boot::Rtc,0,state));
    assert(tr2e::secondsUntilMidnight(23,59,59)==1);
    assert(tr2e::secondsUntilMidnight(0,0,0)==86400);
    assert(!tr2e::batteryDateWarning(0)); // Failed read is not an empty battery.
    assert(tr2e::batteryDateWarning(3100));
    assert(tr2e::batteryDateWarning(3399));
    assert(!tr2e::batteryDateWarning(3400)); // Exactly 5% stays black.
    assert(!tr2e::batteryDateWarning(4200));
    // Check all month/day widths, including double-digit months and leap day.
    for(int month=1;month<=12;++month) for(int day=1;day<=31;++day) {
        tr2e::Date date{2028,month,day};if(!tr2e::ordinal(date)) continue;
        std::vector<uint8_t> full(30000),mask(30000,255);
        assert(pack.render(date,full.data(),full.size()));
        assert(pack.renderHeaderDate(date,mask.data(),mask.size()));
        unsigned ink=0;
        for(int y=0;y<600;++y) for(int x=0;x<400;++x) {
            int offset=y*50+x/8;uint8_t bit=0x80>>(x&7);
            if(mask[offset]&bit) {
                ++ink;assert(full[offset]&bit);
                assert(x>=20 && x<110 && y>38 && y<94);
            } else if(x>=20 && x<110 && y>=50 && y<85) {
                // Weekday starts beyond the right edge of the date plus 10px.
                // Compare only the date's known left-hand portion here.
                if(x<70) assert(!(full[offset]&bit));
            }
        }
        assert(ink>100);
    }
    if(argc==6) {
        tr2e::Date date{std::stoi(argv[3]),std::stoi(argv[4]),std::stoi(argv[5])};
        std::vector<uint8_t> bits(30000);assert(pack.render(date,bits.data(),bits.size()));
        std::ofstream out(argv[2],std::ios::binary);out.write(reinterpret_cast<const char*>(bits.data()),bits.size());
    }
    if(argc==5 && !std::strcmp(argv[2],"--batch")) {
        std::ifstream dates(argv[4]);tr2e::Date date{};
        while(dates>>date.year>>date.month>>date.day) {
            std::vector<uint8_t> bits(30000);assert(pack.render(date,bits.data(),bits.size()));
            char name[32];std::snprintf(name,sizeof(name),"/%04d-%02d-%02d.bin",date.year,date.month,date.day);
            std::ofstream out(std::string(argv[3])+name,std::ios::binary);
            out.write(reinterpret_cast<const char*>(bits.data()),bits.size());assert(out.good());
        }
    }
    data.back()^=1;assert(!pack.open(data.data(),data.size()));
    std::puts("engine/date/rollover/15-day-radio/failed-sync/corruption checks passed");
}
