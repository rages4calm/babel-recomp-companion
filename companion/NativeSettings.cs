using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Companion.Launcher.Core;

internal static class NativeSettings
{
    private sealed record Field(string Section, string Key, OptionDefinition Option);
    private static Field Bool(string id, string page, string label, string section, string key, bool fallback, string help = "") =>
        new(section, key, new(id, page, label, OptionKind.Boolean, OptionValue.From(fallback), help));
    private static Field Int(string id, string page, string label, string section, string key, int fallback, int min, int max, string help = "") =>
        new(section, key, new(id, page, label, OptionKind.Integer, OptionValue.From(fallback), help, min, max));
    private static readonly Field[] Fields = {
        new("Graphics", "Fullscreen", new("video.fullscreen", "Display", "Window mode", OptionKind.Choice, OptionValue.From("0"), "Applies on next launch.", Choices: new[] {
            new ChoiceItem("0", "Windowed"), new ChoiceItem("1", "Desktop fullscreen"), new ChoiceItem("2", "Exclusive fullscreen") })),
        Int("video.scale", "Display", "Window scale", "Graphics", "WindowScale", 3, 1, 10),
        Bool("video.widescreen", "Display", "Babel 16:9 widescreen", "Graphics", "Widescreen", false,
            "Real extra terrain columns. Scene and actor coverage is under audit; 21:9 and 32:9 are not implemented here."),
        new("Graphics", "VSync", new("video.vsync", "Display", "Vertical sync", OptionKind.Choice, OptionValue.From("1"),
            "Adaptive uses late-swap tearing where the graphics driver supports it. Restart after applying.", Choices: new[] {
                new ChoiceItem("0", "Off"), new ChoiceItem("1", "On"), new ChoiceItem("adaptive", "Adaptive") })),
        Bool("video.filter", "Display", "Smooth pixel filtering", "Graphics", "LinearFiltering", false,
            "Off preserves crisp pixels. This does not change gameplay zoom."),
        Bool("video.mode7", "Display", "HD Mode 7", "Graphics", "Mode7Enabled", true,
            "Shared Mode 7 presentation, enabled at the configured quality (default 8x). Preserves scale and sampling. Restart after applying."),
        Bool("audio.enabled", "Audio", "Enable audio", "Sound", "EnableAudio", true,
            "Original SNES audio works offline without optional music. MSU-1 packs remain user supplied in the game folder."),
        Int("audio.volume", "Audio", "Master volume (%)", "Sound", "Volume", 100, 0, 100,
            "Same mixer setting as in-game shortcuts. Use Soundtrack to download/import optional music or select original audio."),
        Bool("input.gamepad", "Input", "Enable gamepad", "GamepadMap", "EnableGamepad1", true,
            "Choose Babel tools on Game for full remapping. Existing bindings and controller GUID remain intact."),
        Int("input.deadzone", "Input", "Analog deadzone", "GamepadMap", "GamepadDeadzone", 3277, 0, 32767,
            "SDL axis units. Settings: Esc / LT+R3. Companion: I / LT+L3. Save states: F11 / LT+Start. Fast forward: Tab / LT+RT.")
    };
    internal static IEnumerable<OptionDefinition> Options => Fields.Select(x => x.Option);
    internal static bool IsNative(string id) => Fields.Any(x => x.Option.Id == id);
    private static string Config(IReadOnlyDictionary<string, JsonElement> values) => System.IO.Path.Combine(System.IO.Path.GetDirectoryName(values["engine.path"].GetString()!)!, "config.ini");
    private static string Hash(byte[]? bytes) => bytes == null ? "missing" : Convert.ToHexString(SHA256.HashData(bytes));
    internal static SettingsSnapshot Read(SettingsSnapshot paths)
    {
        var file = Document.Read(Config(paths.Values));
        foreach (var field in Fields) {
            var text = file.Get(field.Section, field.Key);
            var value = text == null ? field.Option.DefaultValue.Clone() : Parse(field.Option, text);
            if (OptionValidation.ValidateValue(field.Option, value) is { } error) throw new InvalidDataException(error);
            paths.Values[field.Option.Id] = value;
        }
        return new(paths.Values, Hash(Encoding.UTF8.GetBytes(paths.Revision + "\n" + file.Path + "\n" + Hash(file.Original))));
    }
    private static JsonElement Parse(OptionDefinition option, string text)
    {
        if (option.Id == "video.vsync") {
            if (text == "2" || text.Equals("adaptive", StringComparison.OrdinalIgnoreCase)) return OptionValue.From("adaptive");
            if (text == "1" || text.Equals("true", StringComparison.OrdinalIgnoreCase)) return OptionValue.From("1");
            if (text == "0" || text.Equals("false", StringComparison.OrdinalIgnoreCase)) return OptionValue.From("0");
            throw new InvalidDataException("Invalid native Vertical sync setting.");
        }
        if (option.Kind == OptionKind.Boolean) {
            if (text == "1" || text.Equals("true", StringComparison.OrdinalIgnoreCase)) return OptionValue.From(true);
            if (text == "0" || text.Equals("false", StringComparison.OrdinalIgnoreCase)) return OptionValue.From(false);
        } else if (option.Kind == OptionKind.Integer && int.TryParse(text, NumberStyles.Integer, CultureInfo.InvariantCulture, out var n)) return OptionValue.From(n);
        else if (option.Kind == OptionKind.Choice) return OptionValue.From(text);
        throw new InvalidDataException("Invalid native setting: " + option.Label + ". Repair config.ini before applying changes.");
    }
    internal static void Apply(SettingsSnapshot current, IReadOnlyDictionary<string, JsonElement> values, Action validate, Action commitPaths)
    {
        var document = Document.Read(Config(values));
        // The engine generates a complete default file on first launch. A
        // partial INI here would suppress that initialization and change hidden
        // defaults (notably NewRenderer and the system/gamepad bindings).
        if (document.Original == null && Fields.Any(field => values[field.Option.Id].GetRawText() != current.Values[field.Option.Id].GetRawText()))
            throw new InvalidOperationException("Launch the game once to initialize native settings, then Revert before editing Display, Audio or Input.");
        foreach (var field in Fields)
            if (values[field.Option.Id].GetRawText() != current.Values[field.Option.Id].GetRawText())
                document.Set(field.Section, field.Key, field.Option.Kind switch {
                    OptionKind.Boolean => values[field.Option.Id].GetBoolean() ? "1" : "0",
                    OptionKind.Integer => values[field.Option.Id].GetInt32().ToString(CultureInfo.InvariantCulture), _ => values[field.Option.Id].GetString()! });
        validate(); document.AssertUnchanged();
        if (!document.Changed) { commitPaths(); return; }
        document.Commit();
        try { commitPaths(); } catch { document.Restore(); throw; }
    }
    // Preserve comments, unknown fields and untouched key bindings.
    private sealed class Document
    {
        internal string Path { get; }
        internal byte[]? Original { get; }
        private readonly List<string> lines;
        private readonly string newline;
        private readonly bool bom;
        internal bool Changed { get; private set; }
        private Document(string path, byte[]? original)
        {
            Path = path; Original = original;
            bom = original != null && original.AsSpan().StartsWith(new byte[] { 0xef, 0xbb, 0xbf });
            var text = original == null ? "" : new UTF8Encoding(false, true).GetString(original.AsSpan(bom ? 3 : 0));
            if (text.Contains('\0')) throw new InvalidDataException("config.ini contains binary data.");
            newline = text.Contains("\r\n") ? "\r\n" : "\n";
            lines = text.Length == 0 ? new() : text.Replace("\r\n", "\n").Split('\n').ToList();
            string section = ""; var keys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var line in lines) {
                var s = line.Trim();
                if (s.StartsWith('[') && s.EndsWith(']')) section = s[1..^1].Trim();
                else if (s.Length != 0 && !s.StartsWith(';') && !s.StartsWith('#') && s.IndexOf('=') is var eq && eq >= 0)
                    if (!keys.Add(section + "\0" + s[..eq].Trim())) throw new InvalidDataException("Duplicate config.ini key; no settings were written.");
            }
        }
        private static byte[]? ReadBytes(string path) {
            if (!File.Exists(path)) return null;
            using var f = File.OpenRead(path);
            if (f.Length > 1024 * 1024) throw new InvalidDataException("config.ini exceeds 1 MiB.");
            var bytes = new byte[checked((int)f.Length)]; f.ReadExactly(bytes); return bytes;
        }
        internal static Document Read(string path) => new(path, ReadBytes(path));
        private (int index, int end) Locate(string wantedSection, string wantedKey) {
            string section = ""; int found = -1, primaryEnd = -1;
            for (int i = 0; i < lines.Count; i++) {
                var s = lines[i].Trim();
                if (s.StartsWith('[') && s.EndsWith(']')) {
                    if (section.Equals(wantedSection, StringComparison.OrdinalIgnoreCase)) primaryEnd = i;
                    section = s[1..^1].Trim();
                } else if (!s.StartsWith(';') && !s.StartsWith('#')) {
                    var eq = s.IndexOf('=');
                    if (eq < 0) continue;
                    var key = s[..eq].Trim();
                    bool primary = section.Equals(wantedSection, StringComparison.OrdinalIgnoreCase) && key.Equals(wantedKey, StringComparison.OrdinalIgnoreCase);
                    bool videoAlias = wantedSection == "Graphics" && (section.Equals("Video", StringComparison.OrdinalIgnoreCase) || section.Equals("Emulation", StringComparison.OrdinalIgnoreCase)) &&
                        ((wantedKey == "VSync" && key.Equals("Vsync", StringComparison.OrdinalIgnoreCase)) ||
                         (wantedKey == "LinearFiltering" && key.Equals("LinearFilter", StringComparison.OrdinalIgnoreCase)));
                    if (primary || videoAlias) found = i;
                }
            }
            return (found, section.Equals(wantedSection, StringComparison.OrdinalIgnoreCase) ? lines.Count : primaryEnd);
        }
        internal string? Get(string section, string key) {
            var found = Locate(section, key); if (found.index < 0) return null;
            var line = lines[found.index]; return line[(line.IndexOf('=') + 1)..].Split('#')[0].Trim();
        }
        internal void Set(string section, string key, string value) {
            var found = Locate(section, key);
            if (found.index >= 0) {
                var old = lines[found.index]; var comment = old.IndexOf('#');
                lines[found.index] = old[..old.IndexOf('=')].TrimEnd() + " = " + value + (comment < 0 ? "" : " " + old[comment..]);
            } else if (found.end >= 0) lines.Insert(found.end, key + " = " + value);
            else { if (lines.Count != 0 && lines[^1] != "") lines.Add(""); lines.Add("[" + section + "]"); lines.Add(key + " = " + value); }
            Changed = true;
        }
        internal void AssertUnchanged() { if (Hash(ReadBytes(Path)) != Hash(Original)) throw new SettingsConflictException(); }
        internal void Commit() {
            var text = string.Join(newline, lines); if (!text.EndsWith(newline)) text += newline;
            Write(new UTF8Encoding(bom).GetPreamble().Concat(Encoding.UTF8.GetBytes(text)).ToArray());
        }
        private void Write(byte[] content) {
            var temp = Path + "." + Guid.NewGuid().ToString("N") + ".tmp";
            try {
                using (var f = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None)) { f.Write(content); f.Flush(true); }
                File.Move(temp, Path, true);
            } finally { if (File.Exists(temp)) File.Delete(temp); }
        }
        internal void Restore() { if (Original == null) File.Delete(Path); else Write(Original); }
    }
}
