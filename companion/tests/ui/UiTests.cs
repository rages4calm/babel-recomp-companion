using System.Runtime.InteropServices;
using System.Text.Json;

/// <summary>
/// Window tests for the launcher. Modes:
///   --language &lt;fresh scratch folder&gt;     Cheats and Mods Language tab, never shown: choose ROMs, apply, read back, render one PNG
///   --pad &lt;scratch game folder&gt;            mock XInput: every button, trigger and chord through capture and the Controls window
///   --dpi &lt;babel-recomp.exe&gt; &lt;out dir&gt;     Controls window and its dialogs at 96/144/192 DPI (WM_DPICHANGED, as dotnet/winforms' own DPI tests)
///   --click &lt;launcher.exe&gt; &lt;rom&gt; &lt;report&gt;  UI Automation click-through of the real launcher process
/// Run on a hidden desktop: nothing here is meant for the player's screen.
/// </summary>
internal static class UiTests
{
    [STAThread]
    private static int Main(string[] args)
    {
        Application.SetHighDpiMode(HighDpiMode.PerMonitorV2);
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.SetUnhandledExceptionMode(UnhandledExceptionMode.ThrowException);   // no exception dialog: fail the run instead
        try {
            return args[0] switch {
                "--pad" => PadTests.Run(args[1]),
                "--language" => LanguageWindowTests.Run(args[1]),
                "--dpi" => DpiTests.Run(args[1], args[2]),
                "--probe" => Probe(),
                "--invoke" => ClickThrough.Invoke(int.Parse(args[1]), args[2], args[3]),
                "--click" => ClickThrough.Run(args[1], args[2], args[3]),
                _ => throw new ArgumentException("Unknown mode " + args[0]),
            };
        } catch (Exception error) { Console.Error.WriteLine(error); return 1; }
    }
    private static int Probe()
    {
        var controller = new Companion.Launcher.Core.LauncherController(new GameAdapter());
        using var form = new Companion.Launcher.Windows.LauncherForm(controller);
        form.Shown += (_, _) => {
            var game = Native.Descendants(form).OfType<Button>().First(b => b.AccessibleName == "Game");
            string Page() => string.Join("|", Native.Descendants(form).OfType<TextBox>().Select(t => t.AccessibleName));
            Console.WriteLine("canSelect=" + game.CanSelect + " before: " + Page());
            game.PerformClick(); Application.DoEvents(); Console.WriteLine("after PerformClick: " + Page());
            form.Close();
        };
        Application.Run(form);
        return 0;
    }
}

internal static class Native
{
    public const int WM_KEYDOWN = 0x100, WM_KEYUP = 0x101, WM_DPICHANGED = 0x02E0, WM_GETDPISCALEDSIZE = 0x02E4;
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr hwnd, int msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr hwnd, int msg, IntPtr w, ref RECT l);
    [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr hwnd);
    [DllImport("user32.dll", EntryPoint = "SendMessageW", CharSet = CharSet.Unicode)] public static extern IntPtr SendMessageText(IntPtr hwnd, int msg, IntPtr w, string text);
    public delegate bool EnumProc(IntPtr hwnd, IntPtr data);
    [DllImport("user32.dll", EntryPoint = "SendMessageW", CharSet = CharSet.Unicode)] public static extern IntPtr SendMessageBuffer(IntPtr hwnd, int msg, IntPtr w, System.Text.StringBuilder text);
    [DllImport("user32.dll", EntryPoint = "SendMessageW")] public static extern IntPtr SendMessageText(IntPtr hwnd, int msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] public static extern IntPtr GetParent(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern int GetDlgCtrlID(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc proc, IntPtr data);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out int pid);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
    /// <summary>Visible top-level windows of a process, without UI Automation.</summary>
    public static List<IntPtr> TopWindows(int pid)
    {
        var found = new List<IntPtr>();
        EnumWindows((h, _) => { GetWindowThreadProcessId(h, out var p); if (p == pid && IsWindowVisible(h)) found.Add(h); return true; }, IntPtr.Zero);
        return found;
    }
    public static string ClassOf(IntPtr h) { var c = new System.Text.StringBuilder(256); GetClassName(h, c, 256); return c.ToString(); }
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr parent, EnumProc proc, IntPtr data);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr hwnd, System.Text.StringBuilder text, int size);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetClassName(IntPtr hwnd, System.Text.StringBuilder name, int size);
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
    [DllImport("user32.dll")] public static extern bool ScreenToClient(IntPtr hwnd, ref POINT point);
    public static IntPtr KeyParam(int scan, bool extended, bool up) =>
        (IntPtr)(1 | (scan << 16) | (extended ? 1 << 24 : 0) | (up ? (3 << 30) : 0));
    /// <summary>A key press as the window would receive it: WM_KEYDOWN then WM_KEYUP with the physical scan code.</summary>
    public static void Key(IntPtr hwnd, int vk, int scan, bool extended = false)
    {
        PostMessage(hwnd, WM_KEYDOWN, (IntPtr)vk, KeyParam(scan, extended, false));
        PostMessage(hwnd, WM_KEYUP, (IntPtr)vk, KeyParam(scan, extended, true));
    }
    /// <summary>dotnet/winforms DpiMessageHelper.TriggerDpiMessage: WM_GETDPISCALEDSIZE then WM_DPICHANGED with the scaled bounds.</summary>
    public static void ChangeDpi(Control form, int dpi)
    {
        double factor = dpi / 96.0;
        var wParam = (IntPtr)((dpi << 16) | dpi);
        var rect = new RECT { Left = form.Left, Top = form.Top, Right = form.Left + (int)Math.Round(form.Width * factor), Bottom = form.Top + (int)Math.Round(form.Height * factor) };
        var size = new RECT { Left = rect.Right - rect.Left, Top = rect.Bottom - rect.Top };
        SendMessage(form.Handle, WM_GETDPISCALEDSIZE, wParam, ref size);
        SendMessage(form.Handle, WM_DPICHANGED, wParam, ref rect);
    }
    public static IEnumerable<Control> Descendants(Control root)
    {
        foreach (Control c in root.Controls) { yield return c; foreach (var n in Descendants(c)) yield return n; }
    }
}

internal static class PadTests
{
    private static readonly Dictionary<int, XInputPad.Report> pads = new();
    private static int checks;
    private static readonly List<string> failures = new();
    private static readonly List<object> log = new();
    private static readonly Font font = new("Segoe UI", 10);
    private static void Check(bool ok, string what, object? detail = null)
    {
        checks++; log.Add(new { ok, what, detail = detail?.ToString() });
        if (!ok) failures.Add(what + (detail == null ? "" : " → " + detail));
    }
    private const ushort Up = 0x1, Down = 0x2, Left = 0x4, Right = 0x8, Start = 0x10, Back = 0x20, L3 = 0x40, R3 = 0x80, LB = 0x100, RB = 0x200, A = 0x1000, B = 0x2000, X = 0x4000, Y = 0x8000;
    private static readonly (string name, ushort bit)[] Bits = {
        ("DpadUp", Up), ("DpadDown", Down), ("DpadLeft", Left), ("DpadRight", Right), ("Start", Start), ("Back", Back), ("L3", L3), ("R3", R3),
        ("L1", LB), ("R1", RB), ("A", A), ("B", B), ("X", X), ("Y", Y) };
    private static void Set(int slot, ushort buttons, byte lt = 0, byte rt = 0, short x = 0, short y = 0) => pads[slot] = new(buttons, lt, rt, x, y);
    private static void Release() { foreach (var k in pads.Keys.ToList()) pads[k] = new(0); }

    public static int Run(string gameDir)
    {
        XInputPad.Source = slot => pads.TryGetValue(slot, out var r) ? r : null;
        Set(0, 0); Set(1, 0);
        Mapping();
        Captures();
        Window(gameDir);
        XInputPad.Source = null;
        var real = XInputPad.Connected().ToList();
        Console.WriteLine(JsonSerializer.Serialize(new { passed = failures.Count == 0, checks, failures, realXInputSlots = real, log }, new JsonSerializerOptions { WriteIndented = true }));
        return failures.Count == 0 ? 0 : 1;
    }

    private static string Held(int slot) => XInputPad.Read(slot, out _, out _) is { } h ? string.Join("+", h.Select(i => PadCatalog.Names[i])) : "(none)";

    private static void Mapping()
    {
        foreach (var (name, bit) in Bits) { Set(0, bit); Check(Held(0) == name, "XInput bit " + name, Held(0)); }
        Set(0, 0, lt: 93); Check(Held(0) == "", "LT at 93/255 is below the runner's 37% threshold", Held(0));
        Set(0, 0, lt: 94); Check(Held(0) == "L2", "LT at 94/255 counts", Held(0));
        Set(0, 0, rt: 255); Check(Held(0) == "R2", "RT", Held(0));
        Set(0, (ushort)(A | B | LB), lt: 255, rt: 255); Check(Held(0) == "L1+A+B+L2+R2", "several at once (XInput bit order)", Held(0));
        Set(0, 0, x: -20000, y: 12345); XInputPad.Read(0, out var sx, out var sy); Check(sx == -20000 && sy == 12345, "left stick passes through", $"{sx},{sy}");
        pads.Remove(2); Check(XInputPad.Read(2, out _, out _) == null, "unplugged slot reads as nothing");
        Check(XInputPad.Connected().SequenceEqual(new[] { 0, 1 }), "Connected lists the plugged slots", string.Join(",", XInputPad.Connected()));
        Release();
    }

    /// <summary>Opens a real CaptureForm and runs <paramref name="step"/> every 20 ms (tick number, form) until it closes.</summary>
    private static (DialogResult result, string? binding, double seconds) Capture(bool pad, bool hotkey, Action<int, CaptureForm> step, Action? before = null)
    {
        Release(); before?.Invoke();
        using var f = new CaptureForm("Test", pad, hotkey, 0, PadStyle.Xbox, font) { StartPosition = FormStartPosition.Manual, Location = new Point(40, 40) };
        using var timer = new System.Windows.Forms.Timer { Interval = 20 };
        int t = 0; var clock = System.Diagnostics.Stopwatch.StartNew();
        timer.Tick += (_, _) => { if (f.IsDisposed) return; step(t++, f); if (t > 1000) f.DialogResult = DialogResult.Ignore; };
        f.Shown += (_, _) => timer.Start();
        var result = f.ShowDialog();
        timer.Stop(); Release();
        return (result, f.Binding, clock.Elapsed.TotalSeconds);
    }
    private static void Expect(string what, (DialogResult result, string? binding, double seconds) got, DialogResult result, string? binding = null) =>
        Check(got.result == result && (binding == null || got.binding == binding), what, $"{got.result} {got.binding}");

    private static void Captures()
    {
        foreach (var (name, bit) in Bits)
            Expect("capture " + name, Capture(true, false, (t, _) => { if (t == 3) Set(0, bit); }), DialogResult.OK, name);
        Expect("capture RT", Capture(true, false, (t, _) => { if (t == 3) Set(0, 0, rt: 255); }), DialogResult.OK, "R2");
        string? early = "unset";
        var rt = Capture(true, false, (t, f) => { if (t == 3) Set(0, 0, rt: 93); if (t == 12) early = f.Binding; if (t == 14) Set(0, 0, rt: 94); });
        Check(early == null, "RT below threshold does not capture"); Expect("RT at threshold captures", rt, DialogResult.OK, "R2");
        Expect("LT alone (press and release)", Capture(true, false, (t, _) => { if (t == 3) Set(0, 0, lt: 255); if (t == 9) Set(0, 0); }), DialogResult.OK, "L2");
        foreach (var (name, bit) in Bits)
            Expect("chord LT + " + name, Capture(true, false, (t, _) => { if (t == 3) Set(0, 0, lt: 255); if (t == 9) Set(0, bit, lt: 255); }), DialogResult.OK, "L2+" + name);
        Expect("chord LT + RT", Capture(true, false, (t, _) => { if (t == 3) Set(0, 0, lt: 255); if (t == 9) Set(0, 0, lt: 255, rt: 255); }), DialogResult.OK, "L2+R2");
        Expect("button held when capture opened is ignored", Capture(true, false, (t, _) => { if (t == 6) Set(0, (ushort)(A | B)); }, () => Set(0, A)), DialogResult.OK, "B");
        Expect("held button counts after release and press", Capture(true, false, (t, _) => { if (t == 5) Set(0, 0); if (t == 10) Set(0, A); }, () => Set(0, A)), DialogResult.OK, "A");
        Expect("second controller (slot 2) captures too", Capture(true, false, (t, _) => { if (t == 3) Set(1, X); }), DialogResult.OK, "X");
        Expect("Esc cancels a controller capture", Capture(true, false, (t, f) => { if (t == 3) Native.Key(f.Handle, 0x1B, 0x01); }), DialogResult.Cancel);
        Expect("Delete clears", Capture(true, false, (t, f) => { if (t == 3) Native.Key(f.Handle, 0x2E, 0x53, true); }), DialogResult.Abort);
        Expect("controller B cancels a key capture", Capture(false, false, (t, _) => { if (t == 3) Set(0, B); }), DialogResult.Cancel);
        Expect("key K by scan code", Capture(false, false, (t, f) => { if (t == 3) Native.Key(f.Handle, 0x4B, 0x25); }), DialogResult.OK, KeyCatalog.FromScan(0x25, false, 0x4B)!.Name);
        Expect("Keypad Enter (extended scan code)", Capture(false, false, (t, f) => { if (t == 3) Native.Key(f.Handle, 0x0D, 0x1C, true); }), DialogResult.OK, KeyCatalog.FromScan(0x1C, true, 0x0D)!.Name);
        Expect("shortcut key F5", Capture(false, true, (t, f) => { if (t == 3) Native.Key(f.Handle, 0x74, 0x3F); }), DialogResult.OK, Chord.Make(KeyCatalog.FromScan(0x3F, false, 0x74)!, false, false, false));
        Expect("shortcut: Right Shift on its own", Capture(false, true, (t, f) => { if (t == 3) Native.Key(f.Handle, 0x10, 0x36); }), DialogResult.OK, KeyCatalog.ByName("Right Shift")!.Hotkey);
        var timeout = Capture(true, false, (_, _) => { });
        Check(timeout.result == DialogResult.Cancel && timeout.seconds is > 9 and < 13, "capture closes itself after 10 s", $"{timeout.result} {timeout.seconds:0.0}s");
    }

    // ---- the whole window ---------------------------------------------------------------

    private static void Window(string gameDir)
    {
        var engine = Path.Combine(gameDir, "babel-recomp.exe");
        var form = new InputForm(engine, "auto") { StartPosition = FormStartPosition.Manual, Location = new Point(0, 0) };
        form.Shown += async (_, _) => {
            try { await Script(form, gameDir); }
            catch (Exception e) { Check(false, "window script", e); }
            finally {
                var revert = Native.Descendants(form).OfType<Button>().First(b => b.Text == "Revert");
                revert.PerformClick(); form.Close();
            }
        };
        Application.Run(form);
        form.Dispose();
    }

    private static async Task<T> WaitFor<T>(Func<T?> probe, string what, int ms = 4000) where T : class
    {
        var clock = System.Diagnostics.Stopwatch.StartNew();
        while (clock.ElapsedMilliseconds < ms) { if (probe() is { } v) return v; await Task.Delay(20); }
        throw new TimeoutException("waited for " + what);
    }
    private static T? Open<T>() where T : Form => Application.OpenForms.OfType<T>().FirstOrDefault();
    private static async Task Gone<T>() where T : Form { for (int i = 0; i < 200 && Open<T>() != null; i++) await Task.Delay(20); }
    private static Button ButtonIn(Control root, string text) => Native.Descendants(root).OfType<Button>().First(b => b.Text == text);

    /// <summary>Selects a cell, presses Enter on the grid (as a player would), and returns the capture dialog.</summary>
    private static async Task<CaptureForm> Edit(DataGridView grid, int row, int column)
    {
        grid.Focus(); grid.CurrentCell = grid.Rows[row].Cells[column];
        await Task.Delay(40);
        Native.Key(grid.Handle, 0x0D, 0x1C);
        return await WaitFor(Open<CaptureForm>, "capture dialog");
    }
    private static async Task PadPress(ushort bits, byte lt = 0)
    {
        if (lt > 0) { Set(0, 0, lt: lt); await Task.Delay(100); }
        Set(0, bits, lt: lt); await Task.Delay(120); Release(); await Gone<CaptureForm>();
    }

    private static async Task Script(InputForm form, string gameDir)
    {
        await Task.Delay(300);
        var tabs = Native.Descendants(form).OfType<TabControl>().Single(t => t.AccessibleName == "Sections");
        DataGridView Grid(string name) => Native.Descendants(form).OfType<DataGridView>().Single(g => g.AccessibleName == name);
        var p1 = Grid("Player 1 buttons"); var p2 = Grid("Player 2 buttons"); var shortcuts = Grid("Shortcuts");
        int Row(SnesButton b) => Array.IndexOf(new[] { SnesButton.Up, SnesButton.Down, SnesButton.Left, SnesButton.Right, SnesButton.A, SnesButton.B, SnesButton.X, SnesButton.Y, SnesButton.L, SnesButton.R, SnesButton.Start, SnesButton.Select }, b);

        // 1. Player 1's A on the controller: press X (Xbox X, used by SNES Y), conflict -> Swap.
        tabs.SelectedIndex = 0; await Task.Delay(50);
        await Edit(p1, Row(SnesButton.A), 2); await PadPress(X);
        var conflict = await WaitFor(Open<ConflictForm>, "conflict dialog");
        Check(Native.Descendants(conflict).OfType<Button>().Any(b => b.Text == "Swap"), "controller-to-controller conflict offers Swap");
        ButtonIn(conflict, "Swap").PerformClick(); await Gone<ConflictForm>();
        // 2. Player 1's B: LT + Y chord, no conflict.
        await Edit(p1, Row(SnesButton.B), 2); await PadPress(Y, lt: 255);
        await Task.Delay(100); Check(Open<ConflictForm>() == null, "LT + Y is free");
        // 3. Player 1's Select: RT.
        await Edit(p1, Row(SnesButton.Select), 2); Set(0, 0, rt: 255); await Task.Delay(120); Release(); await Gone<CaptureForm>();
        await Task.Delay(100); if (Open<ConflictForm>() is { } c3) { Check(false, "RT unexpectedly conflicts"); ButtonIn(c3, "Cancel").PerformClick(); }

        // 4. Keyboard: Up = W, then Down = W -> conflict -> Replace (Up loses W).
        var cap = await Edit(p1, Row(SnesButton.Up), 1); Native.Key(cap.Handle, 0x57, 0x11); await Gone<CaptureForm>();
        await Task.Delay(100); Check(Open<ConflictForm>() == null, "W is free for Up");
        cap = await Edit(p1, Row(SnesButton.Down), 1); Native.Key(cap.Handle, 0x57, 0x11); await Gone<CaptureForm>();
        conflict = await WaitFor(Open<ConflictForm>, "conflict for W");
        ButtonIn(conflict, "Replace").PerformClick(); await Gone<ConflictForm>();
        await Task.Delay(100);
        Check(form.Pressed(0, out _).Count == 0, "tester: no key stuck after Enter opened capture", string.Join(",", form.Pressed(0, out _)));
        // 5. Keyboard Left = F, which a shortcut (Show frame rate) uses: no Swap across families; Cancel keeps Left.
        cap = await Edit(p1, Row(SnesButton.Left), 1); Native.Key(cap.Handle, 0x46, 0x21); await Gone<CaptureForm>();
        conflict = await WaitFor(Open<ConflictForm>, "conflict for F");
        Check(!Native.Descendants(conflict).OfType<Button>().Any(b => b.Text == "Swap"), "key-vs-shortcut conflict offers no Swap");
        ButtonIn(conflict, "Cancel").PerformClick(); await Gone<ConflictForm>();

        // 6. Shortcuts page: "All save states" on the controller = R3 alone.
        tabs.SelectedIndex = 2; await Task.Delay(80);
        int saveMenu = HotkeyCatalog.All.ToList().FindIndex(d => HotkeyCatalog.Id(d) == "SaveStateMenu");
        await Edit(shortcuts, saveMenu, 2); await PadPress(R3);
        await Task.Delay(100); if (Open<ConflictForm>() is { } c6) { Check(false, "R3 unexpectedly conflicts"); ButtonIn(c6, "Cancel").PerformClick(); }
        // Shortcut key: Screenshot = F9 ... which Load state 9 uses -> Replace.
        int shot = HotkeyCatalog.All.ToList().FindIndex(d => HotkeyCatalog.Id(d) == "Screenshot");
        cap = await Edit(shortcuts, shot, 1); Native.Key(cap.Handle, 0x78, 0x43); await Gone<CaptureForm>();
        conflict = await WaitFor(Open<ConflictForm>, "conflict for F9");
        ButtonIn(conflict, "Replace").PerformClick(); await Gone<ConflictForm>();

        // 7. Player 2: Numpad preset, keyboard only.
        tabs.SelectedIndex = 1; await Task.Delay(80);
        var preset = Native.Descendants(form).OfType<ComboBox>().Single(c => c.AccessibleName == "Preset");
        preset.SelectedIndex = Enumerable.Range(0, preset.Items.Count).First(i => preset.Items[i]!.ToString()!.Contains("Numpad"));
        ButtonIn(form, "Apply preset").PerformClick();
        var device = Native.Descendants(form).OfType<ComboBox>().Single(c => c.AccessibleName == "Player 2 plays with");
        device.SelectedIndex = 2;

        // 8. The live tester follows the mock pad with the edited (unsaved) bindings.
        tabs.SelectedIndex = 0; await Task.Delay(80);
        Set(0, Up); await Task.Delay(80); var lit = form.Pressed(0, out var sc);
        Check(lit.SetEquals(new[] { SnesButton.Up }), "tester: d-pad up lights Up", string.Join(",", lit));
        Set(0, X); await Task.Delay(80); lit = form.Pressed(0, out _);
        Check(lit.SetEquals(new[] { SnesButton.A }), "tester: X now lights SNES A (after the swap)", string.Join(",", lit));
        Set(0, Y, lt: 255); await Task.Delay(80); lit = form.Pressed(0, out sc);
        Check(lit.Contains(SnesButton.B), "tester: LT + Y lights SNES B", string.Join(",", lit) + " " + sc);
        Set(0, RB, lt: 255); await Task.Delay(80); form.Pressed(0, out sc);
        Check(sc == "Save state 1", "tester: LT + RB is the Save state 1 shortcut", sc);
        Set(0, 0, x: 20000, y: 20000); await Task.Delay(80); lit = form.Pressed(0, out _);
        Check(lit.SetEquals(new[] { SnesButton.Up, SnesButton.Right }), "tester: stick up-right", string.Join(",", lit));
        Set(0, 0, x: 2000); await Task.Delay(80); lit = form.Pressed(0, out _);
        Check(lit.Count == 0, "tester: stick inside the deadzone is nothing", string.Join(",", lit));
        Release();

        // 9. Controller navigation. Poll() only navigates while the window is the active one, which a
        // hidden desktop never grants; call the same Navigate the poll would, with what the pad holds.
        // (Only page, edit and clear buttons: the d-pad goes through SendKeys, which would reach the real desktop.)
        form.Activate(); await Task.Delay(100);
        log.Add(new { ok = true, what = "window active on the test desktop (Poll navigates only then)", detail = (Form.ActiveForm == form).ToString() });
        var navigate = typeof(InputForm).GetMethod("Navigate", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic)!;
        void Nav(params string[] held) => navigate.Invoke(form, new object[] { held.Select(PadCatalog.Index).ToArray() });
        Nav("R1"); Nav(); Check(tabs.SelectedIndex == 1, "controller RB: next page", tabs.SelectedIndex);
        Nav("R1"); Nav(); Check(tabs.SelectedIndex == 2, "controller RB again: Shortcuts", tabs.SelectedIndex);
        Nav("L1"); Nav(); Nav("L1"); Nav(); Check(tabs.SelectedIndex == 0, "controller LB twice: back to Player 1", tabs.SelectedIndex);
        Nav("R1"); Check(tabs.SelectedIndex == 1, "held RB moves once"); Nav("R1"); Check(tabs.SelectedIndex == 1, "held RB does not repeat"); Nav();
        Nav("L1"); Nav();
        p1.Focus(); p1.CurrentCell = p1.Rows[Row(SnesButton.X)].Cells[2]; form.ActiveControl = p1; await Task.Delay(60);
        form.BeginInvoke(() => { Nav("A"); Nav(); });
        var navCap = await WaitFor(Open<CaptureForm>, "capture opened by controller A");
        Check(navCap != null, "controller A on a cell opens capture");
        Native.Key(navCap!.Handle, 0x1B, 0x01); await Gone<CaptureForm>();
        p1.CurrentCell = p1.Rows[Row(SnesButton.L)].Cells[2]; form.ActiveControl = p1;
        Nav("Y"); Nav();
        Check(p1.Rows[Row(SnesButton.L)].Cells[2].Value?.ToString() == "—", "controller Y clears the cell", p1.Rows[Row(SnesButton.L)].Cells[2].Value);

        // 10. Save, then read the files back as the game would.
        ButtonIn(form, "Save").PerformClick(); await Task.Delay(200);
        var status = Native.Descendants(form).OfType<TextBox>().Single(t => t.AccessibleName == "Status").Text;
        Check(status.StartsWith("Saved"), "Save", status);
        var m = new InputFiles(gameDir).Load(new List<string>());
        Check(m.Pad[0][(int)SnesButton.A] == "X", "file: P1 A = X", m.Pad[0][(int)SnesButton.A]);
        Check(m.Pad[0][(int)SnesButton.Y] == "B", "file: P1 Y = B (swapped)", m.Pad[0][(int)SnesButton.Y]);
        Check(m.Pad[0][(int)SnesButton.B] == "L2+Y", "file: P1 B = L2+Y", m.Pad[0][(int)SnesButton.B]);
        Check(m.Pad[0][(int)SnesButton.Select] == "R2", "file: P1 Select = R2", m.Pad[0][(int)SnesButton.Select]);
        Check(m.Keys[0][(int)SnesButton.Down] == "W", "file: P1 Down = W", m.Keys[0][(int)SnesButton.Down]);
        Check(string.IsNullOrEmpty(m.Keys[0][(int)SnesButton.Up]) || m.Keys[0][(int)SnesButton.Up] == "None", "file: P1 Up cleared by Replace", m.Keys[0][(int)SnesButton.Up]);
        Check(m.Keys[0][(int)SnesButton.Left] == "Left", "file: P1 Left unchanged after Cancel", m.Keys[0][(int)SnesButton.Left]);
        Check(m.PadHotkeys["SaveStateMenu"] == "R3", "file: All save states pad = R3", m.PadHotkeys["SaveStateMenu"]);
        Check(m.Hotkeys["Screenshot"].SequenceEqual(new[] { "F9" }), "file: Screenshot = F9", string.Join(",", m.Hotkeys["Screenshot"]));
        Check(m.Hotkeys["Load[8]"].Count == 0, "file: Load state 9 lost F9 (Replace)", string.Join(",", m.Hotkeys["Load[8]"]));
        Check(m.Keys[1].SequenceEqual(InputPresets.Keyboard.First(p => p.Name.StartsWith("Numpad")).Values), "file: P2 numpad preset", string.Join(",", m.Keys[1]));
        Check(m.Device(1) == 2, "file: P2 keyboard only", m.Device(1));
        Check(m.Pad[0][(int)SnesButton.L] == "", "file: P1 L cleared by controller Y", m.Pad[0][(int)SnesButton.L]);
        File.Copy(Path.Combine(gameDir, "config.ini"), Path.Combine(gameDir, "pad-test-config.ini"), true);
        File.Copy(Path.Combine(gameDir, "keybinds.ini"), Path.Combine(gameDir, "pad-test-keybinds.ini"), true);
    }
}

internal static class DpiTests
{
    public static int Run(string engine, string outDir)
    {
        Directory.CreateDirectory(outDir);
        var problems = new List<string>(); var facts = new List<object>();
        var screen = Screen.PrimaryScreen!.WorkingArea;
        foreach (var dpi in new[] { 96, 144, 192 }) {
            using var form = new InputForm(engine, "auto") { StartPosition = FormStartPosition.Manual, Location = new Point(0, 0), ShowInTaskbar = false };
            form.Show(); Application.DoEvents();
            var before = form.Font.Size;
            var grid0 = Native.Descendants(form).OfType<DataGridView>().First();
            float gridBefore = grid0.DefaultCellStyle.Font!.Size, labelBefore = Native.Descendants(form).OfType<Label>().First().Font.Size;
            var comboBefore = Native.Descendants(form).OfType<ComboBox>().First().Font.Size;
            if (dpi != 96) { Native.ChangeDpi(form, dpi); Application.DoEvents(); }
            var tabs = Native.Descendants(form).OfType<TabControl>().Single(t => t.AccessibleName == "Sections");
            var label = Native.Descendants(form).OfType<Label>().First();
            facts.Add(new { dpi, deviceDpi = form.DeviceDpi, windowDpi = Native.GetDpiForWindow(form.Handle), fontBefore = before, fontAfter = form.Font.Size,
                firstLabelFont = label.Font.Size, form = form.Bounds.ToString(), client = form.ClientSize.ToString() });
            if (!screen.Contains(form.Bounds)) problems.Add($"{dpi}: window {form.Bounds} is not inside the working area {screen}");
            Application.DoEvents(); Thread.Sleep(100); Application.DoEvents();
            foreach (var (what, was, now) in new[] { ("grid text", gridBefore, grid0.DefaultCellStyle.Font!.Size), ("heading", labelBefore, Native.Descendants(form).OfType<Label>().First().Font.Size),
                                                      ("combo box", comboBefore, Native.Descendants(form).OfType<ComboBox>().First().Font.Size) })
                if (Math.Abs(now / was - dpi / 96f) > 0.05f) problems.Add($"{dpi}: {what} font {was} -> {now}, not scaled by {dpi / 96f}");
            if (dpi != 96 && Math.Abs(form.Font.Size / before - dpi / 96f) > 0.05f) problems.Add($"{dpi}: form font {before} -> {form.Font.Size}, not scaled by {dpi / 96f}");
            for (int i = 0; i < tabs.TabCount; i++) {
                tabs.SelectedIndex = i; Application.DoEvents();
                InputForm.CheckLayout(form, $"{dpi} dpi page {i}", problems);
                using var bmp = new Bitmap(form.Width, form.Height);
                form.DrawToBitmap(bmp, new Rectangle(Point.Empty, form.Size));
                bmp.Save(Path.Combine(outDir, $"controls-{dpi}-{i}.png"), System.Drawing.Imaging.ImageFormat.Png);
            }
            // The dialogs open on the same monitor, with the window's (scaled) font.
            Dialog(new CaptureForm("Player 1 · SNES A", true, false, 0, PadStyle.Xbox, form.Font), $"{dpi} capture (pad)", outDir, problems);
            Dialog(new CaptureForm("Settings and achievements", false, true, 0, PadStyle.Xbox, form.Font), $"{dpi} capture (shortcut)", outDir, problems);
            Dialog(new ConflictForm("Keypad 8 is already used by:\n• Player 2 · D-pad up\n• Volume up", true, form.Font), $"{dpi} conflict", outDir, problems);
            Dialog(new PickForm("Player 1 · SNES A (controller)", PadCatalog.Names.Select(n => (n, PadCatalog.Label(n, PadStyle.PlayStation))).ToList(), "A", form.Font), $"{dpi} pick", outDir, problems);
            form.Close();
        }
        Console.WriteLine(JsonSerializer.Serialize(new { passed = problems.Count == 0, screen = screen.ToString(), facts, problems }, new JsonSerializerOptions { WriteIndented = true }));
        return problems.Count == 0 ? 0 : 1;
    }
    private static void Dialog(Form dialog, string where, string outDir, List<string> problems)
    {
        using (dialog) {
            dialog.StartPosition = FormStartPosition.Manual; dialog.Location = new Point(0, 0); dialog.ShowInTaskbar = false;
            dialog.Show(); Application.DoEvents();
            InputForm.CheckLayout(dialog, where, problems);
            var screen = Screen.PrimaryScreen!.WorkingArea;
            if (dialog.Width > screen.Width || dialog.Height > screen.Height) problems.Add($"{where}: {dialog.Size} larger than the screen {screen.Size}");
            using var bmp = new Bitmap(dialog.Width, dialog.Height);
            dialog.DrawToBitmap(bmp, new Rectangle(Point.Empty, dialog.Size));
            bmp.Save(Path.Combine(outDir, where.Replace(' ', '-').Replace("(", "").Replace(")", "") + ".png"), System.Drawing.Imaging.ImageFormat.Png);
            dialog.Close();
        }
    }
}
