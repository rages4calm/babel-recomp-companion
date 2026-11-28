using System.Text;

/// <summary>
/// The launcher's Language choice: synthetic ROM-shaped files (zeros plus an internal title, no game data)
/// identified by the game's own header test, and the iog.languages state the game reads.
/// </summary>
internal static class LanguageRomTests
{
    /// <summary>A 64 KiB file of zeros whose internal title at $FFC0 is <paramref name="title"/>.</summary>
    private static string Synthetic(string dir, string name, string title, bool copierHeader = false, int size = 0x10000)
    {
        var bytes = new byte[size + (copierHeader ? 0x200 : 0)];
        Encoding.ASCII.GetBytes(title).CopyTo(bytes, (copierHeader ? 0x200 : 0) + 0xFFC0);
        var path = Path.Combine(dir, name); Directory.CreateDirectory(Path.GetDirectoryName(path)!); File.WriteAllBytes(path, bytes); return path;
    }

    internal static void Run()
    {
        var root = Path.Combine(Path.GetTempPath(), "GaiaLanguage-tests-" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(root);
        int checks = 0;
        void Check(bool condition, string name) { if (!condition) throw new Exception(name); checks++; }
        void Throws<T>(Action action, string name) where T : Exception { try { action(); } catch (T) { checks++; return; } throw new Exception(name); }
        try {
            var roms = Path.Combine(root, "owner's roms + extras");   // an apostrophe and a plus: JSON would escape them as \u, which the game cannot read
            var es = Synthetic(roms, "Illusion of Time (S).sfc", "ILLUSION OF TIME SPN");
            var fr = Synthetic(roms, "Illusion of Time (F).smc", "ILLUSION OF TIME FRA", copierHeader: true);
            var de = Synthetic(roms, "Illusion of Time (G).sfc", "ILLUSION OF TIME GRM");
            var it = Synthetic(roms, "italian.sfc", "ILLUSION OF TIME ITA");
            var usa = Synthetic(roms, "Illusion of Gaia (USA).sfc", "ILLUSION OF GAIA USA ");
            var other = Synthetic(roms, "other.sfc", "SUPER MARIOWORLD     ");
            // 512 extra bytes are a copier header, so a title at the bare $FFC0 is in the wrong place (the game reads $101C0).
            var headerless = Synthetic(roms, "shifted.smc", "ILLUSION OF TIME SPN", copierHeader: false, size: 0x10000 + 0x200);
            var tiny = Path.Combine(roms, "tiny.sfc"); File.WriteAllBytes(tiny, new byte[0x8000]);
            var text = Path.Combine(roms, "notes.sfc"); File.WriteAllText(text, "not a rom");

            Check(NativeModSettings.IdentifyLanguageRom(es).Code == "es", "Spanish header identified");
            Check(NativeModSettings.IdentifyLanguageRom(fr).Code == "fr", "French header identified behind a 512-byte copier header");
            Check(NativeModSettings.IdentifyLanguageRom(de).Code == "de", "German header identified");
            Check(NativeModSettings.IdentifyLanguageRom(es).Message.Contains("Spain") && NativeModSettings.IdentifyLanguageRom(es).Message.Contains("Español"), "verdict names release and language");
            Check(NativeModSettings.IdentifyLanguageRom(it).Code == null, "Italian has no slot in the Languages package");
            Check(NativeModSettings.IdentifyLanguageRom(usa) is { Code: null } u && u.Message.Contains("Illusion of Gaia ROM, not a European one"), "USA ROM rejected with its own message");
            foreach (var wrong in new[] { other, headerless, tiny, text, Path.Combine(roms, "missing.sfc") })
                Check(NativeModSettings.IdentifyLanguageRom(wrong) is { Code: null, Message.Length: > 0 }, "rejected: " + Path.GetFileName(wrong));

            var game = Path.Combine(root, "game"); Directory.CreateDirectory(game);
            File.WriteAllText(Path.Combine(game, "babel-recomp.exe"), "synthetic fixture - never executed");
            var state = Path.Combine(game, "mods/preloaded/state.toml"); Directory.CreateDirectory(Path.GetDirectoryName(state)!);
            Check(NativeModSettings.ReadLanguage(game) is { Selected: "original", Found.Count: 0 }, "no state, no ROMs: English, nothing found");
            Throws<InvalidOperationException>(() => NativeModSettings.ApplyLanguage(game, "es"), "Spanish without a ROM refused");
            Check(!File.Exists(state), "refusal writes nothing");
            Throws<InvalidDataException>(() => NativeModSettings.ApplyLanguage(game, "es", new Dictionary<string,string> { ["es"] = usa }), "a USA ROM is not stored as Spanish");
            Throws<InvalidDataException>(() => NativeModSettings.ApplyLanguage(game, "es", new Dictionary<string,string> { ["es"] = fr }), "a French ROM is not stored as Spanish");
            Throws<ArgumentException>(() => NativeModSettings.ApplyLanguage(game, "it", new Dictionary<string,string>()), "unknown language refused");
            Check(!File.Exists(state), "rejected ROMs write nothing");

            // The game's own state keeps everything else; the language goes in beside it.
            var original = "format_version = 1\r\n\r\n[[package]]\r\nid = \"iog.cheats\"\r\nversion = \"1.0.0\"\r\n\r\n[[feature]]\r\npackage_id = \"iog.cheats\"\r\nid = \"dp\"\r\nenabled = true\r\n";
            File.WriteAllText(state, original);
            NativeModSettings.ApplyLanguage(game, "es", new Dictionary<string,string> { ["es"] = es });
            var saved = File.ReadAllText(state);
            Check(saved.StartsWith(original.TrimEnd()), "existing selections kept");
            Check(saved.Contains("[[package]]\r\nid = \"iog.languages\"\r\nversion = \"1.0.0\""), "package selected");
            Check(saved.Contains("[[feature]]\r\npackage_id = \"iog.languages\"\r\nid = \"language\"\r\nenabled = true"), "feature language enabled");
            Check(saved.Contains("[feature.values]\r\ncode = \"es\""), "option code = es (manifest option id)");
            var quoted = "\"" + es.Replace("\\", "\\\\") + "\"";
            Check(saved.Contains("[[resource]]\r\npackage_id = \"iog.languages\"\r\nfeature_id = \"language\"\r\nid = \"rom_es\"\r\npath = " + quoted),
                "resource rom_es holds the full path in the game's own quoting (no \\u escapes)");
            Check(!saved.Contains("\\u"), "no JSON unicode escapes");
            var read = NativeModSettings.ReadLanguage(game);
            Check(read.Selected == "es" && read.Found.Single() is { Code: "es", InLanguagesFolder: false } f && f.Path == es, "Spanish and its ROM read back");

            // Add French and switch; the Spanish ROM stays chosen.
            NativeModSettings.ApplyLanguage(game, "fr", new Dictionary<string,string> { ["fr"] = fr });
            read = NativeModSettings.ReadLanguage(game); saved = File.ReadAllText(state);
            Check(read.Selected == "fr" && read.Found.Select(x => x.Code).SequenceEqual(new[] { "es", "fr" }), "French selected, both ROMs found");
            Check(System.Text.RegularExpressions.Regex.Matches(saved, "(?m)^id = \"language\"").Count == 1 && System.Text.RegularExpressions.Regex.Matches(saved, "(?m)^code = ").Count == 1, "feature and option updated in place");
            // Switching needs no new ROM when one is stored.
            NativeModSettings.ApplyLanguage(game, "es");
            Check(NativeModSettings.ReadLanguage(game).Selected == "es", "switch back to Spanish with the stored ROM");

            // English turns the feature off, keeps the ROMs, and drops a European language Ctrl+L remembered.
            File.WriteAllText(Path.Combine(game, "language.txt"), "fr\n");
            NativeModSettings.ApplyLanguage(game, "original");
            read = NativeModSettings.ReadLanguage(game); saved = File.ReadAllText(state);
            Check(read.Selected == "original" && saved.Contains("id = \"language\"\r\nenabled = false") && read.Found.Count == 2, "English: feature off, ROMs still chosen");
            Check(!File.Exists(Path.Combine(game, "language.txt")), "language.txt naming French removed so English sticks");
            File.WriteAllText(Path.Combine(game, "language.txt"), "gaia\n");
            NativeModSettings.ApplyLanguage(game, "original");
            Check(File.ReadAllText(Path.Combine(game, "language.txt")) == "gaia\n", "language.txt naming the English retranslation kept");

            // A stored ROM that was moved away no longer counts.
            var moved = es + ".moved"; File.Move(es, moved);
            Check(NativeModSettings.ReadLanguage(game).Found.All(x => x.Code != "es"), "missing Spanish ROM not found");
            Throws<InvalidOperationException>(() => NativeModSettings.ApplyLanguage(game, "es"), "Spanish refused once its ROM is gone");
            File.Move(moved, es);

            // languages/ beside the executable, one folder deep, as the game scans it.
            Synthetic(Path.Combine(game, "languages", "german"), "rom.sfc", "ILLUSION OF TIME GRM");
            Synthetic(Path.Combine(game, "languages"), "readme.sfc", "NOT A ROM AT ALL     ");
            read = NativeModSettings.ReadLanguage(game);
            Check(read.Found.SingleOrDefault(x => x.Code == "de") is { InLanguagesFolder: true }, "German found in languages/ subfolder");
            NativeModSettings.ApplyLanguage(game, "de");
            saved = File.ReadAllText(state);
            Check(NativeModSettings.ReadLanguage(game).Selected == "de" && !saved.Contains("rom_de"), "German from languages/ selected without storing a path");

            // A ROM chosen on the game's own Mods page (it writes [[resource]] after the feature values) is read too.
            File.WriteAllText(state, "format_version = 1\n\n[[package]]\nid = \"iog.languages\"\nversion = \"1.0.0\"\n\n[[feature]]\npackage_id = \"iog.languages\"\nid = \"language\"\nenabled = true\n\n[feature.values]\ncode = \"de\"\n\n[[resource]]\npackage_id = \"iog.languages\"\nfeature_id = \"language\"\nid = \"rom_de\"\npath = " + "\"" + de.Replace("\\", "\\\\") + "\"\n");
            read = NativeModSettings.ReadLanguage(game);
            Check(read.Selected == "de" && read.Found.Single(x => x.Code == "de") is { InLanguagesFolder: false } g && g.Path == de, "game-written selection read; chosen ROM wins over languages/");
            NativeModSettings.ApplyLanguage(game, "de", new Dictionary<string,string> { ["de"] = de });
            Check(System.Text.RegularExpressions.Regex.Matches(File.ReadAllText(state), "id = \"rom_de\"").Count == 1 && !File.ReadAllText(state).Contains("\r\n"), "game-written resource updated in place, LF kept");

            Check(!NativeModSettings.IsEngineRunning(Path.Combine(game, "babel-recomp.exe")), "fixture engine is not running");
            Console.WriteLine($"PASS {checks} language checks (synthetic headers; no game data)");
        } finally { Directory.Delete(root, true); }
    }
}
