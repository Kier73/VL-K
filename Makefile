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
	python3 tests/memory.py
	python3 tests/memory_stress.py
	python3 tests/guest_memory.py
	python3 tests/path_guest.py
	python3 tests/lift.py
	python3 tests/weighted_lift.py
	python3 tests/debugger.py
	python3 tests/observation.py
	python3 tests/authority.py
	python3 tests/application.py
	python3 tests/quotient.py
	python3 tests/weighted_ground.py
	python3 tests/effect_image.py
	python3 tests/refine.py
clean:
	rm -f dist/vlk.wasm dist/libvlk.so dist/vlk
