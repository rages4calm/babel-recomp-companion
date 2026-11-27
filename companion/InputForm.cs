using System.Drawing.Drawing2D;
using Companion.Launcher.Core;
using Companion.Launcher.Windows;

/// <summary>
/// Keys, controllers and shortcuts: edits keybinds.ini and the [KeyMap],
/// [GamepadMap] and [Controller] parts of config.ini beside the game, and
/// nothing else. See InputBindings.cs for what each file means to the game.
/// </summary>
internal sealed class InputForm : Form, IMessageFilter
{
    private static readonly Color Background = ColorTranslator.FromHtml("#101A23");
    private static readonly Color Surface = ColorTranslator.FromHtml("#1B2B37");
    private static readonly Color Raised = Color.FromArgb(38, 57, 70);
    private static readonly Color Accent = ColorTranslator.FromHtml("#D7B46A");
    private static readonly Color TextColor = ColorTranslator.FromHtml("#F2EBDD");
    private static readonly Color Muted = ColorTranslator.FromHtml("#A7B5BD");
    private static readonly Color Warning = Color.FromArgb(255, 198, 120);
    private static readonly Color Error = Color.FromArgb(255, 166, 162);
    private static readonly Color Lit = Color.FromArgb(158, 219, 179);

    private readonly string engineExecutable;
    private readonly InputFiles files;
    private InputModel saved = InputModel.Defaults();
    private InputModel model = InputModel.Defaults();
    private PadStyle style;
    private readonly float scale;

    private readonly TabControl tabs = new();
    private readonly DataGridView[] grids = new DataGridView[3];
    private readonly ComboBox[] devices = new ComboBox[2];
    private readonly ComboBox styleBox = new();
    private readonly ComboBox presetBox = new();
    private readonly Label sideNote = new();
    private readonly TextBox status = new();
    private readonly PadView pad = new();
    private readonly CheckBox tryKeys = new();
    private readonly Label padState = new();
    private readonly Button save;
    private readonly System.Windows.Forms.Timer poll = new() { Interval = 16 };
    private readonly HashSet<string> heldKeys = new();
    private readonly int[][] lastPad = { Array.Empty<int>(), Array.Empty<int>(), Array.Empty<int>(), Array.Empty<int>() };
    private int deadzone = 3277;
    private bool captureOpen;
    private bool smoke;
    protected override bool ShowWithoutActivation => smoke;

    /// <summary>
    /// Moved to a screen with a higher scale, Windows suggests the window's old size times the new scale,
    /// which on a 1080p display at 150% or 200% runs under the taskbar and hides Save and Close. Keep it
    /// inside that screen's working area (the content scrolls; the window can still be resized).
    /// </summary>
    protected override void OnDpiChanged(DpiChangedEventArgs e)
    {
        base.OnDpiChanged(e);
        RescaleFonts();
        BeginInvoke(RescaleFonts);   // again once the child controls have had their own DPI messages
        var work = Screen.FromRectangle(e.SuggestedRectangle).WorkingArea;
        var size = new Size(Math.Min(Width, work.Width), Math.Min(Height, work.Height));
        var at = new Point(Math.Clamp(Left, work.Left, work.Right - size.Width), Math.Clamp(Top, work.Top, work.Bottom - size.Height));
        if (size != Size || at != Location) Bounds = new Rectangle(at, size);
    }

    // Every font in this window is set explicitly (captions, grid cells, combo boxes), and WinForms does not
    // rescale all of those on a DPI change (grid cell styles never): grid text stayed at 100% on a 200% screen.
    // Each font's size at 96 DPI is recorded once, and a DPI change sets every one to that size times the scale.
    private readonly List<(Control control, float size)> designFonts = new();
    private readonly List<(DataGridView grid, bool header, float size)> designStyles = new();
    private void RecordFonts()
    {
        float f = DeviceDpi / 96f;
        foreach (var c in Descend(this)) designFonts.Add((c, c.Font.Size / f));
        foreach (var g in grids) { designStyles.Add((g, false, g.DefaultCellStyle.Font!.Size / f)); designStyles.Add((g, true, g.ColumnHeadersDefaultCellStyle.Font!.Size / f)); }
    }
    private void RescaleFonts()
    {
        if (IsDisposed) return;
        float f = DeviceDpi / 96f;
        SuspendLayout();
        foreach (var (c, size) in designFonts)
            if (!c.IsDisposed && Math.Abs(c.Font.Size - size * f) > 0.05f) c.Font = new Font(c.Font.FontFamily, size * f, c.Font.Style);
        // After the controls: a grid's own font change can reset its cell styles.
        foreach (var (grid, header, size) in designStyles) {
            var style = header ? grid.ColumnHeadersDefaultCellStyle : grid.DefaultCellStyle;   // the grid may have replaced the object
            if (style.Font is { } font && Math.Abs(font.Size - size * f) > 0.05f) {
                var scaled = new DataGridViewCellStyle(style) { Font = new Font(font.FontFamily, size * f, font.Style) };
                if (header) grid.ColumnHeadersDefaultCellStyle = scaled; else grid.DefaultCellStyle = scaled;
            }
        }
        // A combo box takes its new height only once the font reaches its window; size it here, then lay out again.
        foreach (var c in Descend(this).OfType<ComboBox>()) { c.MinimumSize = Size.Empty; c.Height = c.PreferredHeight + 4; c.MinimumSize = new Size(0, c.Height); }
        int em = Font.Height; tabs.ItemSize = new Size(em * 9, em * 2 + em / 3); tabs.Padding = new Point(em, em / 3);   // tab headers are sized in pixels
        ResumeLayout(true);
        foreach (var panel in Descend(this).OfType<FlowLayoutPanel>()) panel.PerformLayout();
        foreach (var g in grids) g.AutoResizeRows();
    }

    internal InputForm(string engineExecutable, string prompts, float scale = 1f)
    {
        this.engineExecutable = Path.GetFullPath(engineExecutable);
        this.scale = scale;
        files = new InputFiles(Path.GetDirectoryName(this.engineExecutable)!);
        style = prompts == "snes" ? PadStyle.Nintendo : PadStyle.Xbox;
        Text = "Illusion of Gaia · Keys, controllers and shortcuts";
        BackColor = Background; ForeColor = TextColor;
        Font = new Font("Segoe UI", 10 * scale);
        AutoScaleMode = scale == 1f ? AutoScaleMode.Dpi : AutoScaleMode.None;
        StartPosition = FormStartPosition.CenterParent; KeyPreview = true;
        int em = Font.Height;
        // Fit the screen: at 200% a 1080p display is 960x540 logical, so everything below scrolls rather than overlaps.
        var work = Screen.PrimaryScreen?.WorkingArea.Size ?? new Size(1280, 720);
        ClientSize = new Size(Math.Min(em * 64, work.Width - 40), Math.Min(em * 44, work.Height - 60));
        MinimumSize = new Size(Math.Min(em * 40, work.Width), Math.Min(em * 24, work.Height));

        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 4, Padding = new Padding(em * 3 / 2, em, em * 3 / 2, em) };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 62)); layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 38));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize)); layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize)); layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        Controls.Add(layout);

        var heading = new FlowLayoutPanel { FlowDirection = FlowDirection.TopDown, AutoSize = true, WrapContents = false, Margin = new Padding(0, 0, 0, em / 2), Dock = DockStyle.Fill };
        heading.Controls.Add(Caption("Keys, controllers and shortcuts", 18, Accent, FontStyle.Bold));
        heading.Controls.Add(Caption("Select a row and press Enter (or click a cell, or press A on a controller) to change it. Esc cancels, Delete clears. Saved to keybinds.ini and config.ini beside the game.", 9.5f, Muted));
        layout.Controls.Add(heading, 0, 0); layout.SetColumnSpan(heading, 2);

        tabs.Dock = DockStyle.Fill; tabs.DrawMode = TabDrawMode.OwnerDrawFixed; tabs.SizeMode = TabSizeMode.Fixed;
        tabs.ItemSize = new Size(em * 9, em * 2 + em / 3); tabs.Padding = new Point(em, em / 3); tabs.AccessibleName = "Sections";
        tabs.DrawItem += (_, e) => DrawTab(e); tabs.SelectedIndexChanged += (_, _) => { tabs.Invalidate(); RefreshSide(); };
        for (int i = 0; i < 3; i++) {
            var page = new TabPage(i < 2 ? $"Player {i + 1}" : "Shortcuts") { BackColor = Background, ForeColor = TextColor, Padding = new Padding(0, em / 2, 0, 0) };
            grids[i] = Grid(i); page.Controls.Add(grids[i]); tabs.TabPages.Add(page);
        }
        layout.Controls.Add(tabs, 0, 1);

        // Side panel: who plays with what, button names, presets, the live pad.
        var sideScroll = new Panel { Dock = DockStyle.Fill, AutoScroll = true, BackColor = Surface, Margin = new Padding(em, em * 2 + em / 2, 0, 0) };
        // A top-down flow, every child as wide as the panel: each keeps its own measured height.
        var side = new FlowLayoutPanel { Dock = DockStyle.Top, FlowDirection = FlowDirection.TopDown, WrapContents = false, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, BackColor = Surface, Padding = new Padding(em), Margin = Padding.Empty };
        sideScroll.Controls.Add(side);
        void Row(Control c) { c.Dock = DockStyle.None; side.Controls.Add(c); }
        void Fit()
        {
            int width = Math.Max(em * 8, sideScroll.ClientSize.Width - side.Padding.Horizontal - SystemInformation.VerticalScrollBarWidth);
            side.SuspendLayout();
            foreach (Control c in side.Controls) {
                if (c is Label l) l.MaximumSize = new Size(width, 0);
                else if (c is not CheckBox) c.Width = width;
            }
            side.ResumeLayout(true);
        }
        sideScroll.Resize += (_, _) => Fit(); side.ControlAdded += (_, _) => Fit();
        for (int p = 0; p < 2; p++) {
            int player = p;
            devices[p] = Combo($"Player {p + 1} plays with", new[] { "Keyboard and controller", "Controller only", "Keyboard only", "Nobody" });
            devices[p].SelectedIndexChanged += (_, _) => { if (!syncing) { model.SetDevice(player, devices[player].SelectedIndex); Changed(); } };
        }
        Row(Caption("Player 1 plays with", 9.5f, Muted, FontStyle.Bold)); Row(devices[0]);
        Row(Caption("Player 2 plays with", 9.5f, Muted, FontStyle.Bold)); Row(devices[1]);
        Row(Caption("Show controller buttons as", 9.5f, Muted, FontStyle.Bold));
        styleBox.DropDownStyle = ComboBoxStyle.DropDownList; StyleCombo(styleBox); styleBox.AccessibleName = "Show controller buttons as";
        styleBox.Items.AddRange(new object[] { "Xbox", "Nintendo (SNES / Switch)", "PlayStation" }); styleBox.SelectedIndex = (int)style;
        styleBox.SelectedIndexChanged += (_, _) => { style = (PadStyle)styleBox.SelectedIndex; RefreshGrids(); pad.Invalidate(); };
        Row(styleBox);
        Row(Caption("Presets", 9.5f, Muted, FontStyle.Bold));
        presetBox.DropDownStyle = ComboBoxStyle.DropDownList; StyleCombo(presetBox); presetBox.AccessibleName = "Preset";
        Row(presetBox);
        var presetButtons = new FlowLayoutPanel { AutoSize = true, WrapContents = true, Margin = Padding.Empty };
        presetButtons.Controls.Add(Button("Apply preset", ApplyPreset)); presetButtons.Controls.Add(Button("Reset this page", ResetPage));
        Row(presetButtons);
        pad.Dock = DockStyle.Fill; pad.Height = em * 9; pad.Margin = new Padding(0, 0, 0, em / 3); pad.AccessibleName = "Live input tester"; pad.Owner = this;
        Row(Caption("Try it", 9.5f, Muted, FontStyle.Bold)); Row(pad);
        tryKeys.Text = "Try keys here (Esc stops)"; tryKeys.AutoSize = true; tryKeys.ForeColor = TextColor; tryKeys.AccessibleName = "Try keys on the pad";
        tryKeys.CheckedChanged += (_, _) => { heldKeys.Clear(); pad.Invalidate(); };
        Row(tryKeys);
        padState.AutoSize = true; padState.ForeColor = Muted; padState.Font = new Font(Font.FontFamily, 9 * scale); Row(padState);
        sideNote.AutoSize = true; sideNote.ForeColor = Warning; sideNote.Font = new Font(Font.FontFamily, 9 * scale); Row(sideNote);
        layout.Controls.Add(sideScroll, 1, 1);

        status.ReadOnly = true; status.Multiline = true; status.BorderStyle = BorderStyle.None; status.BackColor = Background; status.ForeColor = Muted;
        status.Dock = DockStyle.Fill; status.Height = em * 3; status.Margin = new Padding(0, em / 2, 0, em / 2); status.AccessibleName = "Status"; status.TabStop = false;
        layout.Controls.Add(status, 0, 2); layout.SetColumnSpan(status, 2);

        var footer = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, FlowDirection = FlowDirection.RightToLeft, WrapContents = false, Margin = Padding.Empty };
        var close = Button("Close", Close); save = Button("Save", Save, true);
        footer.Controls.AddRange(new Control[] { close, save, Button("Export profile…", Export), Button("Import profile…", Import), Button("Revert", () => { Reload(); Report("Reloaded from the game's files."); }) });
        layout.Controls.Add(footer, 0, 3); layout.SetColumnSpan(footer, 2);
        CancelButton = close; AcceptButton = null;

        poll.Tick += (_, _) => Poll();
        Shown += (_, _) => { if (smoke) return; Application.AddMessageFilter(this); poll.Start(); grids[0].Focus(); };
        FormClosed += (_, _) => { poll.Stop(); Application.RemoveMessageFilter(this); };
        Deactivate += (_, _) => { heldKeys.Clear(); pad.Invalidate(); };   // keys released in another window never reach this one
        FormClosing += (_, e) => {
            if (!Dirty || e.CloseReason != CloseReason.UserClosing) return;
            var answer = MessageBox.Show(this, "Save your changes to the game's key and controller settings?", "Unsaved changes", MessageBoxButtons.YesNoCancel, MessageBoxIcon.Question);
            if (answer == DialogResult.Cancel) e.Cancel = true;
            else if (answer == DialogResult.Yes && !Save()) e.Cancel = true;
        };
        Reload();
        RecordFonts();
    }

    // ---- launcher integration -------------------------------------------------------------

    /// <summary>Adds the Controls button to the launcher's rail, beside Soundtrack.</summary>
    internal static void AddLauncherButton(LauncherForm form, LauncherController controller)
    {
        static IEnumerable<Control> All(Control root) { foreach (Control c in root.Controls) { yield return c; foreach (var n in All(c)) yield return n; } }
        var rail = All(form).OfType<FlowLayoutPanel>().Single(panel => panel.Controls.OfType<Button>().Any(b => b.AccessibleName == "Play"));
        var incumbent = rail.Controls.OfType<Button>().First();
        var button = new Button { Text = "Controls", Name = "gaia.controls", AccessibleName = "Keys, controllers and shortcuts", Width = incumbent.Width, Height = incumbent.Height,
            Margin = incumbent.Margin, Font = incumbent.Font, FlatStyle = FlatStyle.Flat, BackColor = rail.BackColor,
            ForeColor = ColorTranslator.FromHtml(controller.Definition.Theme.Muted), Cursor = Cursors.Hand, UseMnemonic = false };
        button.FlatAppearance.BorderColor = rail.BackColor; button.FlatAppearance.MouseOverBackColor = ColorTranslator.FromHtml(controller.Definition.Theme.Surface);
        button.Click += (_, _) => {
            try {
                if (controller.HasChanges) throw new InvalidOperationException("Apply or Revert your settings before opening Controls.");
                var engine = controller.Snapshot.Values["engine.path"].GetString() ?? "";
                if (!Path.IsPathFullyQualified(engine) || !File.Exists(engine)) throw new InvalidOperationException("Set the game program on the Game page, then Apply.");
                var prompts = controller.Snapshot.Values.TryGetValue("input.prompts", out var value) ? value.GetString() ?? "auto" : "auto";
                using var input = new InputForm(engine, prompts) { Icon = form.Icon }; input.ShowDialog(form);
            } catch (Exception error) { MessageBox.Show(form, error.Message, "Could not open Controls", MessageBoxButtons.OK, MessageBoxIcon.Information); }
        };
        rail.Controls.Add(button);
    }

    /// <summary>Renders every page to PNGs and reports any control whose text does not fit. For --smoke-test style checks.</summary>
    internal static IReadOnlyList<string> RenderSmoke(string engineExecutable, string outDir, float scale, string prompts = "auto")
    {
        Directory.CreateDirectory(outDir);
        var problems = new List<string>();
        using var form = new InputForm(engineExecutable, prompts, scale) { StartPosition = FormStartPosition.Manual, Location = new Point(-32000, -32000), ShowInTaskbar = false };
        // Shown fully transparent, off every screen, never activated and not in the taskbar, so an
        // automated run puts nothing in front of the player; WinForms only paints a visible form.
        form.smoke = true; form.Opacity = 0; form.Show(); Application.DoEvents();
        for (int i = 0; i < form.tabs.TabCount; i++) {
            form.tabs.SelectedIndex = i; Application.DoEvents();
            using var bmp = new Bitmap(form.Width, form.Height);
            form.DrawToBitmap(bmp, new Rectangle(Point.Empty, form.Size));
            var name = Path.Combine(outDir, $"input-{(int)(scale * 100)}-{i}.png");
            bmp.Save(name, System.Drawing.Imaging.ImageFormat.Png);
            CheckLayout(form, $"{(int)(scale * 100)}% page {i}", problems);
            var grid = form.grids[i];
            foreach (DataGridViewColumn col in grid.Columns)
                foreach (DataGridViewRow row in grid.Rows) {
                    var text = row.Cells[col.Index].FormattedValue?.ToString() ?? "";
                    var w = TextRenderer.MeasureText(text, grid.Font).Width + 8;
                    if (w > col.Width && !col.DefaultCellStyle.WrapMode.Equals(DataGridViewTriState.True) && col.AutoSizeMode != DataGridViewAutoSizeColumnMode.Fill)
                        problems.Add($"{(int)(scale * 100)}% page {i}: '{text}' clipped in column {col.HeaderText}");
                }
        }
        form.Close();
        File.WriteAllLines(Path.Combine(outDir, $"input-{(int)(scale * 100)}-layout.txt"), problems.DefaultIfEmpty("no clipped text"));
        return problems;
    }
    /// <summary>Text that does not fit, overlapping siblings, children sticking out of a parent that does not scroll.</summary>
    internal static void CheckLayout(Control form, string where, List<string> problems)
    {
        foreach (var c in Descend(form).Where(c => c.Visible && c is Label or System.Windows.Forms.Button or CheckBox)) {
            // Wrapped text must fit the height it got at the width it got; a single line must fit its width.
            bool wraps = c is Label { MaximumSize.Width: > 0 };
            var want = TextRenderer.MeasureText(c.Text, c.Font, new Size(wraps ? c.ClientSize.Width : int.MaxValue, int.MaxValue), TextFormatFlags.WordBreak | TextFormatFlags.NoPrefix);
            if (c.Text.Length > 0 && ((!wraps && want.Width > c.ClientSize.Width + 2) || want.Height > c.ClientSize.Height + 2))
                problems.Add($"{where}: '{c.Text}' needs {want}, has {c.ClientSize}");
        }
        // Siblings must not overlap, and nothing may stick out of a parent that does not scroll.
        foreach (var parent in Descend(form).Prepend(form).Where(p => p.Visible)) {
            var kids = parent.Controls.Cast<Control>().Where(k => k.Visible && k.Width > 0 && k.Height > 0).ToList();
            for (int x = 0; x < kids.Count; x++) {
                for (int y = x + 1; y < kids.Count; y++)
                    if (kids[x].Bounds.IntersectsWith(kids[y].Bounds) && parent is not TabControl)
                        problems.Add($"{where}: '{kids[x].Text}{kids[x].AccessibleName}' overlaps '{kids[y].Text}{kids[y].AccessibleName}'");
                if (parent is not ScrollableControl { AutoScroll: true } && parent is not TabControl && parent is not DataGridView &&
                    (kids[x].Right > parent.ClientSize.Width + 1 || kids[x].Bottom > parent.ClientSize.Height + 1))
                    problems.Add($"{where}: '{kids[x].Text}{kids[x].AccessibleName}' extends past {parent.GetType().Name} '{parent.AccessibleName}'");
            }
        }
    }
    private static IEnumerable<Control> Descend(Control root) { foreach (Control c in root.Controls) { yield return c; foreach (var n in Descend(c)) yield return n; } }

    // ---- grid ------------------------------------------------------------------------------

    private sealed record RowTag(BindingSlot? Keyboard, BindingSlot? Controller);
    private static readonly SnesButton[] RowOrder = { SnesButton.Up, SnesButton.Down, SnesButton.Left, SnesButton.Right, SnesButton.A, SnesButton.B, SnesButton.X, SnesButton.Y, SnesButton.L, SnesButton.R, SnesButton.Start, SnesButton.Select };

    private DataGridView Grid(int page)
    {
        var g = new DataGridView {
            Dock = DockStyle.Fill, BackgroundColor = Background, BorderStyle = BorderStyle.None, GridColor = Raised,
            AllowUserToAddRows = false, AllowUserToDeleteRows = false, AllowUserToResizeRows = false, ReadOnly = true, RowHeadersVisible = false,
            SelectionMode = DataGridViewSelectionMode.CellSelect, MultiSelect = false, EnableHeadersVisualStyles = false,
            AutoSizeRowsMode = DataGridViewAutoSizeRowsMode.AllCells, ColumnHeadersHeightSizeMode = DataGridViewColumnHeadersHeightSizeMode.AutoSize,
            CellBorderStyle = DataGridViewCellBorderStyle.SingleHorizontal, StandardTab = true, AccessibleName = page < 2 ? $"Player {page + 1} buttons" : "Shortcuts",
        };
        g.DefaultCellStyle = new DataGridViewCellStyle { BackColor = Background, ForeColor = TextColor, SelectionBackColor = Raised, SelectionForeColor = Accent, Padding = new Padding(Font.Height / 3), WrapMode = DataGridViewTriState.True, Font = Font };
        g.ColumnHeadersDefaultCellStyle = new DataGridViewCellStyle { BackColor = Surface, ForeColor = Muted, Font = new Font(Font, FontStyle.Bold), Padding = new Padding(Font.Height / 3), SelectionBackColor = Surface, SelectionForeColor = Muted };
        g.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = page < 2 ? "SNES button" : "Shortcut", AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill, FillWeight = 34, SortMode = DataGridViewColumnSortMode.NotSortable });
        g.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = "Keyboard", AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill, FillWeight = 33, SortMode = DataGridViewColumnSortMode.NotSortable });
        g.Columns.Add(new DataGridViewTextBoxColumn { HeaderText = page < 2 ? "Controller" : "Controller (player 1)", AutoSizeMode = DataGridViewAutoSizeColumnMode.Fill, FillWeight = 33, SortMode = DataGridViewColumnSortMode.NotSortable });
        if (page < 2)
            foreach (var b in RowOrder) { int i = g.Rows.Add(); g.Rows[i].Tag = new RowTag(BindingSlot.Key(page, b), BindingSlot.PadButton(page, b)); }
        else
            foreach (var d in HotkeyCatalog.All) { int i = g.Rows.Add(); g.Rows[i].Tag = new RowTag(BindingSlot.Hotkey(HotkeyCatalog.Id(d)), BindingSlot.PadHotkey(HotkeyCatalog.Id(d))); }
        g.CellMouseClick += (_, e) => { if (e.RowIndex < 0) return; g.CurrentCell = g.Rows[e.RowIndex].Cells[Math.Max(1, e.ColumnIndex)];
            if (e.Button == MouseButtons.Right) ShowMenu(g, g.GetCellDisplayRectangle(g.CurrentCell.ColumnIndex, e.RowIndex, false).Location + new Size(e.X, e.Y));
            else if (e.ColumnIndex > 0) Edit(g); };
        g.KeyDown += (_, e) => {
            if (g.CurrentCell == null) return;
            if (e.KeyCode == Keys.Enter || e.KeyCode == Keys.F2 || e.KeyCode == Keys.Space) { e.SuppressKeyPress = e.Handled = true; Edit(g); }
            else if (e.KeyCode is Keys.Delete or Keys.Back) { e.SuppressKeyPress = e.Handled = true; ClearCell(g); }
            else if (e.KeyCode == Keys.Apps || (e.KeyCode == Keys.F10 && e.Shift)) { e.SuppressKeyPress = e.Handled = true; var rc = g.GetCellDisplayRectangle(g.CurrentCell.ColumnIndex, g.CurrentCell.RowIndex, false); ShowMenu(g, new Point(rc.Left, rc.Bottom)); }
        };
        g.CellEnter += (_, e) => { if (e.ColumnIndex == 0) BeginInvoke(() => { if (g.CurrentCell?.ColumnIndex == 0) g.CurrentCell = g.Rows[e.RowIndex].Cells[1]; }); };
        return g;
    }

    private (BindingSlot slot, RowTag tag)? Current(DataGridView g)
    {
        if (g.CurrentCell is not { } cell || g.Rows[cell.RowIndex].Tag is not RowTag tag) return null;
        var slot = cell.ColumnIndex == 2 ? tag.Controller : tag.Keyboard;
        return slot == null ? null : (slot, tag);
    }

    private void ShowMenu(DataGridView g, Point at)
    {
        if (Current(g) is not { } cur) return;
        var slot = cur.slot; var menu = new ContextMenuStrip { ShowImageMargin = false, Font = Font };
        bool hotkey = slot.Kind == "hotkey";
        menu.Items.Add(slot.Kind is "pad" or "padhotkey" ? "Press a controller button…" : "Press a key…", null, (_, _) => Edit(g));
        if (hotkey && HotkeyCatalog.Find(slot.HotkeyId!)!.Slot < 0) menu.Items.Add("Add another key…", null, (_, _) => Edit(g, true));
        menu.Items.Add("Pick from a list…", null, (_, _) => Pick(g));
        if (slot.Kind == "key") {
            var mouse = new ToolStripMenuItem("Mouse button");
            for (int i = 0; i < 5; i++) { var name = KeyCatalog.MouseNames[i]; mouse.DropDownItems.Add(KeyCatalog.Label(name), null, (_, _) => Assign(slot, name, 0)); }
            menu.Items.Add(mouse);
        }
        menu.Items.Add("Clear", null, (_, _) => ClearCell(g));
        menu.Items.Add("Reset to default", null, (_, _) => { ResetSlot(slot); Changed(); });
        menu.Show(g, at);
    }

    private void ResetSlot(BindingSlot slot)
    {
        var d = InputModel.Defaults();
        switch (slot.Kind) {
            case "key": model.Keys[slot.Player][(int)slot.Button!] = InputModel.DefaultKeys[(int)slot.Button!]; break;
            case "pad": model.Pad[slot.Player][(int)slot.Button!] = InputModel.DefaultPad[(int)slot.Button!]; break;
            case "hotkey": model.Hotkeys[slot.HotkeyId!] = FreshKeys(slot.HotkeyId!); break;
            default: model.PadHotkeys[slot.HotkeyId!] = d.PadHotkeys[slot.HotkeyId!]; break;
        }
    }
    /// <summary>What a newly installed game's config.ini says for a shortcut.</summary>
    private static List<string> FreshKeys(string id) { var def = HotkeyCatalog.Find(id)!; return def.FreshKeys.Length == 0 ? new() : def.FreshKeys.Split(',').ToList(); }

    private void ClearCell(DataGridView g)
    {
        if (Current(g) is not { } cur) return;
        if (cur.slot.Kind == "hotkey") model.Hotkeys[cur.slot.HotkeyId!].Clear(); else InputRules.Set(model, cur.slot, "");
        Changed(); Report(cur.slot.Describe(style) + " cleared.");
    }

    /// <summary>Capture a new binding. For a shortcut, <paramref name="add"/> appends another key instead of changing the first.</summary>
    private void Edit(DataGridView g, bool add = false)
    {
        if (Current(g) is not { } cur) return;
        var slot = cur.slot;
        bool padSlot = slot.Kind is "pad" or "padhotkey";
        string title = (slot.Kind is "key" or "pad" ? $"Player {slot.Player + 1} · SNES {slot.Button}" : HotkeyCatalog.Find(slot.HotkeyId!)!.Label);
        captureOpen = true;
        try {
            using var capture = new CaptureForm(title, padSlot, slot.Kind == "hotkey", slot.Kind is "key" or "pad" ? slot.Player : 0, style, Font);
            var result = capture.ShowDialog(this);
            int index = slot.Kind == "hotkey" && add ? model.Hotkeys[slot.HotkeyId!].Count : 0;
            if (result == DialogResult.Abort) {
                if (slot.Kind == "hotkey") model.Hotkeys[slot.HotkeyId!].Clear(); else InputRules.Set(model, slot, "");
                Changed(); Report(slot.Describe(style) + " cleared."); return;
            }
            if (result != DialogResult.OK || capture.Binding == null) { Report("Unchanged."); return; }
            Assign(slot, capture.Binding, index);
        } finally { captureOpen = false; }
    }

    private void Pick(DataGridView g)
    {
        if (Current(g) is not { } cur) return;
        var slot = cur.slot;
        IEnumerable<(string value, string label)> items = slot.Kind switch {
            "key" => KeyCatalog.All.Select(k => (k.Name, k.Label)).Concat(KeyCatalog.MouseNames.Select(m => (m, KeyCatalog.Label(m)))),
            "hotkey" => KeyCatalog.All.Where(k => k.Hotkey != null).SelectMany(k => new[] { ("", ""), ("Shift+", "Shift + "), ("Ctrl+", "Ctrl + "), ("Alt+", "Alt + ") }
                .Select(m => (m.Item1 + k.Hotkey, m.Item2 + k.Label))),
            _ => PadCatalog.Names.Select(n => (n, PadCatalog.Label(n, style)))
                .Concat(PadCatalog.Names.Where(n => n != "L2").Select(n => ("L2+" + n, PadCatalog.Label("L2+" + n, style)))),
        };
        using var picker = new PickForm(slot.Describe(style), items.ToList(), InputRules.Get(model, slot), Font);
        if (picker.ShowDialog(this) == DialogResult.OK && picker.Value != null) Assign(slot, picker.Value, 0);
    }

    private void Assign(BindingSlot slot, string binding, int index)
    {
        var conflicts = InputRules.Conflicts(model, slot, binding);
        if (conflicts.Count == 0) { InputRules.Set(model, slot, binding, index); Changed(); Report($"{slot.Describe(style)}: {Show(slot, binding)}."); return; }
        var names = string.Join("\n", conflicts.Select(c => "• " + c.Describe(style)));
        bool canSwap = conflicts.All(c => InputRules.SameFamily(c, slot));
        using var dialog = new ConflictForm($"{Show(slot, binding)} is already used by:\n{names}", canSwap, Font);
        switch (dialog.ShowDialog(this)) {
            case DialogResult.Yes: InputRules.Swap(model, slot, binding, index); Report($"Swapped: {slot.Describe(style)} is now {Show(slot, binding)}."); break;
            case DialogResult.No: InputRules.Replace(model, slot, binding, index); Report($"{slot.Describe(style)} is now {Show(slot, binding)}; removed from {conflicts.Count} other binding{(conflicts.Count == 1 ? "" : "s")}."); break;
            default: Report("Unchanged."); return;
        }
        Changed();
    }
    private string Show(BindingSlot slot, string binding) => slot.Kind switch {
        "key" => KeyCatalog.Label(binding), "hotkey" => Chord.Label(binding), _ => PadCatalog.Label(binding, style) };

    // ---- state -----------------------------------------------------------------------------

    private bool syncing;
    private bool Dirty => InputProfile.Export(model) != InputProfile.Export(saved);
    private void Reload()
    {
        var warnings = new List<string>();
        try {
            saved = files.Load(warnings); model = saved.Clone();
            if (int.TryParse(IniText.Read(files.ConfigPath, true).Get("GamepadMap", "GamepadDeadzone"), out var dz)) deadzone = Math.Clamp(dz, 0, 32767);
            if (!File.Exists(files.ConfigPath) || !File.Exists(files.KeybindsPath))
                warnings.Add("The game has not been started from this folder yet, so the game's defaults are shown. Saving creates only the keys you change.");
        } catch (Exception e) when (e is IOException or InvalidDataException or UnauthorizedAccessException) {
            saved = InputModel.Defaults(); model = saved.Clone(); Report(e.Message, true); save.Enabled = false; RefreshAll(); return;
        }
        save.Enabled = true; RefreshAll();
        Report(warnings.Count == 0 ? "Loaded the game's current keys and controller buttons." : string.Join(" ", warnings), warnings.Count > 0);
    }
    private void Changed() { RefreshAll(); }
    private void RefreshAll()
    {
        syncing = true;
        for (int p = 0; p < 2; p++) devices[p].SelectedIndex = model.Device(p);
        syncing = false;
        RefreshGrids(); RefreshSide(); pad.Invalidate();
        Text = "Illusion of Gaia · Keys, controllers and shortcuts" + (Dirty ? " (unsaved)" : "");
    }
    private void RefreshGrids()
    {
        for (int page = 0; page < 3; page++)
            foreach (DataGridViewRow row in grids[page].Rows) {
                var tag = (RowTag)row.Tag!;
                if (page < 2) {
                    var b = tag.Keyboard!.Button!.Value;
                    row.Cells[0].Value = ButtonTitle(b);
                    row.Cells[1].Value = KeyCatalog.Label(model.Keys[page][(int)b]);
                    row.Cells[2].Value = PadCatalog.Label(model.Pad[page][(int)b], style);
                    row.Cells[1].Style.ForeColor = model.UsesKeyboard(page) ? TextColor : Muted;
                    row.Cells[2].Style.ForeColor = model.UsesPad(page) ? TextColor : Muted;
                } else {
                    var d = HotkeyCatalog.Find(tag.Keyboard!.HotkeyId!)!;
                    row.Cells[0].Value = d.Label;
                    var keys = model.Hotkeys[HotkeyCatalog.Id(d)];
                    row.Cells[1].Value = keys.Count == 0 ? "—" : string.Join("  or  ", keys.Select(Chord.Label));
                    row.Cells[2].Value = PadCatalog.Label(model.PadHotkeys[HotkeyCatalog.Id(d)], style);
                    row.Cells[0].ToolTipText = d.Help;
                }
                foreach (DataGridViewCell cell in row.Cells) {
                    var slot = cell.ColumnIndex == 1 ? tag.Keyboard : cell.ColumnIndex == 2 ? tag.Controller : null;
                    bool clash = slot != null && InputRules.Get(model, slot) is var v && v.Length > 0 && v != "None" && InputRules.Conflicts(model, slot, v).Count > 0;
                    cell.Style.BackColor = clash ? Color.FromArgb(70, 42, 30) : Background;
                }
            }
    }
    private static string ButtonTitle(SnesButton b) => b switch {
        SnesButton.Up => "D-pad up", SnesButton.Down => "D-pad down", SnesButton.Left => "D-pad left", SnesButton.Right => "D-pad right",
        SnesButton.L => "L (shoulder)", SnesButton.R => "R (shoulder)", _ => b.ToString() };
    private void RefreshSide()
    {
        int page = Page;
        presetBox.Items.Clear();
        if (page < 2) {
            foreach (var p in InputPresets.Keyboard) presetBox.Items.Add(new PresetItem("Keyboard · " + p.Name, p));
            foreach (var p in InputPresets.Controller) presetBox.Items.Add(new PresetItem("Controller · " + p.Name, p));
        } else presetBox.Items.Add(new PresetItem("Game default shortcuts", null));
        presetBox.SelectedIndex = 0;
        var notes = new List<string>();
        var shared = InputRules.SharedKeyboardKeys(model);
        if (shared.Count > 0) notes.Add($"Both players read the keyboard and share {shared.Count} key{(shared.Count == 1 ? "" : "s")} ({string.Join(", ", shared.Take(4))}{(shared.Count > 4 ? "…" : "")}): one key press moves both. Give player 2 other keys (try the Numpad preset).");
        if (page == 1) notes.Add("Illusion of Gaia is a one-player game: player 2's buttons reach the second controller port, which the game does not read.");
        if (page < 2 && model.Device(page) == 1) notes.Add($"Player {page + 1}'s keyboard keys are ignored while this player is on Controller only.");
        if (page == 2) notes.Add("Controller shortcuts are read from player 1's controller. LT (ZL, L2) + a button never reaches the game. The left stick always works as the d-pad.");
        else if (page == 0 && model.Pad[0].Contains("L2")) notes.Add("The left trigger is an SNES button now; the built-in LT shortcuts still fire when it is held with their button.");
        sideNote.Text = string.Join("\n\n", notes);
    }
    private sealed record PresetItem(string Text, InputPreset? Preset) { public override string ToString() => Text; }

    private void ApplyPreset()
    {
        if (presetBox.SelectedItem is not PresetItem item) return;
        int page = Page;
        if (item.Preset == null) {
            foreach (var d in HotkeyCatalog.All) { model.Hotkeys[HotkeyCatalog.Id(d)] = FreshKeys(HotkeyCatalog.Id(d)); model.PadHotkeys[HotkeyCatalog.Id(d)] = d.Pad; }
            Changed(); Report("Shortcuts set to the game's defaults. Save to keep them."); return;
        }
        InputPresets.Apply(model, page, item.Preset);
        Changed();
        var clashes = Enumerable.Range(0, 12).Select(b => item.Preset.Kind == "key" ? BindingSlot.Key(page, (SnesButton)b) : BindingSlot.PadButton(page, (SnesButton)b))
            .SelectMany(s => InputRules.Conflicts(model, s, InputRules.Get(model, s)).Where(c => c.Kind is "hotkey" or "padhotkey")).Distinct().ToList();
        Report($"Player {page + 1}: {item.Preset.Name} — {item.Preset.Description}." + (clashes.Count > 0 ? " Also used by: " + string.Join(", ", clashes.Select(c => c.Describe(style))) + " (highlighted)." : ""), clashes.Count > 0);
    }
    private void ResetPage()
    {
        int page = Page;
        if (page < 2) { model.Keys[page] = (string[])InputModel.DefaultKeys.Clone(); model.Pad[page] = (string[])InputModel.DefaultPad.Clone(); Report($"Player {page + 1}'s keys and controller buttons set to the game's defaults."); }
        else { foreach (var d in HotkeyCatalog.All) { model.Hotkeys[HotkeyCatalog.Id(d)] = FreshKeys(HotkeyCatalog.Id(d)); model.PadHotkeys[HotkeyCatalog.Id(d)] = d.Pad; } Report("Shortcuts set to the game's defaults."); }
        Changed();
    }

    private bool Save()
    {
        try {
            if (NativeModSettings.IsEngineRunning(engineExecutable)) { Report("Close the game first: it rewrites config.ini when it exits, and keys are read only at start.", true); return false; }
            var count = files.Save(saved, model);
            Reload();
            Report(count == 0 ? "Nothing to save." : $"Saved {count} setting{(count == 1 ? "" : "s")}. They apply the next time the game starts.");
            return true;
        } catch (Exception e) when (e is IOException or UnauthorizedAccessException or InvalidDataException) { Report("Could not save: " + e.Message, true); return false; }
    }
    private void Export()
    {
        using var dialog = new SaveFileDialog { Title = "Export input profile", Filter = "Input profile (*.json)|*.json", FileName = "gaia-input-profile.json" };
        if (dialog.ShowDialog(this) != DialogResult.OK) return;
        try { File.WriteAllText(dialog.FileName, InputProfile.Export(model)); Report("Exported to " + dialog.FileName + "."); }
        catch (Exception e) when (e is IOException or UnauthorizedAccessException) { Report("Could not export: " + e.Message, true); }
    }
    private void Import()
    {
        using var dialog = new OpenFileDialog { Title = "Import input profile", Filter = "Input profile (*.json)|*.json", CheckFileExists = true };
        if (dialog.ShowDialog(this) != DialogResult.OK) return;
        try {
            var info = new FileInfo(dialog.FileName); if (info.Length > 1 << 20) throw new InvalidDataException("That file is too large to be an input profile.");
            model = InputProfile.Import(File.ReadAllText(dialog.FileName), model); Changed(); Report("Imported. Review it, then Save.");
        } catch (Exception e) when (e is IOException or UnauthorizedAccessException or InvalidDataException or System.Text.Json.JsonException or InvalidOperationException or FormatException) { Report("Could not import: " + e.Message, true); }
    }
    private void Report(string text, bool error = false) { status.Text = text; status.ForeColor = error ? Error : Muted; }

    // ---- live input ------------------------------------------------------------------------

    public bool PreFilterMessage(ref Message m)
    {
        const int down = 0x100, up = 0x101, sysdown = 0x104, sysup = 0x105;
        if (m.Msg is not (down or up or sysdown or sysup)) return false;
        long lp = m.LParam.ToInt64(); int vk = (int)m.WParam.ToInt64();
        var key = KeyCatalog.FromScan((int)((lp >> 16) & 0xFF), ((lp >> 24) & 1) != 0, vk);
        // A release always counts, even while a capture dialog has it: Enter opens capture on key-down,
        // and its key-up arrives inside that dialog (the tester used to show Start held afterwards).
        if (key != null && m.Msg is up or sysup && heldKeys.Remove(key.Name)) pad.Invalidate();
        if (captureOpen || !ContainsFocus && Form.ActiveForm != this) return false;
        if (key != null && m.Msg is down or sysdown) { heldKeys.Add(key.Name); pad.Invalidate(); }
        if (!tryKeys.Checked) return false;
        if (vk == 0x1B && m.Msg == down) { tryKeys.Checked = false; Report("Stopped trying keys."); }
        return true;   // keys light the pad instead of moving around the window
    }
    /// <summary>SNES buttons the given player would press right now, with the bindings as edited (not yet saved).</summary>
    internal HashSet<SnesButton> Pressed(int player, out string? shortcut)
    {
        var lit = new HashSet<SnesButton>(); shortcut = null;
        if (model.UsesKeyboard(player))
            for (int b = 0; b < 12; b++) if (heldKeys.Contains(model.Keys[player][b])) lit.Add((SnesButton)b);
        // The game seats an XInput pad by its slot first (SDL's player index), so slot N is player N+1.
        var held = model.UsesPad(player) ? lastPad[player] : Array.Empty<int>();
        var names = held.Select(i => PadCatalog.Names[i]).ToHashSet();
        foreach (var d in HotkeyCatalog.All) {
            var chord = model.PadHotkeys[HotkeyCatalog.Id(d)];
            if (player == 0 && chord.Contains('+') && chord.Split('+').All(names.Contains)) { shortcut = d.Label; return lit; }
        }
        for (int b = 0; b < 12; b++) { var chord = model.Pad[player][b]; if (chord.Length > 0 && chord.Split('+').All(names.Contains)) lit.Add((SnesButton)b); }
        if (model.UsesPad(player) && stick[player] is var (x, y) && (long)x * x + (long)y * y >= (long)deadzone * deadzone) {
            double angle = Math.Atan2(-y, x) * 4 / Math.PI;   // sectors of 45 degrees, as the runner splits the stick
            int sector = (int)Math.Round(angle); sector = (sector % 8 + 8) % 8;
            if (sector is 1 or 2 or 3) lit.Add(SnesButton.Down); if (sector is 5 or 6 or 7) lit.Add(SnesButton.Up);
            if (sector is 0 or 1 or 7) lit.Add(SnesButton.Right); if (sector is 3 or 4 or 5) lit.Add(SnesButton.Left);
        }
        if (player == 0) foreach (var d in HotkeyCatalog.All) {
            var keys = model.Hotkeys[HotkeyCatalog.Id(d)];
            if (keys.Any(k => !Chord.HasModifier(k) && Chord.Key(k) is { } info && heldKeys.Contains(info.Name))) { shortcut ??= d.Label; break; }
        }
        return lit;
    }
    private readonly (short, short)[] stick = new (short, short)[4];
    /// <summary>The page shown. TabControl reports -1 until its handle exists, which the constructor's first refresh precedes.</summary>
    private int Page => Math.Clamp(tabs.SelectedIndex, 0, 2);
    internal int PadPlayer => Math.Min(Page, 1);
    internal PadStyle Style => style;
    private readonly bool[] navHeld = new bool[17];
    private void Poll()
    {
        bool any = false;
        for (int slot = 0; slot < 2; slot++) {
            var held = XInputPad.Read(slot, out var x, out var y);
            stick[slot] = (x, y);
            var now = held ?? Array.Empty<int>();
            if (!now.SequenceEqual(lastPad[slot])) { lastPad[slot] = now; any = true; }
        }
        var connected = XInputPad.Connected().ToList();
        padState.Text = connected.Count == 0 ? "No Xbox-compatible (XInput) controller found. PlayStation and Switch pads still work in the game; pick their buttons from a list (right-click a cell)."
            : string.Join("\n", connected.Select(s => $"XInput controller {s + 1} → player {s + 1}" + (s > 1 ? " (not used)" : ""))) + (tryKeys.Checked ? "" : "\nA changes, B closes, LB/RB switch pages.");
        if (any) pad.Invalidate();
        if (!captureOpen && !tryKeys.Checked && Form.ActiveForm == this) Navigate(lastPad[0]);
    }
    /// <summary>Controller navigation of the window: d-pad moves, A edits, B closes, LB/RB change page, Menu/View move focus.</summary>
    private void Navigate(int[] held)
    {
        var map = new (string button, Action act)[] {
            ("DpadUp", () => SendKeys.Send("{UP}")), ("DpadDown", () => SendKeys.Send("{DOWN}")), ("DpadLeft", () => SendKeys.Send("{LEFT}")), ("DpadRight", () => SendKeys.Send("{RIGHT}")),
            ("A", () => { if (ActiveControl is DataGridView g) Edit(g); else SendKeys.Send(" "); }),
            ("B", Close), ("L1", () => tabs.SelectedIndex = (Page + 2) % 3), ("R1", () => tabs.SelectedIndex = (Page + 1) % 3),
            ("Start", () => SelectNextControl(ActiveControl, true, true, true, true)), ("Back", () => SelectNextControl(ActiveControl, false, true, true, true)),
            ("Y", () => { if (ActiveControl is DataGridView g) ClearCell(g); }),
        };
        foreach (var (button, act) in map) {
            int i = PadCatalog.Index(button); bool h = held.Contains(i);
            if (h && !navHeld[i]) { navHeld[i] = true; if (button is "L1" or "R1") grids[Page].Focus(); act(); if (button is "L1" or "R1") grids[Page].Focus(); }
            else if (!h) navHeld[i] = false;
        }
    }

    // ---- drawing helpers ------------------------------------------------------------------

    private void DrawTab(DrawItemEventArgs e)
    {
        bool selected = tabs.SelectedIndex == e.Index;
        Color fill = SystemInformation.HighContrast ? (selected ? SystemColors.Highlight : SystemColors.Control) : selected ? Accent : Surface;
        Color ink = SystemInformation.HighContrast ? (selected ? SystemColors.HighlightText : SystemColors.ControlText) : selected ? Background : TextColor;
        using var background = new SolidBrush(SystemInformation.HighContrast ? SystemColors.Control : Background);
        e.Graphics.FillRectangle(background, e.Bounds);
        if (e.Index == tabs.TabCount - 1) { var last = tabs.GetTabRect(e.Index); e.Graphics.FillRectangle(background, last.Right, 0, tabs.Width - last.Right, last.Bottom + 2); }
        var bounds = Rectangle.Inflate(e.Bounds, -3, -3);
        using var brush = new SolidBrush(fill); e.Graphics.FillRectangle(brush, bounds);
        using var font = new Font(tabs.Font, FontStyle.Bold);
        TextRenderer.DrawText(e.Graphics, tabs.TabPages[e.Index].Text, font, bounds, ink, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine | TextFormatFlags.NoPrefix);
        if (selected && tabs.Focused) ControlPaint.DrawFocusRectangle(e.Graphics, Rectangle.Inflate(bounds, -3, -3), ink, fill);
    }
    private Label Caption(string text, float size, Color color, FontStyle fontStyle = FontStyle.Regular) => new() {
        Text = text, Font = new Font("Segoe UI", size * scale, fontStyle), ForeColor = color, AutoSize = true, MaximumSize = new Size(Font.Height * 60, 0), UseMnemonic = false, Margin = new Padding(0, 0, 0, Font.Height / 4) };
    private ComboBox Combo(string name, string[] items)
    {
        var c = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, AccessibleName = name }; StyleCombo(c);
        c.Items.AddRange(items.Cast<object>().ToArray()); return c;
    }
    private void StyleCombo(ComboBox c) {
        // A combo box takes its font's height only once its handle exists; lay the panel out again then.
        c.HandleCreated += (_, _) => c.Parent?.PerformLayout();
        c.SizeChanged += (_, _) => c.Parent?.PerformLayout();
        c.FlatStyle = FlatStyle.Flat; c.BackColor = Background; c.ForeColor = TextColor; c.Dock = DockStyle.Fill; c.Margin = new Padding(0, 0, 0, Font.Height / 3); c.Font = Font;
        c.Height = c.PreferredHeight + 4; c.MinimumSize = new Size(0, c.Height);   // the height its font needs, before any handle exists
    }
    private Button Button(string text, Action action, bool primary = false) => MakeButton(text, () => action(), primary, Font);
    private Button Button(string text, Func<bool> action, bool primary = false) => MakeButton(text, () => action(), primary, Font);
    internal static Button MakeButton(string text, Action action, bool primary, Font font)
    {
        var b = new Button { Text = text, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, FlatStyle = FlatStyle.Flat, BackColor = primary ? Accent : Surface,
            ForeColor = primary ? Background : TextColor, Font = new Font(font, FontStyle.Bold), Padding = new Padding(font.Height / 2, font.Height / 4, font.Height / 2, font.Height / 4),
            Margin = new Padding(font.Height / 2, 0, 0, font.Height / 3), UseMnemonic = false, Cursor = Cursors.Hand };
        b.FlatAppearance.BorderColor = primary ? Accent : Color.FromArgb(64, 81, 92);
        b.FlatAppearance.MouseOverBackColor = primary ? Color.FromArgb(227, 194, 121) : Raised;
        b.Click += (_, _) => action(); return b;
    }

    /// <summary>The SNES pad, lit by what the selected player is pressing.</summary>
    private sealed class PadView : Control
    {
        internal InputForm? Owner;
        public PadView() { DoubleBuffered = true; SetStyle(ControlStyles.ResizeRedraw | ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint, true); }
        protected override void OnPaint(PaintEventArgs e)
        {
            var g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias; g.Clear(Surface);
            if (Owner == null) return;
            int player = Owner.PadPlayer;
            var lit = Owner.Pressed(player, out var shortcut);
            float w = Width, h = Height, u = Math.Min(w / 16f, h / 8.6f), ox = (w - u * 16) / 2, oy = (h - u * 8) / 2 + u * 0.4f;
            RectangleF R(float x, float y, float rw, float rh) => new(ox + x * u, oy + y * u, rw * u, rh * u);
            using var body = new SolidBrush(Color.FromArgb(206, 204, 214)); using var dark = new SolidBrush(Color.FromArgb(70, 70, 82));
            using var path = Rounded(R(0.5f, 1.2f, 15, 6), 3 * u); g.FillPath(body, path);
            void Btn(SnesButton b, RectangleF r, Color baseColor, string label, bool round = true)
            {
                using var fill = new SolidBrush(lit.Contains(b) ? Lit : baseColor);
                if (round) g.FillEllipse(fill, r); else g.FillRectangle(fill, r);
                using var f = new Font("Segoe UI", Math.Max(6, u * 0.42f), FontStyle.Bold, GraphicsUnit.Pixel);
                TextRenderer.DrawText(g, label, f, Rectangle.Round(r), lit.Contains(b) ? Color.Black : Color.White, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPadding);
            }
            Btn(SnesButton.L, R(1.5f, 0.5f, 3.5f, 0.9f), Color.FromArgb(120, 120, 132), "L", false);
            Btn(SnesButton.R, R(11, 0.5f, 3.5f, 0.9f), Color.FromArgb(120, 120, 132), "R", false);
            Btn(SnesButton.Up, R(2.6f, 2.4f, 1.2f, 1.3f), Color.FromArgb(50, 50, 60), "▲", false);
            Btn(SnesButton.Down, R(2.6f, 4.9f, 1.2f, 1.3f), Color.FromArgb(50, 50, 60), "▼", false);
            Btn(SnesButton.Left, R(1.4f, 3.7f, 1.3f, 1.2f), Color.FromArgb(50, 50, 60), "◀", false);
            Btn(SnesButton.Right, R(3.7f, 3.7f, 1.3f, 1.2f), Color.FromArgb(50, 50, 60), "▶", false);
            g.FillRectangle(dark, R(2.6f, 3.7f, 1.2f, 1.2f));
            Btn(SnesButton.Select, R(6.0f, 4.3f, 1.6f, 0.6f), Color.FromArgb(110, 110, 122), "SELECT", false);
            Btn(SnesButton.Start, R(8.2f, 4.3f, 1.6f, 0.6f), Color.FromArgb(110, 110, 122), "START", false);
            Btn(SnesButton.X, R(12.0f, 2.2f, 1.4f, 1.4f), Color.FromArgb(48, 92, 196), "X");
            Btn(SnesButton.Y, R(10.7f, 3.5f, 1.4f, 1.4f), Color.FromArgb(36, 150, 80), "Y");
            Btn(SnesButton.A, R(13.3f, 3.5f, 1.4f, 1.4f), Color.FromArgb(200, 40, 50), "A");
            Btn(SnesButton.B, R(12.0f, 4.8f, 1.4f, 1.4f), Color.FromArgb(220, 180, 30), "B");
            using var cap = new Font("Segoe UI", Math.Max(7, u * 0.45f), GraphicsUnit.Pixel);
            var text = $"Player {player + 1}" + (shortcut != null ? $" · shortcut: {shortcut}" : lit.Count > 0 ? " · " + string.Join(" ", lit.OrderBy(x => x)) : " · press a key or button");
            TextRenderer.DrawText(g, text, cap, Rectangle.Round(new RectangleF(0, oy + u * 7.3f, w, u * 0.8f)), Muted, TextFormatFlags.HorizontalCenter | TextFormatFlags.EndEllipsis);
        }
        private static GraphicsPath Rounded(RectangleF r, float radius)
        {
            var p = new GraphicsPath(); float d = Math.Min(radius * 2, Math.Min(r.Width, r.Height));
            p.AddArc(r.X, r.Y, d, d, 180, 90); p.AddArc(r.Right - d, r.Y, d, d, 270, 90); p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90); p.AddArc(r.X, r.Bottom - d, d, d, 90, 90); p.CloseFigure(); return p;
        }
    }
}

/// <summary>"Press a key / button…": keyboard through the window's key messages (physical scan codes), controllers through XInput.</summary>
internal sealed class CaptureForm : Form
{
    private readonly bool pad, hotkey;
    private readonly int player;
    private readonly PadStyle style;
    private readonly System.Windows.Forms.Timer poll = new() { Interval = 16 };
    private readonly HashSet<int>[] ignore = { new(), new(), new(), new() };
    private readonly HashSet<int>[] chord = { new(), new(), new(), new() };
    private readonly Label hint;
    // Timer ticks run late (16 ms asks for one, Windows delivers ~25-31 ms), so the countdown uses the clock.
    private readonly System.Diagnostics.Stopwatch opened = new();
    private int shownSeconds = -1;
    private string? pendingModifier;
    internal string? Binding { get; private set; }

    internal CaptureForm(string title, bool pad, bool hotkey, int player, PadStyle style, Font font)
    {
        this.pad = pad; this.hotkey = hotkey; this.player = player; this.style = style;
        Text = "Change binding"; Font = font; BackColor = ColorTranslator.FromHtml("#1B2B37"); ForeColor = ColorTranslator.FromHtml("#F2EBDD");
        FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = MinimizeBox = false; ShowInTaskbar = false; StartPosition = FormStartPosition.CenterParent;
        KeyPreview = true; AutoScaleMode = AutoScaleMode.None; AutoSize = true; AutoSizeMode = AutoSizeMode.GrowAndShrink;
        int em = font.Height;
        var stack = new FlowLayoutPanel { FlowDirection = FlowDirection.TopDown, AutoSize = true, Padding = new Padding(em * 3 / 2), WrapContents = false };
        stack.Controls.Add(new Label { Text = title, AutoSize = true, Font = new Font(font.FontFamily, font.Size * 1.4f, FontStyle.Bold), ForeColor = ColorTranslator.FromHtml("#D7B46A"), UseMnemonic = false });
        stack.Controls.Add(new Label { Text = pad ? "Press a controller button (hold LT first for an LT + button chord)…" : hotkey ? "Press a key, with Shift, Ctrl or Alt if you like…" : "Press a key…", AutoSize = true, MaximumSize = new Size(em * 26, 0), UseMnemonic = false, Margin = new Padding(0, em / 2, 0, 0) });
        hint = new Label { AutoSize = true, MaximumSize = new Size(em * 26, 0), ForeColor = ColorTranslator.FromHtml("#A7B5BD"), UseMnemonic = false, Margin = new Padding(0, em / 2, 0, 0) };
        stack.Controls.Add(hint);
        var buttons = new FlowLayoutPanel { AutoSize = true, Margin = new Padding(0, em, 0, 0) };
        buttons.Controls.Add(InputForm.MakeButton("Cancel", () => { DialogResult = DialogResult.Cancel; }, false, font));
        buttons.Controls.Add(InputForm.MakeButton("Clear", () => { DialogResult = DialogResult.Abort; }, false, font));
        foreach (Control c in buttons.Controls) c.TabStop = false;
        stack.Controls.Add(buttons); Controls.Add(stack);
        poll.Tick += (_, _) => Poll();
        Shown += (_, _) => {
            for (int s = 0; s < 4; s++) foreach (var b in XInputPad.Read(s, out _, out _) ?? Array.Empty<int>()) ignore[s].Add(b);   // the press that opened this
            opened.Restart(); poll.Start();
        };
        FormClosed += (_, _) => poll.Stop();
        UpdateHint();
    }
    private void UpdateHint()
    {
        int left = Math.Max(0, 10 - (int)opened.Elapsed.TotalSeconds); shownSeconds = left;
        hint.Text = (pad ? "Keyboard: " : "") + "Esc cancels · Backspace or Delete clears" + (pad ? "" : " · a controller's B cancels") + $" · closes in {left} s";
    }
    protected override bool ProcessCmdKey(ref Message msg, Keys keyData) => HandleKey(ref msg) || base.ProcessCmdKey(ref msg, keyData);
    protected override void WndProc(ref Message m)
    {
        if (m.Msg is 0x101 or 0x105 && HandleKeyUp(ref m)) return;   // WM_KEYUP / WM_SYSKEYUP: PrintScreen and lone modifiers
        base.WndProc(ref m);
    }
    private bool HandleKey(ref Message msg)
    {
        if (msg.Msg is not (0x100 or 0x104)) return false;
        int vk = (int)msg.WParam.ToInt64(); long lp = msg.LParam.ToInt64();
        if (vk == 0x1B) { DialogResult = DialogResult.Cancel; return true; }
        if (vk is 0x08 or 0x2E) { DialogResult = DialogResult.Abort; return true; }
        if (pad) return true;
        var key = KeyCatalog.FromScan((int)((lp >> 16) & 0xFF), ((lp >> 24) & 1) != 0, vk);
        if (key == null) { hint.Text = "That key is not one the game can read. Try another."; return true; }
        if (!hotkey) { Finish(key.Name); return true; }
        if (vk is 0x10 or 0x11 or 0x12 or 0xA0 or 0xA1 or 0xA2 or 0xA3 or 0xA4 or 0xA5) { pendingModifier = key.Name; return true; }
        if (key.Hotkey == null) { hint.Text = key.Label + " cannot be a shortcut key (config.ini reserves it). Pick another."; return true; }
        var mods = ModifierKeys; Finish(Chord.Make(key, mods.HasFlag(Keys.Shift), mods.HasFlag(Keys.Control), mods.HasFlag(Keys.Alt)));
        return true;
    }
    private bool HandleKeyUp(ref Message m)
    {
        int vk = (int)m.WParam.ToInt64();
        if (!pad && vk == 0x2C) { var k = KeyCatalog.ByName("PrintScreen")!; Finish(hotkey ? Chord.Make(k, ModifierKeys.HasFlag(Keys.Shift), ModifierKeys.HasFlag(Keys.Control), ModifierKeys.HasFlag(Keys.Alt)) : k.Name); return true; }
        if (hotkey && pendingModifier != null) { var k = KeyCatalog.ByName(pendingModifier)!; pendingModifier = null; Finish(k.Hotkey!); return true; }
        return false;
    }
    private readonly HashSet<int>[] previous = { new(), new(), new(), new() };
    private void Poll()
    {
        if (opened.Elapsed.TotalSeconds >= 10) { DialogResult = DialogResult.Cancel; return; }
        if (10 - (int)opened.Elapsed.TotalSeconds != shownSeconds) UpdateHint();
        int trigger = PadCatalog.Index("L2");
        for (int s = 0; s < 4; s++) {
            var held = XInputPad.Read(s, out _, out _) ?? Array.Empty<int>();
            ignore[s].IntersectWith(held);   // a button held when this opened counts once it is released and pressed again
            var fresh = held.Where(b => !ignore[s].Contains(b)).ToHashSet();
            if (!pad) { if (fresh.Contains(PadCatalog.Index("B"))) { DialogResult = DialogResult.Cancel; return; } continue; }
            chord[s].UnionWith(fresh); chord[s].IntersectWith(fresh);
            // A chord completes on the first new button other than LT (ZL), the runner's function button.
            var lead = fresh.Where(b => b != trigger && !previous[s].Contains(b)).DefaultIfEmpty(-1).First();
            if (lead >= 0) {
                Finish(string.Join("+", chord[s].Where(b => b != lead).OrderBy(b => b).Select(b => PadCatalog.Names[b]).Append(PadCatalog.Names[lead])));
                return;
            }
            // LT on its own: pressed and released with nothing else.
            if (previous[s].SetEquals(new[] { trigger }) && fresh.Count == 0) { Finish("L2"); return; }
            previous[s] = fresh;
        }
    }
    private void Finish(string binding) { Binding = binding; DialogResult = DialogResult.OK; }
}

/// <summary>Choose any value from a list: for keys such as Esc that capture reserves, and for controllers XInput cannot see.</summary>
internal sealed class PickForm : Form
{
    private readonly ListBox list = new();
    private readonly List<(string value, string label)> items;
    internal string? Value { get; private set; }
    internal PickForm(string title, List<(string value, string label)> items, string current, Font font)
    {
        this.items = items;
        Text = "Pick · " + title; Font = font; BackColor = ColorTranslator.FromHtml("#1B2B37"); ForeColor = ColorTranslator.FromHtml("#F2EBDD");
        StartPosition = FormStartPosition.CenterParent; ShowInTaskbar = false; MinimizeBox = MaximizeBox = false; AutoScaleMode = AutoScaleMode.None;
        int em = font.Height; ClientSize = new Size(em * 24, em * 26);
        list.Dock = DockStyle.Fill; list.BackColor = ColorTranslator.FromHtml("#101A23"); list.ForeColor = ForeColor; list.BorderStyle = BorderStyle.None; list.IntegralHeight = false; list.AccessibleName = title;
        foreach (var item in items) list.Items.Add(item.label);
        list.SelectedIndex = Math.Max(0, items.FindIndex(i => i.value.Equals(current, StringComparison.OrdinalIgnoreCase)));
        list.DoubleClick += (_, _) => Choose();
        list.KeyDown += (_, e) => { if (e.KeyCode == Keys.Enter) { e.SuppressKeyPress = true; Choose(); } };
        var footer = new FlowLayoutPanel { Dock = DockStyle.Bottom, AutoSize = true, FlowDirection = FlowDirection.RightToLeft, Padding = new Padding(0, em / 2, 0, 0) };
        var cancel = InputForm.MakeButton("Cancel", () => DialogResult = DialogResult.Cancel, false, font);
        footer.Controls.Add(cancel); footer.Controls.Add(InputForm.MakeButton("Use", Choose, true, font));
        CancelButton = cancel;
        var pad = new Panel { Dock = DockStyle.Fill, Padding = new Padding(em) }; pad.Controls.Add(list); pad.Controls.Add(footer);
        Controls.Add(pad);
    }
    private void Choose() { if (list.SelectedIndex >= 0) { Value = items[list.SelectedIndex].value; DialogResult = DialogResult.OK; } }
}

/// <summary>Swap / Replace / Cancel, when a key or button is already in use.</summary>
internal sealed class ConflictForm : Form
{
    internal ConflictForm(string message, bool canSwap, Font font)
    {
        Text = "Already in use"; Font = font; BackColor = ColorTranslator.FromHtml("#1B2B37"); ForeColor = ColorTranslator.FromHtml("#F2EBDD");
        FormBorderStyle = FormBorderStyle.FixedDialog; StartPosition = FormStartPosition.CenterParent; ShowInTaskbar = false; MinimizeBox = MaximizeBox = false;
        AutoScaleMode = AutoScaleMode.None; AutoSize = true; AutoSizeMode = AutoSizeMode.GrowAndShrink;
        int em = font.Height;
        var stack = new FlowLayoutPanel { FlowDirection = FlowDirection.TopDown, AutoSize = true, Padding = new Padding(em * 3 / 2), WrapContents = false };
        stack.Controls.Add(new Label { Text = message, AutoSize = true, MaximumSize = new Size(em * 30, 0), UseMnemonic = false });
        stack.Controls.Add(new Label { Text = (canSwap ? "Swap gives the other binding your old key. " : "") + "Replace takes it away from the other binding.", AutoSize = true, MaximumSize = new Size(em * 30, 0), ForeColor = ColorTranslator.FromHtml("#A7B5BD"), UseMnemonic = false, Margin = new Padding(0, em / 2, 0, 0) });
        var buttons = new FlowLayoutPanel { AutoSize = true, Margin = new Padding(0, em, 0, 0) };
        Button? first = null;
        if (canSwap) buttons.Controls.Add(first = InputForm.MakeButton("Swap", () => DialogResult = DialogResult.Yes, true, font));
        var replace = InputForm.MakeButton("Replace", () => DialogResult = DialogResult.No, !canSwap, font); buttons.Controls.Add(replace);
        var cancel = InputForm.MakeButton("Cancel", () => DialogResult = DialogResult.Cancel, false, font); buttons.Controls.Add(cancel);
        CancelButton = cancel; AcceptButton = first ?? replace;
        stack.Controls.Add(buttons); Controls.Add(stack);
    }
}
