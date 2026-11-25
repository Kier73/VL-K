#ifndef VLK_H
#define VLK_H
#include <stdint.h>
enum { VK_OK=0, VK_INVALID=-1, VK_FULL=-2, VK_CONFLICT=-3, VK_BUDGET=-4 };
enum { VK_AFFINE=1, VK_QUADRATIC=2 };
uint32_t vk_abi(void);
int32_t vk_spawn(uint32_t kind,uint32_t seed,uint32_t a,uint32_t b);
int32_t vk_fork(int32_t id);
int32_t vk_exit(int32_t id);
int32_t vk_observe(int32_t id,uint64_t target,uint32_t budget);
int32_t vk_advance(int32_t id,uint64_t expected,uint64_t target,uint32_t budget);
int32_t vk_restore(uint32_t kind,uint32_t seed,uint32_t a,uint32_t b,uint64_t t,uint32_t budget);
uint32_t vk_value(void);
uint32_t vk_work(void);
uint64_t vk_time(int32_t id);
void vk1_begin(void);
int32_t vk1_seed(uint32_t r,uint32_t v);
int32_t vk1_append(uint32_t op,uint32_t d,uint32_t x);
int32_t vk1_run(uint64_t n,uint32_t budget,uint32_t mode);
uint32_t vk1_result(uint32_t r);
uint32_t vk1_work(void);
uint32_t vk1_method(void);
#endif
