/* SPDX-License-Identifier: MIT */
#include "progress.h"

#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <thread>

#define CHECK(ok) do { if (!(ok)) { std::cerr << #ok << " failed at " << __LINE__ << '\n'; std::exit(1); } } while (0)
namespace fs = std::filesystem;
using namespace std::chrono_literals;

static IogAchievementStatus ready(IogAchievementStore *store) {
    ca_state states[CA_MAX_ACHIEVEMENTS];
    uint64_t notices;
    for (int i = 0; i < 100; ++i) {
        auto status = IogAchievementStoreSnapshot(store, states, &notices);
        if (status != kIogAchievementLoading) return status;
        std::this_thread::sleep_for(20ms);
    }
    return kIogAchievementLoading;
}

static IogAchievementStore *open(const fs::path &path) {
    auto *store = IogAchievementStoreOpen(path.u8string().c_str());
    CHECK(store);
    return store;
}

static std::string read(const fs::path &file) {
    std::ifstream input(file, std::ios::binary);
    CHECK(input);
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

int main() {
    const auto unique = std::chrono::high_resolution_clock::now().time_since_epoch().count();
    const auto dir = fs::current_path() / ("test-progress-" + std::to_string(unique));
    CHECK(fs::create_directory(dir));
    const auto file = dir / "progress.json";
    std::ofstream(file) << R"({"catalogVersion":2,"gameId":"illusion-of-gaia","schemaVersion":1,"seedId":null,"editionId":"stock-companion","achievements":[{"id":"gaia.future","unlockedAt":42,"progress":9}]})";
    auto *store = open(dir);
    CHECK(ready(store) == kIogAchievementReady);
    auto *contender = open(dir);
    CHECK(ready(contender) == kIogAchievementInUse);
    CHECK(!IogAchievementStoreEvent(contender, "jewels.collected", 10));
    IogAchievementStoreClose(contender);
    CHECK(!IogAchievementStoreEvent(store, "unknown", 1));
    CHECK(IogAchievementStoreEvent(store, "jewels.collected", 10));
    ca_state states[CA_MAX_ACHIEVEMENTS];
    uint64_t notices = 0;
    for (int i = 0; i < 100 && !notices; ++i) {
        CHECK(IogAchievementStoreSnapshot(store, states, &notices) == kIogAchievementReady);
        if (!notices) std::this_thread::sleep_for(20ms);
    }
    CHECK(notices == ((1u << 1) | (1u << 2)));
    CHECK(states[1].progress == 1 && states[1].unlocked_at && states[2].progress == 10 && states[2].unlocked_at);
    CHECK(IogAchievementStoreSnapshot(store, states, &notices) == kIogAchievementReady && notices == 0);
    CHECK(IogAchievementStoreEvent(store, "story.finished", 1));
    IogAchievementStoreClose(store);
    const auto json = read(file);
    CHECK(json.find(R"("catalogVersion":2)") != std::string::npos);
    CHECK(json.find(R"({"id":"gaia.future","progress":9,"unlockedAt":42})") != std::string::npos);

    store = open(dir);
    CHECK(ready(store) == kIogAchievementReady);
    CHECK(IogAchievementStoreSnapshot(store, states, &notices) == kIogAchievementReady && notices == 0);
    CHECK(states[5].progress == 1 && states[5].unlocked_at);
    IogAchievementStoreClose(store);

    const auto invalid = json + "{}";
    std::ofstream(file, std::ios::binary) << invalid;
    store = open(dir);
    CHECK(ready(store) == kIogAchievementInvalidProfile);
    CHECK(!IogAchievementStoreEvent(store, "rooms.cleared", 1));
    IogAchievementStoreClose(store);
    CHECK(read(file) == invalid);

    CHECK(fs::remove(file));
    store = open(dir);
    CHECK(ready(store) == kIogAchievementReady);
    CHECK(fs::create_directory(file));
    CHECK(IogAchievementStoreEvent(store, "rooms.cleared", 1));
    auto status = kIogAchievementReady;
    for (int i = 0; i < 100 && status == kIogAchievementReady; ++i) {
        status = IogAchievementStoreSnapshot(store, states, &notices);
        if (status == kIogAchievementReady) std::this_thread::sleep_for(20ms);
    }
    CHECK(status == kIogAchievementWriteFailure && states[0].progress == 0 && notices == 0);
    IogAchievementStoreClose(store);
    CHECK(fs::is_directory(file));
    CHECK(fs::remove(file));
    CHECK(fs::remove(dir / "progress.lock"));
    CHECK(fs::remove(dir));
    std::cout << "PASS durable progress, lock contention, forward IDs, restore, corruption and failed commit\n";
}
