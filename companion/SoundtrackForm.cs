using System.Diagnostics;

internal sealed class SoundtrackForm : Form
{
    private readonly string engineDirectory;
    private readonly Label installed = new();
    private readonly Label active = new();
    private readonly TextBox status = new();
    private readonly ComboBox packs = new();
    private readonly ProgressBar progress = new();
    private readonly Button download;
    private readonly Button zip;
    private readonly Button folder;
    private readonly Button useImported;
    private readonly Button useOriginal;
    private readonly Button cancel;
    private readonly ToolTip tips = new();
    private CancellationTokenSource? operation;
    private bool closeAfterCancel;
    private static readonly Color Background = ColorTranslator.FromHtml("#101A23");
    private static readonly Color Surface = ColorTranslator.FromHtml("#1B2B37");
    private static readonly Color Accent = ColorTranslator.FromHtml("#D7B46A");
    private static readonly Color TextColor = ColorTranslator.FromHtml("#F2EBDD");
    private static readonly Color Muted = ColorTranslator.FromHtml("#A7B5BD");
    private static readonly Color Success = Color.FromArgb(158, 219, 179);
    private static readonly Color Error = Color.FromArgb(255, 166, 162);

    internal SoundtrackForm(string engineDirectory)
    {
        this.engineDirectory = Path.GetFullPath(engineDirectory);
        Text = "Illusion of Gaia · Soundtrack";
        BackColor = Background; ForeColor = TextColor;
        Font = new Font("Segoe UI", 11);
        AutoScaleMode = AutoScaleMode.Dpi; ClientSize = new Size(860, 730); MinimumSize = new Size(800, 710);
        StartPosition = FormStartPosition.CenterParent;
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 7, Padding = new Padding(30, 24, 30, 22) };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        foreach (var height in new[] { 82f, 106f, 100f, 148f, 30f }) layout.RowStyles.Add(new RowStyle(SizeType.Absolute, height));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100)); layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 54));
        Controls.Add(layout);

        var heading = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 2, Margin = Padding.Empty };
        heading.RowStyles.Add(new RowStyle(SizeType.Absolute, 43)); heading.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        heading.Controls.Add(Label("Optional orchestral soundtrack", 23, Accent, FontStyle.Bold), 0, 0);
        heading.Controls.Add(Label("Original SNES audio always works offline, with no optional pack installed.", 10, Muted), 0, 1);
        layout.Controls.Add(heading, 0, 0);

        var source = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 3, Margin = Padding.Empty };
        source.RowStyles.Add(new RowStyle(SizeType.Absolute, 27)); source.RowStyles.Add(new RowStyle(SizeType.Absolute, 46)); source.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        source.Controls.Add(Label(SoundtrackService.Credit, 11, TextColor, FontStyle.Bold), 0, 0);
        source.Controls.Add(Label("Download opens the pack in your browser. When it finishes, import its ZIP or an extracted folder here. The music stays separate from game releases.", 10, Muted), 0, 1);
        var credits = new LinkLabel { Text = "Pack page and musician credits", AutoSize = true, LinkColor = Accent, ActiveLinkColor = TextColor, VisitedLinkColor = Accent, Margin = Padding.Empty };
        credits.LinkClicked += (_, _) => OpenLink(SoundtrackService.SourceListingUrl); source.Controls.Add(credits, 0, 2);
        layout.Controls.Add(source, 0, 1);

        var actions = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.LeftToRight, WrapContents = true, Margin = Padding.Empty };
        download = Button("Download soundtrack…", () => OpenLink(SoundtrackService.SourceDownloadUrl), 238, true);
        zip = Button("Import ZIP…", ImportZip, 166); folder = Button("Import folder…", ImportFolder, 174);
        actions.Controls.AddRange(new Control[] { download, zip, folder });
        var target = Label("Install beside this game: " + this.engineDirectory, 9, Muted); target.Dock = DockStyle.None; target.AutoEllipsis = true; target.AutoSize = false; target.Width = 760; target.Height = 24;
        tips.SetToolTip(target, this.engineDirectory); actions.Controls.Add(target);
        layout.Controls.Add(actions, 0, 2);

        var library = new TableLayoutPanel { Dock = DockStyle.Fill, BackColor = Surface, ColumnCount = 2, RowCount = 3, Padding = new Padding(14, 10, 14, 8), Margin = new Padding(0, 0, 0, 12) };
        library.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); library.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 220));
        library.RowStyles.Add(new RowStyle(SizeType.Absolute, 30)); library.RowStyles.Add(new RowStyle(SizeType.Absolute, 44)); library.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        installed.Dock = DockStyle.Fill; installed.Text = "Checking installed packs…"; installed.ForeColor = Muted; installed.AutoEllipsis = true;
        library.Controls.Add(installed, 0, 0); library.SetColumnSpan(installed, 2);
        packs.Dock = DockStyle.Fill; packs.DropDownStyle = ComboBoxStyle.DropDownList; packs.FlatStyle = FlatStyle.Flat; packs.BackColor = Background; packs.ForeColor = TextColor; packs.AccessibleName = "Verified imported soundtrack";
        packs.Margin = new Padding(0, 4, 12, 4); packs.SelectedIndexChanged += (_, _) => RefreshButtons(); library.Controls.Add(packs, 0, 1);
        useImported = Button("Use imported soundtrack", UseImported, 210); useImported.Margin = Padding.Empty; library.Controls.Add(useImported, 1, 1);
        active.Dock = DockStyle.Fill; active.ForeColor = Muted; active.AutoEllipsis = true; active.Margin = new Padding(0, 7, 0, 0);
        library.Controls.Add(active, 0, 2); library.SetColumnSpan(active, 2); layout.Controls.Add(library, 0, 3);

        progress.Dock = DockStyle.Fill; progress.Style = ProgressBarStyle.Blocks; progress.Margin = new Padding(0, 0, 0, 8); progress.AccessibleName = "Soundtrack import progress"; layout.Controls.Add(progress, 0, 4);
        status.Dock = DockStyle.Fill; status.ForeColor = Muted; status.BackColor = Background; status.BorderStyle = BorderStyle.None;
        status.Multiline = true; status.ReadOnly = true; status.ScrollBars = ScrollBars.None; status.AccessibleName = "Soundtrack status";
        status.Text = "Import verifies the pack before it becomes available. Existing music and saves are preserved.";
        status.Margin = new Padding(0, 8, 0, 8); layout.Controls.Add(status, 0, 5);

        var footer = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.RightToLeft, WrapContents = false, Margin = Padding.Empty };
        var close = Button("Close", Close, 100); close.Margin = new Padding(12, 0, 0, 0);
        cancel = Button("Cancel import", () => operation?.Cancel(), 148); cancel.Margin = new Padding(12, 0, 0, 0);
        useOriginal = Button("Use original audio", UseOriginal, 188); useOriginal.Margin = Padding.Empty;
        footer.Controls.AddRange(new Control[] { close, cancel, useOriginal }); layout.Controls.Add(footer, 0, 6);
        Shown += async (_, _) => await LoadInstalledAsync();
        FormClosing += (_, e) => { if (operation != null) { closeAfterCancel = true; operation.Cancel(); e.Cancel = true; status.Text = "Cancelling safely…"; } };
        RefreshButtons();
    }

    private static Label Label(string text, float size, Color color, FontStyle style = FontStyle.Regular) => new() {
        Text = text, Font = new Font("Segoe UI", size, style), ForeColor = color, Dock = DockStyle.Fill, AutoSize = false, UseMnemonic = false, Margin = Padding.Empty
    };
    private static Button Button(string text, Action action, int width, bool primary = false) {
        var button = new Button { Text = text, Width = width, Height = 43, FlatStyle = FlatStyle.Flat, BackColor = primary ? Accent : Surface,
            ForeColor = primary ? Background : TextColor, Font = new Font("Segoe UI", 10, FontStyle.Bold), Margin = new Padding(0, 0, 12, 9), Cursor = Cursors.Hand, UseMnemonic = false };
        button.FlatAppearance.BorderColor = primary ? Accent : Color.FromArgb(64, 81, 92);
        button.FlatAppearance.MouseOverBackColor = primary ? Color.FromArgb(227, 194, 121) : Color.FromArgb(38, 57, 70);
        button.Click += (_, _) => action(); return button;
    }
    private void OpenLink(string url) { try { Process.Start(new ProcessStartInfo(url) { UseShellExecute = true }); } catch (Exception ex) { Report("Could not open your browser: " + ex.Message, true); } }
    private void Report(string message, bool error = false) {
        status.Text = message; status.ForeColor = error ? Error : Muted;
        var textSize = TextRenderer.MeasureText(message, status.Font, new Size(Math.Max(1, status.ClientSize.Width - 22), int.MaxValue), TextFormatFlags.WordBreak);
        status.ScrollBars = textSize.Height > status.ClientSize.Height ? ScrollBars.Vertical : ScrollBars.None;
    }
    private void RefreshButtons() {
        bool idle = operation == null; download.Enabled = zip.Enabled = folder.Enabled = idle;
        cancel.Enabled = !idle; progress.Visible = !idle; useImported.Enabled = idle && packs.SelectedItem is InstalledPack; useOriginal.Enabled = idle;
    }
    private async Task RunAsync(Func<CancellationToken, Task> work) {
        if (operation != null) return;
        operation = new CancellationTokenSource(); RefreshButtons();
        try { await work(operation.Token); }
        catch (OperationCanceledException) { Report("Cancelled. Existing music, settings and saves were preserved."); }
        catch (Exception ex) { Report(ex.Message, true); }
        finally { operation.Dispose(); operation = null; progress.Style = ProgressBarStyle.Blocks; RefreshButtons(); if (closeAfterCancel) Close(); }
    }
    private Task LoadInstalledAsync() => RunAsync(async token => {
        progress.Style = ProgressBarStyle.Marquee;
        var found = await SoundtrackService.FindInstalledAsync(engineDirectory, token);
        ShowInstalled(found); UpdateActivation();
    });
    private void ShowInstalled(IReadOnlyList<SoundtrackImportResult> found, string? prefer = null) {
        packs.Items.Clear(); foreach (var result in found) packs.Items.Add(new InstalledPack(result));
        if (packs.Items.Count > 0) {
            var selected = packs.Items.Cast<InstalledPack>().FirstOrDefault(item => item.Result.PackDirectory.Equals(prefer, StringComparison.OrdinalIgnoreCase));
            packs.SelectedItem = selected ?? packs.Items[0];
        }
        installed.Text = found.Count == 0 ? "No verified imported pack installed" : $"{found.Count} verified imported pack{(found.Count == 1 ? "" : "s")} available";
        installed.ForeColor = found.Count == 0 ? Muted : Success;
    }
    private void UpdateActivation() {
        try {
            var state = SoundtrackActivation.Read(engineDirectory);
            active.Text = state.Enabled ? "Active: MSU-1 soundtrack · original audio remains the fallback" : "Active: original SNES audio";
            if (state.Enabled && state.PackDirectory is { } path)
                packs.SelectedItem = packs.Items.Cast<InstalledPack>().FirstOrDefault(item => item.Result.PackDirectory.Equals(path, StringComparison.OrdinalIgnoreCase)) ?? packs.SelectedItem;
        } catch (Exception ex) { active.Text = "Active soundtrack status unavailable"; tips.SetToolTip(active, ex.Message); }
    }
    private async void ImportZip() {
        using var picker = new OpenFileDialog { Title = "Import your Illusion of Gaia soundtrack ZIP", Filter = "Soundtrack ZIP (*.zip)|*.zip", CheckFileExists = true };
        var downloads = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "Downloads");
        if (Directory.Exists(downloads)) { picker.InitialDirectory = downloads; var known = Path.Combine(downloads, "Illusion of Gaia Orchestra by JUD6MENT.zip"); if (File.Exists(known)) picker.FileName = known; }
        if (picker.ShowDialog(this) == DialogResult.OK) await ImportAsync(picker.FileName);
    }
    private async void ImportFolder() {
        using var picker = new FolderBrowserDialog { Description = "Choose your extracted Gaia MSU-1 pack", UseDescriptionForTitle = true };
        if (picker.ShowDialog(this) == DialogResult.OK) await ImportAsync(picker.SelectedPath);
    }
    private Task ImportAsync(string source) => RunAsync(async token => {
        progress.Style = ProgressBarStyle.Blocks; progress.Value = 0;
        var updates = new Progress<SoundtrackProgress>(value => {
            if (IsDisposed) return;
            progress.Value = value.TotalBytes > 0 ? (int)Math.Clamp(value.BytesCompleted * 100L / value.TotalBytes, 0L, 100L) : 0;
            Report($"{value.Phase} · {value.TracksCompleted}/{value.TotalTracks} tracks\n{value.FileName}");
        });
        var result = await SoundtrackService.ImportAsync(source, engineDirectory, updates, token);
        string completion;
        try { SoundtrackActivation.Enable(engineDirectory, result.PackDirectory); completion = $"Imported and enabled {result.TrackCount} tracks. Restart the game to hear the orchestral soundtrack."; }
        catch (Exception ex) { completion = $"Imported {result.TrackCount} verified tracks, but could not enable them: {ex.Message}\nThe installed pack is preserved. Select it here and try Use imported soundtrack again."; }
        var found = await SoundtrackService.FindInstalledAsync(engineDirectory, CancellationToken.None);
        ShowInstalled(found, result.PackDirectory); UpdateActivation(); progress.Value = 100; Report(completion);
    });
    private void UseImported() {
        if (packs.SelectedItem is not InstalledPack selected) return;
        try { SoundtrackActivation.Enable(engineDirectory, selected.Result.PackDirectory); UpdateActivation(); Report("Imported soundtrack enabled. Restart the game to apply it."); }
        catch (Exception ex) { Report("Could not enable the imported soundtrack: " + ex.Message, true); }
    }
    private void UseOriginal() {
        try { SoundtrackActivation.Disable(engineDirectory); UpdateActivation(); Report("Original SNES audio selected. Imported music remains installed for later. Restart the game to apply it."); }
        catch (Exception ex) { Report("Could not select original audio: " + ex.Message, true); }
    }
    private sealed record InstalledPack(SoundtrackImportResult Result) {
        public override string ToString() => $"{(Result.CatalogId == null ? "Imported pack" : "JUD6MENT Orchestra")} · {Result.TrackCount} tracks · {Result.Sha256[..8].ToLowerInvariant()}";
    }
    protected override void Dispose(bool disposing) { if (disposing) { operation?.Cancel(); tips.Dispose(); } base.Dispose(disposing); }
}
