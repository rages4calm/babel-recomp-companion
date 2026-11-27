using System.Text;

/// <summary>keybinds.ini / config.ini input editing: round trips, names, conflicts, presets, profiles.</summary>
internal static class InputBindingsTests
{
    private static int checks;
    private static string lastFile = "";
    private static void Check(bool yes, string name) { if (!yes) throw new Exception("input: " + name + "\n" + lastFile); checks++; }
    private static void Throws<T>(Action a, string name) where T : Exception { try { a(); } catch (T) { checks++; return; } throw new Exception("input: " + name); }

    private const string Keybinds =
        "# SNES Controller Keybinds\r\n# Edit values to customize. Restart the game to apply.\r\n#\r\n\r\n" +
        "[player1]\r\na       = X\r\nb       = Z\r\nx       = S\r\ny       = A\r\nl       = C\r\nr       = V\r\nstart   = Return\r\nselect  = Right Shift\r\nup      = Up\r\ndown    = Down\r\nleft    = Left\r\nright   = Right\r\nturbo   = keep me\r\n\r\n" +
        "[player2]\r\na = X\r\n# hand comment\r\nb = Z\r\nstart = enter\r\n\r\n[player3]\r\na = None\r\n";
    private const string Config =
        "[General]\r\nSkipLauncher = 0\r\n[KeyMap]\r\n# system shortcuts\r\nFullscreen = Alt+Return\r\nPause = Shift+p  # keep this comment\r\nPauseDimmed = p\r\nTurbo = Tab\r\n" +
        "SaveStateMenu = F11\r\nRewind = F12\r\nLoad =      F1,     F2,     F3,     F4,     F5,     F6,     F7,     F8,     F9,     F10\r\n" +
        "Save = Shift+F1,Shift+F2,Shift+F3,Shift+F4,Shift+F5,Shift+F6,Shift+F7,Shift+F8,Shift+F9,Shift+F10\r\nCustomThing = 1\r\n\r\n" +
        "[GamepadMap]\r\nEnableGamepad1 = true\r\nEnableGamepad2 = true\r\nControls =   DpadUp, DpadDown, DpadLeft, DpadRight, Back, Start, B, A, Y, X, Lb, Rb\r\nGamepadDeadzone = 3277\r\n\r\n" +
        "[Controller]\r\nSourceP1 = 2\r\nSourceP2 = 2\r\n";

    internal static int Run(string root)
    {
        checks = 0;
        Directory.CreateDirectory(root);
        Names();
        RoundTrip(Path.Combine(root, "roundtrip"));
        Conflicts();
        Presets();
        Profiles();
        Missing(Path.Combine(root, "missing"));
        return checks;
    }

    private static void Names()
    {
        foreach (var k in KeyCatalog.All) {
            Check(KeyCatalog.ByName(k.Name) == k, "by name " + k.Name);
            Check(KeyCatalog.NormalizeBinding(k.Name) == k.Name && KeyCatalog.NormalizeBinding(k.Name.ToLowerInvariant()) == k.Name, "normalize " + k.Name);
            Check(KeyCatalog.FromScan(k.Set1, k.Extended, k.Vk) == k, $"physical key {k.Name} (scan {k.Set1:X2}{(k.Extended ? " ext" : "")})");
            if (k.Name != "Keypad Enter") Check(KeyCatalog.FromVk(k.Vk) == k, "virtual key " + k.Name);
            if (k.Hotkey != null) {
                Check(Chord.Normalize(k.Hotkey) == k.Hotkey && Chord.Key(k.Hotkey) == k, "hotkey " + k.Name);
                foreach (var mod in new[] { "Shift+", "Ctrl+", "Alt+", "Shift+Ctrl+" })
                    Check(Chord.Normalize(mod + k.Hotkey) == mod + k.Hotkey && Chord.Key(mod + k.Hotkey) == k, "chord " + mod + k.Name);
                Check(!k.Hotkey.Contains(',') && !k.Hotkey.Contains('#'), "hotkey name survives config.ini " + k.Name);
            }
        }
        Check(KeyCatalog.All.Select(k => k.Name).Distinct().Count() == KeyCatalog.All.Count && KeyCatalog.All.Select(k => k.Scancode).Distinct().Count() == KeyCatalog.All.Count, "unique names and scancodes");
        Check(KeyCatalog.All.GroupBy(k => (k.Set1, k.Extended)).All(g => g.Count() == 1 || g.All(k => k.Name is "Pause" or "Numlock")), "physical positions unique");
        // VK fallback for generic modifiers: the scan code says which side.
        Check(KeyCatalog.FromScan(0x36, false, 0x10)!.Name == "Right Shift" && KeyCatalog.FromScan(0x2A, false, 0x10)!.Name == "Left Shift", "generic shift side");
        Check(KeyCatalog.FromScan(0x1D, true, 0x11)!.Name == "Right Ctrl" && KeyCatalog.FromScan(0x1D, false, 0x11)!.Name == "Left Ctrl", "generic ctrl side");
        Check(KeyCatalog.FromScan(0x45, false, 0x13)!.Name == "Pause" && KeyCatalog.FromScan(0x45, true, 0x90)!.Name == "Numlock", "pause vs num lock");
        Check(KeyCatalog.NormalizeBinding("None") == "None" && KeyCatalog.NormalizeBinding("") == "None" && KeyCatalog.NormalizeBinding("mouse3") == "Mouse3", "None and mouse");
        Check(KeyCatalog.NormalizeBinding("enter") == "Return" && KeyCatalog.NormalizeBinding("rshift") == "Right Shift" && KeyCatalog.NormalizeBinding("bogus") == null, "runner aliases");
        Check(Chord.Normalize("Ctrl+r") == "Ctrl+r" && Chord.Normalize("ctrl+R") == "Ctrl+r" && Chord.Normalize("Keypad +") == "Keypad +" && Chord.Normalize("Shift+Keypad +") == "Shift+Keypad +", "chord spelling");
        Check(Chord.Normalize("Enter") == "Return" && Chord.Normalize(",") == null && Chord.Normalize("Shift+") == null, "chord aliases and reserved");
        Check(Chord.Label("Alt+Return") == "Alt + Enter" && Chord.Label("Keypad +") == "Keypad +", "chord labels");
        Check(PadCatalog.Normalize("lb") == "L1" && PadCatalog.Normalize("L2 + start") == "L2+Start" && PadCatalog.Normalize("Q") == null && PadCatalog.Normalize("A+A") == null && PadCatalog.Normalize("") == "", "pad names");
        Check(PadCatalog.Label("A", PadStyle.Xbox) == "A" && PadCatalog.Label("A", PadStyle.Nintendo) == "B" && PadCatalog.Label("A", PadStyle.PlayStation) == "Cross", "pad glyph styles by position");
        Check(PadCatalog.Label("L2+Start", PadStyle.Xbox) == "LT + Menu" && PadCatalog.Label("L2+Start", PadStyle.Nintendo) == "ZL + +", "chord glyphs");
    }

    /// <summary>--input-names TSV | --input-e2e DIR EXPECT; false when args name neither.</summary>
    internal static bool Command(string[] args)
    {
        if (args.Length == 2 && args[0] == "--input-names") { WriteNames(args[1]); return true; }
        if (args.Length == 1 && args[0] == "--input-tests") {
            var root = Path.Combine(Path.GetTempPath(), "GaiaCompanion-input-" + Guid.NewGuid().ToString("N"));
            try { Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { passed = true, checks = Run(root) })); }
            finally { if (Directory.Exists(root)) Directory.Delete(root, true); }
            return true;
        }
        if (args.Length == 3 && args[0] == "--input-e2e") { EndToEnd(args[1], args[2]); return true; }
        return false;
    }
    /// <summary>The TSV scripts/test_input_bindings.c checks against SDL itself.</summary>
    internal static void WriteNames(string path) =>
        File.WriteAllLines(path, KeyCatalog.All.Select(k => $"{k.Scancode}\t{k.Name}\t{k.Hotkey ?? ""}"));

    private static void RoundTrip(string dir)
    {
        Directory.CreateDirectory(dir);
        var files = new InputFiles(dir);
        File.WriteAllText(files.KeybindsPath, Keybinds); File.WriteAllText(files.ConfigPath, Config);
        var warnings = new List<string>();
        var loaded = files.Load(warnings);
        Check(warnings.Count == 0, "clean load: " + string.Join(";", warnings));
        Check(loaded.Keys[0][(int)SnesButton.Select] == "Right Shift" && loaded.Keys[1][(int)SnesButton.Start] == "Return", "keybinds read incl. alias");
        Check(loaded.Keys[1][(int)SnesButton.L] == "C", "missing line keeps runner default");
        Check(loaded.Pad[0][(int)SnesButton.L] == "L1" && loaded.Pad[0][(int)SnesButton.A] == "B" && loaded.Pad[1][(int)SnesButton.B] == "A", "controls read; P2 default");
        Check(loaded.Source[0] == 2 && loaded.Device(0) == 1, "source read");
        Check(loaded.Hotkeys["Pause"].SequenceEqual(new[] { "Shift+p" }) && loaded.Hotkeys["Load[6]"].SequenceEqual(new[] { "F7" }), "hotkeys read");
        Check(loaded.Hotkeys["WindowBigger"].Count == 0 && loaded.PadHotkeys["SettingsMenu"] == "L2+R3", "absent lines are engine defaults");
        Check(files.Save(loaded, loaded.Clone()) == 0 && File.ReadAllText(files.KeybindsPath) == Keybinds && File.ReadAllText(files.ConfigPath) == Config, "no-op save writes nothing");

        var edited = loaded.Clone();
        edited.Keys[0][(int)SnesButton.A] = "J"; edited.Keys[1][(int)SnesButton.Y] = "Keypad 4";
        edited.Pad[0][(int)SnesButton.L] = "L2"; edited.Pad[1][(int)SnesButton.R] = "L1+Back";
        edited.Hotkeys["Pause"] = new() { "l", "Pause" }; edited.Hotkeys["Load[6]"] = new() { "F12" }; edited.Hotkeys["Turbo"] = new();
        edited.PadHotkeys["SettingsMenu"] = "R3"; edited.PadHotkeys["SaveStateMenu"] = ""; edited.PadHotkeys["Load[0]"] = "L2+Y";
        edited.SetDevice(0, 0); edited.SetDevice(1, 3);
        // Another program changes a line after the editor loaded: kept, since it was not edited here.
        File.WriteAllText(files.ConfigPath, Config.Replace("Rewind = F12", "Rewind = F9").Replace("CustomThing = 1", "CustomThing = 2"));
        Check(files.Save(loaded, edited) > 0, "save");
        var k = File.ReadAllText(files.KeybindsPath); var c = File.ReadAllText(files.ConfigPath); lastFile = k + "\n----\n" + c;
        Check(k.Contains("a       = J\r\n") && k.Contains("turbo   = keep me\r\n") && k.Contains("# hand comment\r\n") && k.Contains("[player3]\r\na = None\r\n"), "keybinds edit preserves the rest");
        Check(k.Contains("[player2]\r\na = X\r\n# hand comment\r\nb = Z\r\nstart = enter\r\ny       = Keypad 4\r\n\r\n[player3]"), "new keybinds line goes inside its section, before the blank line");
        Check(k.Replace("a       = J", "a       = X").Replace("y       = Keypad 4\r\n", "") == Keybinds, "keybinds: only the edited lines differ");
        Check(c.Contains("Pause = l, Pause  # keep this comment\r\n") && c.Contains("Turbo = None\r\n") && c.Contains("CustomThing = 2\r\n") && c.Contains("Rewind = F9\r\n"), "keymap edits; inline comment; external edit kept");
        Check(c.Contains("Load =      F1,F2,F3,F4,F5,F6,F12,F8,F9,F10\r\n"), "save slot positional, alignment after = kept");
        Check(c.Contains("Controls =   DpadUp, DpadDown, DpadLeft, DpadRight, Back, Start, B, A, Y, X, L2, R1\r\n"), "player 1 controls line keeps alignment");
        Check(c.Contains("ControlsP2 = DpadUp, DpadDown, DpadLeft, DpadRight, Back, Start, B, A, Y, X, L1, L1+Back\r\n"), "player 2 controls line added");
        Check(c.Contains("SettingsMenu = R3\r\n") && c.Contains("SaveStateMenu = \r\n") && c.Contains("Load = L2+Y\r\n"), "pad hotkeys written; cleared is empty");
        Check(c.Contains("SourceP1 = 1\r\n") && c.Contains("SourceP2 = 0\r\n") && c.Contains("EnableGamepad2 = false\r\n") && c.Contains("EnableGamepad1 = true\r\n"), "devices written");
        Check(c.IndexOf("ControlsP2") < c.IndexOf("[Controller]") && c.IndexOf("ControlsP2") > c.IndexOf("[GamepadMap]"), "new [GamepadMap] key inside its section");
        var again = files.Load();
        Check(InputProfile.Export(again) == InputProfile.Export(Merge(edited, "Rewind", "F9")), "reload equals what was saved");
        Check(!Directory.EnumerateFiles(dir, "*.tmp").Any(), "atomic write leaves no temporary files");
        File.WriteAllText(files.ConfigPath, Config + "[KeyMap]\r\nPause = p\r\n");
        Throws<InvalidDataException>(() => files.Load(), "duplicate managed key refused");
        File.WriteAllText(files.KeybindsPath, "[player1]\na = Banana\n"); File.WriteAllText(files.ConfigPath, Config);
        var w = new List<string>(); var bad = files.Load(w);
        Check(bad.Keys[0][0] == "None" && w.Count == 1, "unknown key name reported, read as unbound like the runner");
        Check(File.ReadAllText(files.KeybindsPath) == "[player1]\na = Banana\n", "loading never writes");
    }
    private static InputModel Merge(InputModel m, string id, string chord) { var x = m.Clone(); x.Hotkeys[id] = new() { chord }; return x; }

    private static void Missing(string dir)
    {
        Directory.CreateDirectory(dir);
        var files = new InputFiles(dir);
        var loaded = files.Load();
        Check(InputProfile.Export(loaded) == InputProfile.Export(InputModel.Defaults()), "no files: game defaults");
        var edited = loaded.Clone(); edited.Keys[0][(int)SnesButton.B] = "K"; edited.Hotkeys["Screenshot"] = new() { "F9" };
        files.Save(loaded, edited);
        Check(File.ReadAllText(files.KeybindsPath).Replace("\r\n", "\n") == "[player1]\nb       = K\n", "keybinds created with only the edit");
        Check(File.ReadAllText(files.ConfigPath).Replace("\r\n", "\n") == "[KeyMap]\nScreenshot = F9\n", "config created with only the edit");
        Check(files.Load().Keys[0][(int)SnesButton.A] == "X", "the rest stay engine defaults");
    }

    private static void Conflicts()
    {
        var m = InputModel.Defaults();
        var a = BindingSlot.Key(0, SnesButton.A);
        Check(InputRules.Conflicts(m, a, "X").Count == 0, "own binding is no conflict");
        var hits = InputRules.Conflicts(m, a, "Z");
        Check(hits.SequenceEqual(new[] { BindingSlot.Key(0, SnesButton.B) }), "Z belongs to player 1 B only (player 2 is not on the keyboard)");
        var swap = m.Clone(); InputRules.Swap(swap, a, "Z");
        Check(swap.Keys[0][(int)SnesButton.A] == "Z" && swap.Keys[0][(int)SnesButton.B] == "X", "swap");
        var replace = m.Clone(); InputRules.Replace(replace, a, "Z");
        Check(replace.Keys[0][(int)SnesButton.A] == "Z" && replace.Keys[0][(int)SnesButton.B] == "None", "replace");
        var tab = InputRules.Conflicts(m, a, "Tab");
        Check(tab.SequenceEqual(new[] { BindingSlot.Hotkey("Turbo") }) && !InputRules.SameFamily(tab[0], a), "key vs unmodified hotkey; no swap across families");
        InputRules.Replace(replace, a, "Tab");
        Check(replace.Hotkeys["Turbo"].Count == 0 && replace.Keys[0][0] == "Tab", "replace takes the key from the shortcut");
        Check(InputRules.Conflicts(m, a, "P").SequenceEqual(new[] { BindingSlot.Hotkey("PauseDimmed") }), "Shift+p is a different chord from P");
        var pause = BindingSlot.Hotkey("Pause");
        Check(InputRules.Conflicts(m, pause, "Shift+F1").SequenceEqual(new[] { BindingSlot.Hotkey("Save[0]") }), "hotkey vs hotkey");
        var hs = m.Clone(); InputRules.Swap(hs, pause, "Shift+F1");
        Check(hs.Hotkeys["Pause"].SequenceEqual(new[] { "Shift+F1" }) && hs.Hotkeys["Save[0]"].SequenceEqual(new[] { "Shift+p" }), "hotkey swap");
        Check(InputRules.Conflicts(m, BindingSlot.Hotkey("Screenshot"), "x").SequenceEqual(new[] { BindingSlot.Key(0, SnesButton.A) }), "a hotkey on x meets player 1 A only (player 2 is not on the keyboard)");
        var two = m.Clone(); two.SetDevice(1, 0);
        Check(InputRules.SharedKeyboardKeys(m).Count == 0 && InputRules.SharedKeyboardKeys(two).Count == 12, "shared keyboard warning only when both read it");
        Check(InputRules.Conflicts(two, BindingSlot.Hotkey("Screenshot"), "x").Count == 2, "a hotkey on x meets both keyboard players");
        Check(InputRules.Conflicts(two, a, "Z").Count == 1, "players' own keys do not conflict with the other player's");
        // Controller.
        var pa = BindingSlot.PadButton(0, SnesButton.A);
        Check(InputRules.Conflicts(m, pa, "A").SequenceEqual(new[] { BindingSlot.PadButton(0, SnesButton.B) }), "pad conflict within a player");
        Check(InputRules.Conflicts(m, BindingSlot.PadButton(1, SnesButton.A), "L2+Start").Count == 0, "player 2's pad has no shortcuts");
        Check(InputRules.Conflicts(m, pa, "L2+Start").SequenceEqual(new[] { BindingSlot.PadHotkey("SaveStateMenu") }), "pad chord meets a shortcut");
        var ps = m.Clone(); InputRules.Swap(ps, pa, "A");
        Check(ps.Pad[0][(int)SnesButton.A] == "A" && ps.Pad[0][(int)SnesButton.B] == "B", "pad swap");
        Check(InputRules.Conflicts(m, BindingSlot.PadHotkey("Rewind"), "Start").SequenceEqual(new[] { BindingSlot.PadButton(0, SnesButton.Start) }), "pad shortcut on an SNES button");
        var add = m.Clone(); InputRules.Set(add, pause, "F5", 1);
        Check(add.Hotkeys["Pause"].SequenceEqual(new[] { "Shift+p", "F5" }), "add a second key to a shortcut");
        InputRules.Set(add, BindingSlot.Hotkey("Load[0]"), "F5", 3);
        Check(add.Hotkeys["Load[0]"].SequenceEqual(new[] { "F5" }), "a save slot holds one key");
        // The editor once asked for player -1 (a TabControl's index before its handle exists).
        Throws<ArgumentOutOfRangeException>(() => InputModel.Defaults().Device(-1), "device of a page that is not a player");
        var dev = InputModel.Defaults();
        foreach (var (d, src, pad) in new[] { (0, 1, true), (1, 2, true), (2, 1, false), (3, 0, false) }) {
            dev.SetDevice(0, d); Check(dev.Source[0] == src && dev.Gamepad[0] == pad && dev.Device(0) == d, "device " + d);
        }
    }

    private static void Presets()
    {
        foreach (var p in InputPresets.Keyboard.Concat(InputPresets.Controller)) {
            Check(p.Values.Length == 12 && p.Values.Distinct().Count() == 12, "preset distinct " + p.Name);
            var m = InputModel.Defaults(); InputPresets.Apply(m, 0, p);
            if (p.Kind == "key") {
                Check(p.Values.All(v => KeyCatalog.NormalizeBinding(v) == v), "preset keys valid " + p.Name);
                Check(Enumerable.Range(0, 12).All(b => InputRules.Conflicts(m, BindingSlot.Key(0, (SnesButton)b), m.Keys[0][b]).Count == 0), "keyboard preset clashes with no default shortcut " + p.Name);
            } else {
                Check(p.Values.All(v => PadCatalog.Normalize(v) == v), "preset buttons valid " + p.Name);
                Check(Enumerable.Range(0, 12).All(b => InputRules.Conflicts(m, BindingSlot.PadButton(0, (SnesButton)b), m.Pad[0][b]).Count == 0), "pad preset self-consistent " + p.Name);
            }
        }
        Check(InputPresets.Keyboard[0].Values.SequenceEqual(InputModel.DefaultKeys) && InputPresets.Controller[0].Values.SequenceEqual(InputModel.DefaultPad), "first presets are the game's defaults");
        var two = InputModel.Defaults(); two.SetDevice(1, 0); InputPresets.Apply(two, 1, InputPresets.Keyboard[3]);
        Check(InputRules.SharedKeyboardKeys(two).Count == 0, "numpad preset shares nothing with player 1 defaults");
    }

    private static void Profiles()
    {
        var m = InputModel.Defaults(); m.Keys[0][0] = "Mouse2"; m.Pad[1][3] = "L2+Y"; m.Hotkeys["Pause"] = new() { "l", "Ctrl+p" }; m.PadHotkeys["Rewind"] = ""; m.SetDevice(1, 2);
        var json = InputProfile.Export(m);
        Check(InputProfile.Export(InputProfile.Import(json, InputModel.Defaults())) == json, "profile round trip");
        Throws<InvalidDataException>(() => InputProfile.Import(json.Replace("\"Mouse2\"", "\"Banana\""), m), "profile rejects unknown key");
        Throws<InvalidDataException>(() => InputProfile.Import("{\"format\":\"other\"}", m), "profile rejects other files");
        var partial = InputProfile.Import("{\"format\":\"" + InputProfile.Format + "\",\"version\":1,\"hotkeys\":{\"Turbo\":[\"Space\"]}}", m);
        Check(partial.Hotkeys["Turbo"].SequenceEqual(new[] { "Space" }) && partial.Keys[0][0] == "Mouse2", "partial profile changes only what it names");
    }

    /// <summary>
    /// End to end, part 1: edit a scratch install's files the way the editor does
    /// (Load, InputRules with Swap/Replace, Save) and write the expectations the
    /// runner-side fixture and the game probe check. Prints what changed.
    /// </summary>
    internal static void EndToEnd(string dir, string expectPath)
    {
        var files = new InputFiles(dir);
        var before = files.Load(); var m = before.Clone();
        m.SetDevice(0, 0); m.SetDevice(1, 0);                                      // both players: keyboard and controller
        InputPresets.Apply(m, 0, InputPresets.Keyboard[1]);                         // WASD + JKL
        InputPresets.Apply(m, 1, InputPresets.Keyboard[3]);                         // numpad for player 2
        InputRules.Swap(m, BindingSlot.Key(0, SnesButton.Select), "Right Shift");   // no conflict
        InputRules.Replace(m, BindingSlot.Key(0, SnesButton.R), "Tab");             // takes Tab from Turbo
        InputRules.Set(m, BindingSlot.Hotkey("Turbo"), "Backspace");
        InputRules.Set(m, BindingSlot.Hotkey("Pause"), "Pause", 1);                 // a second key for Pause
        InputRules.Swap(m, BindingSlot.Hotkey("Rewind"), "F7");                     // swap with Load[6]: slot 7 gets F12
        InputRules.Set(m, BindingSlot.Hotkey("SettingsMenu"), "Ctrl+Escape");
        InputPresets.Apply(m, 0, InputPresets.Controller[2]);                       // L/R on the triggers
        InputRules.Swap(m, BindingSlot.PadButton(0, SnesButton.Start), "Back");     // Start <-> Select on the pad
        InputRules.Set(m, BindingSlot.PadButton(1, SnesButton.A), "R3");
        InputRules.Set(m, BindingSlot.PadHotkey("SettingsMenu"), "L2+Y");
        InputRules.Set(m, BindingSlot.PadHotkey("Companion"), "");                  // no controller shortcut
        int written = files.Save(before, m);
        var after = files.Load();
        if (InputProfile.Export(after) != InputProfile.Export(m)) throw new Exception("e2e: files do not read back as edited");
        var e = new StringBuilder();
        for (int p = 0; p < 2; p++)
            for (int b = 0; b < 12; b++) e.AppendLine($"key {p + 1} {InputModel.IniNames[b]} {m.Keys[p][b]}");
        e.AppendLine("hotkey Turbo Backspace").AppendLine("hotkey Pause Pause").AppendLine("hotkey Pause p Shift")
         .AppendLine("hotkey Rewind F7").AppendLine("hotkey Load[6] F12").AppendLine("hotkey SettingsMenu Escape Ctrl")
         .AppendLine("hotkey Save[0] F1 Shift").AppendLine("source 0 1").AppendLine("source 1 1");
        // Synthetic pads, in runner seat bits: B0 Y1 Select2 Start3 Up4 Down5 Left6 Right7 A8 X9 L10 R11.
        e.AppendLine("pad 0 10 - L2").AppendLine("pad 0 11 - R2").AppendLine("pad 0 - - L1").AppendLine("pad 0 2 - Start").AppendLine("pad 0 3 - Back")
         .AppendLine("pad 0 0 - A").AppendLine("pad 0 8 - B").AppendLine("pad 1 8 - R3").AppendLine("pad 1 0 - A")
         .AppendLine("pad 0 10 SettingsMenu L2 Y").AppendLine("pad 0 10 - L2 L3").AppendLine("pad 0 10 SaveStateMenu L2 Start");
        File.WriteAllText(expectPath, e.ToString());
        Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { passed = true, written, dir, expect = expectPath }));
    }
}
