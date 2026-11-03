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
    private static NativeModField Toggle(string id, string section, string label, string package, string feature, string help) =>
        new(package, feature, null, new(id, section, label, OptionKind.Boolean, OptionValue.From(false), help));
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
        Toggle("mod.run", "Convenience", "Hold to run", "iog.enhancements", "run", "Hold the configured run button with a direction (default Y). Uses the game's existing dash and preserves your button binding."),
        Toggle("mod.stacking", "Convenience", "Stack common items", "iog.enhancements", "stacking", "Red Jewels, Herbs and Crystals each share one inventory slot, with a counter."),
        Toggle("mod.equipped", "Convenience", "Mark the equipped item", "iog.enhancements", "equipped", "Draw the equipped-item frame in the original inventory."),
        Toggle("mod.hotswap", "Convenience", "Quick item selection", "iog.enhancements", "hotswap", "Hold the configured modifier and press L/R. Existing modifier mapping is preserved (default X)."),
        Toggle("mod.advance", "Convenience", "Hold to advance dialogue", "iog.enhancements", "hold_advance", "Hold a confirm button through dialogue. Questions still require a fresh press; existing speed choice is preserved.")
    };
    private static readonly GameDefinition ValidationDefinition = new("gaia-mod-options", "Gaia mods", "", Fields.Select(x => x.Option).ToArray());
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
            if (field.ValueKey == null) value = OptionValue.From(Enabled(feature));
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
        if (!File.Exists(executable)) throw new FileNotFoundException("Select the built Babel executable first.");
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
