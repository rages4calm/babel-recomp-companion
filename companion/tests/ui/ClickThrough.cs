using System.Diagnostics;
using System.Text.Json;
using System.Windows.Automation;

/// <summary>
/// Drives the real launcher process through UI Automation, page by page and button by button, and checks
/// what each action wrote to settings.json, config.ini, keybinds.ini and mods/preloaded/state.toml.
/// Buttons that open a modal window are invoked from a worker thread (a WinForms Invoke returns only
/// when the click handler does). Keys are posted as window messages with real scan codes; nothing is
/// sent through the desktop's input queue.
/// </summary>
internal static class ClickThrough
{
    private static int checks;
    private static readonly List<string> failures = new();
    private static readonly List<object> log = new();
    private static int pid;
    private static string install = "", dataRoot = "";

    private static void Check(bool ok, string what, object? detail = null)
    {
        checks++; log.Add(new { ok, what, detail = detail?.ToString() }); Console.WriteLine($"{(ok ? "ok  " : "FAIL")} {what} {detail}");
        if (!ok) failures.Add(what + (detail == null ? "" : " -> " + detail));
    }
    private static void Note(string what, object? detail = null) { log.Add(new { ok = true, what, detail = detail?.ToString() }); Console.WriteLine($"note {what} {detail}"); }

    public static int Run(string launcher, string rom, string reportPath)
    {
        rom = Path.GetFullPath(rom);
        install = Path.GetDirectoryName(Path.GetFullPath(launcher))!;
        dataRoot = Environment.GetEnvironmentVariable("COMPANION_DATA_ROOT") ?? throw new InvalidOperationException("Set COMPANION_DATA_ROOT to a scratch folder.");
        var process = Process.Start(new ProcessStartInfo(launcher) { WorkingDirectory = install, UseShellExecute = false })!;
        pid = process.Id;
        // Watchdog: a UI Automation call that never returns must not leave the run (or the launcher) hanging.
        new Thread(() => {
            Thread.Sleep(300_000);
            failures.Add("watchdog: the click-through did not finish in 300 s");
            File.WriteAllText(reportPath, JsonSerializer.Serialize(new { passed = false, checks, failures, log }, new JsonSerializerOptions { WriteIndented = true }));
            try { process.Kill(true); } catch (Exception) { }
            Environment.Exit(2);
        }) { IsBackground = true }.Start();
        try {
            var main = WaitWindow(w => w.Current.Name.Contains("Companion"), "launcher window", 30000);
            Note("launcher window", main.Current.Name);
            Steps(main, rom);
        } catch (Exception error) { Check(false, "click-through stopped", error.Message + "\n" + error.StackTrace); }
        finally {
            foreach (var stray in Native.TopWindows(pid).Where(h => Native.ClassOf(h) == "#32770")) Check(false, "unexpected message box", MessageBoxText(stray));
            foreach (var helper in invokers) { try { if (!helper.HasExited) helper.Kill(); } catch (Exception) { } }
            try { if (!process.HasExited) { process.CloseMainWindow(); if (!process.WaitForExit(5000)) process.Kill(true); } } catch (Exception) { try { process.Kill(true); } catch (Exception) { } }
        }
        var report = JsonSerializer.Serialize(new { passed = failures.Count == 0, checks, failures, log }, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(reportPath, report);
        Console.WriteLine(report);
        return failures.Count == 0 ? 0 : 1;
    }

    // ---- UI Automation helpers ------------------------------------------------------------

    /// <summary>The launcher's top-level windows (owned dialogs included; UIA files those under their owner).</summary>
    private static IEnumerable<AutomationElement> Windows()
    {
        foreach (var h in Native.TopWindows(pid)) {
            AutomationElement? e = null;
            try { e = AutomationElement.FromHandle(h); } catch (Exception) { }
            if (e != null) yield return e;
        }
    }
    private static AutomationElement WaitWindow(Func<AutomationElement, bool> match, string what, int ms = 8000)
    {
        var clock = Stopwatch.StartNew();
        while (clock.ElapsedMilliseconds < ms) {
            try { if (Windows().FirstOrDefault(match) is { } w) return w; } catch (ElementNotAvailableException) { }
            Thread.Sleep(100);
        }
        throw new TimeoutException("No window: " + what + ". Open: " + string.Join(" | ", Windows().Select(w => w.Current.Name + " [" + w.Current.ClassName + "]")));
    }
    private static void WaitClosed(AutomationElement window, int ms = 8000)
    {
        var clock = Stopwatch.StartNew(); IntPtr handle;
        try { handle = (IntPtr)window.Current.NativeWindowHandle; } catch (Exception) { return; }   // already gone
        while (clock.ElapsedMilliseconds < ms) { if (!Native.TopWindows(pid).Contains(handle)) return; Thread.Sleep(100); }
        throw new TimeoutException("Window stayed open: " + window.Current.Name);
    }
    private static AutomationElement Find(AutomationElement root, string name, ControlType? type = null, int ms = 5000)
    {
        Condition c = new PropertyCondition(AutomationElement.NameProperty, name);
        if (type != null) c = new AndCondition(c, new PropertyCondition(AutomationElement.ControlTypeProperty, type));
        var clock = Stopwatch.StartNew();
        while (true) {
            var found = root.FindFirst(TreeScope.Descendants, c);
            if (found != null) return found;
            if (clock.ElapsedMilliseconds > ms) {
                var near = root.FindAll(TreeScope.Descendants, type == null ? Condition.TrueCondition : new PropertyCondition(AutomationElement.ControlTypeProperty, type))
                    .Cast<AutomationElement>().Take(60).Select(e => $"{e.Current.ControlType.ProgrammaticName.Replace("ControlType.", "")}:{e.Current.Name}");
                throw new InvalidOperationException($"'{name}' ({type?.ProgrammaticName}) not found in '{root.Current.Name}'. Seen: " + string.Join(" | ", near));
            }
            Thread.Sleep(100);
        }
    }
    private static AutomationElement? TryFind(AutomationElement root, string name, ControlType? type = null) { try { return Find(root, name, type, 300); } catch (InvalidOperationException) { return null; } }
    private static string AllText(AutomationElement root) =>
        string.Join(" | ", root.FindAll(TreeScope.Descendants, new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Text)).Cast<AutomationElement>().Select(e => e.Current.Name).Where(n => n.Length > 0));
    /// <summary>
    /// Main-window buttons by UIA Invoke (synchronous). Buttons in the launcher's dialogs by a posted mouse click:
    /// an Invoke that closes its own dialog comes back as "Unrecognized error" and leaves UIA unreliable.
    /// </summary>
    private static void Click(AutomationElement root, string name)
    {
        var button = Find(root, name, ControlType.Button);
        if (root.Current.Name == "Illusion of Gaia Companion") ((InvokePattern)button.GetCurrentPattern(InvokePattern.Pattern)).Invoke();
        else PostClick(Hwnd(button), button.Current.BoundingRectangle);
        Thread.Sleep(350);
    }
    /// <summary>
    /// For a button whose handler opens a modal window. A UI Automation Invoke runs the handler inside an
    /// input-synchronous COM call, so the modal window's loop cannot answer any further UIA request until it
    /// closes (every later call times out). Click with posted mouse messages at the button's centre instead,
    /// as a pointer would; Space as a fallback.
    /// </summary>
    private static readonly List<Process> invokers = new();
    private static void ClickOpening(AutomationElement root, string name)
    {
        var button = Find(root, name, ControlType.Button);
        var before = Native.TopWindows(pid);
        PostClick(Hwnd(button), button.Current.BoundingRectangle);
        var clock = Stopwatch.StartNew();
        while (clock.ElapsedMilliseconds < 1500) { if (Native.TopWindows(pid).Except(before).Any()) { Note($"opened by click: {name}"); return; } Thread.Sleep(50); }
        Native.Key(Hwnd(button), 0x20, 0x39);
        Note($"opened by Space: {name}");
    }
    private static void PostClick(IntPtr hwnd, System.Windows.Rect screen)
    {
        var pt = new Native.POINT { X = (int)(screen.Left + screen.Width / 2), Y = (int)(screen.Top + screen.Height / 2) };
        Native.ScreenToClient(hwnd, ref pt); var at = (IntPtr)((pt.Y << 16) | (pt.X & 0xFFFF));
        Native.PostMessage(hwnd, 0x200, IntPtr.Zero, at);            // WM_MOUSEMOVE
        Native.PostMessage(hwnd, 0x201, (IntPtr)1, at);              // WM_LBUTTONDOWN
        Native.PostMessage(hwnd, 0x202, IntPtr.Zero, at);            // WM_LBUTTONUP
    }
    /// <summary>A Win32 message box: its text, then OK through WM_COMMAND (no UI Automation on it).</summary>
    private static string MessageBoxText(IntPtr box)
    {
        var parts = new List<string>();
        Native.EnumChildWindows(box, (h, _) => { var t = new System.Text.StringBuilder(1024); Native.GetWindowText(h, t, 1024); if (t.Length > 0) parts.Add(t.ToString()); return true; }, IntPtr.Zero);
        return string.Join(" | ", parts);
    }
    public static int Invoke(int process, string window, string button) => 1;
    /// <summary>OK on a message box: WM_COMMAND IDOK, then WM_CLOSE, until it is gone.</summary>
    private static void CloseMessageBox(IntPtr box)
    {
        if (box == IntPtr.Zero) return;
        bool Open() => Native.TopWindows(pid).Contains(box);
        foreach (var (msg, w) in new[] { (0x111, 1), (0x111, 2), (0x10, 0) }) {   // IDOK, IDCANCEL, WM_CLOSE
            Native.PostMessage(box, msg, (IntPtr)w, IntPtr.Zero);
            for (int i = 0; i < 15 && Open(); i++) Thread.Sleep(100);
            if (!Open()) { Note("message box closed by", $"0x{msg:X} {w}"); return; }
        }
        Check(false, "message box would not close");
    }
    private static void Choose(AutomationElement root, string combo, string item)
    {
        AutomationElement? entry = null; AutomationElement box = null!; object? ec = null;
        for (int attempt = 0; attempt < 6 && entry == null; attempt++) {   // the list's items appear a moment after it opens
            box = Find(root, combo, ControlType.ComboBox);
            if (box.TryGetCurrentPattern(ExpandCollapsePattern.Pattern, out ec)) { try { ((ExpandCollapsePattern)ec).Expand(); } catch (Exception) { } }
            Thread.Sleep(150 + attempt * 150);
            entry = box.FindFirst(TreeScope.Descendants, new PropertyCondition(AutomationElement.NameProperty, item));
        }
        if (entry == null) throw new InvalidOperationException($"'{item}' is not in '{combo}': " + string.Join(", ", box.FindAll(TreeScope.Descendants, Condition.TrueCondition).Cast<AutomationElement>().Select(e => e.Current.Name)));
        ((SelectionItemPattern)entry.GetCurrentPattern(SelectionItemPattern.Pattern)).Select();
        if (ec != null) { try { ((ExpandCollapsePattern)ec).Collapse(); } catch (Exception) { } }
        Thread.Sleep(200);
    }
    /// <summary>
    /// Picks a combo box entry with the control's own messages (CB_SETCURSEL, then the CBN_SELCHANGE its parent
    /// would get from a real pick). UIA kept listing this combo's first set of entries after the window refilled it.
    /// </summary>
    private static void ChooseByMessages(AutomationElement root, string combo, string item)
    {
        var box = Hwnd(Find(root, combo, ControlType.ComboBox));
        int count = (int)Native.SendMessageText(box, 0x146, IntPtr.Zero, "");   // CB_GETCOUNT
        var names = new List<string>();
        for (int i = 0; i < count; i++) {
            var len = (int)Native.SendMessageText(box, 0x149, (IntPtr)i, "");     // CB_GETLBTEXTLEN
            var text = new System.Text.StringBuilder(len + 1);
            Native.SendMessageBuffer(box, 0x148, (IntPtr)i, text);                // CB_GETLBTEXT
            names.Add(text.ToString());
        }
        int index = names.IndexOf(item);
        if (index < 0) throw new InvalidOperationException($"'{item}' is not in '{combo}': " + string.Join(", ", names));
        Native.SendMessageText(box, 0x14E, (IntPtr)index, "");                    // CB_SETCURSEL
        var parent = Native.GetParent(box); var id = Native.GetDlgCtrlID(box);
        Native.SendMessageText(parent, 0x111, (IntPtr)((1 << 16) | (id & 0xFFFF)), box);   // WM_COMMAND CBN_SELCHANGE
        Thread.Sleep(250);
    }
    private static string Selected(AutomationElement root, string combo)
    {
        var box = Find(root, combo, ControlType.ComboBox);
        return box.TryGetCurrentPattern(ValuePattern.Pattern, out var v) ? ((ValuePattern)v).Current.Value
            : ((SelectionPattern)box.GetCurrentPattern(SelectionPattern.Pattern)).Current.GetSelection().FirstOrDefault()?.Current.Name ?? "";
    }
    private static void Toggle(AutomationElement element) { ((TogglePattern)element.GetCurrentPattern(TogglePattern.Pattern)).Toggle(); Thread.Sleep(200); }
    private static ToggleState State(AutomationElement element) => ((TogglePattern)element.GetCurrentPattern(TogglePattern.Pattern)).Current.ToggleState;
    /// <summary>WM_SETTEXT to the edit's window (UIA's ValuePattern.SetValue fails on these WinForms text boxes off the input desktop).</summary>
    private static void SetText(AutomationElement element, string text)
    {
        var hwnd = EditWindow(element);
        Native.SendMessageText(hwnd, 0x000C, IntPtr.Zero, text);   // WM_SETTEXT: TextChanged fires as when typing
        Thread.Sleep(200);
    }
    /// <summary>
    /// The HWND behind an edit. Reading NativeWindowHandle from a .NET 8 WinForms TextBox provider fails
    /// ("Unrecognized error"), so match the launcher's child windows by their screen rectangle instead.
    /// </summary>
    private static IntPtr EditWindow(AutomationElement element)
    {
        var r = element.Current.BoundingRectangle; IntPtr found = IntPtr.Zero;
        foreach (var top in Windows().Select(w => (IntPtr)w.Current.NativeWindowHandle))
            Native.EnumChildWindows(top, (h, _) => {
                Native.GetWindowRect(h, out var w);
                if (Math.Abs(w.Left - r.Left) <= 1 && Math.Abs(w.Top - r.Top) <= 1 && Math.Abs(w.Right - r.Right) <= 1 && Math.Abs(w.Bottom - r.Bottom) <= 1) { found = h; return false; }
                return true;
            }, IntPtr.Zero);
        return found != IntPtr.Zero ? found : throw new InvalidOperationException("No window for " + element.Current.Name);
    }
    /// <summary>A NumericUpDown: type into its edit (WM_SETTEXT) and press Enter, which is when it takes the value.</summary>
    private static void SetNumber(AutomationElement root, string name, int value)
    {
        var spinner = Hwnd(Find(root, name, ControlType.Spinner)); IntPtr edit = IntPtr.Zero;
        Native.EnumChildWindows(spinner, (h, _) => { var c = new System.Text.StringBuilder(256); Native.GetClassName(h, c, 256); if (c.ToString().Contains("EDIT", StringComparison.OrdinalIgnoreCase)) { edit = h; return false; } return true; }, IntPtr.Zero);
        if (edit == IntPtr.Zero) throw new InvalidOperationException("No edit inside " + name);
        Native.SendMessageText(edit, 0x000C, IntPtr.Zero, value.ToString());
        Native.Key(edit, 0x0D, 0x1C);
        Thread.Sleep(300);
        var text = new System.Text.StringBuilder(64); Native.GetWindowText(edit, text, 64);
        Note($"spinner {name}", text.ToString());
    }
    /// <summary>A NumericUpDown stepped with the arrow keys, as a player nudges it.</summary>
    private static void StepNumber(AutomationElement root, string name, int steps)
    {
        var spinner = Hwnd(Find(root, name, ControlType.Spinner)); IntPtr edit = IntPtr.Zero;
        Native.EnumChildWindows(spinner, (h, _) => { var c = new System.Text.StringBuilder(256); Native.GetClassName(h, c, 256); if (c.ToString().Contains("EDIT", StringComparison.OrdinalIgnoreCase)) { edit = h; return false; } return true; }, IntPtr.Zero);
        for (int i = 0; i < Math.Abs(steps); i++) Native.PostMessage(edit, Native.WM_KEYDOWN, (IntPtr)(steps < 0 ? 0x28 : 0x26), Native.KeyParam(steps < 0 ? 0x50 : 0x48, true, false));
        Thread.Sleep(400);
        var text = new System.Text.StringBuilder(64); Native.GetWindowText(edit, text, 64);
        Note($"spinner {name} stepped", text.ToString());
    }
    private static IntPtr Hwnd(AutomationElement e)
    {
        try { var h = (IntPtr)e.Current.NativeWindowHandle; if (h != IntPtr.Zero) return h; } catch (Exception) { }
        return EditWindow(e);
    }

    // ---- files --------------------------------------------------------------------------

    private static string SettingsFile => Directory.GetFiles(dataRoot, "settings.json", SearchOption.AllDirectories).Single();
    private static string? Pref(string key) => JsonDocument.Parse(File.ReadAllText(SettingsFile)).RootElement.TryGetProperty(key, out var v) ? v.ToString() : null;
    private static string? Ini(string file, string section, string key)
    {
        string current = "";
        foreach (var raw in File.ReadAllLines(Path.Combine(install, file))) {
            var line = raw.Trim();
            if (line.StartsWith('[') && line.EndsWith(']')) { current = line[1..^1]; continue; }
            var eq = line.IndexOf('=');
            if (eq > 0 && current.Equals(section, StringComparison.OrdinalIgnoreCase) && line[..eq].Trim().Equals(key, StringComparison.OrdinalIgnoreCase)) return line[(eq + 1)..].Split('#')[0].Trim();
        }
        return null;
    }
    /// <summary>The body of a [[feature]] block in state.toml, by package and id.</summary>
    private static string Feature(string package, string id)
    {
        var text = File.ReadAllText(Path.Combine(install, "mods", "preloaded", "state.toml")).Replace("\r\n", "\n");
        foreach (var block in text.Split("[[").Skip(1).Select(b => "[[" + b))
            if (block.StartsWith("[[feature]]") && block.Contains($"package_id = \"{package}\"") && block.Contains($"\nid = \"{id}\"")) return block.Trim();
        return "(none)";
    }
    private static string Status(AutomationElement main) => AllText(main);

    // ---- the walk -----------------------------------------------------------------------

    private static void Steps(AutomationElement main, string rom)
    {
        var engine = Path.Combine(install, "babel-recomp.exe");
        // 0. The saved game program pointed at a deleted folder; the launcher found its own.
        Check(Pref("engine.path") == engine, "stale saved engine path repaired to this folder on start", Pref("engine.path"));
        Check(Path.GetFullPath(Pref("rom.path")!) == Path.GetFullPath(rom), "ROM path kept as saved", Pref("rom.path"));
        Check(TryFind(main, "Set the game program on the Game page, then Apply.") == null, "Play page does not ask for the game program");

        // 1. Game page.
        Click(main, "Game");
        var program = Find(main, "Game program", ControlType.Edit);
        Check(((ValuePattern)program.GetCurrentPattern(ValuePattern.Pattern)).Current.Value == engine, "Game program box shows this folder's game");
        var romBox = Find(main, "Original USA ROM", ControlType.Edit);
        SetText(romBox, rom + "x");   // wrong path first: Apply saves it, Play must say so
        Click(main, "Apply settings");
        Check(Pref("rom.path") == rom + "x", "Apply wrote a typed ROM path", Pref("rom.path"));
        Click(main, "Play");
        Check(TryFind(main, "Select your original USA ROM, then Apply.") != null, "Play page reports the missing ROM", AllText(main));
        Click(main, "Game");
        SetText(Find(main, "Original USA ROM", ControlType.Edit), rom);
        Choose(main, "When you press Play", "Open the setup screen (remapping)");
        Click(main, "Apply settings");
        Check(Pref("rom.path") == rom && Pref("launch.mode") == "babel", "Apply wrote ROM and Play choice", $"{Pref("rom.path")} {Pref("launch.mode")}");
        Click(main, "Game");
        Choose(main, "When you press Play", "Start the game");
        Click(main, "Apply settings");
        Check(Pref("launch.mode") == "game", "Play choice back to Start the game");
        Click(main, "Play");
        Check(TryFind(main, "USA ROM verified · Babel runtime; native coverage under audit.") != null, "Play page: ROM verified", AllText(main));

        // 2. Display: the three Picture choices and Scaling.
        foreach (var (choice, widescreen, wide) in new[] { ("Classic 16:9", "1", "false"), ("Original 4:3", "0", "false"), ("Wide view (recommended)", "1", "true") }) {
            Click(main, "Display");
            Choose(main, "Picture", choice);
            Click(main, "Apply settings");
            var feature = Feature("iog.graphics", "wide_view");
            Check(Ini("config.ini", "Graphics", "Widescreen") == widescreen && feature.Contains("enabled = " + wide), $"Picture {choice}: Widescreen = {widescreen}, wide_view {wide}",
                $"Widescreen={Ini("config.ini", "Graphics", "Widescreen")} {feature.Replace('\n', ' ')}");
            Click(main, "Display");
            Check(Selected(main, "Picture") == choice, $"Picture reads back as {choice}", Selected(main, "Picture"));
        }
        Click(main, "Display");
        Choose(main, "Scaling", "Smooth edges (xBR)");
        Choose(main, "Window mode", "Desktop fullscreen");
        Choose(main, "Vertical sync", "Adaptive");
        Click(main, "Apply settings");
        var hd = Feature("iog.graphics", "hd");
        Check(hd.Contains("enabled = true") && hd.Contains("\"smooth\""), "Scaling Smooth edges: hd filter smooth", hd.Replace('\n', ' '));
        Check(Ini("config.ini", "Graphics", "Fullscreen") == "1" && Ini("config.ini", "Graphics", "VSync") == "adaptive", "Window mode and VSync written",
            $"{Ini("config.ini", "Graphics", "Fullscreen")} {Ini("config.ini", "Graphics", "VSync")}");
        Click(main, "Display");
        Choose(main, "Scaling", "Sharp pixels (recommended)"); Choose(main, "Window mode", "Windowed"); Choose(main, "Vertical sync", "On");
        Click(main, "Apply settings");
        Check(Ini("config.ini", "Graphics", "Fullscreen") == "0" && Ini("config.ini", "Graphics", "VSync") == "1", "Display back to defaults");

        // 3. Audio and Input pages.
        Click(main, "Audio"); Thread.Sleep(300);
        StepNumber(main, "Master volume (%)", -45);
        Note("status after volume", AllText(main).Split(" | ").LastOrDefault());
        Click(main, "Apply settings");
        Check(Ini("config.ini", "Sound", "Volume") == "55", "Audio volume written", Ini("config.ini", "Sound", "Volume"));
        Click(main, "Input");
        Choose(main, "Button prompts", "SNES (classic)");
        SetNumber(main, "Analog deadzone", 5000);
        Toggle(Find(main, "Enable gamepad", ControlType.CheckBox));
        Click(main, "Apply settings");
        Check(Feature("iog.enhancements", "map_controls").Contains("\"snes\""), "Button prompts SNES in state.toml", Feature("iog.enhancements", "map_controls").Replace('\n', ' '));
        Check(Ini("config.ini", "GamepadMap", "GamepadDeadzone") == "5000" && Ini("config.ini", "GamepadMap", "EnableGamepad1") == "0", "deadzone and gamepad written",
            $"{Ini("config.ini", "GamepadMap", "GamepadDeadzone")} {Ini("config.ini", "GamepadMap", "EnableGamepad1")}");
        Click(main, "Input");
        Toggle(Find(main, "Enable gamepad", ControlType.CheckBox)); Choose(main, "Button prompts", "Auto");
        Click(main, "Apply settings");
        Check(Ini("config.ini", "GamepadMap", "EnableGamepad1") == "1", "gamepad back on");
        // Unapplied changes block the rail's windows, with a message box (then Revert).
        Click(main, "Audio"); StepNumber(main, "Master volume (%)", -1);
        ClickOpening(main, "Keys, controllers and shortcuts");
        IntPtr box = IntPtr.Zero; var waited = Stopwatch.StartNew();
        while (box == IntPtr.Zero && waited.ElapsedMilliseconds < 5000) { box = Native.TopWindows(pid).FirstOrDefault(h => Native.ClassOf(h) == "#32770"); Thread.Sleep(100); }
        Check(box != IntPtr.Zero && MessageBoxText(box).Contains("Apply or Revert"), "Controls refuses with unapplied settings", box == IntPtr.Zero ? "(no message box)" : MessageBoxText(box));
        CloseMessageBox(box);
        Thread.Sleep(300);
        Click(main, "Revert"); Thread.Sleep(500);
        Note("status after Revert", AllText(main).Split(" | ").Where(t => t.Contains("settings") || t.Contains("changes")).LastOrDefault());
        Check(Ini("config.ini", "Sound", "Volume") == "55", "Revert left the file alone");

        Controls(main);
        Soundtrack(main);
        CheatsMods(main);
        Achievements(main);
        Update(main);
        // Finish on Original 4:3 for the packaged-game check that follows (gap: Wide view off).
        Click(main, "Display"); Choose(main, "Picture", "Original 4:3"); Click(main, "Apply settings");
        Check(Ini("config.ini", "Graphics", "Widescreen") == "0" && Feature("iog.graphics", "wide_view").Contains("enabled = false"), "final: Original 4:3 saved");
    }

    private static void Controls(AutomationElement main)
    {
        ClickOpening(main, "Keys, controllers and shortcuts");
        var w = WaitWindow(x => x.Current.Name.StartsWith("Illusion of Gaia · Keys"), "Controls window");
        var grid = Find(w, "Player 1 buttons", ControlType.DataGrid);
        // Click a cell as a player does: posted button messages at the cell's centre (CellMouseClick opens capture).
        AutomationElement CellOf(AutomationElement g, int row, int column)
        {
            var rows = g.FindAll(TreeScope.Children, Condition.TrueCondition).Cast<AutomationElement>()
                .Where(e => e.FindAll(TreeScope.Children, Condition.TrueCondition).Count >= 3).ToList();   // data rows (header row first)
            return rows[row + 1].FindAll(TreeScope.Children, Condition.TrueCondition).Cast<AutomationElement>().ToList()[column];
        }
        void Mouse(AutomationElement g, AutomationElement cell, bool right)
        {
            var r = cell.Current.BoundingRectangle; var pt = new Native.POINT { X = (int)(r.Left + r.Width / 2), Y = (int)(r.Top + r.Height / 2) };
            Native.ScreenToClient(Hwnd(g), ref pt); var at = (IntPtr)((pt.Y << 16) | (pt.X & 0xFFFF));
            int down = right ? 0x204 : 0x201, up = right ? 0x205 : 0x202;
            Native.PostMessage(Hwnd(g), down, (IntPtr)(right ? 2 : 1), at); Native.PostMessage(Hwnd(g), up, IntPtr.Zero, at);
        }
        AutomationElement ClickCell(AutomationElement g, int row, int column) { Mouse(g, CellOf(g, row, column), false); return WaitWindow(x => x.Current.Name == "Change binding", "capture"); }

        // Player 1 SNES A (row 4) keyboard = K.
        var cap = ClickCell(grid, 4, 1); Native.Key(Hwnd(cap), 0x4B, 0x25); WaitClosed(cap);
        // Player 1 SNES B (row 5) keyboard = K too -> Swap.
        cap = ClickCell(grid, 5, 1); Native.Key(Hwnd(cap), 0x4B, 0x25); WaitClosed(cap);
        var conflict = WaitWindow(x => x.Current.Name == "Already in use", "conflict");
        Check(AllText(conflict).Contains("Player 1"), "conflict names the other binding", AllText(conflict));
        Click(conflict, "Swap"); WaitClosed(conflict);
        // Player 1 SNES X (row 6) controller: pick from the list (right-click menu by the Menu key).
        Mouse(grid, CellOf(grid, 6, 2), true);
        var menu = WaitWindow(x => x.Current.ControlType == ControlType.Menu || x.Current.ClassName.Contains("WindowsForms") && x.FindFirst(TreeScope.Descendants, new PropertyCondition(AutomationElement.NameProperty, "Pick from a list…")) != null, "context menu");
        Find(menu, "Pick from a list…");
        // The menu takes keys through WinForms' menu message filter: Down to the first item, Down to the second, Enter.
        Native.Key(Hwnd(menu), 0x28, 0x50, true); Thread.Sleep(100); Native.Key(Hwnd(menu), 0x28, 0x50, true); Thread.Sleep(100); Native.Key(Hwnd(menu), 0x0D, 0x1C);
        var picker = WaitWindow(x => x.Current.Name.StartsWith("Pick · "), "picker");
        var item = Find(picker, "LT + RB", ControlType.ListItem);
        ((SelectionItemPattern)item.GetCurrentPattern(SelectionItemPattern.Pattern)).Select(); Thread.Sleep(150);
        Click(picker, "Use"); WaitClosed(picker);
        if (Windows().FirstOrDefault(x => x.Current.Name == "Already in use") is { } c2) { Note("picking LT + RB conflicts (Save state 1)", AllText(c2)); Click(c2, "Replace"); WaitClosed(c2); }
        // Player 2 page: preset.
        var tabs = Find(w, "Sections", ControlType.Tab);
        // Home then Right on the tab strip (the control's own keyboard handling sends the change notification).
        var strip = Hwnd(tabs);
        Native.Key(strip, 0x24, 0x47, true); Thread.Sleep(150); Native.Key(strip, 0x27, 0x4D, true); Thread.Sleep(300);
        Check((int)Native.SendMessageText(strip, 0x130B, IntPtr.Zero, IntPtr.Zero) == 1, "Controls: Player 2 page selected by keyboard");   // TCM_GETCURSEL
        ChooseByMessages(w, "Preset", "Keyboard · WASD + JKL");
        Click(w, "Apply preset");
        Click(w, "Save");
        Check(AllText(w).Contains("Saved") || ((ValuePattern)Find(w, "Status", ControlType.Edit).GetCurrentPattern(ValuePattern.Pattern)).Current.Value.StartsWith("Saved"),
            "Controls Save", ((ValuePattern)Find(w, "Status", ControlType.Edit).GetCurrentPattern(ValuePattern.Pattern)).Current.Value);
        var m = new InputFiles(install).Load(new List<string>());
        Check(m.Keys[0][(int)SnesButton.A] == "Z" && m.Keys[0][(int)SnesButton.B] == "K", "keybinds.ini: A was set to K, then B took K by Swap: B = K, A = Z (B's old key)", $"{m.Keys[0][0]} {m.Keys[0][1]}");
        Check(m.Pad[0][(int)SnesButton.X] == "L2+R1", "config.ini [GamepadMap]: P1 X = L2+R1 from the list", m.Pad[0][(int)SnesButton.X]);
        Check(m.Keys[1].SequenceEqual(InputPresets.Keyboard.Single(p => p.Name == "WASD + JKL").Values), "keybinds.ini: P2 WASD preset", string.Join(",", m.Keys[1]));
        Note("keybinds.ini", string.Join(" / ", File.ReadAllLines(Path.Combine(install, "keybinds.ini")).Where(l => l.Contains('=') && !l.TrimStart().StartsWith('#')).Take(14)));
        Click(w, "Close"); WaitClosed(w);
    }

    private static void Soundtrack(AutomationElement main)
    {
        ClickOpening(main, "Soundtrack download and import");
        var w = WaitWindow(x => x.Current.Name == "Illusion of Gaia · Soundtrack", "Soundtrack window");
        Note("Soundtrack window text", AllText(w));
        Check(TryFind(w, "Download soundtrack…", ControlType.Button) != null && TryFind(w, "Import ZIP…", ControlType.Button) != null && TryFind(w, "Import folder…", ControlType.Button) != null,
            "Soundtrack offers download and both imports (download opens the browser: not clicked)");
        Click(w, "Use original audio");
        var status = ((ValuePattern)Find(w, "Soundtrack status", ControlType.Edit).GetCurrentPattern(ValuePattern.Pattern)).Current.Value;
        Check(status.StartsWith("Original SNES audio selected"), "Use original audio", status);
        Check(Feature("iog.enhancements", "msu1").Contains("enabled = false"), "state.toml msu1 disabled", Feature("iog.enhancements", "msu1").Replace('\n', ' '));
        Click(w, "Close"); WaitClosed(w);
    }

    private static void CheatsMods(AutomationElement main)
    {
        ClickOpening(main, "Cheats and Mods");
        var w = WaitWindow(x => x.Current.Name == "Illusion of Gaia · Cheats and Mods", "Cheats and Mods window");
        var hp = Find(w, "Refill HP", ControlType.CheckBox); Toggle(hp);
        Choose(w, "Room-clear rewards", ((ComboItemsOf(w, "Room-clear rewards")).Last()));
        Click(w, "Apply changes");
        Check(Feature("iog.cheats", "infinite_hp").Contains("enabled = true"), "Refill HP on in state.toml", Feature("iog.cheats", "infinite_hp").Replace('\n', ' '));
        Note("room rewards block", Feature("iog.cheats", "room_rewards").Replace('\n', ' '));
        var tabs = Find(w, "Cheats and convenience sections", ControlType.Tab);
        foreach (var tab in tabs.FindAll(TreeScope.Children, new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.TabItem)).Cast<AutomationElement>()) {
            ((SelectionItemPattern)tab.GetCurrentPattern(SelectionItemPattern.Pattern)).Select(); Thread.Sleep(200);
            Note("Cheats and Mods tab", tab.Current.Name);
        }
        var sections = Hwnd(tabs);
        Native.Key(sections, 0x24, 0x47, true); Thread.Sleep(150); Native.Key(sections, 0x27, 0x4D, true); Thread.Sleep(400);   // Convenience
        var edge = Find(w, "Status display at the screen edges", ControlType.CheckBox);
        Check(edge.Current.IsEnabled, "edge HUD editable in Wide view", edge.Current.IsEnabled);
        Native.Key(sections, 0x24, 0x47, true); Thread.Sleep(400);   // back to Cheats
        Toggle(Find(w, "Refill HP", ControlType.CheckBox));
        Click(w, "Apply changes");
        Check(Feature("iog.cheats", "infinite_hp").Contains("enabled = false"), "Refill HP off again");
        Click(w, "Close"); WaitClosed(w);
        // With Original 4:3 the edge HUD is shown but greyed out.
        Click(main, "Display"); Choose(main, "Picture", "Original 4:3"); Click(main, "Apply settings");
        ClickOpening(main, "Cheats and Mods");
        w = WaitWindow(x => x.Current.Name == "Illusion of Gaia · Cheats and Mods", "Cheats and Mods window (4:3)");
        var sections2 = Hwnd(Find(w, "Cheats and convenience sections", ControlType.Tab));
        Native.Key(sections2, 0x24, 0x47, true); Thread.Sleep(150); Native.Key(sections2, 0x27, 0x4D, true); Thread.Sleep(400);
        Check(!Find(w, "Status display at the screen edges", ControlType.CheckBox).Current.IsEnabled, "edge HUD greyed out in Original 4:3");
        Click(w, "Close"); WaitClosed(w);
        Click(main, "Display"); Choose(main, "Picture", "Wide view (recommended)"); Click(main, "Apply settings");
    }
    private static List<string> ComboItemsOf(AutomationElement root, string combo)
    {
        var box = Find(root, combo, ControlType.ComboBox);
        if (box.TryGetCurrentPattern(ExpandCollapsePattern.Pattern, out var ec)) { ((ExpandCollapsePattern)ec).Expand(); Thread.Sleep(150); }
        var items = box.FindAll(TreeScope.Descendants, new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.ListItem)).Cast<AutomationElement>().Select(e => e.Current.Name).ToList();
        if (ec != null) ((ExpandCollapsePattern)ec).Collapse();
        return items;
    }

    private static void Achievements(AutomationElement main)
    {
        Click(main, "Achievements");
        var texts = main.FindAll(TreeScope.Descendants, new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Text)).Cast<AutomationElement>().Select(e => e.Current.Name).ToList();
        var count = texts.FirstOrDefault(t => t.EndsWith(" earned") && t.Contains(" of "));
        int rows = texts.Count(t => t is "Locked" or "Earned" || System.Text.RegularExpressions.Regex.IsMatch(t, @"^\d+ / \d+$"));
        Check(count == "0 of 15 earned" && rows == 15, "Achievements page lists 15 entries", $"{count}; {rows} rows");
        Click(main, "Refresh progress");
        Check(TryFind(main, "0 of 15 earned") != null, "Refresh progress keeps the list");
    }

    private static void Update(AutomationElement main)
    {
        ClickOpening(main, "Check for updates");
        var w = WaitWindow(x => x.Current.Name == "Illusion of Gaia · Update", "Update window");
        var clock = Stopwatch.StartNew(); string text = "";
        while (clock.ElapsedMilliseconds < 15000) { text = AllText(w); if (!text.Contains("Checking GitHub")) break; Thread.Sleep(200); }
        Note("Update window text", text);
        Check(text.Length > 0 && !text.Contains("Checking GitHub"), "Update window finished its check", text);
        var toggle = Find(w, "Check for updates when the launcher starts", ControlType.CheckBox);
        var before = State(toggle); Toggle(toggle);
        var settings = Directory.GetFiles(install, "*update*.json").Concat(Directory.GetFiles(install, ".companion*")).ToList();
        Note("update settings files", string.Join(", ", settings.Select(Path.GetFileName)));
        Toggle(toggle);
        Check(State(toggle) == before, "check-on-start toggles and restores");
        Click(w, "Close"); WaitClosed(w);
    }
}
