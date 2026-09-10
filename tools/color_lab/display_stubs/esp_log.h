#pragma once
#include <cstdio>
#define ESP_LOGW(tag, ...) ((void)std::fprintf(stderr, __VA_ARGS__))
#define ESP_LOGE(tag, ...) ((void)std::fprintf(stderr, __VA_ARGS__))
