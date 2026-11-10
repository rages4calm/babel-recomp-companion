using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

public sealed record SoundtrackActivationState(bool Enabled, string? PackDirectory);

/// <summary>Edits only Babel's native MSU-1 selection. Other mod settings survive.</summary>
public static class SoundtrackActivation
{
    private const string Package = "iog.enhancements";
    private static readonly Regex Tables = new(@"(?m)^[ \t]*\[\[([\w.-]+)\]\][ \t]*(?:#.*)?\r?$", RegexOptions.Compiled);
    private sealed record Block(string Type, int Start, int BodyStart, int End, string Body);

    private static string StatePath(string engineDirectory) => Path.Combine(Path.GetFullPath(engineDirectory), "mods", "preloaded", "state.toml");
    private static IEnumerable<Block> Blocks(string text)
    {
        var matches = Tables.Matches(text);
        for (int i = 0; i < matches.Count; i++) {
            var m = matches[i]; int end = i + 1 < matches.Count ? matches[i + 1].Index : text.Length;
            yield return new(m.Groups[1].Value, m.Index, m.Index + m.Length, end, text[(m.Index + m.Length)..end]);
        }
    }
    private static string? Value(string body, string key)
    {
        var lines = Regex.Matches(body, @"(?m)^[ \t]*" + Regex.Escape(key) + @"[ \t]*=(.*)\r?$");
        if (lines.Count > 1) throw new InvalidDataException("Duplicate native mod setting: " + key);
        if (lines.Count == 0) return null;
        var raw = lines[0].Groups[1].Value.Trim();
        // Native state writer emits JSON-compatible TOML strings. Reject
        // unfamiliar hand-edited syntax instead of silently replacing it.
        if (raw.StartsWith('"')) {
            var match = Regex.Match(raw, "^\"(?:\\\\.|[^\"\\\\])*\"");
            if (!match.Success || (raw[match.Length..].Trim() is var tail && tail.Length != 0 && !tail.StartsWith('#')))
                throw new InvalidDataException("Unsupported native mod string: " + key);
            return JsonSerializer.Deserialize<string>(match.Value);
        }
        raw = raw.Split('#')[0].Trim();
        if (raw is "true" or "false" || int.TryParse(raw, out _)) return raw;
        throw new InvalidDataException("Unsupported native mod value: " + key);
    }
    private static bool Target(Block b, string type, IReadOnlyDictionary<string,string> identity) =>
        b.Type == type && identity.All(pair => Value(b.Body, pair.Key) == pair.Value);
    private static readonly Dictionary<string,string> PackageKey = new() { ["id"] = Package };
    private static readonly Dictionary<string,string> FeatureKey = new() { ["package_id"] = Package, ["id"] = "msu1" };
    private static readonly Dictionary<string,string> ResourceKey = new() { ["package_id"] = Package, ["feature_id"] = "msu1", ["id"] = "pack" };

    public static SoundtrackActivationState Read(string engineDirectory)
    {
        var path = StatePath(engineDirectory);
        if (!File.Exists(path)) return new(DefaultEnabled(engineDirectory), null);
        var text = ReadBytes(path).Text;
        var features = Blocks(text).Where(b => Target(b, "feature", FeatureKey)).ToArray();
        var resources = Blocks(text).Where(b => Target(b, "resource", ResourceKey)).ToArray();
        if (features.Length > 1 || resources.Length > 1) throw new InvalidDataException("Duplicate MSU-1 selection; repair it in Babel tools.");
        return new(features.Length == 1 ? Value(features[0].Body, "enabled") == "true" : DefaultEnabled(engineDirectory),
                   resources.Length == 1 ? Value(resources[0].Body, "path") : null);
    }
    private static bool DefaultEnabled(string engineDirectory)
    {
        var manifest = Path.Combine(Path.GetFullPath(engineDirectory), "mods/preloaded/packages/iog.enhancements/1.0.0/manifest.toml");
        if (!File.Exists(manifest)) return false;
        var feature = Blocks(ReadManifest(manifest)).SingleOrDefault(b => b.Type == "feature" && Value(b.Body, "id") == "msu1");
        return feature != null && Value(feature.Body, "default_enabled") == "true";
    }
    private static string ReadManifest(string path)
    {
        var info = new FileInfo(path);
        if (info.Length > 1024 * 1024 || (info.Attributes & FileAttributes.ReparsePoint) != 0)
            throw new InvalidDataException("Native mod manifest is oversized or linked.");
        return File.ReadAllText(path, new UTF8Encoding(false, true));
    }
    public static void Enable(string engineDirectory, string packDirectory)
    {
        var root = Path.GetFullPath(Path.Combine(engineDirectory, "msu1", "companion-packs")) + Path.DirectorySeparatorChar;
        var pack = Path.GetFullPath(packDirectory);
        if (!pack.StartsWith(root, StringComparison.OrdinalIgnoreCase) || !Directory.Exists(pack))
            throw new InvalidDataException("Select a soundtrack installed by this Companion importer.");
        if ((File.GetAttributes(pack) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidDataException("Soundtrack folders cannot be links.");
        Edit(engineDirectory, true, pack);
    }
    public static void Disable(string engineDirectory) => Edit(engineDirectory, false, null);

    private static (byte[] Bytes, string Text, bool Bom) ReadBytes(string path)
    {
        var info = new FileInfo(path);
        if (info.Length > 1024 * 1024 || (info.Attributes & FileAttributes.ReparsePoint) != 0)
            throw new InvalidDataException("Native mod state is oversized or linked.");
        var bytes = File.ReadAllBytes(path); bool bom = bytes.AsSpan().StartsWith(new byte[] { 239,187,191 });
        var text = new UTF8Encoding(false, true).GetString(bytes.AsSpan(bom ? 3 : 0));
        if (text.Contains('\0') || Value(text[..(Tables.Match(text).Success ? Tables.Match(text).Index : text.Length)], "format_version") != "1")
            throw new InvalidDataException("Unsupported native mod state format.");
        return (bytes, text, bom);
    }
    private static string Upsert(string text, string type, Dictionary<string,string> identity, string key, string encoded, string newline)
    {
        var blocks = Blocks(text).Where(b => Target(b, type, identity)).ToArray();
        if (blocks.Length > 1) throw new InvalidDataException("Duplicate MSU-1 selection; use Babel tools to repair it.");
        if (blocks.Length == 0) {
            var body = string.Join(newline, identity.Select(p => p.Key + " = " + JsonSerializer.Serialize(p.Value)));
            return text.TrimEnd() + newline + newline + "[[" + type + "]]" + newline + body + newline + key + " = " + encoded + newline;
        }
        var b = blocks[0]; var old = Value(b.Body, key);
        var bodyText = b.Body;
        if (old == null) bodyText = bodyText.TrimEnd() + newline + key + " = " + encoded + newline + newline;
        else bodyText = Regex.Replace(bodyText, @"(?m)^([ \t]*" + Regex.Escape(key) + @"[ \t]*=)[^\r\n]*", m => {
            var comment = m.Value.IndexOf('#');
            return m.Groups[1].Value + " " + encoded + (comment < 0 ? "" : " " + m.Value[comment..]);
        });
        return text[..b.BodyStart] + bodyText + text[b.End..];
    }
    private static void Edit(string engineDirectory, bool enabled, string? pack)
    {
        var engine = Path.GetFullPath(engineDirectory);
        if (!File.Exists(Path.Combine(engine, "babel-recomp.exe"))) throw new FileNotFoundException("Select the built Babel engine first.");
        var manifest = Path.Combine(engine, "mods/preloaded/packages/iog.enhancements/1.0.0/manifest.toml");
        if (!File.Exists(manifest)) throw new InvalidDataException("This engine has no compatible MSU-1 mod catalog.");
        var path = StatePath(engine); Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        using var gate = new FileStream(path + ".companion-lock", FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        var original = File.Exists(path) ? ReadBytes(path) : (Array.Empty<byte>(), "format_version = 1\n", false);
        var text = original.Item2; var newline = text.Contains("\r\n") ? "\r\n" : "\n";
        var packages = Blocks(text).Where(b => Target(b, "package", PackageKey)).ToArray();
        if (packages.Length > 1 || (packages.Length == 1 && Value(packages[0].Body, "version") != "1.0.0"))
            throw new InvalidDataException("Unexpected enhancement-package version; review it in Babel tools.");
        if (enabled) text = Upsert(text, "package", PackageKey, "version", "\"1.0.0\"", newline);
        text = Upsert(text, "feature", FeatureKey, "enabled", enabled ? "true" : "false", newline);
        if (enabled) text = Upsert(text, "resource", ResourceKey, "path", JsonSerializer.Serialize(pack), newline);
        var current = File.Exists(path) ? File.ReadAllBytes(path) : Array.Empty<byte>();
        if (!current.SequenceEqual(original.Item1)) throw new IOException("Mod settings changed during import; reload the soundtrack window.");
        var temp = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try {
            using (var file = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None)) {
                var encoding = new UTF8Encoding(original.Item3); var bytes = encoding.GetPreamble().Concat(encoding.GetBytes(text)).ToArray();
                file.Write(bytes); file.Flush(true);
            }
            File.Move(temp, path, true);
        } finally { if (File.Exists(temp)) File.Delete(temp); }
    }
}
