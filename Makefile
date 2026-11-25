CC ?= cc
CLANG ?= clang
CFLAGS := -std=c11 -O2 -Wall -Wextra -Werror
EXPORTS := vk_abi vk_spawn vk_fork vk_exit vk_observe vk_advance vk_restore vk_value vk_work vk_time vk1_begin vk1_seed vk1_append vk1_run vk1_result vk1_method vk1_work
WASM_EXPORTS := $(foreach x,$(EXPORTS),-Wl,--export=$(x))
.PHONY: all test clean
all: dist/vlk.wasm dist/libvlk.so dist/vlk
dist:
	mkdir -p dist
dist/vlk.wasm: src/vlk.c src/vlk1.c src/vlk.h | dist
	$(CLANG) --target=wasm32 -nostdlib -ffreestanding -fno-builtin $(CFLAGS) -Wl,--no-entry $(WASM_EXPORTS) -Wl,--strip-all src/vlk.c src/vlk1.c -o $@
dist/libvlk.so: src/vlk.c src/vlk1.c src/vlk.h | dist
	$(CC) $(CFLAGS) -shared -fPIC src/vlk.c src/vlk1.c -o $@
dist/vlk: src/launch.c | dist
	$(CC) $(CFLAGS) src/launch.c -o $@
test: all
	python3 tests/native.py
	node tests/wasm.mjs
	node tests/k1.mjs
	python3 tests/k1_native.py
	node tests/adapter.mjs
	python3 tests/commands.py
	python3 tests/processes.py
	python3 tests/pipelines.py
clean:
	rm -f dist/vlk.wasm dist/libvlk.so dist/vlk
