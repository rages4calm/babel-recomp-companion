using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Companion.Launcher.Core;

public sealed record NativeModField(string Package, string Feature, string? ValueKey, OptionDefinition Option);
public sealed record NativeModSnapshot(Dictionary<string, JsonElement> Values, string Revision, IReadOnlySet<string> Available);

/// <summary>Game-specific projection of Babel's authoritative native mod state.</summary>
public static class NativeModSettings
{
    private static NativeModField Toggle(string id, string section, string label, string package, string feature, string help, bool fallback = false) =>
        new(package, feature, null, new(id, section, label, OptionKind.Boolean, OptionValue.From(fallback), help));
    private static NativeModField Number(string id, string label, string feature, string value, int fallback, int min, int max, string help = "") =>
        new("iog.cheats", feature, value, new(id, "Cheats", label, OptionKind.Integer, OptionValue.From(fallback), help, min, max));
    public static readonly IReadOnlyList<NativeModField> Fields = new NativeModField[] {
        Toggle("cheat.hp", "Cheats", "Refill HP", "iog.cheats", "infinite_hp", "Refill HP between frames. A single lethal hit can still kill you; this does not revive a death already in progress."),
        Toggle("cheat.dp", "Cheats", "Keep a minimum DP balance", "iog.cheats", "dp", "Keep at least the selected amount of Dark Power. Continuing after death costs 100 DP; a minimum of 99 does not cover that cost."),
        Number("cheat.dp-min", "Minimum DP", "dp", "amount", 99, 0, 999),
        new("iog.cheats", "room_rewards", "multiplier", new("cheat.room-rewards", "Cheats", "Room-clear rewards", OptionKind.Choice,
            OptionValue.From("1"), "Multiply new room-clear stat rewards (HP cap 40; strength/defense 99). Original 1x is unchanged. Inactive with minimum stats, New Game+, randomizer or Apocalypse Gaia.",
            Choices: Enumerable.Range(1, 8).Select(n => new ChoiceItem(n.ToString(CultureInfo.InvariantCulture), n == 1 ? "Original · 1x" : n + "x rewards")).ToArray())),
        Toggle("cheat.stats", "Cheats", "Keep minimum stats", "iog.cheats", "stats", "Set at least one nonzero minimum below. Raised stats can be saved; switching off does not lower them. Overrides room-reward multiplication while active."),
        Number("cheat.strength", "Minimum strength", "stats", "strength", 0, 0, 99, "0 leaves this stat unchanged."),
        Number("cheat.defense", "Minimum defense", "stats", "defense", 0, 0, 99, "0 leaves this stat unchanged."),
        Number("cheat.max-hp", "Minimum maximum HP", "stats", "max_hp", 0, 0, 40, "0 leaves maximum HP unchanged."),
        Toggle("mod.run", "Convenience", "Run", "iog.enhancements", "run", "Run with the configured run button (default Y). Uses the game's existing dash and preserves your button binding. Choose the style below."),
        new("iog.enhancements", "run", "style", new("mod.run-style", "Convenience", "Run style", OptionKind.Choice, OptionValue.From("auto"),
            "Auto-run (after andrewclunn's Gaia and Time): walk to build speed, hold the run button to start sooner; turning sideways keeps it, reversing or stopping resets it. Hold: hold the run button with a direction to sprint at once.",
            Choices: new[] { new ChoiceItem("auto", "Auto-run"), new ChoiceItem("hold", "Hold to run") })),
        Toggle("mod.text-speed", "Convenience", "Text speed", "iog.enhancements", "text_speed", "Choose how dialogue types out, and hold the run button to hurry any line (after andrewclunn's Gaia and Time). Off leaves the game's own pacing.", true),
        new("iog.enhancements", "text_speed", "speed", new("mod.text-speed-choice", "Convenience", "Dialogue speed", OptionKind.Choice, OptionValue.From("normal"),
            "Normal keeps the game's pacing. Cinematic types plain lines one letter per frame. Instant shows every line at once.",
            Choices: new[] { new ChoiceItem("normal", "Normal"), new ChoiceItem("cinematic", "Cinematic"), new ChoiceItem("instant", "Instant") })),
        Toggle("mod.auto-use", "Convenience", "Use key items on the spot", "iog.enhancements", "auto_use", "Press A where a key item you carry does something and Will uses it without equipping it first (after andrewclunn's Gaia and Time). Melodies and hieroglyphs still work as usual.", true),
        Toggle("mod.jewel-sparkles", "Convenience", "Red Jewel sparkles", "iog.enhancements", "jewel_sparkles", "A twinkle of light marks each hidden Red Jewel you have not found yet, and the people who would give you one (after andrewclunn's Gaia and Time).", true),
        Toggle("mod.stacking", "Convenience", "Stack common items", "iog.enhancements", "stacking", "Red Jewels, Herbs and Crystals each share one inventory slot, with a counter."),
        Toggle("mod.equipped", "Convenience", "Mark the equipped item", "iog.enhancements", "equipped", "Draw the equipped-item frame in the original inventory."),
        Toggle("mod.hotswap", "Convenience", "Quick item selection", "iog.enhancements", "hotswap", "Hold the configured modifier and press L/R. Existing modifier mapping is preserved (default X)."),
        Toggle("mod.advance", "Convenience", "Hold to advance dialogue", "iog.enhancements", "hold_advance", "Hold a confirm button through dialogue. Questions still require a fresh press; existing speed choice is preserved."),
        Toggle("mod.edge-hud", "Convenience", "Status display at the screen edges", "iog.graphics", "edge_hud", "In the wide view: your life at the left edge of the picture, the enemy's at the right edge, the DP ornament in the centre. Off keeps the original status display as one block in the centre. Can also be changed in the in-game settings."),
        Toggle("mod.world-map", "Convenience", "Enhanced world map", "iog.enhancements", "world_map", "On the walkable world map: smoother map picture, higher camera, markers over the places you can visit, a small map and a clearer entry prompt. Off shows the original walking view; in Wide view that includes the original's coarse ground with its horizontal streaks (Classic 16:9 and Original 4:3 smooth the ground with HD Mode 7 either way).", true),
        Toggle("gaialabs.jp-edward", "GaiaLabs", "Edward Castle background: JP", "iog.gaialabs", "jp_edward", "The Japanese release's mountains behind Edward Castle, with its own parallax layers (GaiaLabs). Off: the North American background.", true),
        Toggle("gaialabs.jp-itory", "GaiaLabs", "Itory background: JP", "iog.gaialabs", "jp_itory", "The Japanese release's mountains around Itory, with its own parallax layers (GaiaLabs). Off: the North American background.", true),
        Toggle("gaialabs.jp-wall", "GaiaLabs", "Great Wall background: JP", "iog.gaialabs", "jp_wall", "The Japanese release's dunes behind the Great Wall (GaiaLabs). Off: the North American background.", true),
        Toggle("gaialabs.red-fountain", "GaiaLabs", "Fountain colour: JP (red)", "iog.gaialabs", "red_fountain", "The fountain shimmers red as in the Japanese release (GaiaLabs). Off: the North American brown.", true),
        Toggle("gaialabs.jp-church", "GaiaLabs", "Church cross: JP", "iog.gaialabs", "jp_church", "The Japanese release's cross in the church instead of the North American statue (GaiaLabs).", true),
        Toggle("gaialabs.jp-mines", "GaiaLabs", "Diamond Mine colours: JP (purple)", "iog.gaialabs", "jp_mines", "The Japanese release's purple Diamond Mine (GaiaLabs). Off: the North American brown."),
        Toggle("gaialabs.jp-prologue", "GaiaLabs", "Prologue palettes: JP (dark)", "iog.gaialabs", "jp_prologue", "The Japanese release's darker palettes for the prologue's legends (GaiaLabs). Off: the lighter North American ones.", true),
        Toggle("gaialabs.jp-viper", "GaiaLabs", "Viper: JP", "iog.gaialabs", "jp_viper", "The Japanese release's Viper boss sprites (GaiaLabs). Off: the North American Viper."),
        Toggle("gaialabs.crystal-ring", "GaiaLabs", "Crystal Ring: new palette", "iog.gaialabs", "crystal_ring", "GaiaLabs' recoloured Crystal Ring in the inventory.", true),
        Toggle("gaialabs.no-shira", "GaiaLabs", "Shira's dream: no spotlight", "iog.gaialabs", "no_shira", "In Will's dream of his mother, the picture does not close in to a spotlight while she talks (GaiaLabs)."),
        Toggle("gaialabs.freejia-shortcut", "GaiaLabs", "Shortcut: Mines to Freejia", "iog.gaialabs", "freejia_shortcut", "Sam offers to take you straight to Freejia from the Diamond Mine, skipping the walk back (GaiaLabs).", true),
        Toggle("gaialabs.angkor-shortcut", "GaiaLabs", "Shortcut: Angkor Wat", "iog.gaialabs", "angkor_shortcut", "A voice in Angkor Wat offers to take you back to its entrance (GaiaLabs).", true),
        Toggle("gaialabs.south-cape-return", "GaiaLabs", "South Cape: welcome back", "iog.gaialabs", "south_cape_return", "When you return to South Cape later in the story, its people greet you (GaiaLabs).", true),
        Toggle("gaialabs.thankful-flower", "GaiaLabs", "Thankful Flower", "iog.gaialabs", "thankful_flower", "The flower in the aqueduct doorway thanks you once you have played the melody (GaiaLabs).", true),
        Toggle("gaialabs.slave-return", "GaiaLabs", "Freejia: the runaway laborer returns", "iog.gaialabs", "slave_return", "If you keep the runaway laborer's secret, he thanks you later with the Red Jewel the slaver would have paid (GaiaLabs).", true),
        Toggle("gaialabs.kress-shortcut", "GaiaLabs", "Shortcut: Mt. Kress", "iog.gaialabs", "kress_shortcut", "At the top of Mt. Kress a spirit offers to take you back to the bottom (GaiaLabs).", true),
        Toggle("gaialabs.minimal-hud", "GaiaLabs", "Minimal HUD", "iog.gaialabs", "minimal_hud", "The status display shows only where you can fight; it is hidden in towns and cutscene rooms (GaiaLabs).", false),
        Toggle("gaialabs.blue-journal", "GaiaLabs", "Blue Journal", "iog.gaialabs", "blue_journal", "Lance's father gives you his journal when you return, and the journal reads with GaiaLabs' text (GaiaLabs).", true),
        Toggle("gaialabs.full-herb", "GaiaLabs", "Herbs heal fully", "iog.gaialabs", "full_herb", "A herb refills all of Will's HP instead of 8 (GaiaLabs).", true),
        Toggle("gaialabs.portal-exit", "GaiaLabs", "Pyramid portals: lower hall", "iog.gaialabs", "portal_exit", "The portals in the Pyramid's rooms take you to the lower main area of the entrance hall instead of its top (GaiaLabs).", true),
        Toggle("gaialabs.elevator", "GaiaLabs", "Pyramid moving floors: 2x", "iog.gaialabs", "elevator", "The Pyramid's moving floors travel twice as fast, over the same distance (GaiaLabs).", true)
    };
    /// <summary>Whether a control does anything with the current Picture. The edge status display
    /// exists only in the wide view; the in-game settings leave it out of Classic 16:9 and Original 4:3.</summary>
    public static bool AppliesToPicture(string id, bool wideView) => wideView || id != "mod.edge-hud";
    private static readonly GameDefinition ValidationDefinition =new("gaia-mod-options", "Gaia mods", "", Fields.Select(x => x.Option).ToArray());
    private static readonly Regex Tables = new(@"(?m)^[ \t]*\[\[([\w.-]+)\]\][ \t]*(?:#.*)?\r?$", RegexOptions.Compiled);
    private sealed record Block(string Type, int Start, int BodyStart, int End, string Body);
    private static string StatePath(string engine) => Path.Combine(Path.GetFullPath(engine), "mods", "preloaded", "state.toml");
    private static string Manifest(string engine, string package) => Path.Combine(Path.GetFullPath(engine), "mods", "preloaded", "packages", package, "1.0.0", "manifest.toml");
    private static string Digest(byte[]? bytes) => bytes == null ? "missing" : Convert.ToHexString(SHA256.HashData(bytes));
    private static byte[]? ReadBounded(string path) {
        if (!File.Exists(path)) return null;
        var info = new FileInfo(path);
        if (info.Length > 1024 * 1024 || (info.Attributes & FileAttributes.ReparsePoint) != 0) throw new InvalidDataException("Native mod file is oversized or linked.");
        return File.ReadAllBytes(path);
    }
    private static string Decode(byte[] bytes) => new UTF8Encoding(false, true).GetString(bytes.AsSpan(bytes.AsSpan().StartsWith(new byte[] {239,187,191}) ? 3 : 0));
    private static IEnumerable<Block> Blocks(string text) {
        var matches = Tables.Matches(text);
        for (int i = 0; i < matches.Count; i++) { var m = matches[i]; int end = i+1 < matches.Count ? matches[i+1].Index : text.Length; yield return new(m.Groups[1].Value, m.Index, m.Index+m.Length, end, text[(m.Index+m.Length)..end]); }
    }
    private static (string Root, string Values) SplitValues(string body) {
        var match = Regex.Match(body, @"(?m)^[ \t]*\[feature\.values\][ \t]*(?:#.*)?\r?$");
        return match.Success ? (body[..match.Index], body[match.Index..]) : (body, "");
    }
    private static string? Value(string body, string key) {
        var matches = Regex.Matches(body, @"(?m)^[ \t]*" + Regex.Escape(key) + @"[ \t]*=(.*)\r?$");
        if (matches.Count > 1) throw new InvalidDataException("Duplicate native mod value: " + key);
        if (matches.Count == 0) return null;
        var raw = matches[0].Groups[1].Value.Trim();
        if (raw.StartsWith('"')) {
            var m = Regex.Match(raw, "^\"(?:\\\\.|[^\"\\\\])*\"");
            if (!m.Success || (raw[m.Length..].Trim() is var tail && tail.Length != 0 && !tail.StartsWith('#'))) throw new InvalidDataException("Unsupported native mod string: " + key);
            return JsonSerializer.Deserialize<string>(m.Value);
        }
        raw = raw.Split('#')[0].Trim();
        if (raw is "true" or "false" || int.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out _)) return raw;
        throw new InvalidDataException("Unsupported native mod value: " + key);
    }
    private static Block? Find(string text, string type, IReadOnlyDictionary<string,string> identity) {
        var blocks = Blocks(text).Where(b => b.Type == type && identity.All(pair => Value(SplitValues(b.Body).Root, pair.Key) == pair.Value)).ToArray();
        if (blocks.Length > 1) throw new InvalidDataException("Duplicate native mod selection; repair it in Babel tools.");
        return blocks.SingleOrDefault();
    }
    private static Dictionary<string,string> FeatureKey(NativeModField field) => new() { ["package_id"] = field.Package, ["id"] = field.Feature };
    private static bool Enabled(Block? block) {
        var value = block == null ? null : Value(SplitValues(block.Body).Root, "enabled");
        if (value is null or "false") return false;
        if (value == "true") return true;
        throw new InvalidDataException("Invalid native feature enable value.");
    }
    private static bool Available(string engine, NativeModField field) {
        var bytes = ReadBounded(Manifest(engine, field.Package)); if (bytes == null) return false;
        var manifest = Decode(bytes);
        return Blocks(manifest).Any(b => b.Type == "feature" && Value(b.Body, "id") == field.Feature) &&
            (field.ValueKey == null || Blocks(manifest).Any(b => b.Type == "option" && Value(b.Body, "feature") == field.Feature && Value(b.Body, "id") == field.ValueKey));
    }
    private static string Revision(string engine, byte[]? state) => Digest(Encoding.UTF8.GetBytes(Digest(state) + "\n" + string.Join("\n",
        Fields.Select(f => f.Package).Distinct().Select(p => p + ":" + Digest(ReadBounded(Manifest(engine, p)))))));
    public static NativeModSnapshot Read(string engineDirectory) {
        var bytes = ReadBounded(StatePath(engineDirectory)); var text = bytes == null ? "format_version = 1\n" : Decode(bytes);
        if (text.Contains('\0') || Value(text[..(Tables.Match(text).Success ? Tables.Match(text).Index : text.Length)], "format_version") != "1") throw new InvalidDataException("Unsupported native mod state format.");
        var values = new Dictionary<string,JsonElement>(); var available = new HashSet<string>();
        foreach (var field in Fields) {
            if (Available(engineDirectory, field)) available.Add(field.Option.Id);
            var feature = Find(text, "feature", FeatureKey(field));
            JsonElement value;
            // A feature the state file has never named keeps its manifest default.
            if (field.ValueKey == null) value = feature == null ? field.Option.DefaultValue.Clone() : OptionValue.From(Enabled(feature));
            else {
                var raw = feature == null ? null : Value(SplitValues(feature.Body).Values, field.ValueKey);
                value = raw == null ? field.Option.DefaultValue.Clone() : field.Option.Kind == OptionKind.Integer && int.TryParse(raw, out var number) ? OptionValue.From(number) : OptionValue.From(raw);
                if (field.Option.Id == "cheat.room-rewards" && !Enabled(feature)) value = OptionValue.From("1");
            }
            if (OptionValidation.ValidateValue(field.Option, value) is { } error) throw new InvalidDataException(error);
            values[field.Option.Id] = value;
        }
        return new(values, Revision(engineDirectory, bytes), available);
    }
    private static string SetValue(string body, string key, string encoded, string newline) {
        var old = Value(body, key);
        if (old == null) return body.TrimEnd() + newline + key + " = " + encoded + newline + newline;
        return Regex.Replace(body, @"(?m)^([ \t]*" + Regex.Escape(key) + @"[ \t]*=)[^\r\n]*", m => {
            var comment = m.Value.IndexOf('#'); return m.Groups[1].Value + " " + encoded + (comment < 0 ? "" : " " + m.Value[comment..]); });
    }
    private static string Upsert(string text, string type, Dictionary<string,string> identity, string key, string encoded, string newline, bool nested = false) {
        var block = Find(text, type, identity);
        if (block == null) {
            text = text.TrimEnd() + newline + newline + "[[" + type + "]]" + newline + string.Join(newline, identity.Select(pair => pair.Key + " = " + JsonSerializer.Serialize(pair.Value))) + newline;
            block = Find(text, type, identity)!;
        }
        var (root, values) = SplitValues(block.Body);
        if (nested) values = SetValue(values.Length == 0 ? "[feature.values]" + newline : values, key, encoded, newline);
        else root = SetValue(root, key, encoded, newline);
        return text[..block.BodyStart] + root + values + text[block.End..];
    }
    private static readonly Dictionary<string,string> MapControls = new() { ["package_id"] = "iog.enhancements", ["id"] = "map_controls" };
    /// <summary>The button-prompt style the game will use: auto, snes or xbox.</summary>
    public static string ReadPrompts(string engineDirectory) {
        var bytes = ReadBounded(StatePath(engineDirectory)); if (bytes == null) return "auto";
        var feature = Find(Decode(bytes), "feature", MapControls);
        // The game only reads the style while the map controls feature is on.
        if (feature != null && Value(SplitValues(feature.Body).Root, "enabled") == "false") return "auto";
        var style = feature == null ? null : Value(SplitValues(feature.Body).Values, "prompts");
        return style is "snes" or "xbox" ? style : "auto";
    }
    public static void ApplyPrompts(string engineDirectory, string style) {
        if (style is not ("auto" or "snes" or "xbox")) throw new ArgumentException("Unknown button prompt style.");
        Edit(engineDirectory, (text, newline) => {
            text = Upsert(text, "package", new Dictionary<string,string> { ["id"] = "iog.enhancements" }, "version", "\"1.0.0\"", newline);
            // Map controls are on by default; keep them on so the style is read.
            text = Upsert(text, "feature", MapControls, "enabled", "true", newline);
            return Upsert(text, "feature", MapControls, "prompts", JsonSerializer.Serialize(style), newline, nested: true);
        });
    }
    /// <summary>The two graphics selections the Display page folds into Picture and Scaling.</summary>
    public sealed record DisplayState(bool WideView, bool Hd, string Filter);
    private static readonly Dictionary<string,string> WideViewKey = new() { ["package_id"] = "iog.graphics", ["id"] = "wide_view" };
    private static readonly Dictionary<string,string> HdKey = new() { ["package_id"] = "iog.graphics", ["id"] = "hd" };
    public static DisplayState ReadDisplay(string engineDirectory) {
        var bytes = ReadBounded(StatePath(engineDirectory)); if (bytes == null) return new(true, true, "sharp");
        var text = Decode(bytes); var wide = Find(text, "feature", WideViewKey); var hd = Find(text, "feature", HdKey);
        // Both are on in the game's catalog until the state file says otherwise.
        return new(wide == null || Enabled(wide), hd == null || Enabled(hd),
            (hd == null ? null : Value(SplitValues(hd.Body).Values, "filter")) == "smooth" ? "smooth" : "sharp");
    }
    public static void ApplyDisplay(string engineDirectory, DisplayState state) {
        if (state.Filter is not ("sharp" or "smooth")) throw new ArgumentException("Unknown scaling filter.");
        Edit(engineDirectory, (text, newline) => {
            text = Upsert(text, "package", new Dictionary<string,string> { ["id"] = "iog.graphics" }, "version", "\"1.0.0\"", newline);
            text = Upsert(text, "feature", WideViewKey, "enabled", state.WideView ? "true" : "false", newline);
            text = Upsert(text, "feature", HdKey, "enabled", state.Hd ? "true" : "false", newline);
            return Upsert(text, "feature", HdKey, "filter", JsonSerializer.Serialize(state.Filter), newline, nested: true);
        });
    }
    private static void Edit(string engineDirectory, Func<string,string,string> change) {
        var path = StatePath(engineDirectory); Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        using var gate = new FileStream(path + ".companion-lock", FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        var original = ReadBounded(path); var text = original == null ? "format_version = 1\n" : Decode(original);
        text = change(text, text.Contains("\r\n") ? "\r\n" : "\n");
        if (original != null && text == Decode(original)) return;
        var temp = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try {
            var encoding = new UTF8Encoding(original != null && original.AsSpan().StartsWith(new byte[] {239,187,191}));
            using (var stream = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None)) { stream.Write(encoding.GetPreamble().Concat(encoding.GetBytes(text)).ToArray()); stream.Flush(true); }
            File.Move(temp, path, true);
        } finally { if (File.Exists(temp)) File.Delete(temp); }
    }
    public static bool IsEngineRunning(string executable) {
        var expected = Path.GetFullPath(executable);
        foreach (var process in Process.GetProcessesByName(Path.GetFileNameWithoutExtension(expected))) {
            using (process) { try { if (string.Equals(process.MainModule?.FileName, expected, StringComparison.OrdinalIgnoreCase)) return true; }
                catch (Win32Exception) { return true; } catch (InvalidOperationException) { } }
        }
        return false;
    }
    public static void Apply(string engineDirectory, IReadOnlyDictionary<string,JsonElement> values, string expectedRevision) {
        var executable = Path.Combine(Path.GetFullPath(engineDirectory), "babel-recomp.exe");
        if (!File.Exists(executable)) throw new FileNotFoundException("Set the game program on the Game page first.");
        if (IsEngineRunning(executable)) throw new InvalidOperationException("Close the game before applying launcher mods. In-game settings can change the live session.");
        var errors = OptionValidation.Validate(ValidationDefinition, values); if (errors.Count > 0) throw new SettingsValidationException(errors);
        var path = StatePath(engineDirectory); Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        using var gate = new FileStream(path + ".companion-lock", FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        var before = Read(engineDirectory); if (before.Revision != expectedRevision) throw new SettingsConflictException();
        var original = ReadBounded(path); var text = original == null ? "format_version = 1\n" : Decode(original);
        var newline = text.Contains("\r\n") ? "\r\n" : "\n";
        foreach (var field in Fields.Where(field => values[field.Option.Id].GetRawText() != before.Values[field.Option.Id].GetRawText())) {
            if (!before.Available.Contains(field.Option.Id)) throw new InvalidOperationException("This engine's mod catalog does not implement " + field.Option.Label + ". Build its matching engine and catalog first.");
            var packageKey = new Dictionary<string,string> { ["id"] = field.Package }; var package = Find(text, "package", packageKey);
            if (package != null && Value(package.Body, "version") != "1.0.0") throw new InvalidDataException("Unexpected native mod version; review it in Babel tools.");
            text = Upsert(text, "package", packageKey, "version", "\"1.0.0\"", newline);
            var identity = FeatureKey(field);
            if (field.ValueKey == null) text = Upsert(text, "feature", identity, "enabled", values[field.Option.Id].GetBoolean() ? "true" : "false", newline);
            else {
                if (field.Option.Id == "cheat.room-rewards") text = Upsert(text, "feature", identity, "enabled", values[field.Option.Id].GetString() == "1" ? "false" : "true", newline);
                else if (Find(text, "feature", identity) == null) text = Upsert(text, "feature", identity, "enabled", "false", newline);
                var raw = field.Option.Kind == OptionKind.Integer ? values[field.Option.Id].GetInt32().ToString(CultureInfo.InvariantCulture) : values[field.Option.Id].GetString()!;
                text = Upsert(text, "feature", identity, field.ValueKey, JsonSerializer.Serialize(raw), newline, nested: true);
            }
        }
        if (Read(engineDirectory).Revision != expectedRevision || Digest(ReadBounded(path)) != Digest(original)) throw new SettingsConflictException();
        if (original != null && text == Decode(original)) return;
        var temp = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try {
            var encoding = new UTF8Encoding(original != null && original.AsSpan().StartsWith(new byte[] {239,187,191}));
            using (var stream = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None)) { stream.Write(encoding.GetPreamble().Concat(encoding.GetBytes(text)).ToArray()); stream.Flush(true); }
            File.Move(temp, path, true);
        } finally { if (File.Exists(temp)) File.Delete(temp); }
    }
}
