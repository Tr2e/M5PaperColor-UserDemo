#pragma once
#include <cstddef>
#include <cstdint>

namespace tr2e {
struct Date { int year, month, day; };
uint32_t ordinal(Date date); // zero means invalid; same epoch as Python date.toordinal
struct Entry { uint16_t record, lunar, label; };

// Pure portable core: no ESP-IDF, networking, filesystem or mutable selection.
class CalendarPack {
public:
    bool open(const uint8_t* data, size_t size);
    bool entry(Date date, Entry& result) const;
    bool render(Date date, uint8_t* black_bits, size_t size) const;
    uint32_t planHash(int year) const;
    uint32_t firstDay() const { return field(2); }
    uint32_t dayCount() const { return field(3); }
private:
    const uint8_t* data_ = nullptr;
    size_t size_ = 0;
    uint32_t field(unsigned n) const;
    bool range(size_t offset, size_t bytes) const;
    void glyph(uint16_t id, int x64, int baseline, uint8_t* bits) const;
    int textWidth(uint16_t id) const;
    void text(uint16_t id, int x64, int y, int font_size, uint8_t* bits) const;
};

enum class Boot { Manual, Rtc, Recovery };
enum class Reset { PowerOn, External, DeepSleep, Recovery };
Boot classifyBoot(Reset reset, bool physical_button, bool rtc_signal, bool timer_wake);
struct SyncState { uint32_t next_attempt_day = 0, last_success_day = 0; };
bool shouldSync(Boot boot, uint32_t today, const SyncState& state);
void recordAttempt(SyncState& state, uint32_t today, bool success);
uint32_t secondsUntilMidnight(int hour, int minute, int second);
} // namespace tr2e
