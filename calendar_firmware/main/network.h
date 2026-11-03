#pragma once
#include <cstdint>
struct CalendarCredentials { char ssid[33]{}; char password[65]{}; };
bool calendar_load_credentials(CalendarCredentials& credentials);
// At most 12 s association + 18 s SNTP; no retry task remains afterwards.
bool calendar_sync_time(const CalendarCredentials& credentials, int64_t& utc_seconds);
// Explicit boot-button setup only. Never called by ordinary/maintenance wake.
bool calendar_setup_start(char* ssid, unsigned ssid_size, char* password, unsigned password_size);
bool calendar_setup_saved();
void calendar_setup_stop();
