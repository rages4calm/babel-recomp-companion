using System.Text;

/// <summary>
/// The Language tab of Cheats and Mods, driven without ever showing the window: synthetic ROM headers
/// (no game data) are chosen, applied and read back from state.toml, and the tab is drawn to one PNG
/// in the scratch folder for a layout look.
/// </summary>
internal static class LanguageWindowTests
{
    public static int Run(string scratch)
    {
        if (Directory.Exists(scratch) && Directory.EnumerateFileSystemEntries(scratch).Any()) throw new ArgumentException("Supply a fresh scratch folder.");
        var game = Path.Combine(scratch, "game"); Directory.CreateDirectory(game);
        File.WriteAllText(Path.Combine(game, "babel-recomp.exe"), "synthetic fixture - never executed");
        string Rom(string name, string title) {
            var bytes = new byte[0x10000]; Encoding.ASCII.GetBytes(title).CopyTo(bytes, 0xFFC0);
            var path = Path.Combine(scratch, "roms", name); Directory.CreateDirectory(Path.GetDirectoryName(path)!); File.WriteAllBytes(path, bytes); return path;
        }
        var es = Rom("Illusion of Time (Spain).sfc", "ILLUSION OF TIME SPN"); var usa = Rom("Illusion of Gaia (USA).sfc", "ILLUSION OF GAIA USA ");
        int checks = 0;
        void Check(bool yes, string name, object? detail = null) { if (!yes) throw new Exception(name + (detail == null ? "" : ": " + detail)); checks++; Console.WriteLine("ok  " + name); }
        using (var form = new CheatsModsForm(game, openLanguage: true)) {
            form.CreateControl();
            Check(form.LanguageChoices.SequenceEqual(new[] { "English" }), "no ROM: only English offered", string.Join(",", form.LanguageChoices));
            Check(!form.UseLanguageRom(usa) && form.StatusText.Contains("not a European one"), "USA ROM refused with a clear message", form.StatusText);
            Check(form.LanguageChoices.Count == 1, "refused ROM adds nothing");
            Check(form.UseLanguageRom(es) && form.StatusText.StartsWith("Illusion of Time (Spain) ROM verified: Español."), "Spanish ROM verified", form.StatusText);
            Check(form.LanguageChoices.SequenceEqual(new[] { "English", "Español" }), "Español offered after choosing", string.Join(",", form.LanguageChoices));
            form.ClientSize = new Size(900, 790);
            // Only on a hidden desktop (GAIA_UI_SHOW=1 from the hidden runner): lay the window out for the picture.
            if (Environment.GetEnvironmentVariable("GAIA_UI_SHOW") == "1") { form.Show(); Application.DoEvents(); }
            using (var picture = new Bitmap(form.Width, form.Height)) { form.DrawToBitmap(picture, new Rectangle(Point.Empty, form.Size)); picture.Save(Path.Combine(scratch, "language-tab.png")); }
            if (form.Visible) form.Hide();
            form.ApplyChanges();
            Check(form.StatusText.StartsWith("Native mod settings saved"), "Apply succeeds", form.StatusText);
        }
        var state = File.ReadAllText(Path.Combine(game, "mods", "preloaded", "state.toml"));
        Check(state.Contains("id = \"language\"\nenabled = true") && state.Contains("code = \"es\"") && state.Contains("id = \"rom_es\"\npath = \"" + es.Replace("\\", "\\\\") + "\""),
            "state.toml: language on, code es, rom_es path", state.Replace('\n', ' '));
        using (var form = new CheatsModsForm(game, openLanguage: true)) {
            form.CreateControl();
            Check(form.LanguageChoices.SequenceEqual(new[] { "English", "Español" }), "reopened: Español still offered");
            form.SelectLanguage("original"); form.ApplyChanges();
        }
        Check(File.ReadAllText(Path.Combine(game, "mods", "preloaded", "state.toml")).Contains("id = \"language\"\nenabled = false"), "English applied: feature off");
        Console.WriteLine($"PASS {checks} Language tab checks (synthetic headers; shown only with GAIA_UI_SHOW=1 on a hidden desktop)");
        return 0;
    }
}
