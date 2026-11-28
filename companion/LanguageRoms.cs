using System.Text;

/// <summary>
/// The game language, from the player's own official European release (Illusion of Time: Spain,
/// France or Germany), stored the way the iog.languages package and src/iog_i18n.c read it:
/// feature "language" (enabled, value "code") and one [[resource]] rom_es / rom_fr / rom_de per ROM.
/// The launcher reads only the ROM header and stores the path; it never copies ROM data.
/// </summary>
public static partial class NativeModSettings
{
    public sealed record LanguageInfo(string Code, string Name, string Country);
    public static readonly IReadOnlyList<LanguageInfo> Languages = new LanguageInfo[] {
        new("es", "Español", "Spain"), new("fr", "Français", "France"), new("de", "Deutsch", "Germany") };
    /// <summary>A ROM that gives a language: chosen in the launcher (or on the game's Mods page), or found in languages/.</summary>
    public sealed record LanguageRom(string Code, string Path, bool InLanguagesFolder);
    /// <summary>Selected is "original" (English) or a language code; Found has at most one ROM per language.</summary>
    public sealed record LanguageState(string Selected, IReadOnlyList<LanguageRom> Found);
    public sealed record RomCheck(string? Code, string Message);

    private const string LanguagesPackage = "iog.languages", LanguageFeature = "language";
    private static readonly Dictionary<string,string> LanguageKey = new() { ["package_id"] = LanguagesPackage, ["id"] = LanguageFeature };
    private static Dictionary<string,string> RomKey(string code) => new() { ["package_id"] = LanguagesPackage, ["feature_id"] = LanguageFeature, ["id"] = "rom_" + code };
    public static LanguageInfo? Language(string code) => Languages.FirstOrDefault(x => x.Code == code);

    /// <summary>
    /// Which language a ROM gives, by the same test the game uses (IogTextRomLanguage in src/iog_text.c):
    /// a copier header is skipped when the size is a multiple of 32 KiB plus 512 bytes, and the internal
    /// title at $FFC0 must read "ILLUSION OF TIME " followed by SPN, FRA or GRM. Only the header is read.
    /// </summary>
    public static RomCheck IdentifyLanguageRom(string path)
    {
        try {
            var info = new FileInfo(path);
            if (!info.Exists) return new(null, "That file does not exist.");
            if (info.Length > 8 << 20) return new(null, "That file is too large to be a SNES ROM. Choose your Illusion of Time ROM (.sfc or .smc).");
            long offset = info.Length % 0x8000 == 0x200 ? 0x200 : 0;
            if (info.Length - offset < 0x10000) return new(null, "That file is too small to be a SNES ROM. Choose your Illusion of Time ROM (.sfc or .smc).");
            var title = new byte[21];
            using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite)) {
                stream.Position = offset + 0xFFC0;
                stream.ReadExactly(title);
            }
            var text = Encoding.ASCII.GetString(title);
            if (text.StartsWith("ILLUSION OF TIME ", StringComparison.Ordinal)) {
                var code = text.Substring(17, 3) switch { "SPN" => "es", "FRA" => "fr", "GRM" => "de", _ => null };
                if (code != null) {
                    var language = Language(code)!;
                    return new(code, $"Illusion of Time ({language.Country}) ROM verified: {language.Name}.");
                }
                return new(null, "This Illusion of Time ROM is not one of the supported releases. Choose the Spanish, French or German release.");
            }
            if (text.StartsWith("ILLUSION OF GAIA", StringComparison.Ordinal))
                return new(null, "This is an Illusion of Gaia ROM, not a European one. Choose your Illusion of Time ROM from Spain, France or Germany.");
            return new(null, "This file is not an Illusion of Time ROM. Choose your own copy of the official release from Spain, France or Germany (.sfc or .smc).");
        } catch (Exception error) when (error is IOException or UnauthorizedAccessException or ArgumentException or NotSupportedException) {
            return new(null, "Cannot read that file: " + error.Message);
        }
    }

    /// <summary>ROMs in <paramref name="dir"/> and one level of folders below it, as the game scans languages/.</summary>
    private static IEnumerable<string> RomFiles(string dir, int depth)
    {
        if (!Directory.Exists(dir)) yield break;
        string[] entries;
        try { entries = Directory.GetFileSystemEntries(dir); } catch (Exception error) when (error is IOException or UnauthorizedAccessException) { yield break; }
        foreach (var entry in entries.OrderBy(x => x, StringComparer.Ordinal)) {
            if (Path.GetFileName(entry).StartsWith('.')) continue;
            if (Directory.Exists(entry)) { if (depth > 0) foreach (var nested in RomFiles(entry, depth - 1)) yield return nested; }
            else if (Path.GetExtension(entry).ToLowerInvariant() is ".sfc" or ".smc") yield return entry;
        }
    }

    public static LanguageState ReadLanguage(string engineDirectory)
    {
        var bytes = ReadBounded(StatePath(engineDirectory)); var text = bytes == null ? "format_version = 1\n" : Decode(bytes);
        var feature = Find(text, "feature", LanguageKey);
        var code = feature == null ? null : Value(SplitValues(feature.Body).Values, "code");
        var selected = Enabled(feature) && Language(code ?? "es") != null ? code ?? "es" : "original";   // the manifest's default is es
        var found = new List<LanguageRom>();
        // The game's order: ROMs chosen on the Mods page first, then languages/ beside the executable.
        foreach (var language in Languages) {
            var block = Find(text, "resource", RomKey(language.Code));
            var path = block == null ? null : Value(block.Body, "path");
            if (path is { Length: > 0 } && IdentifyLanguageRom(path).Code == language.Code) found.Add(new(language.Code, path, false));
        }
        foreach (var path in RomFiles(Path.Combine(Path.GetFullPath(engineDirectory), "languages"), 1))
            if (IdentifyLanguageRom(path).Code is { } rom && found.All(x => x.Code != rom)) found.Add(new(rom, path, true));
        return new(selected, found.OrderBy(x => Languages.ToList().FindIndex(l => l.Code == x.Code)).ToList());
    }

    /// <summary>The game's own TOML string quoting (quote_toml in mod_runtime.cpp): it reads no \u escapes.</summary>
    private static string QuoteToml(string value)
    {
        var quoted = new StringBuilder("\"");
        foreach (var c in value) quoted.Append(c switch { '\\' => "\\\\", '"' => "\\\"", '\n' => "\\n", '\r' => "\\r", '\t' => "\\t", _ => c.ToString() });
        return quoted.Append('"').ToString();
    }

    /// <summary>Throws with a message for the player when <see cref="ApplyLanguage"/> would refuse; writes nothing.</summary>
    public static void CheckLanguage(string engineDirectory, string code, IReadOnlyDictionary<string,string> chosenRoms)
    {
        if (code != "original" && Language(code) == null) throw new ArgumentException("Unknown language.");
        var executable = Path.Combine(Path.GetFullPath(engineDirectory), "babel-recomp.exe");
        if (!File.Exists(executable)) throw new FileNotFoundException("Set the game program on the Game page first.");
        if (IsEngineRunning(executable)) throw new InvalidOperationException("Close the game before changing its language here. While you play, Ctrl+L or the in-game settings switch language.");
        foreach (var (rom, path) in chosenRoms) {
            if (Language(rom) == null) throw new ArgumentException("Unknown language.");
            if (!Path.IsPathFullyQualified(path)) throw new ArgumentException("Choose the ROM with its full path.");
            var check = IdentifyLanguageRom(path);
            if (check.Code != rom) throw new InvalidDataException(check.Code == null ? check.Message : "That ROM is for " + Language(check.Code)!.Name + ", not " + Language(rom)!.Name + ".");
        }
        if (code != "original" && !chosenRoms.ContainsKey(code) && ReadLanguage(engineDirectory).Found.All(x => x.Code != code)) {
            var language = Language(code)!;
            throw new InvalidOperationException($"Choose your Illusion of Time ({language.Country}) ROM first: {language.Name} comes from it.");
        }
    }

    /// <summary>
    /// Store the language and any newly chosen ROMs (code to full path). Each ROM is checked again and must give the
    /// language it is stored for; a language needs a ROM, chosen now, before, or in languages/.
    /// </summary>
    public static void ApplyLanguage(string engineDirectory, string code, IReadOnlyDictionary<string,string>? chosenRoms = null)
    {
        chosenRoms ??= new Dictionary<string,string>();
        CheckLanguage(engineDirectory, code, chosenRoms);
        Edit(engineDirectory, (text, newline) => {
            text = Upsert(text, "package", new Dictionary<string,string> { ["id"] = LanguagesPackage }, "version", "\"1.0.0\"", newline);
            text = Upsert(text, "feature", LanguageKey, "enabled", code == "original" ? "false" : "true", newline);
            if (code != "original") text = Upsert(text, "feature", LanguageKey, "code", QuoteToml(code), newline, nested: true);
            foreach (var (rom, path) in chosenRoms.OrderBy(x => x.Key, StringComparer.Ordinal))
                text = Upsert(text, "resource", RomKey(rom), "path", QuoteToml(Path.GetFullPath(path)), newline);
            return text;
        });
        // English from here must not be overridden by a European language Ctrl+L left in language.txt (read
        // while the Mods feature is off). Without the file the game starts in its default English text.
        var remembered = Path.Combine(Path.GetFullPath(engineDirectory), "language.txt");
        if (code == "original" && File.Exists(remembered) && File.ReadAllText(remembered).Trim() is "es" or "fr" or "de" or "it")
            File.Delete(remembered);
    }
}
