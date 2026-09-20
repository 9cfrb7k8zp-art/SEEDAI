#include "config_driver.h"
#include <cstring>
#include <cstdlib>

extern PlatformAdapter* createPlatformAdapter();

ConfigDriver::ConfigDriver() : adapter(nullptr), alive(false) {
    table.count = 0;
}

bool ConfigDriver::boot() {
    adapter = createPlatformAdapter();
    if (!adapter) return false;

    set("scheduler.mode", "normal");
    set("cache.size", "medium");

    alive = true;
    return true;
}

void ConfigDriver::set(const char* key, const char* value) {
    for (int i = 0; i < table.count; i++) {
        if (strcmp(table.entries[i].key, key) == 0) {
            strncpy(table.entries[i].value, value, SEED_VAL_LEN);
            return;
        }
    }

    if (table.count < SEED_MAX_CONFIGS) {
        strncpy(table.entries[table.count].key, key, SEED_KEY_LEN);
        strncpy(table.entries[table.count].value, value, SEED_VAL_LEN);
        table.count++;
    }
}

const char* ConfigDriver::get(const char* key) {
    for (int i = 0; i < table.count; i++)
        if (strcmp(table.entries[i].key, key) == 0)
            return table.entries[i].value;
    return nullptr;
}

void ConfigDriver::policy(int cpu, int mem) {
    if (cpu > 80) set("scheduler.mode", "safe");
    if (mem > 80) set("cache.size", "low");
}

void ConfigDriver::persist() {
    for (int i = 0; i < table.count; i++)
        adapter->write(table.entries[i].key, table.entries[i].value);

    adapter->flush();
}

void ConfigDriver::eventTick() {
    if (!alive) return;

    int cpu = rand() % 100;
    int mem = rand() % 100;

    policy(cpu, mem);
    persist();
}

void ConfigDriver::shutdown() {
    alive = false;
}
