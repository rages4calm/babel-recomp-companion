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
            var controller = new LauncherController(new GameAdapter());
            using var form = new LauncherForm(controller);
            AddSoundtrackButton(form, controller);
            var smoke = Array.IndexOf(args, "--smoke-test");
            if (smoke >= 0) {
                if (smoke + 1 >= args.Length) throw new ArgumentException("Supply a fresh smoke-test directory.");
                var images = form.RenderSmokeTest(args[smoke + 1]);
                Console.WriteLine(System.Text.Json.JsonSerializer.Serialize(new { passed = true, pages = images.Count }));
            } else if (args.Contains("--soundtrack-preview")) {
                var index = Array.IndexOf(args, "--soundtrack-preview");
                var engineDirectory = index + 1 < args.Length ? Path.GetFullPath(args[index + 1])
                    : Path.GetDirectoryName(controller.Snapshot.Values["engine.path"].GetString()!)!;
                Application.Run(new SoundtrackForm(engineDirectory));
            } else Application.Run(form);
            return 0;
        } catch (Exception error) {
            Console.Error.WriteLine(error.Message);
            if (!args.Contains("--smoke-test")) MessageBox.Show(error.Message, "Companion could not start", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
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
                MessageBox.Show(form, "Select the existing Babel executable on Game, then Apply.", "Select the game first", MessageBoxButtons.OK, MessageBoxIcon.Information); return;
            }
            using var soundtrack = new SoundtrackForm(Path.GetDirectoryName(engine)!);
            soundtrack.ShowDialog(form);
        };
        rail.Controls.Add(button);
    }
}
