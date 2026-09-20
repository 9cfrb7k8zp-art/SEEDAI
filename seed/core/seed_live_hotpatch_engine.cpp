// ==========================================================
// FILE: seed_live_hotpatch_engine.cpp
// PROJECT: SEED AI OS
// VERSION: 1.0
//
// PURPOSE:
//  - Live in-memory binary patching
//  - Redirect execution safely
//  - Enable hot-repair with no reboot
//
// DESIGN CONSTRAINTS:
//  - No STL
//  - No heap allocation
//  - Win95-era compatible logic
//  - Deterministic behavior
// ==========================================================

#include <stdint.h>
#include <string.h>
#include <stdio.h>

#if defined(_WIN32)
#include <windows.h>
#else
#include <unistd.h>
#include <sys/mman.h>
#endif

// ==========================================================
// LIMITS
// ==========================================================

#define SEED_MAX_PATCHES   32
#define SEED_MAX_REGIONS  16

// ==========================================================
// PATCH TYPES
// ==========================================================

#define PATCH_REPLACE   1
#define PATCH_JUMP      2
#define PATCH_DISABLE   3

// ==========================================================
// PATCH RECORD
// ==========================================================

struct SeedHotPatch {
    void*    target_addr;
    uint8_t  original[16];
    uint8_t  patch[16];
    uint32_t size;
    uint8_t  applied;
};

// ==========================================================
// REGION RECORD
// ==========================================================

struct SeedExecRegion {
    void*    base;
    uint32_t size;
    uint8_t  executable;
};

// ==========================================================
// GLOBAL STATE
// ==========================================================

static SeedHotPatch  g_patches[SEED_MAX_PATCHES];
static uint32_t      g_patch_count = 0;

static SeedExecRegion g_regions[SEED_MAX_REGIONS];
static uint32_t       g_region_count = 0;

// ==========================================================
// MEMORY PROTECTION CONTROL
// ==========================================================

int seed_make_writable(void* addr, uint32_t size) {
#if defined(_WIN32)
    DWORD old;
    return VirtualProtect(addr, size, PAGE_EXECUTE_READWRITE, &old) ? 0 : -1;
#else
    uintptr_t page = (uintptr_t)addr & ~(getpagesize() - 1);
    return mprotect((void*)page, size, PROT_READ | PROT_WRITE | PROT_EXEC);
#endif
}

// ==========================================================
// REGISTER EXECUTABLE REGION
// ==========================================================

int seed_register_exec_region(void* base, uint32_t size) {
    if (g_region_count >= SEED_MAX_REGIONS)
        return -1;

    g_regions[g_region_count].base = base;
    g_regions[g_region_count].size = size;
    g_regions[g_region_count].executable = 1;
    g_region_count++;
    return 0;
}

// ==========================================================
// APPLY PATCH
// ==========================================================

int seed_apply_patch(void* target,
                     const uint8_t* patch,
                     uint32_t size) {
    if (g_patch_count >= SEED_MAX_PATCHES || size > 16)
        return -1;

    SeedHotPatch* p = &g_patches[g_patch_count++];

    p->target_addr = target;
    p->size = size;
    p->applied = 0;

    memcpy(p->original, target, size);
    memcpy(p->patch, patch, size);

    if (seed_make_writable(target, size) != 0)
        return -2;

    memcpy(target, patch, size);
    p->applied = 1;
    return 0;
}

// ==========================================================
// ROLLBACK PATCH
// ==========================================================

int seed_rollback_patch(uint32_t index) {
    if (index >= g_patch_count)
        return -1;

    SeedHotPatch* p = &g_patches[index];
    if (!p->applied)
        return -2;

    seed_make_writable(p->target_addr, p->size);
    memcpy(p->target_addr, p->original, p->size);
    p->applied = 0;
    return 0;
}

// ==========================================================
// BUILD RELATIVE JMP PATCH (x86)
// ==========================================================

void seed_build_jump(void* src, void* dst, uint8_t* out) {
    uintptr_t rel = (uintptr_t)dst - ((uintptr_t)src + 5);
    out[0] = 0xE9; // JMP rel32
    memcpy(out + 1, &rel, 4);
}

// ==========================================================
// DISABLE FUNCTION (RET)
// ==========================================================

void seed_build_disable(uint8_t* out) {
    out[0] = 0xC3; // RET
}

// ==========================================================
// HOT REDIRECT EXECUTION
// ==========================================================

int seed_redirect(void* from, void* to) {
    uint8_t patch[5];
    seed_build_jump(from, to, patch);
    return seed_apply_patch(from, patch, 5);
}

// ==========================================================
// SYSTEM HEALTH MONITOR (HOOK)
// ==========================================================

void seed_monitor_and_patch(void* fault_addr,
                            void* safe_handler) {
    printf("[SEED] Fault detected at %p — redirecting\n", fault_addr);
    seed_redirect(fault_addr, safe_handler);
}

// ==========================================================
// TEST TARGET FUNCTIONS
// ==========================================================

int unstable_function() {
    printf("Unstable function executing\n");
    return -1;
}

int safe_function() {
    printf("Safe function executing\n");
    return 0;
}

// ==========================================================
// TEST HARNESS
// ==========================================================

int main() {
    seed_register_exec_region((void*)unstable_function, 64);

    printf("Calling unstable function:\n");
    unstable_function();

    seed_monitor_and_patch((void*)unstable_function,
                           (void*)safe_function);

    printf("Calling unstable function after patch:\n");
    unstable_function();

    return 0;
}
