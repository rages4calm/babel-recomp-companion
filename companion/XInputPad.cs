using System.Runtime.InteropServices;

/// <summary>
/// Controllers through XInput (xinput1_4.dll, part of Windows 8 and later; no
/// extra dependency). It sees Xbox-compatible pads and anything Steam Input or
/// a driver presents as one. PlayStation, Switch and most 8BitDo pads in their
/// native modes are not XInput devices: the game still reads them through SDL,
/// and the editor lets you pick their buttons from a list instead.
/// Buttons are reported in the runner's [GamepadMap] vocabulary (positions).
/// </summary>
internal static class XInputPad
{
    [StructLayout(LayoutKind.Sequential)]
    private struct Gamepad { public ushort Buttons; public byte LeftTrigger, RightTrigger; public short ThumbLX, ThumbLY, ThumbRX, ThumbRY; }
    [StructLayout(LayoutKind.Sequential)]
    private struct State { public uint Packet; public Gamepad Pad; }
    [DllImport("xinput1_4.dll", EntryPoint = "XInputGetState")] private static extern int GetState14(int user, out State state);
    [DllImport("xinput9_1_0.dll", EntryPoint = "XInputGetState")] private static extern int GetState910(int user, out State state);
    private static bool? modern;

    /// <summary>Held controls of XInput slot <paramref name="user"/> (0..3) as kGamepadBtn indices, or null when nothing is connected there.</summary>
    public static int[]? Read(int user, out short stickX, out short stickY)
    {
        stickX = stickY = 0;
        State s;
        try {
            int rc;
            if (modern != false) { try { rc = GetState14(user, out s); modern = true; } catch (DllNotFoundException) { modern = false; rc = GetState910(user, out s); } }
            else rc = GetState910(user, out s);
            if (rc != 0) return null;
        } catch (Exception e) when (e is DllNotFoundException or EntryPointNotFoundException) { return null; }
        var held = new List<int>();
        void Bit(int mask, string name) { if ((s.Pad.Buttons & mask) != 0) held.Add(PadCatalog.Index(name)); }
        Bit(0x0001, "DpadUp"); Bit(0x0002, "DpadDown"); Bit(0x0004, "DpadLeft"); Bit(0x0008, "DpadRight");
        Bit(0x0010, "Start"); Bit(0x0020, "Back"); Bit(0x0040, "L3"); Bit(0x0080, "R3");
        Bit(0x0100, "L1"); Bit(0x0200, "R1"); Bit(0x1000, "A"); Bit(0x2000, "B"); Bit(0x4000, "X"); Bit(0x8000, "Y");
        // The runner counts a trigger from 12000 of 32767 (37%); XInput reports 0..255.
        if (s.Pad.LeftTrigger >= 94) held.Add(PadCatalog.Index("L2"));
        if (s.Pad.RightTrigger >= 94) held.Add(PadCatalog.Index("R2"));
        stickX = s.Pad.ThumbLX; stickY = s.Pad.ThumbLY;
        return held.ToArray();
    }
    public static IEnumerable<int> Connected() { for (int i = 0; i < 4; i++) if (Read(i, out _, out _) != null) yield return i; }
}
