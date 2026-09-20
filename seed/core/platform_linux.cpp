#ifndef _WIN32
#include "platform_adapter.h"
#include <fstream>

class LinuxConfigAdapter : public PlatformAdapter {
    const std::string path = "/etc/seedos.conf";

public:
    bool read(const std::string& key, std::string& value) override {
        std::ifstream f(path);
        std::string line;
        while (std::getline(f, line)) {
            auto pos = line.find('=');
            if (pos != std::string::npos && line.substr(0, pos) == key) {
                value = line.substr(pos + 1);
                return true;
            }
        }
        return false;
    }

    bool write(const std::string& key, const std::string& value) override {
        std::ofstream f(path, std::ios::app);
        if (!f) return false;
        f << key << "=" << value << "\n";
        return true;
    }

    void flush() override {}
};

PlatformAdapter* createPlatformAdapter() {
    return new LinuxConfigAdapter();
}
#endif
