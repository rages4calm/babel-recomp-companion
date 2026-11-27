using System.Diagnostics;
using System.Text.Json;
using Companion.Launcher.Core;
using Companion.Launcher.Windows;

/// <summary>Check, show what's new, then update side by side. Nothing installs until the player clicks Update.</summary>
internal sealed class UpdateForm : Form
{
    private readonly string installDirectory;
    private readonly Label summary = new();
    private readonly TextBox notes = new();
    private readonly ProgressBar progress = new();
    private readonly Label status = new();
    private readonly CheckBox checkOnStart = new();
    private readonly Button update, check, cancel, close;
    private CancellationTokenSource? operation;
    private bool closeAfterCancel;
    private UpdateCheck? result;
    private static readonly Color Background = ColorTranslator.FromHtml("#101A23");
    private static readonly Color Surface = ColorTranslator.FromHtml("#1B2B37");
    private static readonly Color Accent = ColorTranslator.FromHtml("#D7B46A");
    private static readonly Color TextColor = ColorTranslator.FromHtml("#F2EBDD");
    private static readonly Color Muted = ColorTranslator.FromHtml("#A7B5BD");
    private static readonly Color Success = Color.FromArgb(158, 219, 179);
    private static readonly Color Error = Color.FromArgb(255, 166, 162);

    /// <summary>Set after a successful install: the new folder's launcher, started once this one closes.</summary>
    internal string? InstalledLauncher { get; private set; }

    internal UpdateForm(string installDirectory, UpdateCheck? known)
    {
        this.installDirectory = installDirectory; result = known;
        Text = "Illusion of Gaia · Update";
        BackColor = Background; ForeColor = TextColor; Font = new Font("Segoe UI", 11);
        AutoScaleMode = AutoScaleMode.Dpi; ClientSize = new Size(780, 640); MinimumSize = new Size(700, 560);
        StartPosition = FormStartPosition.CenterParent;
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 7, Padding = new Padding(30, 24, 30, 22) };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        foreach (var height in new[] { 74f, 70f }) layout.RowStyles.Add(new RowStyle(SizeType.Absolute, height));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        foreach (var height in new[] { 30f, 52f, 36f, 54f }) layout.RowStyles.Add(new RowStyle(SizeType.Absolute, height));
        Controls.Add(layout);

        var heading = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 2, Margin = Padding.Empty };
        heading.RowStyles.Add(new RowStyle(SizeType.Absolute, 43)); heading.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        heading.Controls.Add(Label("Updates", 23, Accent, FontStyle.Bold), 0, 0);
        var current = UpdateService.CurrentVersion(installDirectory);
        var where = Label($"This build: {current?.ToString() ?? "unknown"} · {installDirectory}", 10, Muted); where.AutoEllipsis = true;
        heading.Controls.Add(where, 0, 1); layout.Controls.Add(heading, 0, 0);

        summary.Dock = DockStyle.Fill; summary.Font = new Font("Segoe UI", 11, FontStyle.Bold); summary.UseMnemonic = false; summary.Margin = Padding.Empty;
        layout.Controls.Add(summary, 0, 1);

        notes.Dock = DockStyle.Fill; notes.Multiline = true; notes.ReadOnly = true; notes.ScrollBars = ScrollBars.Vertical; notes.WordWrap = true;
        notes.BackColor = Surface; notes.ForeColor = TextColor; notes.BorderStyle = BorderStyle.None; notes.Font = new Font("Segoe UI", 10);
        notes.AccessibleName = "What's new in this release"; notes.Margin = new Padding(0, 0, 0, 10);
        layout.Controls.Add(notes, 0, 2);

        progress.Dock = DockStyle.Fill; progress.Margin = new Padding(0, 4, 0, 4); progress.AccessibleName = "Update progress"; layout.Controls.Add(progress, 0, 3);
        status.Dock = DockStyle.Fill; status.ForeColor = Muted; status.Font = new Font("Segoe UI", 10); status.UseMnemonic = false; status.Margin = Padding.Empty;
        status.Text = "Updates install beside this folder. Your saves, settings, screenshots and soundtrack come along; this build stays usable until the new one is ready.";
        layout.Controls.Add(status, 0, 4);

        checkOnStart.Text = "Check for updates when the launcher starts"; checkOnStart.AutoSize = true; checkOnStart.ForeColor = Muted;
        checkOnStart.Checked = UpdateService.ReadCheckOnStart(installDirectory); checkOnStart.Margin = new Padding(0, 6, 0, 0);
        checkOnStart.CheckedChanged += (_, _) => { try { UpdateService.WriteCheckOnStart(installDirectory, checkOnStart.Checked); } catch (Exception ex) { Report("Could not save that choice: " + ex.Message, true); } };
        layout.Controls.Add(checkOnStart, 0, 5);

        var footer = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.RightToLeft, WrapContents = false, Margin = Padding.Empty };
        close = Button("Close", Close, 100); close.Margin = new Padding(12, 0, 0, 0);
        cancel = Button("Cancel", () => operation?.Cancel(), 110); cancel.Margin = new Padding(12, 0, 0, 0);
        update = Button("Update", StartUpdate, 150, true); update.Margin = new Padding(12, 0, 0, 0);
        check = Button("Check again", () => _ = CheckAsync(), 150); check.Margin = Padding.Empty;
        close.Name = "update.close"; cancel.Name = "update.cancel"; update.Name = "update.install"; check.Name = "update.check";
        footer.Controls.AddRange(new Control[] { close, cancel, update, check }); layout.Controls.Add(footer, 0, 6);
        AcceptButton = update;

        Shown += async (_, _) => { if (result == null) await CheckAsync(); else Show(result); };
        FormClosing += (_, e) => { if (operation != null) { closeAfterCancel = true; operation.Cancel(); e.Cancel = true; Report("Cancelling safely…"); } };
        RefreshButtons();
    }

    private static Label Label(string text, float size, Color color, FontStyle style = FontStyle.Regular) => new() {
        Text = text, Font = new Font("Segoe UI", size, style), ForeColor = color, Dock = DockStyle.Fill, AutoSize = false, UseMnemonic = false, Margin = Padding.Empty
    };
    private static Button Button(string text, Action action, int width, bool primary = false)
    {
        var button = new Button { Text = text, Width = width, Height = 43, FlatStyle = FlatStyle.Flat, BackColor = primary ? Accent : Surface,
            ForeColor = primary ? Background : TextColor, Font = new Font("Segoe UI", 10, FontStyle.Bold), Cursor = Cursors.Hand, UseMnemonic = false };
        button.FlatAppearance.BorderColor = primary ? Accent : Color.FromArgb(64, 81, 92);
        button.FlatAppearance.MouseOverBackColor = primary ? Color.FromArgb(227, 194, 121) : Color.FromArgb(38, 57, 70);
        button.Click += (_, _) => action(); return button;
    }
    private void Report(string message, bool error = false) { status.Text = message; status.ForeColor = error ? Error : Muted; }
    private void RefreshButtons()
    {
        bool idle = operation == null;
        update.Enabled = idle && result?.IsNewer == true && InstalledLauncher == null;
        check.Enabled = idle && InstalledLauncher == null; cancel.Enabled = !idle; progress.Visible = !idle;
    }
    private static string Megabytes(long bytes) => $"{bytes / 1048576.0:0.0} MB";

    private void Show(UpdateCheck found)
    {
        result = found;
        if (found.Latest is not { } latest) { summary.Text = "No downloadable build was found."; summary.ForeColor = Muted; notes.Text = ""; }
        else if (found.IsNewer) {
            summary.Text = $"Update available: {latest.Version} · {Megabytes(latest.Zip.Size)} download\r\nInstalls next to this folder as {latest.FolderName}.";
            summary.ForeColor = Success; notes.Text = latest.Notes;
        } else {
            summary.Text = $"You have the latest build ({found.Current}).";
            summary.ForeColor = TextColor; notes.Text = latest.Notes;
        }
        RefreshButtons();
    }

    private async Task RunAsync(Func<CancellationToken, Task> work)
    {
        if (operation != null) return;
        operation = new CancellationTokenSource(); RefreshButtons();
        try { await work(operation.Token); }
        catch (OperationCanceledException) { Report("Cancelled. Nothing was changed; this build is exactly as it was."); }
        catch (UpdateException ex) { Report(ex.Message, true); }
        catch (Exception ex) { Report("The update stopped: " + ex.Message, true); }
        finally { operation.Dispose(); operation = null; progress.Style = ProgressBarStyle.Blocks; RefreshButtons(); if (closeAfterCancel) Close(); }
    }

    private Task CheckAsync() => RunAsync(async token => {
        progress.Style = ProgressBarStyle.Marquee; summary.Text = "Checking GitHub for a newer build…"; summary.ForeColor = Muted;
        Show(await UpdateService.CheckAsync(installDirectory, null, token));
        Report(result!.IsNewer ? "Read what's new, then press Update. The launcher restarts from the new folder when it is done." : "Nothing to do. You can close this window.");
    });

    private async void StartUpdate()
    {
        if (result?.Latest is not { } latest || !result.IsNewer) return;
        if (UpdateService.IsGameRunning(installDirectory)) { Report("Close the game first. It must not be running while it is updated.", true); return; }
        await RunAsync(async token => {
            progress.Style = ProgressBarStyle.Blocks; progress.Value = 0;
            var updates = new Progress<UpdateProgress>(value => {
                if (IsDisposed) return;
                progress.Value = value.Total > 0 ? (int)Math.Clamp(value.Done * 100L / value.Total, 0L, 100L) : 0;
                Report(value.Phase == "Downloading" ? $"Downloading and verifying · {Megabytes(value.Done)} of {Megabytes(value.Total)}" : value.Phase + "…");
            });
            var installed = await UpdateService.DownloadAndInstallAsync(installDirectory, latest, updates, cancel: token);
            InstalledLauncher = Path.Combine(installed.NewDirectory, UpdateService.LauncherName);
            progress.Value = 100;
            var extra = installed.Warnings.Count == 0 ? "" : " " + string.Join(" ", installed.Warnings);
            var links = installed.Shortcuts.Count == 0 ? "" : $" Updated {installed.Shortcuts.Count} shortcut{(installed.Shortcuts.Count == 1 ? "" : "s")}.";
            Report($"Installed {latest.Version} in {installed.NewDirectory}.{links}{extra} Restarting the launcher…");
            summary.Text = "Update installed."; summary.ForeColor = Success;
        });
        if (InstalledLauncher != null) { await Task.Delay(900); DialogResult = DialogResult.OK; Close(); }
    }

    protected override void Dispose(bool disposing) { if (disposing) operation?.Cancel(); base.Dispose(disposing); }
}

/// <summary>Adds the Update button and runs the new build's first-start tidy-up.</summary>
internal static class UpdateFeature
{
    private static UpdateCheck? latest;

    internal static void Attach(LauncherForm form, LauncherController controller)
    {
        var install = UpdateService.InstallDirectory;
        var rail = Descendants(form).OfType<FlowLayoutPanel>().Single(panel => panel.Controls.OfType<Button>().Any(button => button.AccessibleName == "Play"));
        var incumbent = rail.Controls.OfType<Button>().First();
        var muted = ColorTranslator.FromHtml(controller.Definition.Theme.Muted);
        var button = new Button { Text = "Update", Name = "gaia.update", AccessibleName = "Check for updates", Width = incumbent.Width, Height = incumbent.Height,
            Margin = incumbent.Margin, Font = incumbent.Font, FlatStyle = FlatStyle.Flat, BackColor = rail.BackColor, ForeColor = muted,
            Cursor = Cursors.Hand, UseMnemonic = false, AutoEllipsis = true };
        button.FlatAppearance.BorderColor = rail.BackColor; button.FlatAppearance.MouseOverBackColor = ColorTranslator.FromHtml(controller.Definition.Theme.Surface);
        button.Click += (_, _) => {
            if (controller.HasChanges) { MessageBox.Show(form, "Apply or Revert your settings before updating.", "Unapplied settings", MessageBoxButtons.OK, MessageBoxIcon.Information); return; }
            if (!UpdateService.IsInstalledRelease(install)) {
                MessageBox.Show(form, "This launcher is not running from an installed release folder, so it cannot update itself.", "Update", MessageBoxButtons.OK, MessageBoxIcon.Information); return;
            }
            using var dialog = new UpdateForm(install, latest) { Icon = form.Icon };
            if (dialog.ShowDialog(form) == DialogResult.OK && dialog.InstalledLauncher != null) Restart(form, dialog.InstalledLauncher);
        };
        rail.Controls.Add(button);

        var unattended = UpdateService.UsingTestFeed && Environment.GetCommandLineArgs().Contains("--update-unattended");
        if (!string.IsNullOrEmpty(Environment.GetEnvironmentVariable("GAIA_UPDATE_LOG")))
            UpdateService.Trace = (requested, final, status) => Log(new { step = "http", requested = requested.ToString(), final = final?.ToString(), status });
        form.Shown += async (_, _) => {
            if (UpdateService.HasPendingFinish(install)) await FinishAsync(form, controller, install, unattended);
            if (unattended) { await RunUnattendedAsync(form, install); return; }
            if (!UpdateService.IsInstalledRelease(install) || !UpdateService.ReadCheckOnStart(install)) return;
            try {
                latest = await UpdateService.CheckAsync(install);
                if (latest.IsNewer && !button.IsDisposed) {
                    // Two short lines fit the rail's fixed width at any DPI.
                    button.Text = "Update available\n" + latest.Latest!.Version.ShortLabel;
                    button.Font = new Font(button.Font.FontFamily, button.Font.Size * 0.85f, button.Font.Style);
                    button.ForeColor = ColorTranslator.FromHtml(controller.Definition.Theme.Accent);
                    button.AccessibleName = $"Update available: {latest.Latest.Version}";
                }
            } catch (Exception) { /* a quiet background check: offline or rate-limited just means no notice */ }
        };
    }

    private static void Restart(Form form, string launcher)
    {
        Process.Start(new ProcessStartInfo(launcher) { WorkingDirectory = Path.GetDirectoryName(launcher)!, UseShellExecute = false });
        form.Close();
        Application.Exit();
    }

    /// <summary>First start of a new build: point the saved game/ROM paths here, then remove the old folder if it is safe.</summary>
    private static async Task FinishAsync(LauncherForm form, LauncherController controller, string install, bool unattended)
    {
        var old = UpdateService.PendingSource(install);
        var retargeted = new List<string>();
        if (old != null && !controller.HasChanges) {
            try {
                foreach (var id in new[] { "engine.path", "rom.path" })
                    if (controller.Snapshot.Values.TryGetValue(id, out var value) && value.ValueKind == JsonValueKind.String
                        && UpdateService.Retarget(value.GetString(), old, install) is { } moved && File.Exists(moved)) {
                        controller.SetOption(id, OptionValue.From(moved)); retargeted.Add(id);
                    }
                if (retargeted.Count > 0) {
                    controller.Apply();
                    var revert = typeof(LauncherForm).GetMethod("Revert", System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic, Type.EmptyTypes);
                    try { revert?.Invoke(form, null); } catch (Exception) { }
                }
            } catch (Exception error) { Log(new { step = "preferences", error = error.Message }); }
        }
        var finished = await Task.Run(() => UpdateService.FinishPending(install));
        Log(new { step = "finish", state = finished.State, old = finished.OldDirectory, kept = finished.Kept, retargeted, version = UpdateService.CurrentVersion(install)?.ToString(), launcher = Environment.ProcessPath });
        if (unattended || Environment.GetEnvironmentVariable("GAIA_UPDATE_EXIT_AFTER_FINISH") == "1") {
            if (Environment.GetEnvironmentVariable("GAIA_UPDATE_EXIT_AFTER_FINISH") == "1") form.Close();
            return;
        }
        var version = UpdateService.CurrentVersion(install);
        if (finished.State is "removed" or "gone")
            MessageBox.Show(form, $"Updated to {version}. Your saves and settings came along. {finished.Message}".Trim(), "Update complete", MessageBoxButtons.OK, MessageBoxIcon.Information);
        else if (finished.Message.Length > 0)
            MessageBox.Show(form, $"Updated to {version}. {finished.Message}", "Update complete", MessageBoxButtons.OK, MessageBoxIcon.Information);
    }

    /// <summary>Test entry point (only with GAIA_UPDATE_FEED set): check and install without dialogs, then restart.</summary>
    private static async Task RunUnattendedAsync(Form form, string install)
    {
        try {
            var check = await UpdateService.CheckAsync(install);
            Log(new { step = "check", current = check.Current?.ToString(), latest = check.Latest?.Version.ToString(), newer = check.IsNewer });
            if (!check.IsNewer) { form.Close(); return; }
            var result = await UpdateService.DownloadAndInstallAsync(install, check.Latest!);
            Log(new { step = "install", result.NewDirectory, result.FilesCarried, result.MovedFolders, result.Shortcuts, result.Warnings });
            Restart(form, Path.Combine(result.NewDirectory, UpdateService.LauncherName));
        } catch (Exception error) { Log(new { step = "error", error = error.Message }); form.Close(); }
    }

    private static void Log(object entry)
    {
        var path = Environment.GetEnvironmentVariable("GAIA_UPDATE_LOG");
        if (string.IsNullOrEmpty(path)) return;
        try { File.AppendAllText(path, JsonSerializer.Serialize(entry) + Environment.NewLine); } catch (Exception) { }
    }

    private static IEnumerable<Control> Descendants(Control root)
    {
        foreach (Control child in root.Controls) { yield return child; foreach (var nested in Descendants(child)) yield return nested; }
    }
}
