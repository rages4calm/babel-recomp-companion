using Companion.Launcher.Windows;
using Companion.Launcher.Core;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        try {
            Application.SetHighDpiMode(HighDpiMode.PerMonitorV2);
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            using var launcherIcon = LoadLauncherIcon();
            var controller = new LauncherController(new GameAdapter());
            using var form = new LauncherForm(controller);
            form.Icon = launcherIcon;
            AddSoundtrackButton(form, controller);
            AddCheatsModsButton(form, controller);
            AddCheatsModsButton(form, controller, language: true);
            InputForm.AddLauncherButton(form, controller);
            UpdateFeature.Attach(form, controller);
            ReloadWhenReturning(form, controller);
            var smoke = Array.IndexOf(args, "--smoke-test");
            if (smoke >= 0) {
                if (smoke + 1 >= args.Length) throw new ArgumentException("Supply a fresh smoke-test directory.");
                var images = form.RenderSmokeTest(args[smoke + 1]);
                Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { passed = true, pages = images.Count }));
            } else if (Array.IndexOf(args, "--input-smoke") is var input && input >= 0) {
                if (input + 2 >= args.Length) throw new ArgumentException("Usage: --input-smoke <babel-recomp.exe> <fresh output directory>");
                var layout = new[] { 1f, 1.5f, 2f }.SelectMany(scale => InputForm.RenderSmoke(args[input + 1], args[input + 2], scale)).ToList();
                Console.WriteLine(layout.Count == 0 ? "Controls window: no clipped or overlapping controls at 100, 150 and 200%" : string.Join("\n", layout));
                if (layout.Count != 0) throw new InvalidOperationException("Controls window layout check failed.");
            } else if (args.Contains("--soundtrack-preview")) {
                var index = Array.IndexOf(args, "--soundtrack-preview");
                var engineDirectory = index + 1 < args.Length ? Path.GetFullPath(args[index + 1])
                    : Path.GetDirectoryName(controller.Snapshot.Values["engine.path"].GetString()!)!;
                using var soundtrack = new SoundtrackForm(engineDirectory) { Icon = launcherIcon };
                Application.Run(soundtrack);
            } else Application.Run(form);
            return 0;
        } catch (Exception error) {
            var headless = args.Contains("--smoke-test") || args.Contains("--input-smoke");   // automated runs never show UI
            Console.Error.WriteLine(headless ? error.ToString() : error.Message);
            if (!headless) MessageBox.Show(error.Message, "Companion could not start", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }

    /// <summary>
    /// The game rewrites its own settings while it runs. Coming back to the
    /// launcher with nothing unapplied, pick those up, so the next Apply is
    /// not refused as a conflict with a file the player never touched here.
    /// </summary>
    private static void ReloadWhenReturning(LauncherForm form, LauncherController controller)
    {
        // The shell's own Revert also redraws the open page; fall back to a plain reload.
        var revert = typeof(LauncherForm).GetMethod("Revert", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic, Type.EmptyTypes);
        form.Activated += (_, _) => {
            if (controller.HasChanges) return;
            try {
                // Only when a file actually changed: rebuilding the page on every activation reset its
                // scroll position and focus each time the player switched back to the launcher.
                if (controller.Adapter.ReadSettings(controller.Profile).Revision == controller.Snapshot.Revision) return;
                if (revert != null) revert.Invoke(form, null); else controller.Reload();
            }
            catch (Exception) { /* a locked or half-written file: the next activation tries again */ }
        };
    }

    private static Icon LoadLauncherIcon()
    {
        using var stream = typeof(Program).Assembly.GetManifestResourceStream("Gaia.Companion.Icon")
            ?? throw new InvalidDataException("The embedded Companion icon is missing. Rebuild the launcher.");
        using var embedded = new Icon(stream);
        return (Icon)embedded.Clone();
    }

    private static IEnumerable<Control> Descendants(Control root)
    {
        foreach (Control child in root.Controls) {
            yield return child;
            foreach (var nested in Descendants(child)) yield return nested;
        }
    }

    private static void AddSoundtrackButton(LauncherForm form, LauncherController controller)
    {
        // Compose the public shell's existing navigation, without copying it or
        // reaching into private fields. The package owns the rest of the UI.
        var rail = Descendants(form).OfType<FlowLayoutPanel>().Single(panel =>
            panel.Controls.OfType<Button>().Any(button => button.AccessibleName == "Play"));
        var incumbent = rail.Controls.OfType<Button>().First();
        var button = new Button {
            Text = "Soundtrack", Name = "gaia.soundtrack", AccessibleName = "Soundtrack download and import",
            Width = incumbent.Width, Height = incumbent.Height, Margin = incumbent.Margin,
            Font = incumbent.Font, FlatStyle = FlatStyle.Flat,
            BackColor = rail.BackColor, ForeColor = ColorTranslator.FromHtml(controller.Definition.Theme.Muted),
            Cursor = Cursors.Hand, UseMnemonic = false
        };
        button.FlatAppearance.BorderColor = rail.BackColor;
        button.FlatAppearance.MouseOverBackColor = ColorTranslator.FromHtml(controller.Definition.Theme.Surface);
        button.Click += (_, _) => {
            if (controller.HasChanges) {
                MessageBox.Show(form, "Apply or Revert your settings before opening Soundtrack.", "Unapplied settings", MessageBoxButtons.OK, MessageBoxIcon.Information); return;
            }
            var engine = controller.Snapshot.Values["engine.path"].GetString() ?? "";
            if (!Path.IsPathFullyQualified(engine) || !File.Exists(engine)) {
                MessageBox.Show(form, "Set the game program on the Game page, then Apply.", "Select the game first", MessageBoxButtons.OK, MessageBoxIcon.Information); return;
            }
            if (NativeModSettings.IsEngineRunning(engine)) {
                MessageBox.Show(form, "Close the game before changing its soundtrack. In-game settings remain available during play.", "Game is running", MessageBoxButtons.OK, MessageBoxIcon.Information); return;
            }
            using var soundtrack = new SoundtrackForm(Path.GetDirectoryName(engine)!) { Icon = form.Icon };
            soundtrack.ShowDialog(form);
        };
        rail.Controls.Add(button);
    }

    /// <summary>Cheats and Mods, or the same window opened on its Language tab (the Spanish, French and German ROM choice).</summary>
    private static void AddCheatsModsButton(LauncherForm form, LauncherController controller, bool language = false)
    {
        var rail = Descendants(form).OfType<FlowLayoutPanel>().Single(panel => panel.Controls.OfType<Button>().Any(button => button.AccessibleName == "Play"));
        var incumbent = rail.Controls.OfType<Button>().First();
        var button = new Button { Text = language ? "Language" : "Cheats and Mods", Name = language ? "gaia.language" : "gaia.cheats-mods",
            AccessibleName = language ? "Game language" : "Cheats and Mods", Width = incumbent.Width, Height = incumbent.Height,
            Margin = incumbent.Margin, Font = incumbent.Font, FlatStyle = FlatStyle.Flat, BackColor = rail.BackColor,
            ForeColor = ColorTranslator.FromHtml(controller.Definition.Theme.Muted), Cursor = Cursors.Hand, UseMnemonic = false };
        button.FlatAppearance.BorderColor = rail.BackColor; button.FlatAppearance.MouseOverBackColor = ColorTranslator.FromHtml(controller.Definition.Theme.Surface);
        button.Click += (_, _) => {
            try {
                if (controller.HasChanges) throw new InvalidOperationException("Apply or Revert your settings before opening " + (language ? "Language." : "Cheats and Mods."));
                var engine = controller.Snapshot.Values["engine.path"].GetString() ?? "";
                if (!Path.IsPathFullyQualified(engine) || !File.Exists(engine)) throw new InvalidOperationException("Set the game program on the Game page, then Apply.");
                if (NativeModSettings.IsEngineRunning(engine)) throw new InvalidOperationException("Close the game before editing launcher mods. Use in-game settings for the live session.");
                using var mods = new CheatsModsForm(Path.GetDirectoryName(engine)!, language) { Icon = form.Icon }; mods.ShowDialog(form);
            } catch (Exception error) { MessageBox.Show(form, error.Message, language ? "Could not open Language" : "Could not open Cheats and Mods", MessageBoxButtons.OK, MessageBoxIcon.Information); }
        };
        rail.Controls.Add(button);
    }
}
