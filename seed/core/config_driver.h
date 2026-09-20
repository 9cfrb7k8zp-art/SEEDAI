#pragma once
#include <atomic>
#include "platform_adapter.h"
#include "config_table.h"

class ConfigDriver {
public:
    ConfigDriver();
    bool boot();
    void eventTick();
    void shutdown();

private:
    void set(const char* key, const char* value);
    const char* get(const char* key);
    void persist();
    void policy(int cpu, int mem);

    ConfigTable table;
    PlatformAdapter* adapter;
    bool alive;
};
