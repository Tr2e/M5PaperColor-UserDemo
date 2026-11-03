#include "calendar_engine.h"
#include <cstring>
#include <initializer_list>

namespace tr2e {
namespace {
uint16_t u16(const uint8_t* p) { return p[0] | (uint16_t(p[1]) << 8); }
uint32_t u32(const uint8_t* p) { return u16(p) | (uint32_t(u16(p + 2)) << 16); }
int s16(const uint8_t* p) { return int16_t(u16(p)); }
bool leap(int year) { return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0); }
void pixel(uint8_t* b, int x, int y) {
    if (x >= 0 && x < 400 && y >= 0 && y < 600) b[y * 50 + x / 8] |= uint8_t(0x80 >> (x & 7));
}
void rule(uint8_t* b, int x, int y, int w, int h = 1) {
    for (int j = 0; j < h; ++j) for (int i = 0; i < w; ++i) pixel(b, x+i, y+j);
}
uint32_t crc(const uint8_t* data, size_t size) {
    uint32_t value = 0xffffffff;
    for (size_t i = 0; i < size; ++i) {
        value ^= (i >= 12 && i < 16) ? 0 : data[i];
        for (int k = 0; k < 8; ++k) value = (value >> 1) ^ ((value & 1) ? 0xedb88320U : 0);
    }
    return ~value;
}
}

uint32_t ordinal(Date d) {
    constexpr int days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
    if (d.year < 1 || d.year > 9999 || d.month < 1 || d.month > 12 || d.day < 1 ||
        d.day > days[d.month-1] + (d.month == 2 && leap(d.year))) return 0;
    uint32_t y = d.year-1, total = 365*y + y/4 - y/100 + y/400 + d.day;
    for (int m = 1; m < d.month; ++m) total += days[m-1] + (m == 2 && leap(d.year));
    return total;
}
uint32_t CalendarPack::field(unsigned n) const { return data_ ? u32(data_+8+4*n) : 0; }
bool CalendarPack::range(size_t offset, size_t bytes) const { return offset <= size_ && bytes <= size_-offset; }
bool CalendarPack::open(const uint8_t* data, size_t size) {
    data_ = nullptr; size_ = 0;
    if (!data || size < 72 || std::memcmp(data,"TR2EPK02",8) || u32(data+8)!=size ||
        u32(data+64)!=2 || crc(data,size)!=u32(data+12)) return false;
    data_ = data; size_ = size;
    bool ok = field(4)>0 && field(4)<65536 && field(5)>0 && field(5)<65536 &&
        field(10)>=73 && range(field(6),16*size_t(field(4))) && range(field(7),4*(size_t(field(5))+1)) &&
        range(field(8),6*size_t(field(3))) && range(field(9),4*(size_t(field(10))+1)) && range(field(11),80);
    for (uint32_t i=0; ok && i<field(4); ++i) {
        const auto* g=data_+field(6)+i*16;size_t w=u16(g+4),h=u16(g+6);
        ok=w<=400 && h<=600 && range(u32(g),((w+7)/8)*h);
    }
    for (unsigned table : {7U,9U}) {
        uint32_t count=field(table==7?5:10);
        if (!ok) break;
        for (uint32_t i=0;i<count;++i) {
            uint32_t a=u32(data_+field(table)+4*i),b=u32(data_+field(table)+4*(i+1));
            if (a>b || !range(a,b-a) || b-a<(table==7?14U:2U)) {ok=false;break;}
            if (table==9) {
                if (2+size_t(u16(data_+a))*2!=b-a) {ok=false;break;}
                for (uint32_t j=a+2;j<b;j+=2) if(u16(data_+j)>=field(4)) ok=false;
            } else {
                if (u16(data_+a+6)>=4) {ok=false;break;}
                uint32_t n=u16(data_+a+12),p=a+14;
                for (uint32_t j=0;ok && j<n;++j) {
                    if (p+6>b) {ok=false;break;}
                    uint32_t len=data_[p+5];p+=6;
                    if (p+len*2>b) {ok=false;break;}
                    for(uint32_t k=0;k<len;++k,p+=2) if(u16(data_+p)>=field(4)) ok=false;
                }
                if(p!=b) ok=false;
            }
        }
    }
    for(uint32_t i=0;ok && i<40;++i) if(u16(data_+field(11)+i*2)>=field(4)) ok=false;
    if (!ok) {data_=nullptr;size_=0;}
    return ok;
}
bool CalendarPack::entry(Date date, Entry& result) const {
    uint32_t day=ordinal(date);
    if (!data_ || day<firstDay() || day-firstDay()>=dayCount()) return false;
    const auto* p=data_+field(8)+(day-firstDay())*6;
    result={u16(p),u16(p+2),u16(p+4)};
    return result.record<field(5) && result.label<field(10) &&
        (result.lunar&15)>=1 && (result.lunar&15)<=12 && ((result.lunar>>4)&31)>=1 && ((result.lunar>>4)&31)<=30;
}
void CalendarPack::glyph(uint16_t id,int x64,int baseline,uint8_t* bits) const {
    const auto* g=data_+field(6)+id*16;int w=u16(g+4),h=u16(g+6),stride=(w+7)/8;
    int x=(x64>>6)+s16(g+8),y=baseline+s16(g+10);const auto* source=data_+u32(g);
    for(int j=0;j<h;++j) for(int i=0;i<w;++i) if(source[j*stride+i/8]&(0x80>>(i&7))) pixel(bits,x+i,y+j);
}
int CalendarPack::textWidth(uint16_t id) const {
    const auto* p=data_+u32(data_+field(9)+4*id);int width=0;
    for(int i=0;i<u16(p);++i) width+=u16(data_+field(6)+16*u16(p+2+2*i)+12);
    return width;
}
void CalendarPack::text(uint16_t id,int x64,int y,int size,uint8_t* bits) const {
    const auto* p=data_+u32(data_+field(9)+4*id);
    for(int i=0;i<u16(p);++i) {
        uint16_t g=u16(p+2+2*i);glyph(g,x64,y+size,bits);x64+=u16(data_+field(6)+16*g+12);
    }
}
bool CalendarPack::render(Date date,uint8_t* bits,size_t size) const {
    Entry e{};if(!bits || size<30000 || !entry(date,e)) return false;
    std::memset(bits,0,30000);
    rule(bits,20,38,360);rule(bits,20,94,360,2);rule(bits,20,578,360,2);
    rule(bits,20,94,2,486);rule(bits,378,94,2,486);rule(bits,250,50,1,31);
    int x=20*64;
    auto header=[&](int id){text(id,x,49,31,bits);x+=textWidth(id);};
    if(date.month>=10) { header(date.month/10); }
    header(date.month%10);header(10);header(date.day/10);header(date.day%10);
    const int meta_x=x+10*64;
    text(22+(ordinal(date)-1)%7,meta_x,50,14,bits);text(e.label,meta_x,70,14,bits);
    int year_ids[]={11+date.year/1000,11+(date.year/100)%10,11+(date.year/10)%10,11+date.year%10,21};
    int w=0;for(int id:year_ids) w+=textWidth(id);x=379*64-w;
    for(int id:year_ids) {text(id,x,50,14,bits);x+=textWidth(id);}
    int month=29+(e.lunar&15)-1,day=41+((e.lunar>>4)&31)-1;
    w=textWidth(month)+textWidth(day)+((e.lunar&512)?textWidth(71):0);x=379*64-w;
    if(e.lunar&512){text(71,x,70,14,bits);x+=textWidth(71);}
    text(month,x,70,14,bits);x+=textWidth(month);text(day,x,70,14,bits);
    const auto* record=data_+u32(data_+field(7)+e.record*4)+4;
    uint16_t digit_y=u16(record),scale=u16(record+2);int count=date.day>=10?2:1;
    uint16_t digits[2]={u16(data_+field(11)+(scale*10+(date.day>=10?date.day/10:date.day))*2),u16(data_+field(11)+(scale*10+date.day%10)*2)};
    w=u16(data_+field(6)+digits[0]*16+4)+(count==2?8+u16(data_+field(6)+digits[1]*16+4):0);x=((400-w)/2)*64;
    for(int i=0;i<count;++i){glyph(digits[i],x,digit_y,bits);x+=(u16(data_+field(6)+digits[i]*16+4)+8)*64;}
    rule(bits,36,u16(record+4),328);rule(bits,36,u16(record+6),328);
    uint16_t lines=u16(record+8);record+=10;
    for(uint16_t i=0;i<lines;++i) {
        x=s16(record);int baseline=s16(record+2)+record[4],n=record[5];record+=6;
        for(int j=0;j<n;++j){uint16_t g=u16(record);record+=2;glyph(g,x,baseline,bits);x+=u16(data_+field(6)+16*g+12);}
    }
    return true;
}

uint32_t CalendarPack::planHash(int year) const {
    uint32_t begin=ordinal({year,1,1}),end=ordinal({year+1,1,1}),value=2166136261U;
    if(!data_ || begin<firstDay() || end>firstDay()+dayCount()) return 0;
    for(uint32_t day=begin;day<end;++day) {
        uint16_t record=u16(data_+field(8)+(day-firstDay())*6);
        if(record>=field(5)) return 0;
        uint32_t source=u32(data_+u32(data_+field(7)+record*4));
        for(unsigned k=0;k<4;++k) {value^=(source>>(8*k))&255;value*=16777619U;}
    }
    return value;
}

Boot classifyBoot(Reset reset,bool physical_button,bool rtc_signal,bool timer_wake) {
    // PMIC wake flags can survive an ESP crash: never let stale flags turn
    // watchdog/brownout/software recovery into repeated network attempts.
    if(reset==Reset::Recovery) return Boot::Recovery;
    // A real button press wins if it coincides with the midnight alarm.
    if(physical_button) return Boot::Manual;
    if(timer_wake || (reset==Reset::PowerOn && rtc_signal)) return Boot::Rtc;
    if(reset==Reset::PowerOn || reset==Reset::External) return Boot::Manual;
    return Boot::Recovery;
}
bool shouldSync(Boot boot,uint32_t today,const SyncState& state) {
    return boot==Boot::Manual || (boot==Boot::Rtc && today && (!state.next_attempt_day || today>=state.next_attempt_day));
}
void recordAttempt(SyncState& state,uint32_t today,bool success) {
    if(today) state.next_attempt_day=today+15;
    if(success) state.last_success_day=today;
}
uint32_t secondsUntilMidnight(int h,int m,int s) {
    if(h<0||h>23||m<0||m>59||s<0||s>59) return 86400;
    return 86400-(h*3600+m*60+s);
}
} // namespace tr2e
