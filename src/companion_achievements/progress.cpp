/* SPDX-License-Identifier: MIT */
#include "progress.h"
#include "catalog.generated.h"

#include <algorithm>
#include <array>
#include <condition_variable>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <memory>
#include <mutex>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#else
#include <cerrno>
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
#endif

namespace {
namespace fs = std::filesystem;
constexpr size_t MaxProfileBytes = 256 * 1024, MaxProfileRows = 1024;
constexpr uint64_t MaxTimestamp = INT64_MAX;
struct Row { std::string id; ca_state state{}; };

/* Schema 1 uses identifiers, decimal integers, and a null seed. Parse
 * member order independently and reject duplicate or unexpected members. */
struct Reader {
    std::string_view remainder;
    void space() {
        const auto pos = remainder.find_first_not_of(" \r\n\t");
        remainder.remove_prefix(pos == std::string_view::npos ? remainder.size() : pos);
    }
    bool take(char token) {
        space();
        if (remainder.empty() || remainder.front() != token) return false;
        remainder.remove_prefix(1);
        return true;
    }
    bool identifier(std::string &out, bool member = false) {
        if (!take('"')) return false;
        out.clear();
        while (!remainder.empty() && remainder.front() != '"') {
            unsigned c = static_cast<unsigned char>(remainder.front());
            remainder.remove_prefix(1);
            if (c == '\\') {
                if (remainder.size() < 5 || remainder.front() != 'u') return false;
                c = 0;
                for (unsigned i = 1; i != 5; ++i) {
                    unsigned digit = remainder[i];
                    if (digit >= '0' && digit <= '9') digit -= '0';
                    else if (digit >= 'a' && digit <= 'f') digit -= 'a' - 10;
                    else if (digit >= 'A' && digit <= 'F') digit -= 'A' - 10;
                    else return false;
                    c = (c << 4) | digit;
                }
                remainder.remove_prefix(5);
            }
            if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
                  (member && c >= 'A' && c <= 'Z') || c == '.' || c == '_' || c == '-') ||
                out.size() == 80) return false;
            out += static_cast<char>(c);
        }
        return !out.empty() && !remainder.empty() && take('"');
    }
    bool number(uint64_t &out, uint64_t limit) {
        space();
        const auto end = remainder.find_first_not_of("0123456789");
        const auto digits = remainder.substr(0, end);
        if (digits.empty() || (digits.size() > 1 && digits.front() == '0')) return false;
        out = 0;
        for (char ch : digits) {
            const unsigned digit = ch - '0';
            if (digit > limit || out > (limit - digit) / 10) return false;
            out = out * 10 + digit;
        }
        remainder.remove_prefix(digits.size());
        return true;
    }
    bool null_seed() {
        space();
        if (remainder.substr(0, 4) != "null") return false;
        remainder.remove_prefix(4);
        return true;
    }
    template<class F> bool object(F member) {
        if (!take('{')) return false;
        std::string key;
        do {
            if (!identifier(key, true) || !take(':') || !member(key)) return false;
        } while (take(','));
        return take('}');
    }
};

bool once(unsigned &seen, unsigned field, bool valid) {
    if (!valid || (seen & field)) return false;
    seen |= field;
    return true;
}

bool read_rows(Reader &reader, std::vector<Row> &rows) {
    if (!reader.take('[')) return false;
    if (reader.take(']')) return true;
    do {
        if (rows.size() == MaxProfileRows) return false;
        Row row;
        unsigned seen = 0;
        if (!reader.object([&](const std::string &key) {
            if (key == "id") return once(seen, 1, reader.identifier(row.id));
            if (key == "unlockedAt") return once(seen, 2, reader.number(row.state.unlocked_at, MaxTimestamp));
            if (key != "progress") return false;
            uint64_t progress;
            if (!reader.number(progress, UINT32_MAX)) return false;
            row.state.progress = static_cast<uint32_t>(progress);
            return once(seen, 4, true);
        }) || seen != 7) return false;
        for (const Row &previous : rows) if (row.id == previous.id) return false;
        rows.push_back(std::move(row));
    } while (reader.take(','));
    return reader.take(']');
}

bool read_profile(std::string_view json, ca_engine &engine, std::vector<Row> &unknown, uint32_t &version) {
    Reader reader{json};
    std::vector<Row> rows;
    std::string value;
    uint64_t catalog = 0, schema = 0;
    unsigned seen = 0;
    if (!reader.object([&](const std::string &key) {
        if (key == "schemaVersion") return once(seen, 1, reader.number(schema, 1) && schema == 1);
        if (key == "gameId") return once(seen, 2, reader.identifier(value) && value == GAIA_GAME_ID);
        if (key == "editionId") return once(seen, 4, reader.identifier(value) && value == GAIA_EDITION_ID);
        if (key == "seedId") return once(seen, 8, reader.null_seed());
        if (key == "catalogVersion") return once(seen, 16, reader.number(catalog, UINT32_MAX) && catalog > 0);
        return key == "achievements" && once(seen, 32, read_rows(reader, rows));
    }) || seen != 63) return false;
    reader.space();
    if (!reader.remainder.empty()) return false;
    for (Row &row : rows) {
        size_t i = 0;
        while (i < engine.count && row.id != engine.definitions[i].id) ++i;
        if (i == engine.count) unknown.push_back(std::move(row));
        else if (!ca_restore(&engine, row.id.c_str(), row.state.progress, row.state.unlocked_at)) return false;
    }
    if (unknown.size() + engine.count > MaxProfileRows) return false;
    if (catalog > version) version = static_cast<uint32_t>(catalog);
    return true;
}

struct ProfileLock {
#ifdef _WIN32
    HANDLE handle = INVALID_HANDLE_VALUE;
    ~ProfileLock() { if (handle != INVALID_HANDLE_VALUE) CloseHandle(handle); }
    IogAchievementStatus open(const fs::path &path) {
        handle = CreateFileW(path.c_str(), GENERIC_READ | GENERIC_WRITE, 0, nullptr, OPEN_ALWAYS,
                             FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
        if (handle == INVALID_HANDLE_VALUE)
            return GetLastError() == ERROR_SHARING_VIOLATION ? kIogAchievementInUse : kIogAchievementWriteFailure;
        BY_HANDLE_FILE_INFORMATION info{};
        if (!GetFileInformationByHandle(handle, &info) ||
            (info.dwFileAttributes & (FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT)))
            return kIogAchievementWriteFailure;
        return kIogAchievementReady;
    }
#else
    int handle = -1;
    ~ProfileLock() { if (handle != -1) close(handle); }
    IogAchievementStatus open(const fs::path &path) {
        handle = ::open(path.c_str(), O_RDWR | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0600);
        if (handle < 0) return kIogAchievementWriteFailure;
        if (flock(handle, LOCK_EX | LOCK_NB) == 0) return kIogAchievementReady;
        return errno == EWOULDBLOCK ? kIogAchievementInUse : kIogAchievementWriteFailure;
    }
#endif
};

bool write_profile(const fs::path &file, const std::string &data) {
#ifdef _WIN32
    const auto temp = file.parent_path() / (L"progress.tmp-" + std::to_wstring(GetCurrentProcessId()) +
                                           L"-" + std::to_wstring(GetTickCount64()));
    HANDLE handle = CreateFileW(temp.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (handle == INVALID_HANDLE_VALUE) return false;
    DWORD written = 0;
    bool ok = WriteFile(handle, data.data(), static_cast<DWORD>(data.size()), &written, nullptr) &&
              written == data.size() && FlushFileBuffers(handle);
    if (!CloseHandle(handle)) ok = false;
    if (ok) ok = MoveFileExW(temp.c_str(), file.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
    if (!ok) DeleteFileW(temp.c_str());
    return ok;
#else
    std::string temp = (file.parent_path() / "progress.tmp-XXXXXX").string();
    int handle = mkstemp(temp.data());
    if (handle < 0) return false;
    size_t offset = 0;
    while (offset < data.size()) {
        const ssize_t n = write(handle, data.data() + offset, data.size() - offset);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) break;
        offset += static_cast<size_t>(n);
    }
    bool ok = offset == data.size() && fsync(handle) == 0;
    if (close(handle)) ok = false;
    const int directory = ::open(file.parent_path().c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (ok) ok = directory >= 0 && rename(temp.c_str(), file.c_str()) == 0 && fsync(directory) == 0;
    if (directory >= 0) close(directory);
    if (!ok) unlink(temp.c_str());
    return ok;
#endif
}

const char *const Events[] = {"rooms.cleared", "jewels.collected", "story.finished"};
struct Event { size_t id; uint32_t value; };
} // namespace

struct IogAchievementStore {
    fs::path directory;
    ca_engine engine{};
    std::vector<Row> unknown;
    uint32_t catalog_version = GAIA_CATALOG_VERSION;
    std::mutex mutex;
    std::condition_variable ready;
    std::array<Event, 64> queue{};
    size_t next = 0, pending = 0;
    bool stopping = false;
    IogAchievementStatus status = kIogAchievementLoading;
    std::array<ca_state, CA_MAX_ACHIEVEMENTS> published{};
    uint64_t notices = 0, earned = 0;
    std::thread worker;

    void publish(IogAchievementStatus value) {
        std::lock_guard<std::mutex> guard(mutex);
        status = value;
        if (value == kIogAchievementReady) {
            std::copy_n(engine.states, engine.count, published.begin());
            notices |= earned;
            earned = 0;
        }
    }
    static bool commit(void *context, const ca_state *states, size_t count) {
        auto &self = *static_cast<IogAchievementStore *>(context);
        std::string json = "{\n\"schemaVersion\":1,\"gameId\":\"" GAIA_GAME_ID
                           "\",\"editionId\":\"" GAIA_EDITION_ID "\",\"seedId\":null,\"catalogVersion\":" +
                           std::to_string(self.catalog_version) + ",\"achievements\":[\n";
        auto row = [&](const char *id, ca_state state) {
            if (json.back() == '}') json += ",\n";
            json += "{\"id\":\"" + std::string(id) + "\",\"progress\":" + std::to_string(state.progress) +
                    ",\"unlockedAt\":" + std::to_string(state.unlocked_at) + "}";
        };
        for (size_t i = 0; i < count; ++i) row(self.engine.definitions[i].id, states[i]);
        for (const Row &item : self.unknown) row(item.id.c_str(), item.state);
        json += "\n]}\n";
        return write_profile(self.directory / "progress.json", json);
    }
    static void notice(void *context, const ca_definition *def, const ca_state *) {
        auto &self = *static_cast<IogAchievementStore *>(context);
        self.earned |= uint64_t{1} << (def - self.engine.definitions);
    }
    bool load() {
        if (!ca_init(&engine, gaia_definitions, GAIA_ACHIEVEMENT_COUNT, commit, notice, this)) return false;
        const fs::path file = directory / "progress.json";
        std::error_code ec;
        const auto type = fs::symlink_status(file, ec).type();
        if (type == fs::file_type::not_found) return true;
        if (ec || type != fs::file_type::regular || fs::file_size(file, ec) > MaxProfileBytes || ec) return false;
        std::ifstream input(file, std::ios::binary);
        if (!input) return false;
        std::string data(MaxProfileBytes + 1, '\0');
        input.read(data.data(), data.size());
        if (input.bad() || !input.eof() || input.gcount() > MaxProfileBytes) return false;
        data.resize(static_cast<size_t>(input.gcount()));
        return read_profile(data, engine, unknown, catalog_version);
    }
    void run() {
        std::error_code ec;
        fs::create_directories(directory, ec);
        if (ec) { publish(kIogAchievementWriteFailure); return; }
        ProfileLock lock;
        auto admission = lock.open(directory / "progress.lock");
        if (admission != kIogAchievementReady) { publish(admission); return; }
        if (!load()) { publish(kIogAchievementInvalidProfile); return; }
        publish(kIogAchievementReady);
        for (;;) {
            Event event;
            {
                std::unique_lock<std::mutex> guard(mutex);
                ready.wait(guard, [&] { return stopping || pending; });
                if (!pending) return;
                event = queue[next];
                next = (next + 1) % queue.size();
                --pending;
            }
            const auto now = std::time(nullptr);
            if (now <= 0 || !ca_event(&engine, Events[event.id], event.value, static_cast<uint64_t>(now))) {
                publish(kIogAchievementWriteFailure);
                return;
            }
            publish(kIogAchievementReady);
        }
    }
};

IogAchievementStore *IogAchievementStoreOpen(const char *profile_directory) {
    if (!profile_directory || !*profile_directory) return nullptr;
    try {
        auto store = std::make_unique<IogAchievementStore>();
        store->directory = fs::u8path(profile_directory);
        store->worker = std::thread([p = store.get()] {
            try { p->run(); } catch (...) { p->publish(kIogAchievementWriteFailure); }
        });
        return store.release();
    } catch (...) { return nullptr; }
}

void IogAchievementStoreClose(IogAchievementStore *store) {
    if (!store) return;
    {
        std::lock_guard<std::mutex> guard(store->mutex);
        store->stopping = true;
    }
    store->ready.notify_one();
    store->worker.join();
    delete store;
}

bool IogAchievementStoreEvent(IogAchievementStore *store, const char *event, uint32_t value) {
    if (!store || !event || !value) return false;
    size_t id = 0;
    while (id < std::size(Events) && std::string_view(event) != Events[id]) ++id;
    if (id == std::size(Events)) return false;
    {
        std::lock_guard<std::mutex> guard(store->mutex);
        if (store->status > kIogAchievementReady || store->stopping || store->pending == store->queue.size()) return false;
        store->queue[(store->next + store->pending) % store->queue.size()] = {id, value};
        ++store->pending;
    }
    store->ready.notify_one();
    return true;
}

IogAchievementStatus IogAchievementStoreSnapshot(IogAchievementStore *store,
    ca_state states[CA_MAX_ACHIEVEMENTS], uint64_t *notices) {
    if (!store || !states || !notices) return kIogAchievementWriteFailure;
    std::lock_guard<std::mutex> guard(store->mutex);
    std::copy(store->published.begin(), store->published.end(), states);
    *notices = store->notices;
    store->notices = 0;
    return store->status;
}
