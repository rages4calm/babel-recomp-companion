using System.Security.Cryptography;
using System.Text.Json;
using Companion.Launcher.Core;

internal static class AchievementProviderTests
{
    private const string StockEdition = "stock-companion";
    private const ulong EarnedAt = 1762000000;

    internal static int Run(string root)
    {
        Directory.CreateDirectory(root);
        var adapter = new GameAdapter(Path.Combine(root, "preferences"));
        var profile = adapter.Profiles.Single();
        var one = CreateEngine(root, "first game");
        var two = CreateEngine(root, "second game");
        var progress = ProgressPath(one);
        var otherProgress = ProgressPath(two);
        var catalog = Path.Combine(AppContext.BaseDirectory, "assets", "achievements", "catalog.json");
        var catalogBefore = Describe(catalog);
        int checks = 0;

        void Check(bool condition, string message)
        {
            if (!condition) throw new Exception(message);
            checks++;
        }

        void ReadOnly(Action action)
        {
            var before = Inventory(root);
            action();
            Check(before.SequenceEqual(Inventory(root)), "achievement reads must preserve files and directories");
        }

        void Refuses<T>(Action action, string message) where T : Exception
        {
            try { action(); }
            catch (T) { checks++; return; }
            throw new Exception(message);
        }

        void Select(string engine)
        {
            var settings = adapter.ReadSettings(profile);
            settings.Values["engine.path"] = OptionValue.From(engine);
            adapter.ApplySettings(profile, settings.Values, settings.Revision);
        }

        Check(adapter.Definition.HasAchievements, "shared launcher exposes the Gaia achievements page");
        Check(profile.EditionId == "original", "native achievement identity preserves launcher preferences");
        Select(one);
        WriteProgress(otherProgress);
        var decoy = Path.Combine(adapter.ProfileDirectory(profile), "progress.json");
        WriteProgress(decoy);
        ReadOnly(() =>
        {
            var locked = adapter.ReadAchievements(profile);
            Check(locked.Title == "Illusion of Gaia Companion" && locked.Entries.Count == 6,
                "packaged Gaia catalog loads with its six definitions");
            Check(locked.Entries.All(row => row.Progress == 0 && row.UnlockedAt == 0),
                "a missing progress file locks every achievement even when other profiles have data");
            Check(!Directory.Exists(Path.Combine(Path.GetDirectoryName(one)!, "UserData")),
                "the browser does not create the selected engine's progress directory");
        });

        WriteProgress(progress);
        ReadOnly(() =>
        {
            var saved = adapter.ReadAchievements(profile);
            var earned = saved.Entries.Single(row => row.Id == "gaia.first-jewel");
            var partial = saved.Entries.Single(row => row.Id == "gaia.ten-jewels");
            Check(earned is { Progress: 1, UnlockedAt: EarnedAt }, "read the exact engine award and timestamp");
            Check(partial is { Progress: 4, Target: 10, UnlockedAt: 0 }, "read partial progress without awarding");
            Check(saved.Entries.All(row => row.Id != "gaia.future"), "ignore progress for an unknown future ID");
        });

        foreach (var invalid in new[]
        {
            ProgressJson(game: "another-game"),
            ProgressJson(edition: "original"),
            ProgressJson(seed: "randomized"),
            ProgressJson(unlockedAt: 0)
        })
        {
            File.WriteAllText(progress, invalid);
            ReadOnly(() => Refuses<InvalidDataException>(() => adapter.ReadAchievements(profile),
                "refuse wrong identities and inconsistent unlock data"));
        }
        File.WriteAllText(progress, "{invalid json");
        ReadOnly(() => Refuses<JsonException>(() => adapter.ReadAchievements(profile), "refuse malformed progress"));
        ReadOnly(() => Refuses<ArgumentException>(() => adapter.ReadAchievements(profile with { SeedId = "private" }),
            "refuse a profile that Gaia does not declare"));

        Select(two);
        File.Delete(otherProgress);
        File.WriteAllText(Path.Combine(Path.GetDirectoryName(two)!, "config.ini"), "[Sound]\nVolume = broken\n");
        ReadOnly(() => Check(adapter.ReadAchievements(profile).Entries.All(row => row.UnlockedAt == 0),
            "engine selection switches progress namespace and achievements require no native config parsing"));
        var preferences = new JsonSettingsStore(Path.Combine(adapter.ProfileDirectory(profile), "settings.json"));
        var persisted = preferences.Read();
        persisted.Values["engine.path"] = OptionValue.From("relative-game.exe");
        preferences.Write(persisted.Values, persisted.Revision);
        ReadOnly(() => Refuses<InvalidDataException>(() => adapter.ReadAchievements(profile),
            "refuse a non-absolute engine path in persisted preferences"));
        Check(catalogBefore == Describe(catalog), "the packaged catalog remains byte-identical");
        return checks;
    }

    private static string CreateEngine(string root, string folder)
    {
        var engineRoot = Directory.CreateDirectory(Path.Combine(root, folder)).FullName;
        var executable = Path.Combine(engineRoot, "babel-recomp.exe");
        File.WriteAllText(executable, "fixture; never executed");
        return executable;
    }

    private static string ProgressPath(string engine) => Path.Combine(Path.GetDirectoryName(engine)!,
        "UserData", "Achievements", "illusion-of-gaia", StockEdition, "unseeded", "progress.json");

    private static void WriteProgress(string path)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, ProgressJson());
    }

    private static string ProgressJson(string game = "illusion-of-gaia", string edition = StockEdition,
        string? seed = null, ulong unlockedAt = EarnedAt) => JsonSerializer.Serialize(new
    {
        schemaVersion = 1,
        gameId = game,
        editionId = edition,
        seedId = seed,
        catalogVersion = 1,
        achievements = new[]
        {
            new { id = "gaia.first-jewel", progress = 1, unlockedAt },
            new { id = "gaia.ten-jewels", progress = 4, unlockedAt = 0UL },
            new { id = "gaia.future", progress = 1, unlockedAt = EarnedAt }
        }
    });

    private static (long Modified, string Hash) Describe(string path) =>
        (File.GetLastWriteTimeUtc(path).Ticks, Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(path))));

    private static string[] Inventory(string root) => Directory.EnumerateFileSystemEntries(root, "*", SearchOption.AllDirectories)
        .OrderBy(path => path, StringComparer.Ordinal)
        .Select(path => $"{Path.GetRelativePath(root, path)}|{(Directory.Exists(path) ? "directory" : Describe(path).ToString())}")
        .ToArray();
}
