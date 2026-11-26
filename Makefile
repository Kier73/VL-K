CC ?= cc
CLANG ?= clang
CFLAGS := -std=c11 -O2 -Wall -Wextra -Werror
EXPORTS := vk_abi vk_spawn vk_fork vk_exit vk_observe vk_advance vk_restore vk_value vk_work vk_time vk1_begin vk1_seed vk1_append vk1_run vk1_result vk1_method vk1_work
WASM_EXPORTS := $(foreach x,$(EXPORTS),-Wl,--export=$(x))
.PHONY: all test clean
all: dist/vlk-session-objects dist/vlk.wasm dist/libvlk.so dist/vlk dist/vlk-session dist/vlk-elf dist/demo.rv32 dist/file.rv32
dist:
	mkdir -p dist
dist/vlk.wasm: src/vlk.c src/vlk1.c src/vlk.h | dist
	$(CLANG) --target=wasm32 -nostdlib -ffreestanding -fno-builtin $(CFLAGS) -Wl,--no-entry $(WASM_EXPORTS) -Wl,--strip-all src/vlk.c src/vlk1.c -o $@
dist/libvlk.so: src/vlk.c src/vlk1.c src/vlk.h | dist
	$(CC) $(CFLAGS) -shared -fPIC src/vlk.c src/vlk1.c -o $@
dist/vlk: src/launch.c | dist
	$(CC) $(CFLAGS) src/launch.c -o $@
test: all boot dist/filter.rv32 dist/abi.rv32 dist/runtime.rv32 dist/descriptor.rv32 dist/control.rv32 dist/worker.rv32 dist/shell.rv32 dist/cow.rv32 dist/execfs.rv32 dist/compiler.rv32
	python3 tests/native.py
	node tests/wasm.mjs
	node tests/realization.mjs
	node tests/ground-atlas.mjs
	node tests/finite-coordinate.mjs
	node tests/layered-realization.mjs
	node tests/dependency-ground.mjs
	node tests/composite-ground.mjs
	node tests/driven-ground.mjs --wasm
	node tests/application-ground.mjs
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
	python3 tests/elf.py
	python3 tests/fs.py
	python3 tests/runtime.py
	python3 tests/descriptors.py
	python3 tests/structural_files.py
	python3 tests/rvproc.py
	python3 tests/rvpipe.py
	python3 tests/guest_control.py
	python3 tests/cow.py
	python3 tests/rvobjects.py
	python3 tests/object_runtime.py
	python3 tests/execfs.py
	python3 tests/compiler.py
clean:
	rm -f dist/vlk-session-objects dist/vlk.wasm dist/libvlk.so dist/vlk dist/vlk-elf dist/demo.rv32 dist/filter.rv32 dist/abi.rv32 dist/file.rv32 dist/runtime.rv32 dist/vlk-boot.elf dist/descriptor.rv32 dist/vlk-session dist/control.rv32 dist/worker.rv32 dist/shell.rv32 dist/cow.rv32 dist/execfs.rv32 dist/compiler.rv32

RVFLAGS := --target=riscv32-none-elf -march=rv32im -mabi=ilp32 -ffreestanding -fno-builtin -fno-stack-protector -fno-pic -msmall-data-limit=0 -O2 -nostdlib -fuse-ld=lld -Wl,--no-relax,-T,examples/rv32/app.ld
BOOTFLAGS := --target=i386-none-elf -ffreestanding -fno-builtin -fno-stack-protector -fno-pic -mno-sse -mno-mmx -O2 -Wall -Wextra -Werror
.PHONY: boot
boot: dist/vlk-boot.elf
dist/vlk-elf: src/rv32.c src/rv32.h src/rvfs.c src/rvfs.h src/rvbytes.h src/elf_run.c | dist
	$(CC) $(CFLAGS) src/rv32.c src/rvfs.c src/elf_run.c -o $@
dist/demo.rv32: examples/rv32/demo.c examples/rv32/start.S examples/rv32/app.ld | dist
	$(CLANG) $(RVFLAGS) examples/rv32/start.S examples/rv32/demo.c -o $@
dist/vlk-boot.elf: boot/start.S boot/kernel.c boot/embed.S boot/link.ld boot/module.h src/rvproc.c src/rvproc.h src/rv32.c src/rv32.h src/rvfs.c src/rvfs.h src/rvbytes.h dist/demo.rv32 dist/file.rv32 dist/shell.rv32 dist/filter.rv32 | dist
	$(CLANG) $(BOOTFLAGS) -Isrc -nostdlib -static -fuse-ld=lld -Wl,-no-pie,-T,boot/link.ld boot/start.S boot/kernel.c boot/embed.S src/rv32.c src/rvfs.c src/rvproc.c -o $@
dist/filter.rv32: examples/rv32/filter.c examples/rv32/start.S examples/rv32/app.ld | dist
	$(CLANG) $(RVFLAGS) examples/rv32/start.S examples/rv32/filter.c -o $@
dist/abi.rv32: examples/rv32/abi.S examples/rv32/app.ld | dist
	$(CLANG) $(RVFLAGS) examples/rv32/abi.S -o $@
.PHONY: boot-test
boot-test: boot dist/runtime.rv32
	python3 tests/boot_qemu.py

dist/file.rv32: examples/rv32/file.c examples/rv32/start.S examples/rv32/app.ld | dist
	$(CLANG) $(RVFLAGS) examples/rv32/start.S examples/rv32/file.c -o $@

dist/runtime.rv32: examples/rv32/runtime.c examples/rv32/runtime_start.S examples/rv32/runtime.ld | dist
	$(CLANG) $(subst examples/rv32/app.ld,examples/rv32/runtime.ld,$(RVFLAGS)) examples/rv32/runtime_start.S examples/rv32/runtime.c -o $@

dist/descriptor.rv32: examples/rv32/descriptor.c examples/rv32/start.S examples/rv32/app.ld | dist
	$(CLANG) $(RVFLAGS) examples/rv32/start.S examples/rv32/descriptor.c -o $@

dist/control.rv32: examples/rv32/control.c examples/rv32/start.S examples/rv32/app.ld | dist
	$(CLANG) $(RVFLAGS) examples/rv32/start.S examples/rv32/control.c -o $@
dist/worker.rv32: examples/rv32/worker.c examples/rv32/start.S examples/rv32/app.ld | dist
	$(CLANG) $(RVFLAGS) examples/rv32/start.S examples/rv32/worker.c -o $@

dist/shell.rv32: examples/rv32/shell.c examples/rv32/start.S examples/rv32/app.ld | dist
	$(CLANG) $(RVFLAGS) examples/rv32/start.S examples/rv32/shell.c -o $@
dist/vlk-session: src/session.c src/rvproc.c src/rvproc.h src/rv32.c src/rv32.h src/rvfs.c src/rvfs.h src/rvbytes.h | dist
	$(CC) $(CFLAGS) src/session.c src/rvproc.c src/rv32.c src/rvfs.c -o $@

dist/cow.rv32: examples/rv32/cow.c examples/rv32/start.S examples/rv32/app.ld | dist
	$(CLANG) $(RVFLAGS) examples/rv32/start.S examples/rv32/cow.c -o $@

# Experimental alternate runtime: 4 process slots, 4 MiB aggregate backing reservations.
dist/vlk-session-objects: src/session.c src/rvproc.c src/rvproc.h src/rv32.c src/rv32.h src/rvfs.c src/rvfs.h src/rvbytes.h src/rvobjects.c src/rvobjects.h | dist
	$(CC) $(CFLAGS) -DRV_OBJECT_BACKEND -DRO_OBJECTS=1024 -DRP_SLOTS=4 src/session.c src/rvproc.c src/rv32.c src/rvfs.c src/rvobjects.c -o $@

dist/execfs.rv32: examples/rv32/execfs.c examples/rv32/start.S examples/rv32/app.ld | dist
	$(CLANG) $(RVFLAGS) examples/rv32/start.S examples/rv32/execfs.c -o $@

dist/compiler.rv32: examples/rv32/compiler.c examples/rv32/start.S examples/rv32/app.ld | dist
	$(CLANG) $(RVFLAGS) examples/rv32/start.S examples/rv32/compiler.c -o $@
