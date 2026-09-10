#pragma once
#include <cstdlib>
constexpr int MALLOC_CAP_INTERNAL=1,MALLOC_CAP_8BIT=2,MALLOC_CAP_SPIRAM=4;
inline bool mock_fail_alloc=false;
inline size_t mock_allocations=0;
inline size_t heap_caps_get_free_size(int){return 1024*1024;}
inline size_t heap_caps_get_largest_free_block(int){return 1024*1024;}
inline void* heap_caps_calloc(size_t n,size_t s,int){if(mock_fail_alloc)return nullptr;auto p=std::calloc(n,s);if(p)++mock_allocations;return p;}
inline void heap_caps_free(void*p){if(p)--mock_allocations;std::free(p);}
