// Scene Picker: trailer recording scenes for the Illusion of Gaia Companion.
// Pick a scene, press Play: a fresh private session folder is made from the
// Showcase runtime (a copy of the installed game, no player data), the scene's
// checkpoint and the scene's own settings, and the game starts there. The
// owner's install, saves and achievements are never written.
//
//   Scene Picker.exe                      the picker
//   Scene Picker.exe --self-check         every baseline, runtime file, the ROM and the
//                                         soundtrack present; writes picker-self-check.json
//   Scene Picker.exe --build-runtime      copy the game files (no player data) from the
//                                         newest install into Runtime/
//   Scene Picker.exe --stage <id> <json>  make a session exactly as Play does, but do not
//                                         start it; write {exe, args, cwd} to <json>
//   Scene Picker.exe --smoke <png>        draw the window into a picture and exit
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace ScenePicker;

sealed record Scene(string Id, string Title, string Slug, string Kind, string Shot, string Caption, string Settings,
                    string? Baseline, string? Picture, Dictionary<string, JsonElement>? Mods, List<string>? Slots, bool Maps = false) {
    public override string ToString() => $"{Id}   {Title}";
}

static class Program {
    [STAThread]
    static int Main(string[] args) {
        ApplicationConfiguration.Initialize();
        try {
            if (args.Length >= 1 && args[0] == "--self-check") return Paths.SelfCheck();
            if (args.Length >= 1 && args[0] == "--build-runtime") { Paths.BuildRuntime(); return 0; }
            if (args.Length >= 3 && args[0] == "--stage") {
                var scene = Scenes.Read().First(s => s.Id == args[1]);
                var start = Session.Create(scene, args.Contains("--fullscreen"));
                File.WriteAllText(args[2], JsonSerializer.Serialize(new { exe = start.FileName, args = start.ArgumentList, cwd = start.WorkingDirectory },
                    new JsonSerializerOptions { WriteIndented = true }));
                return 0;
            }
            if (args.Length >= 2 && args[0] == "--smoke") { Picker.Smoke(args[1]); return 0; }
        } catch (Exception e) {
            File.WriteAllText(Path.Combine(Paths.Root, "picker-error.txt"), e.ToString());
            return 1;
        }
        Application.Run(new Picker());
        return 0;
    }
}

static class Scenes {
    static readonly JsonSerializerOptions Options = new() { PropertyNameCaseInsensitive = true, ReadCommentHandling = JsonCommentHandling.Skip };
    public static List<Scene> Read() => JsonSerializer.Deserialize<List<Scene>>(File.ReadAllText(Path.Combine(Paths.Root, "scenes.json")), Options)!;
}

static class Paths {
    public static readonly string Root = Path.TrimEndingDirectorySeparator(AppContext.BaseDirectory);
    public static readonly string Project = Directory.GetParent(Root)!.FullName;
    public static string Runtime => Path.Combine(Root, "Runtime");
    public static string Baselines => Path.Combine(Root, "Baselines");
    public static string Sessions => Path.Combine(Root, "Sessions");
    public static string Recordings => Path.Combine(Root, "Recordings");

    /// The newest installed build: %USERPROFILE%\Games\Illusion of Gaia Companion\v<version>.
    /// Only read: its launcher for the launcher scene and its imported soundtrack.
    public static string? Install() {
        var parent = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Games", "Illusion of Gaia Companion");
        if (!Directory.Exists(parent)) return null;
        return Directory.GetDirectories(parent, "v*")
            .Where(d => File.Exists(Path.Combine(d, "babel-recomp.exe")))
            .OrderByDescending(d => File.GetLastWriteTimeUtc(Path.Combine(d, "babel-recomp.exe"))).FirstOrDefault();
    }

    /// The USA ROM: beside the project, else the one the install remembers.
    public static string? Rom() {
        var local = Path.Combine(Project, "Illusion of Gaia (USA).sfc");
        if (File.Exists(local)) return local;
        var install = Install();
        var cfg = install is null ? null : Path.Combine(install, "rom.cfg");
        var remembered = cfg is not null && File.Exists(cfg) ? File.ReadAllText(cfg).Trim() : null;
        return remembered is not null && File.Exists(remembered) ? remembered : null;
    }

    /// The imported MSU-1 pack in the install (msu1\companion-packs\<id>, ~700 MB):
    /// never copied, the session's state.toml points at it.
    public static string? MusicPack() {
        var install = Install();
        if (install is null) return null;
        var packs = Path.Combine(install, "msu1", "companion-packs");
        if (!Directory.Exists(packs)) return null;
        return Directory.GetDirectories(packs).Where(d => Directory.EnumerateFiles(d, "*.pcm").Any())
            .OrderByDescending(Directory.GetLastWriteTimeUtc).FirstOrDefault();
    }

    // What the runtime takes from an install: the game, its art, text and mod packages,
    // and the owner's settings as templates. Never saves, achievements, soundtrack,
    // screenshots, logs or diagnostics.
    static readonly string[] RuntimeFiles = { "babel-recomp.exe", "config.ini", "keybinds.ini" };
    static readonly string[] RuntimeDirs = { "assets", "i18n", Path.Combine("mods", "preloaded", "packages") };
    public static readonly string[] Templates = { "config.ini", "keybinds.ini", Path.Combine("mods", "preloaded", "state.toml") };

    public static void BuildRuntime() {
        var install = Install() ?? throw new DirectoryNotFoundException("No installed build found.");
        if (Directory.Exists(Runtime)) Directory.Delete(Runtime, true);
        Directory.CreateDirectory(Runtime);
        foreach (var f in RuntimeFiles) File.Copy(Path.Combine(install, f), Path.Combine(Runtime, f));
        var state = Path.Combine("mods", "preloaded", "state.toml");
        Directory.CreateDirectory(Path.GetDirectoryName(Path.Combine(Runtime, state))!);
        File.Copy(Path.Combine(install, state), Path.Combine(Runtime, state));
        foreach (var d in RuntimeDirs) CopyTree(Path.Combine(install, d), Path.Combine(Runtime, d));
        File.WriteAllText(Path.Combine(Runtime, "runtime-source.txt"),
            $"Copied {DateTime.Now:yyyy-MM-dd HH:mm} from {install}\r\nbabel-recomp.exe {new FileInfo(Path.Combine(install, "babel-recomp.exe")).Length} bytes\r\n");
    }

    static void CopyTree(string from, string to) {
        Directory.CreateDirectory(to);
        foreach (var f in Directory.GetFiles(from)) File.Copy(f, Path.Combine(to, Path.GetFileName(f)));
        foreach (var d in Directory.GetDirectories(from)) CopyTree(d, Path.Combine(to, Path.GetFileName(d)));
    }

    public static int SelfCheck() {
        var problems = new List<string>();
        var scenes = Scenes.Read();
        var report = new List<object>();
        foreach (var s in scenes) {
            var need = new List<string>();
            if (s.Kind == "game") {
                if (s.Baseline is null) problems.Add($"{s.Id}: no baseline");
                else need.Add(Path.Combine(Baselines, s.Baseline, "save0.sav"));
                foreach (var slot in s.Slots ?? new()) need.Add(Path.Combine(Baselines, slot, "save0.sav"));
                if (s.Maps && s.Baseline is not null && !Directory.Exists(Path.Combine(Baselines, s.Baseline, "maps"))) problems.Add($"{s.Id}: no maps folder");
                if (s.Picture is not (null or "wide" or "classic" or "original")) problems.Add($"{s.Id}: unknown picture {s.Picture}");
                foreach (var key in (s.Mods ?? new()).Keys)
                    if (key.Split('/').Length is not (2 or 3)) problems.Add($"{s.Id}: bad mod key {key}");
            } else if (s.Kind != "launcher") problems.Add($"{s.Id}: unknown kind {s.Kind}");
            foreach (var n in need) if (!File.Exists(n)) problems.Add($"{s.Id}: missing {n}");
            report.Add(new { s.Id, s.Title, s.Kind, s.Baseline, Picture = s.Picture ?? "wide", Video = $"{s.Id}_{s.Slug}_Take01.mp4", Files = need.Count });
        }
        if (scenes.Select(s => s.Id).Distinct().Count() != scenes.Count) problems.Add("duplicate scene ids");
        foreach (var f in new[] { "babel-recomp.exe", "config.ini", "keybinds.ini", Path.Combine("mods", "preloaded", "state.toml"),
                                  Path.Combine("i18n", "gaialabs-mods.bin"), Path.Combine("i18n", "gaialabs-world-map.bin") })
            if (!File.Exists(Path.Combine(Runtime, f))) problems.Add("runtime: missing " + f);
        foreach (var d in RuntimeDirs) if (!Directory.Exists(Path.Combine(Runtime, d))) problems.Add("runtime: missing " + d);
        var install = Install();
        if (install is null || !File.Exists(Path.Combine(install, "illusion-of-gaia.Companion.exe"))) problems.Add("install: launcher not found");
        if (Rom() is null) problems.Add("ROM not found");
        var music = MusicPack();
        if (music is null) problems.Add("MSU-1 pack not found (music would be the original SNES audio)");
        var result = new { ok = problems.Count == 0, problems, install, rom = Rom(), music, scenes = report };
        File.WriteAllText(Path.Combine(Root, "picker-self-check.json"), JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true }));
        return problems.Count == 0 ? 0 : 2;
    }
}

/// One private game folder per Play click.
static class Session {
    const int Keep = 5;

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool CreateHardLink(string newFile, string existingFile, IntPtr security);

    // The settings every recording session starts from; a scene's own "Mods" go on top.
    // Cheats off, Wide view, HD scaling (smooth) and HD Mode 7 as the owner has them,
    // MSU-1 on, the owner's conveniences, the optional-by-default GaiaLabs art off.
    static readonly Dictionary<string, object> BaseMods = new() {
        ["iog.cheats/infinite_hp"] = false, ["iog.cheats/dp"] = false, ["iog.cheats/stats"] = false, ["iog.cheats/room_rewards"] = false,
        ["iog.apocalypse/apocalypse_gaia"] = false, ["iog.randomizer/randomizer"] = false, ["iog.enhancements/ngplus"] = false,
        ["snesrecomp.diagnostics.coverage/capture"] = false,
        ["iog.graphics/wide_view"] = true, ["iog.graphics/hd"] = true, ["iog.graphics/hd/filter"] = "smooth", ["iog.graphics/edge_hud"] = true,
        ["iog.enhancements/msu1"] = true, ["iog.enhancements/world_map"] = true,
        ["iog.enhancements/map_controls"] = true, ["iog.enhancements/map_controls/radar"] = "off", ["iog.enhancements/map_controls/prompts"] = "snes",
        ["iog.enhancements/text_speed"] = true, ["iog.enhancements/text_speed/speed"] = "normal",
        ["iog.enhancements/hold_advance"] = true, ["iog.enhancements/hold_advance/speed"] = "fast",
        ["iog.enhancements/run"] = true, ["iog.enhancements/run/style"] = "hold",
        ["iog.gaialabs/minimal_hud"] = false, ["iog.gaialabs/jp_mines"] = false, ["iog.gaialabs/jp_viper"] = false, ["iog.gaialabs/no_shira"] = false,
    };

    public static ProcessStartInfo Create(Scene s, bool fullscreen) {
        if (s.Kind != "game" || s.Baseline is null) throw new InvalidOperationException("Not a game scene.");
        if (!Regex.IsMatch(s.Id, "^[0-9]{2}$") || !Regex.IsMatch(s.Baseline, "^[a-z0-9]+$")) throw new InvalidDataException("Invalid scene id or baseline.");
        var rom = Paths.Rom() ?? throw new FileNotFoundException("The Illusion of Gaia (USA) ROM was not found.");
        if (!File.Exists(Path.Combine(Paths.Runtime, "babel-recomp.exe"))) throw new FileNotFoundException("Runtime is missing: run Scene Picker.exe --build-runtime.");
        Directory.CreateDirectory(Paths.Sessions);
        Prune(Keep - 1);
        var dir = Path.Combine(Paths.Sessions, $"{s.Id}-{DateTime.Now:yyyyMMdd-HHmmss}-{Guid.NewGuid().ToString("N")[..6]}");
        Directory.CreateDirectory(dir);
        LinkRuntime(Paths.Runtime, dir, "");
        // saves: the checkpoint is slot 1 (save0.sav), loaded at start by Autosave;
        // extra slots for the save-state scene; the area maps for the map scene
        var saves = Path.Combine(dir, "saves");
        Directory.CreateDirectory(saves);
        var baseline = Path.Combine(Paths.Baselines, s.Baseline);
        CopyState(Path.Combine(baseline, "save0.sav"), Path.Combine(saves, "save0.sav"));
        var slot = 1;
        foreach (var name in s.Slots ?? new()) CopyState(Path.Combine(Paths.Baselines, name, "save0.sav"), Path.Combine(saves, $"save{slot++}.sav"));
        if (s.Maps) CopyDir(Path.Combine(baseline, "maps"), Path.Combine(saves, "maps"));
        WriteConfig(dir, s, fullscreen);
        WriteState(dir, s);
        var start = new ProcessStartInfo(Path.Combine(dir, "babel-recomp.exe")) { UseShellExecute = false, WorkingDirectory = dir };
        foreach (var a in new[] { "--no-launcher", "--rom", rom, "--config", Path.Combine(dir, "config.ini") }) start.ArgumentList.Add(a);
        // nothing from a developer shell reaches the session
        foreach (var key in start.Environment.Keys.ToList())
            if (key.StartsWith("IOG_", StringComparison.OrdinalIgnoreCase) || key.StartsWith("SNESRECOMP_", StringComparison.OrdinalIgnoreCase) ||
                key.StartsWith("SDL_", StringComparison.OrdinalIgnoreCase) || key.StartsWith("SNES_", StringComparison.OrdinalIgnoreCase))
                start.Environment.Remove(key);
        File.WriteAllText(Path.Combine(dir, "scene.txt"), $"{s.Id} {s.Title}\r\nbaseline {s.Baseline}\r\n{(fullscreen ? "fullscreen" : "windowed")}\r\n{s.Settings}\r\n");
        return start;
    }

    static void CopyState(string from, string to) {
        File.Copy(from, to);
        if (File.Exists(from + ".thumb")) File.Copy(from + ".thumb", to + ".thumb");
    }

    static void CopyDir(string from, string to) {
        Directory.CreateDirectory(to);
        foreach (var f in Directory.GetFiles(from)) File.Copy(f, Path.Combine(to, Path.GetFileName(f)));
    }

    /// Hard links to the runtime's read-only files (same volume: no extra disk),
    /// a copy where a link cannot be made. The settings files are written fresh.
    static void LinkRuntime(string from, string to, string rel) {
        Directory.CreateDirectory(to);
        foreach (var f in Directory.GetFiles(from)) {
            var r = Path.Combine(rel, Path.GetFileName(f));
            if (Paths.Templates.Contains(r, StringComparer.OrdinalIgnoreCase) || r == "runtime-source.txt") continue;
            var dest = Path.Combine(to, Path.GetFileName(f));
            if (!CreateHardLink(dest, f, IntPtr.Zero)) File.Copy(f, dest);
        }
        foreach (var d in Directory.GetDirectories(from)) LinkRuntime(d, Path.Combine(to, Path.GetFileName(d)), Path.Combine(rel, Path.GetFileName(d)));
    }

    /// Keep the newest sessions; a folder still in use (a running game) is skipped.
    public static void Prune(int keep) {
        if (!Directory.Exists(Paths.Sessions)) return;
        var root = Path.GetFullPath(Paths.Sessions) + Path.DirectorySeparatorChar;
        foreach (var d in new DirectoryInfo(Paths.Sessions).GetDirectories().OrderByDescending(d => d.CreationTimeUtc).Skip(keep)) {
            if (!Path.GetFullPath(d.FullName).StartsWith(root, StringComparison.OrdinalIgnoreCase) || d.Attributes.HasFlag(FileAttributes.ReparsePoint)) continue;
            try { d.Delete(true); } catch (IOException) { } catch (UnauthorizedAccessException) { }
        }
    }

    static void WriteConfig(string dir, Scene s, bool fullscreen) {
        var text = File.ReadAllText(Path.Combine(Paths.Runtime, "config.ini"));
        var picture = s.Picture ?? "wide";
        var set = new (string Section, string Key, string Value)[] {
            ("General", "Autosave", "1"),            // loads slot 1 (save0.sav, the checkpoint) at start; no --script, so achievements stay live
            ("General", "SkipLauncher", "1"),
            ("General", "RunAhead", "0"),
            ("Graphics", "Fullscreen", fullscreen ? "1" : "0"),   // 1 = desktop fullscreen (the 1080p display)
            ("Graphics", "WindowSize", fullscreen ? "Auto" : "1600x900"),
            ("Graphics", "Widescreen", picture == "classic" ? "1" : "0"),
            ("Graphics", "Mode7Enabled", "1"),       // HD Mode 7, as in the owner's install
            ("Graphics", "VSync", "1"),
            ("Sound", "EnableAudio", "1"),
            ("Sound", "Volume", "100"),
            // F9 and F10 belong to OBS: load/save state slots 9 and 10 are unbound
            ("KeyMap", "Load", "F1,F2,F3,F4,F5,F6,F7,F8,None,None"),
            ("KeyMap", "Save", "Shift+F1,Shift+F2,Shift+F3,Shift+F4,Shift+F5,Shift+F6,Shift+F7,Shift+F8,None,None"),
        };
        foreach (var (section, key, value) in set) text = Ini.Set(text, section, key, value);
        File.WriteAllText(Path.Combine(dir, "config.ini"), text, new UTF8Encoding(false));
        File.Copy(Path.Combine(Paths.Runtime, "keybinds.ini"), Path.Combine(dir, "keybinds.ini"));
    }

    static void WriteState(string dir, Scene s) {
        var state = Toml.Parse(File.ReadAllText(Path.Combine(Paths.Runtime, "mods", "preloaded", "state.toml")));
        foreach (var (k, v) in BaseMods) state.Set(k, v);
        var picture = s.Picture ?? "wide";
        state.Set("iog.graphics/wide_view", picture == "wide");
        foreach (var (k, v) in s.Mods ?? new()) state.Set(k, v.ValueKind switch {
            JsonValueKind.True => true, JsonValueKind.False => false,
            JsonValueKind.Number => (object)v.GetInt32(), _ => v.GetString()! });
        state.Resources.Clear();
        var music = Paths.MusicPack();
        if (music is not null && state.Enabled("iog.enhancements/msu1"))
            state.Resources.Add(("iog.enhancements", "msu1", "pack", music));
        var path = Path.Combine(dir, "mods", "preloaded", "state.toml");
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, state.Write(), new UTF8Encoding(false));
    }
}

static class Ini {
    /// Set Key = Value in [Section], replacing the line or adding it after the header.
    public static string Set(string text, string section, string key, string value) {
        var nl = text.Contains("\r\n") ? "\r\n" : "\n";
        var lines = text.Split(nl).ToList();
        int start = lines.FindIndex(l => l.Trim().Equals($"[{section}]", StringComparison.OrdinalIgnoreCase));
        if (start < 0) { lines.Add($"[{section}]"); lines.Add($"{key} = {value}"); return string.Join(nl, lines); }
        int end = lines.FindIndex(start + 1, l => l.TrimStart().StartsWith("["));
        if (end < 0) end = lines.Count;
        for (int i = start + 1; i < end; i++) {
            var t = lines[i].TrimStart();
            if (t.StartsWith("#")) continue;
            var eq = t.IndexOf('=');
            if (eq > 0 && t[..eq].Trim().Equals(key, StringComparison.OrdinalIgnoreCase)) { lines[i] = $"{key} = {value}"; return string.Join(nl, lines); }
        }
        lines.Insert(start + 1, $"{key} = {value}");
        return string.Join(nl, lines);
    }
}

/// The mod selection file (mods/preloaded/state.toml): packages, features with
/// their option values, and resources. Read from the runtime's template and
/// written whole for each session.
sealed class Toml {
    public readonly List<string> Head = new();
    public readonly List<(string Id, string Version)> Packages = new();
    public readonly List<(string Package, string Id, bool Enabled, List<(string Key, string Value)> Values)> Features = new();
    public readonly List<(string Package, string Feature, string Id, string Path)> Resources = new();

    static string Unquote(string v) => v.Length >= 2 && v[0] == '"' ? JsonSerializer.Deserialize<string>(v)! : v;
    static string Quote(string v) => JsonSerializer.Serialize(v, new JsonSerializerOptions { Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping });

    public static Toml Parse(string text) {
        var t = new Toml();
        string? block = null; Dictionary<string, string> cur = new(); List<(string, string)> values = new();
        void Flush() {
            if (block == "[[package]]") t.Packages.Add((Unquote(cur["id"]), Unquote(cur["version"])));
            else if (block == "[[feature]]") t.Features.Add((Unquote(cur["package_id"]), Unquote(cur["id"]), cur.GetValueOrDefault("enabled") == "true", values));
            else if (block == "[[resource]]") t.Resources.Add((Unquote(cur["package_id"]), Unquote(cur["feature_id"]), Unquote(cur["id"]), Unquote(cur["path"])));
            cur = new(); values = new();
        }
        bool inValues = false;
        foreach (var raw in text.Replace("\r\n", "\n").Split('\n')) {
            var line = raw.Trim();
            if (line.Length == 0 || line.StartsWith("#")) continue;
            if (line == "[feature.values]") { inValues = true; continue; }
            if (line.StartsWith("[[")) { Flush(); block = line; inValues = false; continue; }
            var eq = line.IndexOf('=');
            if (eq < 0) continue;
            var (k, v) = (line[..eq].Trim(), line[(eq + 1)..].Trim());
            if (block is null) t.Head.Add(line);
            else if (inValues) values.Add((k, v));
            else cur[k] = v;
        }
        Flush();
        return t;
    }

    int Find(string pkg, string id) => Features.FindIndex(f => f.Package == pkg && f.Id == id);

    public bool Enabled(string key) { var p = key.Split('/'); var i = Find(p[0], p[1]); return i >= 0 && Features[i].Enabled; }

    /// "package/feature" = bool sets enabled; "package/feature/option" = value sets an option.
    public void Set(string key, object value) {
        var p = key.Split('/');
        var i = Find(p[0], p[1]);
        if (i < 0) {
            if (!Packages.Any(x => x.Id == p[0])) Packages.Add((p[0], "1.0.0"));
            Features.Add((p[0], p[1], p.Length == 2 ? (bool)value : true, new()));
            i = Features.Count - 1;
        }
        var f = Features[i];
        if (p.Length == 2) { Features[i] = (f.Package, f.Id, (bool)value, f.Values); return; }
        var text = value switch { bool b => b ? "true" : "false", int n => n.ToString(), _ => Quote(value.ToString()!) };
        var j = f.Values.FindIndex(v => v.Key == p[2]);
        if (j >= 0) f.Values[j] = (p[2], text); else f.Values.Add((p[2], text));
    }

    public string Write() {
        var sb = new StringBuilder();
        foreach (var h in Head) sb.Append(h).Append('\n');
        foreach (var (id, version) in Packages) sb.Append($"\n[[package]]\nid = {Quote(id)}\nversion = {Quote(version)}\n");
        foreach (var f in Features) {
            sb.Append($"\n[[feature]]\npackage_id = {Quote(f.Package)}\nid = {Quote(f.Id)}\nenabled = {(f.Enabled ? "true" : "false")}\n");
            if (f.Values.Count > 0) { sb.Append("\n[feature.values]\n"); foreach (var (k, v) in f.Values) sb.Append($"{k} = {v}\n"); }
        }
        foreach (var r in Resources)
            sb.Append($"\n[[resource]]\npackage_id = {Quote(r.Package)}\nfeature_id = {Quote(r.Feature)}\nid = {Quote(r.Id)}\npath = {Quote(r.Path)}\n");
        return sb.ToString();
    }
}

sealed class Picker : Form {
    static readonly Color Background = ColorTranslator.FromHtml("#101A23");
    static readonly Color Surface = ColorTranslator.FromHtml("#1B2B37");
    static readonly Color Raised = Color.FromArgb(38, 57, 70);
    static readonly Color Accent = ColorTranslator.FromHtml("#D7B46A");
    static readonly Color TextColor = ColorTranslator.FromHtml("#F2EBDD");
    static readonly Color Muted = ColorTranslator.FromHtml("#A7B5BD");
    static readonly Color Good = Color.FromArgb(158, 219, 179);

    readonly ListBox scenes = new() { Dock = DockStyle.Fill, IntegralHeight = false };
    readonly Label title = new() { AutoSize = true, MaximumSize = new(700, 0) };
    readonly Label shot = new() { AutoSize = true, MaximumSize = new(700, 0) };
    readonly Label caption = new() { AutoSize = true, MaximumSize = new(700, 0) };
    readonly Label settings = new() { AutoSize = true, MaximumSize = new(700, 0) };
    readonly Label filename = new() { AutoSize = true, MaximumSize = new(700, 0) };
    readonly Label status = new() { AutoSize = true, MaximumSize = new(700, 0) };
    readonly NumericUpDown take = new() { Minimum = 1, Maximum = 99, Value = 1, Width = 70 };
    readonly CheckBox fullscreen = new() { Text = "Fullscreen 1080p (otherwise a 1600×900 window)", Checked = false, AutoSize = true };
    Process? game;
    Scene Selected => (Scene)scenes.SelectedItem!;
    string VideoName => $"{Selected.Id}_{Selected.Slug}_Take{take.Value:00}.mp4";

    public Picker() {
        Text = "Illusion of Gaia Companion — Recording Scenes";
        Icon = Icon.ExtractAssociatedIcon(Environment.ProcessPath!);
        ClientSize = new(1180, 800); MinimumSize = new(1100, 760); StartPosition = FormStartPosition.CenterScreen;
        Font = new("Segoe UI", 11); BackColor = Background; ForeColor = TextColor;
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new(24), ColumnCount = 2, RowCount = 2 };
        layout.ColumnStyles.Add(new(SizeType.Absolute, 380)); layout.ColumnStyles.Add(new(SizeType.Percent, 100));
        layout.RowStyles.Add(new(SizeType.Absolute, 65)); layout.RowStyles.Add(new(SizeType.Percent, 100));
        var heading = new Label { Text = "Recording scenes", Font = new("Segoe UI", 25, FontStyle.Bold), AutoSize = true, ForeColor = Accent };
        layout.Controls.Add(heading, 0, 0); layout.SetColumnSpan(heading, 2);
        scenes.BackColor = Surface; scenes.ForeColor = TextColor; scenes.BorderStyle = BorderStyle.FixedSingle;
        scenes.Font = new("Segoe UI", 10.5f); scenes.ItemHeight = 30; scenes.Margin = new(0, 0, 24, 0);
        layout.Controls.Add(scenes, 0, 1);
        var detail = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.TopDown, WrapContents = false, AutoScroll = true };
        title.Font = new("Segoe UI", 18, FontStyle.Bold); title.Margin = new(0, 0, 0, 12); detail.Controls.Add(title);
        detail.Controls.Add(Small("WHAT TO CAPTURE"));
        shot.Margin = new(0, 2, 0, 12); detail.Controls.Add(shot);
        detail.Controls.Add(Small("CAPTION (for the edit)"));
        caption.ForeColor = Good; caption.Margin = new(0, 2, 0, 12); detail.Controls.Add(caption);
        detail.Controls.Add(Small("THIS SESSION'S SETTINGS"));
        settings.ForeColor = Muted; settings.Font = new("Segoe UI", 9.5f); settings.Margin = new(0, 2, 0, 14); detail.Controls.Add(settings);
        filename.ForeColor = Accent; filename.Font = new("Consolas", 12); filename.Margin = new(0, 0, 0, 8); detail.Controls.Add(filename);
        var row = new FlowLayoutPanel { AutoSize = true, WrapContents = false };
        row.Controls.Add(new Label { Text = "Take", AutoSize = true, Margin = new(0, 8, 8, 0) }); row.Controls.Add(take);
        take.BackColor = Surface; take.ForeColor = TextColor;
        row.Controls.Add(Button("Copy video name", () => Clipboard.SetText(VideoName))); detail.Controls.Add(row);
        fullscreen.Margin = new(0, 6, 0, 10); detail.Controls.Add(fullscreen);
        var actions = new FlowLayoutPanel { AutoSize = true, WrapContents = false };
        actions.Controls.Add(Button("Play / reset scene", Launch, true));
        actions.Controls.Add(Button("Close staged game", CloseGame)); detail.Controls.Add(actions);
        var files = new FlowLayoutPanel { AutoSize = true, WrapContents = false };
        files.Controls.Add(Button("Open recordings", () => { Directory.CreateDirectory(Paths.Recordings); Open(Paths.Recordings); }));
        files.Controls.Add(Button("Recording guide", () => Open(Path.Combine(Paths.Root, "RECORDING-GUIDE.md")))); detail.Controls.Add(files);
        detail.Controls.Add(new Label {
            Text = "Arrows: move   X: attack / talk / confirm   Z: cancel   hold A: run\n" +
                   "Enter: area map   Right Shift: items   Esc: settings   Tab: fast forward\n" +
                   "F1: back to the scene's start (asks)   F11: save states   F12: rewind\n" +
                   "P: pause   Alt+Enter: fullscreen   F9 / F10: OBS record / stop (free in the game)",
            AutoSize = true, MaximumSize = new(700, 0), Margin = new(0, 12, 0, 10), Font = new("Segoe UI", 10) });
        status.ForeColor = Good; status.Margin = new(0, 6, 0, 8); detail.Controls.Add(status);
        detail.Controls.Add(new Label {
            Text = "Record manually in OBS. Stop recording before resetting.\nEvery Play starts a private session; your saves, settings and achievements stay untouched.",
            AutoSize = true, MaximumSize = new(700, 0), ForeColor = Muted });
        layout.Controls.Add(detail, 1, 1); Controls.Add(layout);
        scenes.DataSource = Scenes.Read();
        scenes.SelectedIndexChanged += (_, _) => RefreshSelection(); take.ValueChanged += (_, _) => RefreshSelection();
        RefreshSelection(); FormClosing += (_, _) => CloseGame();
    }

    static Label Small(string text) => new() { Text = text, AutoSize = true, ForeColor = Muted, Font = new("Segoe UI", 8.5f, FontStyle.Bold), Margin = new(0, 0, 0, 0) };

    Button Button(string text, Action action, bool primary = false) {
        var b = new Button { Text = text, AutoSize = false, Size = new(200, 44), Margin = new(0, 4, 10, 8), FlatStyle = FlatStyle.Flat,
            BackColor = primary ? Accent : Raised, ForeColor = primary ? Background : TextColor };
        b.FlatAppearance.BorderColor = primary ? Accent : Color.FromArgb(64, 81, 92);
        b.FlatAppearance.MouseOverBackColor = primary ? Color.FromArgb(227, 194, 121) : Surface;
        b.Click += (_, _) => { try { action(); } catch (Exception e) { MessageBox.Show(this, e.Message, "Scene Picker", MessageBoxButtons.OK, MessageBoxIcon.Error); } };
        return b;
    }

    static void Open(string path) => Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });

    void RefreshSelection() {
        if (scenes.SelectedItem is not Scene s) return;
        title.Text = s.Title; shot.Text = s.Shot; caption.Text = s.Caption; settings.Text = s.Settings; filename.Text = VideoName;
        fullscreen.Enabled = s.Kind == "game";
    }

    void CloseGame() {
        if (game is null) return;
        try {
            if (!game.HasExited) { game.CloseMainWindow(); if (!game.WaitForExit(3000)) { game.Kill(); game.WaitForExit(); } }
        } catch (InvalidOperationException) { }
        game.Dispose(); game = null; status.Text = "Staged game closed. Stop OBS before starting the next take.";
    }

    void Launch() {
        var s = Selected;
        if (s.Kind == "launcher") {
            var install = Paths.Install() ?? throw new DirectoryNotFoundException("The installed game was not found.");
            Process.Start(new ProcessStartInfo(Path.Combine(install, "illusion-of-gaia.Companion.exe")) { UseShellExecute = true, WorkingDirectory = install });
            status.Text = "Your installed launcher opened. Show its pages; do not press Apply, Play or Update.";
            return;
        }
        CloseGame();
        game = Process.Start(Session.Create(s, fullscreen.Checked))!;
        status.Text = $"Scene {s.Id} started. Record in OBS, then save as\n{VideoName}\nPlay / reset starts again from the checkpoint.";
    }

    /// The window drawn into a picture, never shown on screen (layout check).
    public static void Smoke(string png) {
        using var f = new Picker { StartPosition = FormStartPosition.Manual, Location = new(-32000, -32000), ShowInTaskbar = false };
        f.CreateControl();
        f.Show();
        Application.DoEvents();
        using var bmp = new Bitmap(f.Width, f.Height);
        f.DrawToBitmap(bmp, new Rectangle(0, 0, f.Width, f.Height));
        bmp.Save(png, System.Drawing.Imaging.ImageFormat.Png);
        f.Close();
    }
}
