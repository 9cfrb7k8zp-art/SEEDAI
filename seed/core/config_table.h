#pragma once
#include "config_defs.h"

struct ConfigEntry {
    char key[SEED_KEY_LEN];
    char value[SEED_VAL_LEN];
};

struct ConfigTable {
    ConfigEntry entries[SEED_MAX_CONFIGS];
    int count;
};
