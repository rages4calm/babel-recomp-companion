using System.Globalization;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

// The game's input files, as the runner reads them (snesrecomp/runner/src):
//   keybinds.ini  [player1]/[player2]  a b x y l r start select up down left right
//                 one SDL scancode name per button (or Mouse1..Mouse5, or None);
//                 keybinds.c load_ini, SDL_GetScancodeFromName.
//   config.ini    [KeyMap]     system hotkeys, SDL keycode names with Shift+/Ctrl+/Alt+,
//                              several keys per command separated by commas, Load/Save
//                              positional per slot (desktop/mmx_config.c ParseKeyArray).
//                 [GamepadMap] Controls / ControlsP2: 12 pad buttons in the order
//                              Up Down Left Right Select Start A B X Y L R; any command
//                              may name one pad button or chord ("L2+Start"), player 1's
//                              pad only (ParseGamepadArray).
//                              EnableGamepad1/2 open a pad for that player.
//                 [Controller] SourceP1/SourceP2: 0 nobody, 1 keyboard, 2 controller.
// Nothing here writes a key the game does not read.

public enum SnesButton { A, B, X, Y, L, R, Start, Select, Up, Down, Left, Right }

public sealed record KeyInfo(string Name, int Scancode, int Vk, int Set1, bool Extended, string? Hotkey, string Label);

public static class KeyCatalog
{
    private static readonly List<KeyInfo> all = new();
    private static void Add(string name, int sc, int vk, int set1, bool ext = false, string? hotkey = "", string? label = null) =>
        all.Add(new(name, sc, vk, set1, ext, hotkey == "" ? name : hotkey, label ?? name));
    static KeyCatalog()
    {
        // SDL scancode numbers and names are SDL3's own (verified against SDL by
        // scripts/test_input_bindings.c --names); set-1 scan codes are the PC
        // keyboard's physical positions, which is what keybinds.ini names.
        const string letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
        int[] letterScan = { 0x1E, 0x30, 0x2E, 0x20, 0x12, 0x21, 0x22, 0x23, 0x17, 0x24, 0x25, 0x26, 0x32, 0x31, 0x18, 0x19, 0x10, 0x13, 0x1F, 0x14, 0x16, 0x2F, 0x11, 0x2D, 0x15, 0x2C };
        for (int i = 0; i < 26; i++) Add(letters[i].ToString(), 4 + i, 'A' + i, letterScan[i], hotkey: char.ToLowerInvariant(letters[i]).ToString());
        for (int i = 1; i <= 9; i++) Add(i.ToString(CultureInfo.InvariantCulture), 29 + i, '0' + i, 1 + i);
        Add("0", 39, '0', 0x0B);
        Add("Return", 40, 0x0D, 0x1C, label: "Enter"); Add("Escape", 41, 0x1B, 0x01, label: "Esc"); Add("Backspace", 42, 0x08, 0x0E);
        Add("Tab", 43, 0x09, 0x0F); Add("Space", 44, 0x20, 0x39);
        Add("-", 45, 0xBD, 0x0C); Add("=", 46, 0xBB, 0x0D); Add("[", 47, 0xDB, 0x1A); Add("]", 48, 0xDD, 0x1B); Add("\\", 49, 0xDC, 0x2B);
        Add(";", 51, 0xBA, 0x27); Add("'", 52, 0xDE, 0x28); Add("`", 53, 0xC0, 0x29);
        Add(",", 54, 0xBC, 0x33, hotkey: null); // config.ini separates keys with commas
        Add(".", 55, 0xBE, 0x34); Add("/", 56, 0xBF, 0x35);
        Add("CapsLock", 57, 0x14, 0x3A, label: "Caps Lock");
        for (int i = 1; i <= 10; i++) Add("F" + i, 57 + i, 0x6F + i, 0x3A + i);
        Add("F11", 68, 0x7A, 0x57); Add("F12", 69, 0x7B, 0x58);
        Add("PrintScreen", 70, 0x2C, 0x37, true, label: "Print Screen"); Add("ScrollLock", 71, 0x91, 0x46, label: "Scroll Lock");
        Add("Pause", 72, 0x13, 0x45);   // matched by virtual key (shares 0x45 with Num Lock)
        Add("Insert", 73, 0x2D, 0x52, true); Add("Home", 74, 0x24, 0x47, true); Add("PageUp", 75, 0x21, 0x49, true, label: "Page Up");
        Add("Delete", 76, 0x2E, 0x53, true); Add("End", 77, 0x23, 0x4F, true); Add("PageDown", 78, 0x22, 0x51, true, label: "Page Down");
        Add("Right", 79, 0x27, 0x4D, true, label: "Right arrow"); Add("Left", 80, 0x25, 0x4B, true, label: "Left arrow");
        Add("Down", 81, 0x28, 0x50, true, label: "Down arrow"); Add("Up", 82, 0x26, 0x48, true, label: "Up arrow");
        Add("Numlock", 83, 0x90, 0x45, true, label: "Num Lock");
        Add("Keypad /", 84, 0x6F, 0x35, true); Add("Keypad *", 85, 0x6A, 0x37); Add("Keypad -", 86, 0x6D, 0x4A); Add("Keypad +", 87, 0x6B, 0x4E);
        Add("Keypad Enter", 88, 0x0D, 0x1C, true);
        int[] padScan = { 0x4F, 0x50, 0x51, 0x4B, 0x4C, 0x4D, 0x47, 0x48, 0x49 };
        for (int i = 1; i <= 9; i++) Add("Keypad " + i, 88 + i, 0x60 + i, padScan[i - 1]);
        Add("Keypad 0", 98, 0x60, 0x52); Add("Keypad .", 99, 0x6E, 0x53);
        Add("NonUSBackslash", 100, 0xE2, 0x56, hotkey: null, label: "< > (ISO key)"); // SDL gives its keycode no name
        Add("Application", 101, 0x5D, 0x5D, true, label: "Menu key");
        Add("Left Ctrl", 224, 0xA2, 0x1D); Add("Left Shift", 225, 0xA0, 0x2A); Add("Left Alt", 226, 0xA4, 0x38); Add("Left GUI", 227, 0x5B, 0x5B, true, label: "Left Windows");
        Add("Right Ctrl", 228, 0xA3, 0x1D, true); Add("Right Shift", 229, 0xA1, 0x36); Add("Right Alt", 230, 0xA5, 0x38, true); Add("Right GUI", 231, 0x5C, 0x5C, true, label: "Right Windows");
    }
    public static IReadOnlyList<KeyInfo> All => all;
    public static readonly string[] MouseNames = { "Mouse1", "Mouse2", "Mouse3", "Mouse4", "Mouse5" };
    private static readonly string[] mouseLabels = { "Left mouse button", "Right mouse button", "Middle mouse button", "Mouse back", "Mouse forward" };

    /// <summary>The keybinds.ini name for a physical key (set-1 scan code), with the virtual key to tell apart keys sharing a code.</summary>
    public static KeyInfo? FromScan(int set1, bool extended, int vk)
    {
        if (vk == 0x13) return ByName("Pause");
        if (vk == 0x90) return ByName("Numlock");
        if (vk is 0x10 or 0x11 or 0x12) { // generic Shift/Ctrl/Alt: the scan code says which side
            if (set1 == 0x36) return ByName("Right Shift");
            if (set1 == 0x2A) return ByName("Left Shift");
        }
        return all.FirstOrDefault(k => k.Set1 == set1 && k.Extended == extended && k.Name is not "Pause" and not "Numlock")
            ?? FromVk(vk);
    }
    public static KeyInfo? FromVk(int vk) => all.FirstOrDefault(k => k.Vk == vk && k.Name != "Keypad Enter");
    public static KeyInfo? ByName(string name) =>
        all.FirstOrDefault(k => k.Name.Equals(name, StringComparison.OrdinalIgnoreCase));
    /// <summary>A [KeyMap] key name (keycode): matches the hotkey spelling, then the scancode name.</summary>
    public static KeyInfo? ByHotkey(string name) =>
        all.FirstOrDefault(k => k.Hotkey != null && k.Hotkey.Equals(name, StringComparison.OrdinalIgnoreCase)) ??
        (name.Equals("Enter", StringComparison.OrdinalIgnoreCase) ? ByName("Return") : ByName(name));

    /// <summary>keybinds.ini value -> canonical name, or null when the runner would not understand it. Accepts the runner's aliases.</summary>
    public static string? NormalizeBinding(string value)
    {
        var v = value.Trim();
        if (v.Length == 0 || v.Equals("None", StringComparison.OrdinalIgnoreCase)) return "None";
        var mouse = MouseNames.FirstOrDefault(m => m.Equals(v, StringComparison.OrdinalIgnoreCase)); if (mouse != null) return mouse;
        if (ByName(v) is { } k) return k.Name;
        return v.ToLowerInvariant() switch {
            "enter" => "Return", "esc" => "Escape", "lshift" => "Left Shift", "rshift" => "Right Shift",
            "lctrl" => "Left Ctrl", "rctrl" => "Right Ctrl", _ => null };
    }
    public static string Label(string binding)
    {
        if (binding == "None") return "—";
        var m = Array.IndexOf(MouseNames, binding); if (m >= 0) return mouseLabels[m];
        return ByName(binding)?.Label ?? binding;
    }
}

public enum PadStyle { Xbox, Nintendo, PlayStation }

/// <summary>Controller buttons by the runner's [GamepadMap] names. Positions, not letters: A is the bottom face button.</summary>
public static class PadCatalog
{
    // Index = runner kGamepadBtn_*.
    public static readonly string[] Names = { "A", "B", "X", "Y", "Back", "Guide", "Start", "L3", "R3", "L1", "R1", "DpadUp", "DpadDown", "DpadLeft", "DpadRight", "L2", "R2" };
    private static readonly string[][] labels = {
        new[] { "A", "B", "X", "Y", "View", "Xbox button", "Menu", "Left stick press (LS)", "Right stick press (RS)", "LB", "RB", "D-pad up", "D-pad down", "D-pad left", "D-pad right", "LT", "RT" },
        new[] { "B", "A", "Y", "X", "−", "Home", "+", "Left stick press", "Right stick press", "L", "R", "D-pad up", "D-pad down", "D-pad left", "D-pad right", "ZL", "ZR" },
        new[] { "Cross", "Circle", "Square", "Triangle", "Create", "PS button", "Options", "L3", "R3", "L1", "R1", "D-pad up", "D-pad down", "D-pad left", "D-pad right", "L2", "R2" },
    };
    public static int Index(string name)
    {
        var n = name.Trim();
        if (n.Equals("Lb", StringComparison.OrdinalIgnoreCase)) return 9;
        if (n.Equals("Rb", StringComparison.OrdinalIgnoreCase)) return 10;
        return Array.FindIndex(Names, x => x.Equals(n, StringComparison.OrdinalIgnoreCase));
    }
    /// <summary>"L2+Start" -> canonical chord, "" for unbound, null when the runner would reject it.</summary>
    public static string? Normalize(string value)
    {
        var v = value.Trim();
        if (v.Length == 0 || v.Equals("None", StringComparison.OrdinalIgnoreCase)) return "";
        var parts = v.Split('+').Select(p => Index(p)).ToArray();
        if (parts.Any(p => p < 0) || parts.Distinct().Count() != parts.Length) return null;
        return string.Join("+", parts.Select(p => Names[p]));
    }
    public static string Label(string chord, PadStyle style) =>
        chord.Length == 0 ? "—" : string.Join(" + ", chord.Split('+').Select(p => Index(p) is var i && i >= 0 ? labels[(int)style][i] : p));
}

/// <summary>A keyboard hotkey chord in [KeyMap] spelling: "Shift+F1", "Alt+Return", "p".</summary>
public static class Chord
{
    public static string? Normalize(string value)
    {
        var s = value.Trim(); if (s.Length == 0) return null;
        bool shift = false, ctrl = false, alt = false;
        for (;;) {
            if (s.StartsWith("Shift+", StringComparison.OrdinalIgnoreCase)) { shift = true; s = s[6..]; }
            else if (s.StartsWith("Ctrl+", StringComparison.OrdinalIgnoreCase)) { ctrl = true; s = s[5..]; }
            else if (s.StartsWith("Alt+", StringComparison.OrdinalIgnoreCase)) { alt = true; s = s[4..]; }
            else break;
        }
        var key = KeyCatalog.ByHotkey(s);
        if (key?.Hotkey == null) return null;
        return Make(key, shift, ctrl, alt);
    }
    public static string Make(KeyInfo key, bool shift, bool ctrl, bool alt) =>
        (shift ? "Shift+" : "") + (ctrl ? "Ctrl+" : "") + (alt ? "Alt+" : "") + key.Hotkey;
    private static string Strip(string chord, out string mods)
    {
        var s = chord; var m = new StringBuilder();
        foreach (var prefix in new[] { "Shift+", "Ctrl+", "Alt+" })
            while (s.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)) { m.Append(prefix); s = s[prefix.Length..]; }
        mods = m.ToString(); return s;
    }
    public static KeyInfo? Key(string chord) => KeyCatalog.ByHotkey(Strip(chord, out _));
    public static bool HasModifier(string chord) => chord.StartsWith("Shift+") || chord.StartsWith("Ctrl+") || chord.StartsWith("Alt+");
    public static string Label(string chord)
    {
        var rest = Strip(chord, out var mods); var key = KeyCatalog.ByHotkey(rest);
        return mods.Replace("+", " + ") + (key?.Label ?? rest);
    }
}

public sealed record HotkeyDefinition(string Command, int Slot, string Label, string Group, string[] Keys, string FreshKeys, string Pad, string Help = "");

/// <summary>The hotkeys this game offers (src/main.c's host flags: no in-game launcher, legacy state slots).</summary>
public static class HotkeyCatalog
{
    private static HotkeyDefinition K(string cmd, string label, string group, string keys, string? fresh = null, string pad = "", string help = "") =>
        new(cmd, -1, label, group, keys.Length == 0 ? Array.Empty<string>() : keys.Split(','), fresh ?? keys, pad, help);
    public static readonly IReadOnlyList<HotkeyDefinition> All = BuildAll();
    private static List<HotkeyDefinition> BuildAll()
    {
        var list = new List<HotkeyDefinition> {
            K("SettingsMenu", "Settings and achievements", "Menus", "Escape", pad: "L2+R3"),
            K("Companion", "Companion screen", "Menus", "i", pad: "L2+L3"),
            K("SaveStateMenu", "All save states", "Menus", "F11", pad: "L2+Start"),
            K("Rewind", "Rewind", "Menus", "F12", pad: "L2+Back", help: "The controller can also rewind with Select + right stick press ([Controller] RewindGesture)."),
            K("Turbo", "Fast forward (hold)", "Play", "Tab"),
            K("Pause", "Pause", "Play", "Shift+p"),
            K("PauseDimmed", "Pause (dimmed)", "Play", "p"),
            K("Reset", "Reset the console", "Play", "Ctrl+r"),
            K("Fullscreen", "Fullscreen on/off", "Window", "Alt+Return"),
            K("WindowBigger", "Bigger window", "Window", "", "Ctrl+Up"),
            K("WindowSmaller", "Smaller window", "Window", "", "Ctrl+Down"),
            K("Screenshot", "Screenshot", "Window", "PrintScreen"),
            K("DisplayPerf", "Show frame rate", "Window", "f", pad: "L2+X"),
            K("VolumeUp", "Volume up", "Sound", "Keypad +", pad: "L2+DpadUp"),
            K("VolumeDown", "Volume down", "Sound", "Keypad -", pad: "L2+DpadDown"),
            K("ToggleVSync", "Vertical sync on/off", "Window", ""),
            K("ToggleFrameBlend", "Frame blending on/off", "Window", ""),
            K("ToggleRunAhead", "Run-ahead frames +1", "Play", ""),
            K("ToggleRenderer", "Switch PPU renderer (diagnostic)", "Window", "r"),
        };
        for (int i = 0; i < 10; i++)
            list.Add(new("Load", i, $"Load state {i + 1}", "Save states", new[] { "F" + (i + 1) }, "F" + (i + 1), i == 0 ? "L2+L1" : ""));
        for (int i = 0; i < 10; i++)
            list.Add(new("Save", i, $"Save state {i + 1}", "Save states", new[] { "Shift+F" + (i + 1) }, "Shift+F" + (i + 1), i == 0 ? "L2+R1" : ""));
        return list;
    }
    public static string Id(HotkeyDefinition d) => d.Slot < 0 ? d.Command : d.Command + "[" + d.Slot + "]";
    public static HotkeyDefinition? Find(string id) => All.FirstOrDefault(d => Id(d) == id);
}

/// <summary>Everything the editor manages, in the game's own vocabulary.</summary>
public sealed class InputModel
{
    public string[][] Keys = { new string[12], new string[12] };      // keybinds.ini, by SnesButton
    public string[][] Pad = { new string[12], new string[12] };       // [GamepadMap] chord per SnesButton
    public Dictionary<string, List<string>> Hotkeys = new();           // HotkeyCatalog id -> chords ([KeyMap])
    public Dictionary<string, string> PadHotkeys = new();              // id -> chord ([GamepadMap]), "" none
    public int[] Source = { 1, 0 };                                    // [Controller] SourceP1/P2
    public bool[] Gamepad = { true, true };                            // [GamepadMap] EnableGamepad1/2

    public static readonly string[] IniNames = { "a", "b", "x", "y", "l", "r", "start", "select", "up", "down", "left", "right" };
    /// <summary>[GamepadMap] Controls order: Up Down Left Right Select Start A B X Y L R.</summary>
    public static readonly SnesButton[] ControlsOrder = { SnesButton.Up, SnesButton.Down, SnesButton.Left, SnesButton.Right, SnesButton.Select, SnesButton.Start, SnesButton.A, SnesButton.B, SnesButton.X, SnesButton.Y, SnesButton.L, SnesButton.R };
    public static readonly string[] DefaultKeys = { "X", "Z", "S", "A", "C", "V", "Return", "Right Shift", "Up", "Down", "Left", "Right" };
    public static readonly string[] DefaultPad = { "B", "A", "Y", "X", "L1", "R1", "Start", "Back", "DpadUp", "DpadDown", "DpadLeft", "DpadRight" };

    public static InputModel Defaults()
    {
        var m = new InputModel();
        for (int p = 0; p < 2; p++) { m.Keys[p] = (string[])DefaultKeys.Clone(); m.Pad[p] = (string[])DefaultPad.Clone(); }
        foreach (var d in HotkeyCatalog.All) { m.Hotkeys[HotkeyCatalog.Id(d)] = d.Keys.ToList(); m.PadHotkeys[HotkeyCatalog.Id(d)] = d.Pad; }
        return m;
    }
    public InputModel Clone()
    {
        var m = new InputModel { Source = (int[])Source.Clone(), Gamepad = (bool[])Gamepad.Clone() };
        for (int p = 0; p < 2; p++) { m.Keys[p] = (string[])Keys[p].Clone(); m.Pad[p] = (string[])Pad[p].Clone(); }
        foreach (var pair in Hotkeys) m.Hotkeys[pair.Key] = pair.Value.ToList();
        foreach (var pair in PadHotkeys) m.PadHotkeys[pair.Key] = pair.Value;
        return m;
    }
    public bool UsesKeyboard(int player) => Source[player] == 1;
    /// <summary>With the launcher's normal Play (--no-launcher) a controller drives a player whenever EnableGamepadN is on; SourceN gates only the keyboard.</summary>
    public bool UsesPad(int player) => Gamepad[player];
    /// <summary>The editor's single "plays with" choice: 0 keyboard and controller, 1 controller only, 2 keyboard only, 3 nobody.</summary>
    public int Device(int player) => player is < 0 or > 1 ? throw new ArgumentOutOfRangeException(nameof(player), "Players are 0 and 1.") : Source[player] == 1 ? (Gamepad[player] ? 0 : 2) : Gamepad[player] ? 1 : 3;
    public void SetDevice(int player, int device)
    {
        // Leave Source alone where it already means the same thing (0 and 2 both keep the keyboard off).
        switch (device) {
            case 0: Source[player] = 1; Gamepad[player] = true; break;
            case 1: if (Source[player] == 1) Source[player] = 2; Gamepad[player] = true; break;
            case 2: Source[player] = 1; Gamepad[player] = false; break;
            default: Source[player] = 0; Gamepad[player] = false; break;
        }
    }
}

/// <summary>A line-preserving INI text: comments, order, unknown keys and newline style survive.</summary>
public sealed class IniText
{
    private readonly List<string> lines;
    public string Newline { get; }
    public bool Bom { get; }
    private readonly bool hashComments;   // config.ini strips "# ..." anywhere; keybinds.ini only at line start
    public IniText(string? text, bool hashCommentsInline, bool bom = false)
    {
        text ??= "";
        if (text.Contains('\0')) throw new InvalidDataException("The file contains binary data.");
        Newline = text.Contains("\r\n") ? "\r\n" : "\n"; Bom = bom; hashComments = hashCommentsInline;
        lines = text.Length == 0 ? new() : text.Replace("\r\n", "\n").Split('\n').ToList();
        if (lines.Count > 0 && lines[^1] == "") lines.RemoveAt(lines.Count - 1);
    }
    public static IniText Read(string path, bool hashCommentsInline)
    {
        if (!File.Exists(path)) return new(null, hashCommentsInline);
        var bytes = File.ReadAllBytes(path);
        if (bytes.Length > 1 << 20) throw new InvalidDataException(Path.GetFileName(path) + " exceeds 1 MiB.");
        var bom = bytes.AsSpan().StartsWith(new byte[] { 0xEF, 0xBB, 0xBF });
        return new(new UTF8Encoding(false, true).GetString(bytes, bom ? 3 : 0, bytes.Length - (bom ? 3 : 0)), hashCommentsInline, bom);
    }
    public override string ToString() => string.Join(Newline, lines) + (lines.Count == 0 ? "" : Newline);
    public byte[] ToBytes() => (Bom ? new byte[] { 0xEF, 0xBB, 0xBF } : Array.Empty<byte>()).Concat(Encoding.UTF8.GetBytes(ToString())).ToArray();

    private static string? SectionOf(string line) { var s = line.Trim(); return s.StartsWith('[') && s.Contains(']') ? s[1..s.IndexOf(']')].Trim() : null; }
    private (string key, string value)? Pair(string line)
    {
        var s = line.TrimStart();
        if (s.Length == 0 || s[0] == '#' || s[0] == ';' || s[0] == '[') return null;
        var eq = s.IndexOf('='); if (eq < 0) return null;
        var v = s[(eq + 1)..];
        if (hashComments) { var c = v.IndexOf('#'); if (c >= 0) v = v[..c]; }
        return (s[..eq].Trim(), v.Trim());
    }
    /// <summary>Indices of every line for section/key (case-insensitive, as the runner compares).</summary>
    private List<int> Find(string section, string key)
    {
        var found = new List<int>(); string? current = null;
        for (int i = 0; i < lines.Count; i++) {
            if (SectionOf(lines[i]) is { } sec) { current = sec; continue; }
            if (current != null && current.Equals(section, StringComparison.OrdinalIgnoreCase) && Pair(lines[i]) is { } kv && kv.key.Equals(key, StringComparison.OrdinalIgnoreCase)) found.Add(i);
        }
        return found;
    }
    /// <summary>The value the runner ends up with: the last line wins for keybinds.ini; config.ini rejects duplicates in managed sections.</summary>
    public string? Get(string section, string key) { var f = Find(section, key); return f.Count == 0 ? null : Pair(lines[f[^1]])!.Value.value; }
    public int Count(string section, string key) => Find(section, key).Count;
    public bool HasSection(string section) => lines.Any(l => SectionOf(l)?.Equals(section, StringComparison.OrdinalIgnoreCase) == true);
    public IEnumerable<string> Keys(string section)
    {
        string? current = null;
        foreach (var l in lines) {
            if (SectionOf(l) is { } sec) { current = sec; continue; }
            if (current?.Equals(section, StringComparison.OrdinalIgnoreCase) == true && Pair(l) is { } kv) yield return kv.key;
        }
    }
    /// <summary>Set in place (keeping the key's spelling, alignment and any trailing comment), else append to the section, else add the section.</summary>
    public void Set(string section, string key, string value, string? newKeyFormat = null)
    {
        var found = Find(section, key);
        if (found.Count > 0) {
            int i = found[^1]; var line = lines[i]; var eq = line.IndexOf('=');
            var rest = line[(eq + 1)..]; var comment = "";
            if (hashComments && rest.IndexOf('#') is var c && c >= 0) {   // keep the comment and the spacing before it
                int ws = rest[..c].Length - rest[..c].TrimEnd().Length;
                comment = (ws == 0 ? " " : "") + rest[(c - ws)..];
            }
            var gap = rest.Length - rest.TrimStart().Length;
            lines[i] = line[..(eq + 1)] + (gap > 0 ? rest[..gap] : " ") + value + comment;
            return;
        }
        var text = newKeyFormat != null ? string.Format(CultureInfo.InvariantCulture, newKeyFormat, key, value) : key + " = " + value;
        string? current = null; int end = -1, start = -1;
        for (int i = 0; i < lines.Count; i++) {
            if (SectionOf(lines[i]) is { } sec) {
                if (start >= 0 && end < 0) end = i;
                current = sec;
                if (start < 0 && sec.Equals(section, StringComparison.OrdinalIgnoreCase)) start = i;
            }
        }
        if (start >= 0) {
            if (end < 0) end = lines.Count;
            int at = end; while (at - 1 > start && lines[at - 1].Trim().Length == 0) at--;   // before the blank lines that close the section
            lines.Insert(at, text);
            return;
        }
        if (lines.Count > 0 && lines[^1].Trim().Length != 0) lines.Add("");
        lines.Add("[" + section + "]"); lines.Add(text);
    }
}

public sealed record Conflict(string Where, string Description);

/// <summary>Reads and writes the model to an install's config.ini and keybinds.ini.</summary>
public sealed class InputFiles
{
    public string Directory { get; }
    public string ConfigPath => Path.Combine(Directory, "config.ini");
    public string KeybindsPath => Path.Combine(Directory, "keybinds.ini");
    public string LocalOverridePath => Path.Combine(Directory, "config.local.ini");
    public InputFiles(string directory) => Directory = Path.GetFullPath(directory);
    private static readonly string[] Managed = { "KeyMap", "GamepadMap", "Controller" };

    public InputModel Load(List<string>? warnings = null)
    {
        var m = InputModel.Defaults();
        var config = IniText.Read(ConfigPath, true); var keys = IniText.Read(KeybindsPath, false);
        foreach (var section in Managed)
            foreach (var dup in config.Keys(section).GroupBy(k => k, StringComparer.OrdinalIgnoreCase).Where(g => g.Count() > 1))
                throw new InvalidDataException($"config.ini names [{section}] {dup.Key} twice. Remove one of them; nothing was changed.");
        for (int p = 0; p < 2; p++) {
            string section = "player" + (p + 1);
            for (int b = 0; b < 12; b++) {
                var text = keys.Get(section, InputModel.IniNames[b]);
                if (text == null) continue;   // the runner keeps its default for a missing line
                var norm = KeyCatalog.NormalizeBinding(text);
                if (norm == null) { warnings?.Add($"keybinds.ini [{section}] {InputModel.IniNames[b]} = {text} is not a key the game knows; it is treated as unbound."); norm = "None"; }
                m.Keys[p][b] = norm;
            }
            var controls = config.Get("GamepadMap", p == 0 ? "Controls" : "ControlsP2");
            if (controls != null) {
                var parts = controls.Split(',');
                for (int i = 0; i < 12; i++) {
                    var chord = i < parts.Length ? PadCatalog.Normalize(parts[i]) : "";
                    if (chord == null) { warnings?.Add($"config.ini [GamepadMap] {(p == 0 ? "Controls" : "ControlsP2")} item {i + 1} '{parts[i].Trim()}' is not a controller button; treated as unbound."); chord = ""; }
                    m.Pad[p][(int)InputModel.ControlsOrder[i]] = chord;
                }
            }
            if (int.TryParse(config.Get("Controller", "SourceP" + (p + 1)), NumberStyles.Integer, CultureInfo.InvariantCulture, out var src) && src is >= 0 and <= 2) m.Source[p] = src;
            var enable = config.Get("GamepadMap", "EnableGamepad" + (p + 1));
            if (enable != null) m.Gamepad[p] = enable == "1" || enable.Equals("true", StringComparison.OrdinalIgnoreCase);
        }
        foreach (var group in HotkeyCatalog.All.GroupBy(d => d.Command)) {
            var line = config.Get("KeyMap", group.Key);
            if (line != null) {
                var parts = line.Split(',').Select(x => x.Trim()).ToArray();
                foreach (var d in group) {
                    List<string> chords;
                    if (d.Slot < 0) chords = parts.Where(x => x.Length > 0 && !IsNone(x)).Select(x => Chord.Normalize(x) ?? Warn(warnings, $"[KeyMap] {group.Key}: '{x}' is not a key the game knows")).Where(x => x != null).Select(x => x!).ToList();
                    else chords = d.Slot < parts.Length && parts[d.Slot].Length > 0 && !IsNone(parts[d.Slot]) && Chord.Normalize(parts[d.Slot]) is { } c ? new() { c } : new();
                    m.Hotkeys[HotkeyCatalog.Id(d)] = chords;
                }
            }
            var pad = config.Get("GamepadMap", group.Key);
            if (pad != null) {
                var parts = pad.Split(',');
                foreach (var d in group) {
                    int slot = Math.Max(0, d.Slot);
                    var chord = slot < parts.Length ? PadCatalog.Normalize(parts[slot]) : "";
                    m.PadHotkeys[HotkeyCatalog.Id(d)] = chord ?? "";
                }
            }
        }
        if (File.Exists(LocalOverridePath)) warnings?.Add("config.local.ini exists beside the game and is read after config.ini; its [KeyMap] or [GamepadMap] lines can override what is shown here.");
        return m;
    }
    private static bool IsNone(string s) => s.Equals("None", StringComparison.OrdinalIgnoreCase) || s.Equals("(unbound)", StringComparison.OrdinalIgnoreCase);
    private static string? Warn(List<string>? w, string text) { w?.Add(text + "; it is ignored."); return null; }

    /// <summary>
    /// Writes only what differs between <paramref name="before"/> (what was loaded) and
    /// <paramref name="after"/>, onto the files as they are now, so a value another
    /// program changed meanwhile survives unless the player changed it here too.
    /// Both files are written atomically. Returns the number of keys written.
    /// </summary>
    public int Save(InputModel before, InputModel after)
    {
        var config = IniText.Read(ConfigPath, true); var keys = IniText.Read(KeybindsPath, false);
        string configOriginal = config.ToString(), keysOriginal = keys.ToString();
        int written = 0;
        for (int p = 0; p < 2; p++) {
            string section = "player" + (p + 1);
            for (int b = 0; b < 12; b++)
                if (before.Keys[p][b] != after.Keys[p][b]) { keys.Set(section, InputModel.IniNames[b], after.Keys[p][b], "{0,-7} = {1}"); written++; }
            if (!before.Pad[p].SequenceEqual(after.Pad[p])) {
                var current = Load().Pad[p];   // fresh file state for the buttons not edited here
                var merged = Enumerable.Range(0, 12).Select(i => before.Pad[p][i] != after.Pad[p][i] ? after.Pad[p][i] : current[i]).ToArray();
                config.Set("GamepadMap", p == 0 ? "Controls" : "ControlsP2", string.Join(", ", InputModel.ControlsOrder.Select(s => merged[(int)s])));
                written++;
            }
            if (before.Source[p] != after.Source[p]) { config.Set("Controller", "SourceP" + (p + 1), after.Source[p].ToString(CultureInfo.InvariantCulture)); written++; }
            if (before.Gamepad[p] != after.Gamepad[p]) { config.Set("GamepadMap", "EnableGamepad" + (p + 1), after.Gamepad[p] ? "true" : "false"); written++; }
        }
        var fresh = HotkeyCatalog.All.Any(d => !Same(before, after, d)) ? Load() : null;
        foreach (var group in HotkeyCatalog.All.GroupBy(d => d.Command)) {
            var list = group.ToList();
            if (list.Any(d => !before.Hotkeys[HotkeyCatalog.Id(d)].SequenceEqual(after.Hotkeys[HotkeyCatalog.Id(d)]))) {
                string value;
                if (list[0].Slot < 0) value = Join(after.Hotkeys[list[0].Command]);
                else {
                    // Load/Save: one key per slot, positionally; slots beyond the ten shown here are kept.
                    var existing = config.Get("KeyMap", group.Key)?.Split(',').Select(x => x.Trim()).ToList() ?? new();
                    var slots = list.Select(d => (Changed(before, after, d) ? after : fresh!).Hotkeys[HotkeyCatalog.Id(d)].FirstOrDefault() ?? "None").ToList();
                    slots.AddRange(existing.Skip(list.Count));
                    while (slots.Count > list.Count && (slots[^1].Length == 0 || IsNone(slots[^1]))) slots.RemoveAt(slots.Count - 1);
                    value = string.Join(",", slots);
                }
                config.Set("KeyMap", group.Key, value); written++;
            }
            if (list.Any(d => before.PadHotkeys[HotkeyCatalog.Id(d)] != after.PadHotkeys[HotkeyCatalog.Id(d)])) {
                // [GamepadMap] reads one pad button per Load/Save slot; an empty item is no binding.
                var value = list[0].Slot < 0 ? after.PadHotkeys[list[0].Command]
                    : string.Join(", ", list.Select(d => before.PadHotkeys[HotkeyCatalog.Id(d)] != after.PadHotkeys[HotkeyCatalog.Id(d)] ? after.PadHotkeys[HotkeyCatalog.Id(d)] : fresh!.PadHotkeys[HotkeyCatalog.Id(d)])).TrimEnd(',', ' ');
                config.Set("GamepadMap", group.Key, value); written++;
            }
        }
        if (keys.ToString() != keysOriginal) AtomicWrite(KeybindsPath, keys.ToBytes());
        if (config.ToString() != configOriginal) AtomicWrite(ConfigPath, config.ToBytes());
        return written;
    }
    private static bool Changed(InputModel a, InputModel b, HotkeyDefinition d) =>
        !a.Hotkeys[HotkeyCatalog.Id(d)].SequenceEqual(b.Hotkeys[HotkeyCatalog.Id(d)]);
    private static bool Same(InputModel a, InputModel b, HotkeyDefinition d) =>
        a.Hotkeys[HotkeyCatalog.Id(d)].SequenceEqual(b.Hotkeys[HotkeyCatalog.Id(d)]) && a.PadHotkeys[HotkeyCatalog.Id(d)] == b.PadHotkeys[HotkeyCatalog.Id(d)];
    private static string Join(List<string> chords) => chords.Count == 0 ? "None" : string.Join(", ", chords);
    public static void AtomicWrite(string path, byte[] content)
    {
        var temp = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try {
            using (var f = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None)) { f.Write(content); f.Flush(true); }
            File.Move(temp, path, true);
        } finally { if (File.Exists(temp)) File.Delete(temp); }
    }
}

/// <summary>Where a binding lives, for conflict checks and the editor's rows.</summary>
public sealed record BindingSlot(string Kind, int Player, SnesButton? Button, string? HotkeyId)
{
    public static BindingSlot Key(int player, SnesButton b) => new("key", player, b, null);
    public static BindingSlot PadButton(int player, SnesButton b) => new("pad", player, b, null);
    public static BindingSlot Hotkey(string id) => new("hotkey", 0, null, id);
    public static BindingSlot PadHotkey(string id) => new("padhotkey", 0, null, id);
    public string Describe(PadStyle style = PadStyle.Xbox) => Kind switch {
        "key" => $"Player {Player + 1} {Button} (keyboard)",
        "pad" => $"Player {Player + 1} {Button} (controller)",
        "hotkey" => HotkeyCatalog.Find(HotkeyId!)!.Label + " (keyboard shortcut)",
        _ => HotkeyCatalog.Find(HotkeyId!)!.Label + " (controller shortcut)" };
}

public static class InputRules
{
    /// <summary>The scancode a keybinds.ini name or [KeyMap] chord presses (the chord's key itself), for comparing the two files.</summary>
    private static string? Physical(string binding) => KeyCatalog.ByName(binding)?.Name ?? (KeyCatalog.MouseNames.Contains(binding) ? binding : null);

    /// <summary>Other slots that the given binding would collide with, as the game would see it.</summary>
    public static List<BindingSlot> Conflicts(InputModel m, BindingSlot target, string binding)
    {
        var hits = new List<BindingSlot>();
        if (binding.Length == 0 || binding == "None") return hits;
        if (target.Kind is "key" or "hotkey") {
            // keyboard: same physical key within one player's buttons, or between a button and an unmodified hotkey
            string? phys = target.Kind == "key" ? Physical(binding) : Chord.HasModifier(binding) ? null : Chord.Key(binding)?.Name;
            for (int p = 0; p < 2; p++)
                for (int b = 0; b < 12; b++) {
                    var slot = BindingSlot.Key(p, (SnesButton)b);
                    if (slot == target || m.Keys[p][b] == "None") continue;
                    // A player's own buttons always count; a hotkey only meets the buttons of a player reading the keyboard.
                    bool relevant = target.Kind == "hotkey" ? m.UsesKeyboard(p) : p == target.Player;
                    if (relevant && phys != null && Physical(m.Keys[p][b]) == phys) hits.Add(slot);
                }
            foreach (var d in HotkeyCatalog.All) {
                var slot = BindingSlot.Hotkey(HotkeyCatalog.Id(d));
                if (slot == target) continue;
                foreach (var chord in m.Hotkeys[HotkeyCatalog.Id(d)])
                    if (target.Kind == "hotkey" ? chord.Equals(binding, StringComparison.OrdinalIgnoreCase)
                                                : !Chord.HasModifier(chord) && Chord.Key(chord)?.Name == phys)
                        { hits.Add(slot); break; }
            }
        } else {
            // controller: same chord on one pad. Hotkeys are read from player 1's pad only.
            for (int b = 0; b < 12; b++) {
                var slot = BindingSlot.PadButton(target.Player, (SnesButton)b);
                if (slot != target && m.Pad[target.Player][b] == binding) hits.Add(slot);
            }
            if (target.Kind == "padhotkey" || target.Player == 0)
                foreach (var d in HotkeyCatalog.All) {
                    var slot = BindingSlot.PadHotkey(HotkeyCatalog.Id(d));
                    if (slot != target && m.PadHotkeys[HotkeyCatalog.Id(d)] == binding) hits.Add(slot);
                }
            if (target.Kind == "padhotkey")
                for (int b = 0; b < 12; b++) {
                    var slot = BindingSlot.PadButton(0, (SnesButton)b);
                    if (m.Pad[0][b] == binding && !hits.Contains(slot)) hits.Add(slot);
                }
        }
        return hits.Distinct().ToList();
    }

    public static string Get(InputModel m, BindingSlot s, int index = 0) => s.Kind switch {
        "key" => m.Keys[s.Player][(int)s.Button!], "pad" => m.Pad[s.Player][(int)s.Button!],
        "hotkey" => m.Hotkeys[s.HotkeyId!].ElementAtOrDefault(index) ?? "", _ => m.PadHotkeys[s.HotkeyId!] };

    /// <summary>Assign <paramref name="binding"/>. For hotkeys, <paramref name="index"/> picks which of the command's keys (Count = add another).</summary>
    public static void Set(InputModel m, BindingSlot s, string binding, int index = 0)
    {
        switch (s.Kind) {
            case "key": m.Keys[s.Player][(int)s.Button!] = binding.Length == 0 ? "None" : binding; break;
            case "pad": m.Pad[s.Player][(int)s.Button!] = binding == "None" ? "" : binding; break;
            case "padhotkey": m.PadHotkeys[s.HotkeyId!] = binding == "None" ? "" : binding; break;
            default: {
                var list = m.Hotkeys[s.HotkeyId!];
                var def = HotkeyCatalog.Find(s.HotkeyId!)!;
                if (binding.Length == 0 || binding == "None") { if (index < list.Count) list.RemoveAt(index); }
                else if (def.Slot >= 0) { list.Clear(); list.Add(binding); }   // one key per save slot
                else if (index < list.Count) list[index] = binding;
                else if (!list.Contains(binding, StringComparer.OrdinalIgnoreCase)) list.Add(binding);
                break;
            }
        }
    }
    private static string Empty(BindingSlot s) => s.Kind == "key" ? "None" : "";

    /// <summary>Replace: take the binding away from every conflicting slot.</summary>
    public static void Replace(InputModel m, BindingSlot target, string binding, int index = 0)
    {
        foreach (var other in Conflicts(m, target, binding)) Remove(m, other, binding);
        Set(m, target, binding, index);
    }
    /// <summary>Swap: the conflicting slot gets the target's previous binding (only meaningful for slots of the same kind).</summary>
    public static void Swap(InputModel m, BindingSlot target, string binding, int index = 0)
    {
        var previous = Get(m, target, index);
        foreach (var other in Conflicts(m, target, binding)) {
            Remove(m, other, binding);
            if (SameFamily(other, target) && previous.Length != 0 && previous != "None") Set(m, other, previous, other.Kind == "hotkey" ? int.MaxValue : 0);
        }
        Set(m, target, binding, index);
    }
    public static bool SameFamily(BindingSlot a, BindingSlot b) => (a.Kind is "key" or "pad") == (b.Kind is "key" or "pad") && a.Kind == b.Kind;
    private static void Remove(InputModel m, BindingSlot s, string binding)
    {
        if (s.Kind == "hotkey") {
            var list = m.Hotkeys[s.HotkeyId!];
            var phys = KeyCatalog.ByName(binding)?.Name ?? Chord.Key(binding)?.Name;
            list.RemoveAll(c => c.Equals(binding, StringComparison.OrdinalIgnoreCase) || (!Chord.HasModifier(c) && Chord.Key(c)?.Name == phys && !Chord.HasModifier(binding)));
        } else Set(m, s, Empty(s));
    }

    /// <summary>Both players reading the same keyboard keys.</summary>
    public static List<SnesButton> SharedKeyboardKeys(InputModel m)
    {
        var shared = new List<SnesButton>();
        if (!(m.UsesKeyboard(0) && m.UsesKeyboard(1))) return shared;
        var p2 = new HashSet<string>(m.Keys[1].Where(k => k != "None"));
        for (int b = 0; b < 12; b++) if (m.Keys[0][b] != "None" && p2.Contains(m.Keys[0][b])) shared.Add((SnesButton)b);
        return shared;
    }
}

public sealed record InputPreset(string Name, string Kind, string[] Values, string Description);

public static class InputPresets
{
    public static readonly IReadOnlyList<InputPreset> Keyboard = new[] {
        new InputPreset("Game default", "key", InputModel.DefaultKeys, "Arrows · X A · Z B · S X · A Y · C L · V R · Enter Start · Right Shift Select"),
        new InputPreset("WASD + JKL", "key", new[] { "L", "K", "O", "J", "Q", "E", "Return", "Space", "W", "S", "A", "D" }, "WASD move · K B · L A · J Y · O X · Q L · E R · Enter Start · Space Select"),
        new InputPreset("Arrows + ZXC", "key", new[] { "C", "X", "D", "Z", "A", "S", "Return", "Right Shift", "Up", "Down", "Left", "Right" }, "Arrows move · Z Y · X B · C A · D X · A L · S R (the SNES face layout on the bottom row)"),
        new InputPreset("Numpad (second player)", "key", new[] { "Keypad 3", "Keypad 1", "Keypad 9", "Keypad 7", "Keypad /", "Keypad *", "Keypad Enter", "Keypad 0", "Keypad 8", "Keypad 5", "Keypad 4", "Keypad 6" }, "Numpad 8 5 4 6 move · 7 Y · 9 X · 1 B · 3 A · / L · * R · Enter Start · 0 Select · for a second player on one keyboard"),
    };
    public static readonly IReadOnlyList<InputPreset> Controller = new[] {
        new InputPreset("Game default (SNES positions)", "pad", InputModel.DefaultPad, "Buttons in the SNES pad's positions: bottom = B, right = A, top = X, left = Y; bumpers L and R"),
        new InputPreset("Matching letters (Xbox)", "pad", new[] { "A", "B", "X", "Y", "L1", "R1", "Start", "Back", "DpadUp", "DpadDown", "DpadLeft", "DpadRight" }, "SNES A on the pad's A, B on B, X on X, Y on Y (Xbox labels)"),
        new InputPreset("Shoulders on triggers", "pad", new[] { "B", "A", "Y", "X", "L2", "R2", "Start", "Back", "DpadUp", "DpadDown", "DpadLeft", "DpadRight" }, "SNES positions; L and R on the triggers. Note: the built-in controller shortcuts use the left trigger as their function button."),
    };
    public static void Apply(InputModel m, int player, InputPreset preset)
    {
        var target = preset.Kind == "key" ? m.Keys[player] : m.Pad[player];
        for (int b = 0; b < 12; b++) target[b] = preset.Values[b];
    }
}

/// <summary>A portable profile: what the editor manages, as JSON. Import validates every value with the same rules the files get.</summary>
public static class InputProfile
{
    public const string Format = "illusion-of-gaia-companion-input";
    public static string Export(InputModel m)
    {
        var root = new JsonObject {
            ["format"] = Format, ["version"] = 1,
            ["players"] = new JsonArray(Enumerable.Range(0, 2).Select(p => (JsonNode)new JsonObject {
                ["source"] = m.Source[p], ["controller"] = m.Gamepad[p],
                ["keyboard"] = Obj(Enumerable.Range(0, 12).ToDictionary(b => InputModel.IniNames[b], b => m.Keys[p][b])),
                ["pad"] = Obj(Enumerable.Range(0, 12).ToDictionary(b => InputModel.IniNames[b], b => m.Pad[p][b])),
            }).ToArray()),
            ["hotkeys"] = new JsonObject(HotkeyCatalog.All.Select(d => KeyValuePair.Create(HotkeyCatalog.Id(d), (JsonNode?)new JsonArray(m.Hotkeys[HotkeyCatalog.Id(d)].Select(c => (JsonNode)JsonValue.Create(c)!).ToArray())))),
            ["padHotkeys"] = Obj(HotkeyCatalog.All.ToDictionary(HotkeyCatalog.Id, d => m.PadHotkeys[HotkeyCatalog.Id(d)])),
        };
        return root.ToJsonString(new JsonSerializerOptions { WriteIndented = true });
    }
    private static JsonObject Obj(Dictionary<string, string> values) => new(values.Select(p => KeyValuePair.Create(p.Key, (JsonNode?)JsonValue.Create(p.Value))));
    public static InputModel Import(string json, InputModel baseline)
    {
        var m = baseline.Clone();
        var root = JsonNode.Parse(json) as JsonObject ?? throw new InvalidDataException("Not an input profile.");
        if (root["format"]?.GetValue<string>() != Format) throw new InvalidDataException("This file is not an Illusion of Gaia Companion input profile.");
        if (root["version"]?.GetValue<int>() != 1) throw new InvalidDataException("This input profile was made by a newer launcher.");
        if (root["players"] is JsonArray players)
            for (int p = 0; p < Math.Min(2, players.Count); p++) {
                if (players[p] is not JsonObject player) continue;
                if (player["source"] is JsonValue src && src.GetValue<int>() is var s && s is >= 0 and <= 2) m.Source[p] = s;
                if (player["controller"] is JsonValue c) m.Gamepad[p] = c.GetValue<bool>();
                for (int b = 0; b < 12; b++) {
                    if (player["keyboard"]?[InputModel.IniNames[b]] is JsonValue k)
                        m.Keys[p][b] = KeyCatalog.NormalizeBinding(k.GetValue<string>()) ?? throw new InvalidDataException($"Player {p + 1} {InputModel.IniNames[b]}: '{k}' is not a key.");
                    if (player["pad"]?[InputModel.IniNames[b]] is JsonValue pv)
                        m.Pad[p][b] = PadCatalog.Normalize(pv.GetValue<string>()) ?? throw new InvalidDataException($"Player {p + 1} {InputModel.IniNames[b]}: '{pv}' is not a controller button.");
                }
            }
        if (root["hotkeys"] is JsonObject hot)
            foreach (var d in HotkeyCatalog.All)
                if (hot[HotkeyCatalog.Id(d)] is JsonArray chords)
                    m.Hotkeys[HotkeyCatalog.Id(d)] = chords.Select(c => Chord.Normalize(c!.GetValue<string>()) ?? throw new InvalidDataException($"{d.Label}: '{c}' is not a key.")).Take(d.Slot >= 0 ? 1 : 8).ToList();
        if (root["padHotkeys"] is JsonObject pad)
            foreach (var d in HotkeyCatalog.All)
                if (pad[HotkeyCatalog.Id(d)] is JsonValue v)
                    m.PadHotkeys[HotkeyCatalog.Id(d)] = PadCatalog.Normalize(v.GetValue<string>()) ?? throw new InvalidDataException($"{d.Label}: '{v}' is not a controller button.");
        return m;
    }
}
