#include "calendar_engine.h"
#include <cassert>
#include <fstream>
#include <iterator>
#include <vector>
#include <cstdio>

int main(int argc,char** argv) {
    assert(argc>=2);std::ifstream input(argv[1],std::ios::binary);
    std::vector<uint8_t> data{std::istreambuf_iterator<char>(input),{}};
    tr2e::CalendarPack pack;assert(pack.open(data.data(),data.size()));
    assert(tr2e::ordinal({2028,2,29})+1==tr2e::ordinal({2028,3,1}));
    assert(!tr2e::ordinal({2027,2,29}));assert(!tr2e::ordinal({2100,2,29}));
    assert(tr2e::ordinal({2026,12,31})+1==tr2e::ordinal({2027,1,1}));
    tr2e::Entry e;assert(pack.entry({2026,12,31},e));assert(pack.entry({2027,1,1},e));
    assert(!pack.entry({2025,12,31},e));assert(!pack.entry({2100,1,1},e));
    assert(pack.planHash(2026)!=0 && pack.planHash(2027)!=0);
    assert(pack.planHash(2026)!=pack.planHash(2027));assert(pack.planHash(2100)==0);
    tr2e::SyncState state;auto today=tr2e::ordinal({2026,12,25});
    assert(tr2e::shouldSync(tr2e::Boot::Manual,today,state));
    tr2e::recordAttempt(state,today,true);
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
    if(argc==6) {
        tr2e::Date date{std::stoi(argv[3]),std::stoi(argv[4]),std::stoi(argv[5])};
        std::vector<uint8_t> bits(30000);assert(pack.render(date,bits.data(),bits.size()));
        std::ofstream out(argv[2],std::ios::binary);out.write(reinterpret_cast<const char*>(bits.data()),bits.size());
    }
    data.back()^=1;assert(!pack.open(data.data(),data.size()));
    std::puts("engine/date/rollover/15-day-radio/failed-sync/corruption checks passed");
}
