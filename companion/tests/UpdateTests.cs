using System.IO.Compression;
using System.Net;
using System.Net.Sockets;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

/// <summary>Updater checks: synthetic packages, a loopback HTTP server, scratch folders only.</summary>
internal static class UpdateTests
{
    private static int checks;
    private static void Check(bool yes, string name) { if (!yes) throw new Exception("update test failed: " + name); checks++; }
    private static async Task Refused(Func<Task> action, string name, string? contains = null)
    {
        try { await action(); }
        catch (UpdateException error) {
            if (contains != null && !error.Message.Contains(contains, StringComparison.OrdinalIgnoreCase)) throw new Exception($"{name}: unexpected message: {error.Message}");
            checks++; return;
        }
        throw new Exception("update test failed (not refused): " + name);
    }
    private static Task Refused(Action action, string name, string? contains = null) => Refused(() => { action(); return Task.CompletedTask; }, name, contains);

    public static async Task RunAsync()
    {
        if (Environment.GetCommandLineArgs().Contains("--live-check")) {
            // Read-only query of the real GitHub feed; downloads nothing.
            Environment.SetEnvironmentVariable(UpdateService.FeedVariable, null);
            var live = await UpdateService.CheckAsync(Path.GetTempPath());
            var l = live.Latest;
            Console.WriteLine(JsonSerializer.Serialize(new { feed = UpdateService.DefaultFeed, latest = l?.Version.ToString(), tag = l?.Tag, zip = l?.Zip.Name,
                size = l?.Zip.Size, digest = l?.Zip.Sha256, checksumAsset = l?.ChecksumFile?.Name, notesChars = l?.Notes.Length, notesStart = l?.Notes[..Math.Min(120, l.Notes.Length)] }));
            return;
        }
        var root = Path.Combine(Path.GetTempPath(), "GaiaCompanion-update-tests-" + Guid.NewGuid().ToString("N")[..8]);
        Directory.CreateDirectory(root);
        var savedFeed = Environment.GetEnvironmentVariable(UpdateService.FeedVariable);
        try {
            Versions();
            Picking();
            Policy();
            await Zips(root);
            CarryOver(root);
            Rollback(root);
            Removal(root);
            ManifestCarry(root);
            Shortcuts(root);
            await Network(root);
            Console.WriteLine(JsonSerializer.Serialize(new { passed = true, checks, suite = "updater", synthetic = true }));
        } finally {
            Environment.SetEnvironmentVariable(UpdateService.FeedVariable, savedFeed);
            try { UpdateService.DeleteTree(root); } catch (Exception) { }
        }
    }

    private static ReleaseVersion V(string text) => ReleaseVersion.Parse(text);

    private static void Versions()
    {
        Check(V("0.2.0-beta.21") > V("0.2.0-beta.9"), "beta.21 is newer than beta.9");
        Check(V("0.2.0-beta.10") > V("0.2.0-beta.2"), "numeric identifiers compare as numbers");
        Check(V("0.2.0") > V("0.2.0-beta.99"), "a release outranks its pre-releases");
        Check(V("0.3.0-alpha.1") > V("0.2.9"), "core version first");
        Check(V("v0.2.0-beta.21").Equals(V("0.2.0-beta.21")), "tag v prefix");
        Check(V("0.2.0-beta.21+abc123").Equals(V("0.2.0-beta.21")), "build metadata ignored");
        var spec = new[] { "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11", "1.0.0-rc.1", "1.0.0" };
        for (int i = 1; i < spec.Length; i++) Check(V(spec[i]) > V(spec[i - 1]), "SemVer precedence " + spec[i]);
        var shuffled = new[] { "0.2.0-beta.9", "0.2.0-beta.21", "0.2.0-beta.1", "0.2.0-beta.19", "0.2.0-beta.3" }.Select(V).OrderBy(x => x).Select(x => x.ToString()).ToArray();
        Check(shuffled.SequenceEqual(new[] { "0.2.0-beta.1", "0.2.0-beta.3", "0.2.0-beta.9", "0.2.0-beta.19", "0.2.0-beta.21" }), "sorting a release list");
        Check(!ReleaseVersion.TryParse("0.2.0-beta.01", out _) && !ReleaseVersion.TryParse("latest", out _) && !ReleaseVersion.TryParse("0.2", out _), "invalid versions rejected");
        Check(V("0.2.0-beta.22").ShortLabel == "beta 22", "button label");
    }

    private static string Feed(params object[] releases) => JsonSerializer.Serialize(releases);
    private static object Release(string tag, bool draft = false, bool prerelease = true, string body = "", params object[] assets) =>
        new { tag_name = tag, name = tag, draft, prerelease, body, html_url = "https://github.com/rages4calm/babel-recomp-companion/releases/tag/" + tag, assets };
    private static object Asset(string name, string url, long size = 100, string? digest = null) =>
        new { name, browser_download_url = url, size, digest };
    private static string Zip(string version) => $"babel-recomp-{version}-windows-x86_64.zip";
    private const string Hash = "60a2e575f40b3a77e8e626fdf3b4fc23b636cc9ebcd0380717762e4cd9586ac9";

    private static void Picking()
    {
        var feed = Feed(
            Release("v0.2.0-beta.30", draft: true, assets: Asset(Zip("0.2.0-beta.30"), "https://github.com/x/" + Zip("0.2.0-beta.30"))),
            Release("v0.2.0-beta.22", assets: Asset("babel-recomp-0.2.0-beta.22-linux-x86_64.zip", "https://github.com/x/linux.zip")),
            Release("nightly", assets: Asset(Zip("nightly"), "https://github.com/x/n.zip")),
            Release("v0.2.0-beta.9", assets: Asset(Zip("0.2.0-beta.9"), "https://github.com/x/9.zip", 9, "sha256:" + new string('a', 64))),
            Release("v0.2.0-beta.21", body: "## What's new\r\n\r\n**Bold** fix, see [the issue](https://github.com/x/1).\r\n* item `code`",
                assets: new[] { Asset(Zip("0.2.0-beta.21"), "https://github.com/x/21.zip", 10901781, "sha256:" + Hash.ToUpperInvariant()),
                                Asset(Zip("0.2.0-beta.21") + ".sha256", "https://github.com/x/21.zip.sha256", 111) }),
            Release("v0.2.0-beta.20", assets: Asset(Zip("0.2.0-beta.21"), "https://github.com/x/wrong-name.zip")));
        var latest = UpdateService.PickLatest(feed)!;
        Check(latest.Version.ToString() == "0.2.0-beta.21", "newest with a Windows zip wins; drafts, other platforms and odd tags ignored");
        Check(latest.Zip.Sha256 == Hash && latest.Zip.Size == 10901781, "digest and size read");
        Check(latest.ChecksumFile?.Name == Zip("0.2.0-beta.21") + ".sha256", ".sha256 asset paired");
        Check(latest.TopFolder == "babel-recomp-0.2.0-beta.21-windows-x86_64" && latest.FolderName == "v0.2.0-beta.21", "folder names");
        Check(latest.Notes == "What's new\r\n\r\nBold fix, see the issue.\r\n- item code", "release notes as plain text: " + latest.Notes);
        Check(UpdateService.PickLatest("[]") == null, "empty feed");
        Check(new UpdateCheck(V("0.2.0-beta.21"), latest).IsNewer == false && new UpdateCheck(V("0.2.0-beta.20"), latest).IsNewer, "compare with running build");
        Check(UpdateService.ParseChecksumFile($"{Hash} *{Zip("0.2.0-beta.21")}\n", Zip("0.2.0-beta.21")) == Hash, "sha256sum format");
        Check(UpdateService.ParseChecksumFile(Hash.ToUpperInvariant(), "x.zip") == Hash, "bare hash");
    }

    private static void Policy()
    {
        Environment.SetEnvironmentVariable(UpdateService.FeedVariable, null);
        UpdateService.RequireAllowed(new Uri("https://api.github.com/repos/x/y/releases"));
        UpdateService.RequireAllowed(new Uri("https://release-assets.githubusercontent.com/a"));
        checks += 2;
        Refused(() => UpdateService.RequireAllowed(new Uri("http://github.com/x")), "plain HTTP refused", "HTTPS").Wait();
        Refused(() => UpdateService.RequireAllowed(new Uri("http://127.0.0.1:8080/x")), "loopback HTTP refused without a test feed").Wait();
        Refused(() => UpdateService.RequireAllowed(new Uri("https://example.com/x.zip")), "non-GitHub host refused").Wait();
        Refused(() => UpdateService.RequireAllowed(new Uri("https://github.com.evil.example/x.zip")), "look-alike host refused").Wait();
        Environment.SetEnvironmentVariable(UpdateService.FeedVariable, "http://127.0.0.1:1/feed");
        UpdateService.RequireAllowed(new Uri("http://127.0.0.1:8080/x")); checks++;
        Refused(() => UpdateService.RequireAllowed(new Uri("http://192.168.1.5/x")), "test feed still refuses remote HTTP").Wait();
        // A test run against GitHub's own feed keeps the production host policy (redirect targets are checked).
        Environment.SetEnvironmentVariable(UpdateService.FeedVariable, UpdateService.DefaultFeed);
        Check(UpdateService.UsingTestFeed && !UpdateService.RelaxedHosts, "GitHub test feed is not relaxed");
        UpdateService.RequireAllowed(new Uri("https://release-assets.githubusercontent.com/a")); checks++;
        Refused(() => UpdateService.RequireAllowed(new Uri("https://example.com/x.zip")), "GitHub test feed refuses other hosts").Wait();
        Refused(() => UpdateService.RequireAllowed(new Uri("http://127.0.0.1:8080/x")), "GitHub test feed refuses loopback HTTP").Wait();
        Environment.SetEnvironmentVariable(UpdateService.FeedVariable, null);
    }

    // ---------- packages ----------

    private static readonly Dictionary<string, string> NewPackage = new() {
        ["babel-recomp.exe"] = "engine v2", ["illusion-of-gaia.Companion.exe"] = "launcher v2", ["illusion-of-gaia.Companion.dll"] = "launcher dll v2",
        ["README.md"] = "new readme", ["mods/preloaded/catalog.toml"] = "catalog v2", ["docs/MSU1.md"] = "guide"
    };
    private static void WriteZip(string path, IEnumerable<(string Name, string Text)> entries)
    {
        using var zip = ZipFile.Open(path, ZipArchiveMode.Create);
        foreach (var (name, text) in entries) { var entry = zip.CreateEntry(name); using var s = entry.Open(); s.Write(Encoding.UTF8.GetBytes(text)); }
    }
    private static string PackageZip(string dir, string version, Dictionary<string, string>? files = null)
    {
        var top = $"babel-recomp-{version}-windows-x86_64"; var path = Path.Combine(dir, top + ".zip");
        WriteZip(path, (files ?? NewPackage).Select(p => (top + "/" + p.Key, p.Value)));
        return path;
    }
    private static UpdateRelease ReleaseFor(string version, string url, string? sha, string? sumUrl = null) =>
        new(V(version), "v" + version, "v" + version, "notes", new UpdateAsset(Zip(version), new Uri(url), 0, sha),
            sumUrl == null ? null : new UpdateAsset(Zip(version) + ".sha256", new Uri(sumUrl), 0, null), null);

    private static async Task Zips(string root)
    {
        var dir = Path.Combine(root, "zips"); Directory.CreateDirectory(dir);
        var top = "babel-recomp-0.2.0-beta.22-windows-x86_64";
        (string, string)[] Valid() => NewPackage.Select(p => (top + "/" + p.Key, p.Value)).ToArray();
        var cases = new (string Name, (string, string)[] Entries)[] {
            ("dot-dot", Valid().Append((top + "/../escaped.txt", "x")).ToArray()),
            ("nested dot-dot", Valid().Append((top + "/mods/../../escaped.txt", "x")).ToArray()),
            ("absolute", Valid().Append(("/escaped.txt", "x")).ToArray()),
            ("drive letter", Valid().Append(("C:/escaped.txt", "x")).ToArray()),
            ("backslash dot-dot", Valid().Append((top + "\\..\\escaped.txt", "x")).ToArray()),
            ("second top folder", Valid().Append(("other/escaped.txt", "x")).ToArray()),
            ("missing launcher", Valid().Where(e => !e.Item1.EndsWith("Companion.exe")).ToArray()),
            ("missing engine", Valid().Where(e => !e.Item1.EndsWith("babel-recomp.exe")).ToArray()),
        };
        foreach (var (name, entries) in cases) {
            var zip = Path.Combine(dir, name + ".zip"); WriteZip(zip, entries);
            var staging = Path.Combine(dir, "stage-" + name.Replace(' ', '-'));
            await Refused(() => UpdateService.ExtractVerified(zip, staging, top), "zip refused: " + name, "refused");
            Check(!File.Exists(Path.Combine(dir, "escaped.txt")) && !File.Exists(Path.Combine(root, "escaped.txt")) && !File.Exists(Path.Combine(dir, "C", "escaped.txt")), "nothing written outside: " + name);
            Check(!Directory.Exists(staging) || !Directory.EnumerateFileSystemEntries(staging).Any(), "validated before extracting: " + name);
        }
        var good = PackageZip(dir, "0.2.0-beta.22");
        var files = UpdateService.ExtractVerified(good, Path.Combine(dir, "good"), top);
        Check(files.Count == NewPackage.Count && File.ReadAllText(Path.Combine(dir, "good", top, "mods/preloaded/catalog.toml")) == "catalog v2", "valid package extracts");
    }

    // ---------- install ----------

    private sealed record Fixture(string Parent, string Old, string Zip, UpdateRelease Release, string Work, string Shortcuts);
    private static readonly byte[] Bom = { 239, 187, 191 };

    private static Fixture MakeInstall(string root, string name, Dictionary<string, string>? oldPackageFiles = null)
    {
        var parent = Path.Combine(root, name, "Illusion of Gaia Companion"); var old = Path.Combine(parent, "v0.2.0-beta.21");
        Directory.CreateDirectory(old);
        void Put(string rel, string text) { var p = Path.Combine(old, rel); Directory.CreateDirectory(Path.GetDirectoryName(p)!); File.WriteAllText(p, text); }
        void PutBytes(string rel, byte[] bytes) { var p = Path.Combine(old, rel); Directory.CreateDirectory(Path.GetDirectoryName(p)!); File.WriteAllBytes(p, bytes); }
        foreach (var pair in oldPackageFiles ?? new() { ["babel-recomp.exe"] = "engine v1", ["illusion-of-gaia.Companion.exe"] = "launcher v1", ["illusion-of-gaia.Companion.dll"] = "dll v1",
                     ["README.md"] = "old readme", ["mods/preloaded/catalog.toml"] = "catalog v1" }) Put(pair.Key, pair.Value);
        // Every kind of player data.
        Put("UserData/Achievements/illusion-of-gaia/progress.json", "{\"unlocked\":3}");
        Put("UserData/Companion/updates.json", "{\"CheckOnStart\":false}");
        PutBytes("saves/save.srm", Enumerable.Range(0, 8192).Select(i => (byte)i).ToArray());
        Put("saves/states/slot1.state", "state");
        Put("msu1/companion-packs/jud6ment/gaia-1.pcm", "MSU1 track");
        Put("msu1/companion-packs/jud6ment/receipt.json", "{}");
        Put("screenshots/shot-001.png", "png");
        Put("diagnostics/marks.json", "[]");
        Put("logs/run.log", "log");
        var escaped = old.Replace("\\", "\\\\");
        Put("config.ini", $"[Graphics]\r\nWidescreen = 1\r\n[Paths]\r\nMsu = {old}\\msu1\r\n");
        Put("keybinds.ini", "[Keys]\nA = X\n");
        Put("rom.cfg", Path.Combine(old, "Illusion of Gaia (USA).sfc") + "\n");
        PutBytes("gaia-launcher.ico", new byte[] { 0, 0, 1, 0 });
        PutBytes("mods/preloaded/state.toml", Bom.Concat(Encoding.UTF8.GetBytes($"format_version = 1\n[[resource]]\npackage_id = \"iog.enhancements\"\npath = \"{escaped}\\\\msu1\\\\companion-packs\\\\jud6ment\"\n")).ToArray());
        PutBytes("Illusion of Gaia (USA).sfc", new byte[2048]);
        Put("my notes.txt", "player's own file");
        Put("mods/custom/thing.toml", "custom mod");
        var zips = Path.Combine(root, name, "zips"); Directory.CreateDirectory(zips);
        var zip = PackageZip(zips, "0.2.0-beta.22");
        var work = Path.Combine(parent, ".companion-update-test"); Directory.CreateDirectory(work);
        var shortcuts = Path.Combine(root, name, "Desktop"); Directory.CreateDirectory(shortcuts);
        return new(parent, old, zip, ReleaseFor("0.2.0-beta.22", "https://github.com/x/y.zip", null), work, shortcuts);
    }
    private static Dictionary<string, string> Snapshot(string dir) =>
        Directory.EnumerateFiles(dir, "*", SearchOption.AllDirectories).ToDictionary(
            f => Path.GetRelativePath(dir, f), f => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(f))), StringComparer.OrdinalIgnoreCase);
    private static bool SameTree(Dictionary<string, string> a, Dictionary<string, string> b) => a.Count == b.Count && a.All(p => b.TryGetValue(p.Key, out var v) && v == p.Value);

    private static void CarryOver(string root)
    {
        var f = MakeInstall(root, "carry");
        var before = Snapshot(f.Old);
        var result = UpdateService.Install(f.Old, f.Release, f.Zip, f.Work, new() { ShortcutDirectories = new[] { f.Shortcuts } });
        var n = result.NewDirectory;
        Check(n == Path.Combine(f.Parent, "v0.2.0-beta.22"), "sibling folder named v<version>");
        string R(string rel) => File.ReadAllText(Path.Combine(n, rel));
        Check(R("babel-recomp.exe") == "engine v2" && R("README.md") == "new readme" && R("mods/preloaded/catalog.toml") == "catalog v2", "new package files win");
        foreach (var rel in new[] { "UserData/Achievements/illusion-of-gaia/progress.json", "UserData/Companion/updates.json", "saves/save.srm", "saves/states/slot1.state",
                     "screenshots/shot-001.png", "diagnostics/marks.json", "logs/run.log", "keybinds.ini", "gaia-launcher.ico",
                     "Illusion of Gaia (USA).sfc", "my notes.txt", "mods/custom/thing.toml" })
            Check(File.Exists(Path.Combine(n, rel)) && before[rel.Replace('/', '\\')] == Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(Path.Combine(n, rel)))), "carried exactly: " + rel);
        Check(File.Exists(Path.Combine(n, "msu1/companion-packs/jud6ment/gaia-1.pcm")) && !Directory.Exists(Path.Combine(f.Old, "msu1")), "msu1 moved, not copied");
        Check(result.MovedFolders.SequenceEqual(new[] { "msu1" }), "moved list");
        var state = File.ReadAllBytes(Path.Combine(n, "mods/preloaded/state.toml"));
        Check(!state.AsSpan().StartsWith(Bom), "state.toml written without a BOM");
        var stateText = Encoding.UTF8.GetString(state);
        Check(stateText.Contains(n.Replace("\\", "\\\\") + "\\\\msu1") && !stateText.Contains(f.Old.Replace("\\", "\\\\")), "soundtrack path in state.toml points at the new folder");
        Check(R("config.ini").Contains($"Msu = {n}\\msu1\r\n") && R("config.ini").StartsWith("[Graphics]\r\nWidescreen = 1\r\n"), "config.ini carried with paths retargeted and CRLF kept");
        Check(R("rom.cfg") == Path.Combine(n, "Illusion of Gaia (USA).sfc") + "\n", "rom.cfg follows the ROM it pointed at");
        Check(File.Exists(Path.Combine(n, UpdateService.MarkerName)) && File.Exists(Path.Combine(n, UpdateService.ManifestName)), "marker and package manifest written");
        Check(File.ReadAllText(Path.Combine(f.Old, "config.ini")).Contains(f.Old), "old install untouched apart from the moved folder");
        Check(UpdateService.Retarget(Path.Combine(f.Old, "babel-recomp.exe"), f.Old, n) == Path.Combine(n, "babel-recomp.exe")
              && UpdateService.Retarget(Path.Combine(f.Parent, "elsewhere", "rom.sfc"), f.Old, n) == null
              && UpdateService.Retarget(f.Old + "-other\\babel-recomp.exe", f.Old, n) == null, "launcher preference paths retarget only inside the old folder");
        Refused(() => UpdateService.Install(f.Old, f.Release, f.Zip, Path.Combine(f.Parent, ".companion-update-again"), new() { ShortcutDirectories = Array.Empty<string>() }),
            "existing target folder refused", "already exists").Wait();
    }

    private static void Rollback(string root)
    {
        foreach (var step in new[] { "copy:saves/save.srm", "marker", "move:msu1", "moved:msu1", "cancel" }) {
            var f = MakeInstall(root, "rollback-" + step.Replace(':', '-').Replace('/', '-'));
            var before = Snapshot(f.Old);
            using var cancel = new CancellationTokenSource();
            var options = new UpdateService.InstallOptions { ShortcutDirectories = Array.Empty<string>(), Step = s => {
                if (step == "cancel" && s == "marker") cancel.Cancel();
                else if (s == step) throw new IOException("synthetic failure at " + s);
            } };
            try {
                UpdateService.Install(f.Old, f.Release, f.Zip, f.Work, options, null, cancel.Token);
                throw new Exception("rollback test did not fail: " + step);
            } catch (UpdateException error) { Check(step != "cancel" && error.Message.Contains("left exactly as it was"), "failure reported: " + step); }
            catch (OperationCanceledException) { Check(step == "cancel", "cancel reported"); }
            Check(SameTree(before, Snapshot(f.Old)), "old install byte-identical after rollback: " + step);
            Check(!Directory.Exists(Path.Combine(f.Parent, "v0.2.0-beta.22")), "partial new folder removed: " + step);
        }
    }

    private static void Removal(string root)
    {
        // Clean case: everything left is package files or identical copies.
        var f = MakeInstall(root, "remove");
        var n = UpdateService.Install(f.Old, f.Release, f.Zip, f.Work, new() { ShortcutDirectories = Array.Empty<string>() }).NewDirectory;
        UpdateService.DeleteTree(f.Work);
        var done = UpdateService.FinishPending(n, TimeSpan.Zero);
        Check(done.State == "removed" && !Directory.Exists(f.Old), "old folder removed when it holds nothing of the player's: " + done.Message);
        Check(!Directory.EnumerateDirectories(f.Parent).Any(d => Path.GetFileName(d).StartsWith(".companion-old-")), "no hidden leftover");
        Check(!File.Exists(Path.Combine(n, UpdateService.MarkerName)) && UpdateService.FinishPending(n).State == "none", "marker cleared; later starts do nothing");
        Check(File.Exists(Path.Combine(n, "saves/save.srm")) && File.Exists(Path.Combine(n, "msu1/companion-packs/jud6ment/gaia-1.pcm")), "player data safe in the new folder");

        // A file that appeared later, or a save that changed after the copy, keeps the old folder.
        foreach (var change in new[] { "new file", "changed save" }) {
            var g = MakeInstall(root, "keep-" + change.Replace(' ', '-'));
            var m = UpdateService.Install(g.Old, g.Release, g.Zip, g.Work, new() { ShortcutDirectories = Array.Empty<string>() }).NewDirectory;
            if (change == "new file") File.WriteAllText(Path.Combine(g.Old, "saves", "later.srm"), "written after the copy");
            else File.WriteAllText(Path.Combine(g.Old, "saves", "save.srm"), "different");
            var kept = UpdateService.FinishPending(m, TimeSpan.Zero);
            Check(kept.State == "kept" && Directory.Exists(g.Old) && kept.Kept.Count == 1 && kept.Kept[0].StartsWith("saves/"), "old folder kept: " + change);
            Check(kept.Message.Contains(g.Old), "player told where: " + change);
            Check(!File.Exists(Path.Combine(m, UpdateService.MarkerName)), "kept folder reported once: " + change);
        }

        // A marker that names a folder outside the install's parent is never acted on.
        var h = MakeInstall(root, "outside");
        var mark = Path.Combine(h.Parent, "v9", UpdateService.MarkerName); Directory.CreateDirectory(Path.GetDirectoryName(mark)!);
        var victim = Path.Combine(root, "outside", "not-ours"); Directory.CreateDirectory(victim); File.WriteAllText(Path.Combine(victim, "keep.txt"), "x");
        File.WriteAllText(mark, JsonSerializer.Serialize(new { From = victim, FromVersion = "", Version = "9.0.0", LauncherProcess = 0, Carried = Array.Empty<string>() }));
        Check(UpdateService.FinishPending(Path.GetDirectoryName(mark)!, TimeSpan.Zero).State == "refused" && File.Exists(Path.Combine(victim, "keep.txt")), "outside folder refused");
    }

    private static void ManifestCarry(string root)
    {
        // An install made by a previous update knows its own package: files it shipped that the
        // new build dropped are not mistaken for player data.
        var f = MakeInstall(root, "manifest", new() { ["babel-recomp.exe"] = "engine v1", ["illusion-of-gaia.Companion.exe"] = "launcher v1",
            ["illusion-of-gaia.Companion.dll"] = "dll v1", ["README.md"] = "old readme", ["dropped.dll"] = "old package only" });
        File.WriteAllText(Path.Combine(f.Old, UpdateService.ManifestName), JsonSerializer.Serialize(new { Version = "0.2.0-beta.21",
            Files = new[] { "babel-recomp.exe", "illusion-of-gaia.Companion.exe", "illusion-of-gaia.Companion.dll", "README.md", "dropped.dll" } }));
        var n = UpdateService.Install(f.Old, f.Release, f.Zip, f.Work, new() { ShortcutDirectories = Array.Empty<string>() }).NewDirectory;
        Check(!File.Exists(Path.Combine(n, "dropped.dll")) && File.Exists(Path.Combine(n, "my notes.txt")), "old package file not carried; player file carried");
        UpdateService.DeleteTree(f.Work);
        Check(UpdateService.FinishPending(n, TimeSpan.Zero).State == "removed", "old package-only file does not block removal");

        // Without a manifest an unknown file is treated as the player's and carried.
        var g = MakeInstall(root, "no-manifest", new() { ["babel-recomp.exe"] = "e", ["illusion-of-gaia.Companion.exe"] = "l", ["illusion-of-gaia.Companion.dll"] = "d", ["dropped.dll"] = "?" });
        var m = UpdateService.Install(g.Old, g.Release, g.Zip, g.Work, new() { ShortcutDirectories = Array.Empty<string>() }).NewDirectory;
        Check(File.Exists(Path.Combine(m, "dropped.dll")), "unknown file carried when the old package list is not known");
    }

    private static void Shortcuts(string root)
    {
        if (!OperatingSystem.IsWindows()) return;
        var f = MakeInstall(root, "shortcuts");
        var link = Path.Combine(f.Shortcuts, "Illusion of Gaia.lnk");
        var other = Path.Combine(f.Shortcuts, "Something else.lnk");
        var launcher = Path.Combine(f.Old, UpdateService.LauncherName);
        UpdateService.Shortcut.Create(link, launcher, f.Old, Path.Combine(f.Old, "gaia-launcher.ico"));
        UpdateService.Shortcut.Create(other, Path.Combine(f.Parent, "unrelated.exe"), f.Parent, "");
        var otherBytes = File.ReadAllBytes(other);
        var result = UpdateService.Install(f.Old, f.Release, f.Zip, f.Work, new() { ShortcutDirectories = new[] { f.Shortcuts } });
        var (target, work, icon) = UpdateService.Shortcut.Read(link);
        Check(result.Shortcuts.Count == 1 && result.Shortcuts[0] == link, "only the game's shortcut changed");
        Check(target == Path.Combine(result.NewDirectory, UpdateService.LauncherName), "shortcut target retargeted: " + target);
        Check(work == result.NewDirectory, "shortcut start-in folder retargeted: " + work);
        Check(icon == Path.Combine(result.NewDirectory, "gaia-launcher.ico"), "shortcut icon retargeted: " + icon);
        Check(File.ReadAllBytes(other).SequenceEqual(otherBytes), "unrelated shortcut untouched");
    }

    // ---------- network (loopback only) ----------

    private sealed class LocalServer : IDisposable
    {
        private readonly TcpListener listener = new(IPAddress.Loopback, 0);
        private readonly Dictionary<string, (int Status, string[] Headers, byte[] Body)> routes = new();
        private readonly CancellationTokenSource stop = new();
        public string Base { get; }
        public LocalServer() { listener.Start(); Base = $"http://127.0.0.1:{((IPEndPoint)listener.LocalEndpoint).Port}"; _ = Loop(); }
        public void Map(string path, byte[] body, int status = 200, params string[] headers) => routes[path] = (status, headers, body);
        private async Task Loop()
        {
            while (!stop.IsCancellationRequested) {
                TcpClient client;
                try { client = await listener.AcceptTcpClientAsync(stop.Token); } catch (Exception) { return; }
                _ = Task.Run(async () => {
                    using (client) {
                        var stream = client.GetStream(); var reader = new StreamReader(stream, Encoding.ASCII);
                        var line = await reader.ReadLineAsync() ?? ""; string? header;
                        while (!string.IsNullOrEmpty(header = await reader.ReadLineAsync())) { }
                        var path = line.Split(' ').ElementAtOrDefault(1) ?? "/";
                        var (status, headers, body) = routes.TryGetValue(path, out var r) ? r : (404, Array.Empty<string>(), Encoding.ASCII.GetBytes("missing"));
                        var head = $"HTTP/1.1 {status} {(status == 200 ? "OK" : "Error")}\r\nContent-Length: {body.Length}\r\nConnection: close\r\n" + string.Concat(headers.Select(h => h + "\r\n")) + "\r\n";
                        await stream.WriteAsync(Encoding.ASCII.GetBytes(head)); await stream.WriteAsync(body);
                    }
                });
            }
        }
        public void Dispose() { stop.Cancel(); listener.Stop(); }
    }

    private static async Task Network(string root)
    {
        using var server = new LocalServer();
        Environment.SetEnvironmentVariable(UpdateService.FeedVariable, server.Base + "/feed");
        var f = MakeInstall(root, "network");
        File.WriteAllBytes(Path.Combine(f.Old, "babel-recomp.exe"), Encoding.ASCII.GetBytes("MZ....illusionofgaiausa-usa\00.2.0-beta.21\0saves/save.srm\0"));
        Check(UpdateService.EngineVersion(Path.Combine(f.Old, "babel-recomp.exe"))?.ToString() == "0.2.0-beta.21", "running version read from the engine");
        var zipBytes = File.ReadAllBytes(f.Zip); var sha = Convert.ToHexString(SHA256.HashData(zipBytes)).ToLowerInvariant();
        server.Map("/dl/good.zip", zipBytes);
        server.Map("/dl/good.zip.sha256", Encoding.ASCII.GetBytes($"{sha} *{Zip("0.2.0-beta.22")}\n"));
        server.Map("/dl/bad.zip.sha256", Encoding.ASCII.GetBytes($"{new string('0', 64)} *{Zip("0.2.0-beta.22")}\n"));
        server.Map("/feed", Encoding.UTF8.GetBytes(Feed(
            Release("v0.2.0-beta.22", body: "Fixes.", assets: new[] { Asset(Zip("0.2.0-beta.22"), server.Base + "/dl/good.zip", zipBytes.Length, "sha256:" + sha),
                                                                     Asset(Zip("0.2.0-beta.22") + ".sha256", server.Base + "/dl/good.zip.sha256") }),
            Release("v0.2.0-beta.21", assets: Asset(Zip("0.2.0-beta.21"), server.Base + "/dl/old.zip", 1, "sha256:" + sha)))));
        var check = await UpdateService.CheckAsync(f.Old);
        Check(check.IsNewer && check.Current?.ToString() == "0.2.0-beta.21" && check.Latest!.Version.ToString() == "0.2.0-beta.22", "check through the feed");

        // Integrity: a wrong digest, a wrong .sha256, or no checksum at all is refused, and nothing is left behind.
        var dl = Path.Combine(f.Work, "x.zip");
        await Refused(() => UpdateService.DownloadAsync(ReleaseFor("0.2.0-beta.22", server.Base + "/dl/good.zip", new string('b', 64)), dl), "digest mismatch refused", "does not match");
        Check(!File.Exists(dl) && !File.Exists(dl + ".partial"), "mismatched download deleted");
        await Refused(() => UpdateService.DownloadAsync(ReleaseFor("0.2.0-beta.22", server.Base + "/dl/good.zip", null, server.Base + "/dl/bad.zip.sha256"), dl), ".sha256 mismatch refused", "does not match");
        await Refused(() => UpdateService.DownloadAsync(ReleaseFor("0.2.0-beta.22", server.Base + "/dl/good.zip", sha, server.Base + "/dl/bad.zip.sha256"), dl), "digest and .sha256 disagree", "disagree");
        await Refused(() => UpdateService.DownloadAsync(ReleaseFor("0.2.0-beta.22", server.Base + "/dl/good.zip", null), dl), "unverifiable download refused", "cannot be verified");
        Check(!File.Exists(dl), "nothing kept from refused downloads");
        Check(await UpdateService.DownloadAsync(ReleaseFor("0.2.0-beta.22", server.Base + "/dl/good.zip", sha, server.Base + "/dl/good.zip.sha256"), dl) == sha && File.Exists(dl), "matching download accepted");

        // Rate limits and being offline give a clear message.
        server.Map("/limited", Encoding.ASCII.GetBytes("{}"), 403, "X-RateLimit-Remaining: 0", "X-RateLimit-Reset: 1900000000");
        Environment.SetEnvironmentVariable(UpdateService.FeedVariable, server.Base + "/limited");
        await Refused(() => UpdateService.CheckAsync(f.Old), "rate limit explained", "limiting update checks");
        var closed = new TcpListener(IPAddress.Loopback, 0); closed.Start(); var port = ((IPEndPoint)closed.LocalEndpoint).Port; closed.Stop();
        Environment.SetEnvironmentVariable(UpdateService.FeedVariable, $"http://127.0.0.1:{port}/feed");
        await Refused(() => UpdateService.CheckAsync(f.Old), "offline explained", "internet connection");
        var feedFile = Path.Combine(root, "feed.json"); File.WriteAllText(feedFile, "[]");
        Environment.SetEnvironmentVariable(UpdateService.FeedVariable, feedFile);
        Check((await UpdateService.CheckAsync(f.Old)).Latest == null, "file feed for tests");

        // Whole flow: lock, work folder beside the install, cleaned up afterwards.
        UpdateService.DeleteTree(f.Work);
        var progress = new List<string>();
        var installed = await UpdateService.DownloadAndInstallAsync(f.Old, check.Latest!, new Progress<UpdateProgress>(p => { lock (progress) progress.Add(p.Phase); }),
            new() { ShortcutDirectories = Array.Empty<string>() });
        Check(Directory.Exists(installed.NewDirectory) && File.ReadAllText(Path.Combine(installed.NewDirectory, "README.md")) == "new readme", "download and install");
        Check(!Directory.EnumerateFileSystemEntries(f.Parent).Any(e => Path.GetFileName(e).StartsWith(".companion-update")), "work folder and lock removed");
        Check(Directory.EnumerateFileSystemEntries(f.Parent).Select(Path.GetFileName).OrderBy(x => x).SequenceEqual(new[] { "v0.2.0-beta.21", "v0.2.0-beta.22" }), "nothing else written beside the install");
    }
}
