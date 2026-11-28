using System.Text.Json;
using Companion.Launcher.Core;

internal sealed class CheatsModsForm : Form
{
    private readonly string engineDirectory;
    private NativeModSnapshot saved = null!;
    private readonly Dictionary<string, Control> editors = new();
    private readonly TextBox status = new();
    private readonly Button apply;
    private readonly Button revert;
    private bool syncing;
    // Language tab: its own draft, applied with the rest (the iog.languages package).
    private readonly ComboBox language = new();
    private readonly Label languageRoms = new();
    private readonly Dictionary<string, string> pickedRoms = new();
    private NativeModSettings.LanguageState savedLanguage = new("original", Array.Empty<NativeModSettings.LanguageRom>());
    internal const string LanguageTab = "Language";
    private static readonly Color Background = ColorTranslator.FromHtml("#101A23");
    private static readonly Color Surface = ColorTranslator.FromHtml("#1B2B37");
    private static readonly Color Accent = ColorTranslator.FromHtml("#D7B46A");
    private static readonly Color TextColor = ColorTranslator.FromHtml("#F2EBDD");
    private static readonly Color Muted = ColorTranslator.FromHtml("#A7B5BD");

    internal CheatsModsForm(string engineDirectory, bool openLanguage = false)
    {
        this.engineDirectory = Path.GetFullPath(engineDirectory);
        Text = "Illusion of Gaia · Cheats and Mods"; BackColor = Background; ForeColor = TextColor;
        Font = new Font("Segoe UI", 11); AutoScaleMode = AutoScaleMode.Dpi;
        ClientSize = new Size(900, 790); MinimumSize = new Size(820, 710); StartPosition = FormStartPosition.CenterParent;
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 4, Padding = new Padding(28, 20, 28, 20) };
        layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 96)); layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 74)); layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 50)); Controls.Add(layout);
        var heading = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 2, Margin = Padding.Empty };
        heading.RowStyles.Add(new RowStyle(SizeType.Absolute, 42)); heading.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        heading.Controls.Add(Label("Cheats and Mods", 24, Accent, FontStyle.Bold), 0, 0);
        heading.Controls.Add(Label("Cheats disable local achievement eligibility for the session. Open Convenience for hold-to-run and item controls.", 10, Muted), 0, 1);
        layout.Controls.Add(heading, 0, 0);
        var tabs = new TabControl {
            Dock = DockStyle.Fill, Font = new Font("Segoe UI", 11),
            DrawMode = TabDrawMode.OwnerDrawFixed, SizeMode = TabSizeMode.Fixed,
            ItemSize = new Size(200, 48), Padding = new Point(20, 10),
            AccessibleName = "Cheats and convenience sections"
        };
        tabs.DrawItem += (_, e) => DrawSectionTab(tabs, e);
        tabs.SelectedIndexChanged += (_, _) => tabs.Invalidate();
        tabs.GotFocus += (_, _) => tabs.Invalidate();
        tabs.LostFocus += (_, _) => tabs.Invalidate();
        foreach (var section in NativeModSettings.Fields.Select(x => x.Option.Section).Distinct()) {
            var tab = new TabPage(section) { BackColor = Background, ForeColor = TextColor, Padding = new Padding(12) };
            var rows = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, ColumnCount = 2, Margin = Padding.Empty };
            rows.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 70)); rows.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 30));
            var scroll = new Panel { Dock = DockStyle.Fill, AutoScroll = true, BackColor = Background }; scroll.Controls.Add(rows); tab.Controls.Add(scroll);
            foreach (var field in NativeModSettings.Fields.Where(x => x.Option.Section == section)) {
                int row = rows.RowCount++; rows.RowStyles.Add(new RowStyle(SizeType.Absolute, string.IsNullOrEmpty(field.Option.Help) ? 58 : 100));
                var description = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 2, Margin = new Padding(0, 0, 16, 10) };
                description.RowStyles.Add(new RowStyle(SizeType.Absolute, 28)); description.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
                description.Controls.Add(Label(field.Option.Label, 11, TextColor, FontStyle.Bold), 0, 0);
                description.Controls.Add(Label(field.Option.Help, 9, Muted), 0, 1); rows.Controls.Add(description, 0, row);
                Control editor;
                if (field.Option.Kind == OptionKind.Boolean) {
                    var check = new CheckBox { Text = "Enabled", AutoSize = true, ForeColor = TextColor, Margin = new Padding(4, 5, 0, 0) };
                    check.CheckedChanged += (_, _) => RefreshDraft(); editor = check;
                } else if (field.Option.Kind == OptionKind.Integer) {
                    var number = new NumericUpDown { Minimum = field.Option.Minimum ?? 0, Maximum = field.Option.Maximum ?? 999, Width = 174, BackColor = Surface, ForeColor = TextColor, BorderStyle = BorderStyle.FixedSingle, Margin = new Padding(0, 4, 0, 0) };
                    number.ValueChanged += (_, _) => RefreshDraft(); editor = number;
                } else {
                    var choice = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Width = 206, FlatStyle = FlatStyle.Flat, BackColor = Surface, ForeColor = TextColor, Margin = new Padding(0, 4, 0, 0) };
                    foreach (var item in field.Option.Choices!) choice.Items.Add(new Choice(item));
                    choice.SelectedIndexChanged += (_, _) => RefreshDraft(); editor = choice;
                }
                editor.Name = field.Option.Id; editor.AccessibleName = field.Option.Label; editors[field.Option.Id] = editor; rows.Controls.Add(editor, 1, row);
            }
            tabs.TabPages.Add(tab);
        }
        tabs.TabPages.Add(BuildLanguageTab());
        if (openLanguage) tabs.SelectedIndex = tabs.TabCount - 1;
        layout.Controls.Add(tabs, 0, 1);
        status.ReadOnly = true; status.Multiline = true; status.Dock = DockStyle.Fill; status.BorderStyle = BorderStyle.None;
        status.BackColor = Background; status.ForeColor = Muted; status.AccessibleName = "Mods status"; status.Margin = new Padding(0, 12, 0, 8); layout.Controls.Add(status, 0, 2);
        var footer = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.RightToLeft, WrapContents = false };
        var close = Button("Close", Close, 100); apply = Button("Apply changes", Apply, 168, true); revert = Button("Revert", Reload, 112);
        footer.Controls.AddRange(new Control[] { close, apply, revert }); layout.Controls.Add(footer, 0, 3);
        Reload();
    }
    private TabPage BuildLanguageTab()
    {
        var tab = new TabPage(LanguageTab) { BackColor = Background, ForeColor = TextColor, Padding = new Padding(12) };
        var rows = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, ColumnCount = 2, RowCount = 2, Margin = Padding.Empty };
        rows.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 70)); rows.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 30));
        rows.RowStyles.Add(new RowStyle(SizeType.Absolute, 150)); rows.RowStyles.Add(new RowStyle(SizeType.Absolute, 150));
        var scroll = new Panel { Dock = DockStyle.Fill, AutoScroll = true, BackColor = Background }; scroll.Controls.Add(rows); tab.Controls.Add(scroll);
        Control Describe(string title, Control help) {
            var description = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, RowCount = 2, Margin = new Padding(0, 0, 16, 10) };
            description.RowStyles.Add(new RowStyle(SizeType.Absolute, 28)); description.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            description.Controls.Add(Label(title, 11, TextColor, FontStyle.Bold), 0, 0); description.Controls.Add(help, 0, 1); return description;
        }
        rows.Controls.Add(Describe("Game language", Label("Spanish, French and German come from your own copy of the official European release, Illusion of Time " +
            "(Spain, France or Germany). Nothing is included: the game reads the text and font from your ROM, which is checked here and never copied. " +
            "Untranslated lines stay in English. While you play, Ctrl+L switches language.", 9, Muted)), 0, 0);
        language.DropDownStyle = ComboBoxStyle.DropDownList; language.Width = 206; language.FlatStyle = FlatStyle.Flat; language.BackColor = Surface; language.ForeColor = TextColor;
        language.Margin = new Padding(0, 4, 0, 0); language.Name = "language.code"; language.AccessibleName = "Game language";
        language.SelectedIndexChanged += (_, _) => RefreshDraft(); rows.Controls.Add(language, 1, 0);
        languageRoms.Font = new Font("Segoe UI", 9); languageRoms.ForeColor = Muted; languageRoms.Dock = DockStyle.Fill; languageRoms.UseMnemonic = false;
        languageRoms.Margin = Padding.Empty; languageRoms.AccessibleName = "Language ROMs found";
        rows.Controls.Add(Describe("Illusion of Time ROM", languageRoms), 0, 1);
        var choose = Button("Choose Illusion of Time ROM…", ChooseLanguageRom, 260); choose.Margin = new Padding(0, 4, 0, 0); choose.AccessibleName = "Choose Illusion of Time ROM";
        rows.Controls.Add(choose, 1, 1);
        return tab;
    }
    private string SelectedLanguage => language.SelectedItem is LanguageChoice choice ? choice.Code : "original";
    /// <summary>The languages that have a ROM: saved ones, then ROMs chosen in this window and not yet applied.</summary>
    private void ShowLanguages(string select)
    {
        var found = savedLanguage.Found.ToDictionary(x => x.Code, x => x.Path + (x.InLanguagesFolder ? " (languages folder)" : ""));
        foreach (var (code, path) in pickedRoms) found[code] = path + " (not applied yet)";
        bool was = syncing; syncing = true;
        language.Items.Clear(); language.Items.Add(new LanguageChoice("original", "English"));
        foreach (var item in NativeModSettings.Languages.Where(x => found.ContainsKey(x.Code))) language.Items.Add(new LanguageChoice(item.Code, item.Name));
        // A language whose ROM has gone missing stays listed while selected, so it is not silently changed.
        if (select != "original" && !found.ContainsKey(select) && NativeModSettings.Language(select) is { } missing)
            language.Items.Add(new LanguageChoice(missing.Code, missing.Name + " (ROM missing)"));
        language.SelectedItem = language.Items.Cast<LanguageChoice>().First(x => x.Code == select || x.Code == "original" && select == "original");
        syncing = was;
        languageRoms.Text = found.Count == 0
            ? "None yet. Choose your ROM (.sfc or .smc), or put it in the languages folder beside babel-recomp.exe. The game takes it from where it is."
            : string.Join(Environment.NewLine, NativeModSettings.Languages.Where(x => found.ContainsKey(x.Code)).Select(x => x.Name + ": " + found[x.Code]));
    }
    private void ChooseLanguageRom()
    {
        using var dialog = new OpenFileDialog { Title = "Choose your Illusion of Time ROM (Spain, France or Germany)", Filter = "SNES ROM (*.sfc;*.smc)|*.sfc;*.smc|All files (*.*)|*.*", CheckFileExists = true };
        if (dialog.ShowDialog(this) == DialogResult.OK) UseLanguageRom(dialog.FileName);
    }
    /// <summary>Check a ROM the player chose and add its language to the draft (also the test entry point).</summary>
    internal bool UseLanguageRom(string path)
    {
        var check = NativeModSettings.IdentifyLanguageRom(path);
        if (check.Code == null) { Report(check.Message, true); return false; }
        pickedRoms[check.Code] = Path.GetFullPath(path);
        ShowLanguages(check.Code); RefreshDraft();
        Report(check.Message + " Apply changes to play in " + NativeModSettings.Language(check.Code)!.Name + ".");
        return true;
    }
    private bool LanguageDirty => pickedRoms.Count > 0 || SelectedLanguage != savedLanguage.Selected;
    private sealed record LanguageChoice(string Code, string Label) { public override string ToString() => Label; }
    private static void DrawSectionTab(TabControl tabs, DrawItemEventArgs e)
    {
        bool selected = tabs.SelectedIndex == e.Index;
        Color fill = SystemInformation.HighContrast ? (selected ? SystemColors.Highlight : SystemColors.Control) : selected ? Accent : Surface;
        Color ink = SystemInformation.HighContrast ? (selected ? SystemColors.HighlightText : SystemColors.ControlText) : selected ? Background : TextColor;
        using var background = new SolidBrush(SystemInformation.HighContrast ? SystemColors.Control : Background);
        e.Graphics.FillRectangle(background, e.Bounds);
        if (e.Index == tabs.TabCount - 1) {
            // The strip beside the last tab is otherwise the system's light control colour.
            var last = tabs.GetTabRect(e.Index);
            e.Graphics.FillRectangle(background, last.Right, 0, tabs.Width - last.Right, last.Bottom + 2);
        }
        var bounds = Rectangle.Inflate(e.Bounds, -4, -4);
        using var brush = new SolidBrush(fill);
        using var border = new Pen(SystemInformation.HighContrast ? SystemColors.ControlText : selected ? Accent : Muted);
        e.Graphics.FillRectangle(brush, bounds);
        e.Graphics.DrawRectangle(border, bounds.X, bounds.Y, bounds.Width - 1, bounds.Height - 1);
        using var font = new Font(tabs.Font, FontStyle.Bold);
        TextRenderer.DrawText(e.Graphics, tabs.TabPages[e.Index].Text, font, bounds, ink,
            TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine | TextFormatFlags.NoPrefix);
        if (selected && tabs.Focused)
            ControlPaint.DrawFocusRectangle(e.Graphics, Rectangle.Inflate(bounds, -4, -4), ink, fill);
    }
    private static Label Label(string text, float size, Color color, FontStyle style = FontStyle.Regular) => new() { Text = text, Font = new Font("Segoe UI", size, style), ForeColor = color, Dock = DockStyle.Fill, UseMnemonic = false, Margin = Padding.Empty };
    private static Button Button(string text, Action action, int width, bool primary = false) {
        var button = new Button { Text = text, Width = width, Height = 42, FlatStyle = FlatStyle.Flat, BackColor = primary ? Accent : Surface, ForeColor = primary ? Background : TextColor, Font = new Font("Segoe UI", 10, FontStyle.Bold), Margin = new Padding(10, 0, 0, 0), UseMnemonic = false };
        button.FlatAppearance.BorderColor = primary ? Accent : Color.FromArgb(64, 81, 92); button.Click += (_, _) => action(); return button;
    }
    private Dictionary<string, JsonElement> Values() => NativeModSettings.Fields.ToDictionary(field => field.Option.Id, field => editors[field.Option.Id] switch {
        CheckBox check => OptionValue.From(check.Checked), NumericUpDown number => OptionValue.From((int)number.Value),
        ComboBox choice => OptionValue.From(((Choice)choice.SelectedItem!).Item.Value), _ => throw new InvalidOperationException("Unknown mod control.") });
    private void RefreshDraft() {
        if (syncing || saved == null) return;
        var current = Values(); bool dirty = LanguageDirty || current.Any(pair => pair.Value.GetRawText() != saved.Values[pair.Key].GetRawText());
        apply.Enabled = revert.Enabled = dirty;
        if (dirty) Report("Unapplied changes. Apply to use them on the next launch, or Revert to reload native settings.");
    }
    private void Report(string text, bool error = false) { status.Text = text; status.ForeColor = error ? Color.FromArgb(255,166,162) : Muted; }
    private void Reload() {
        try {
            var next = NativeModSettings.Read(engineDirectory); syncing = true;
            // Picture is chosen on the Display page; a control the current picture ignores is shown but not editable.
            bool wideView = true;
            try { wideView = NativeModSettings.ReadDisplay(engineDirectory).WideView; }
            catch (Exception error) when (error is IOException or InvalidDataException or UnauthorizedAccessException or ArgumentException) { }
            foreach (var field in NativeModSettings.Fields) {
                var editor = editors[field.Option.Id]; var value = next.Values[field.Option.Id];
                editor.Enabled = next.Available.Contains(field.Option.Id) && NativeModSettings.AppliesToPicture(field.Option.Id, wideView);
                if (editor is CheckBox check) check.Checked = value.GetBoolean();
                else if (editor is NumericUpDown number) number.Value = value.GetInt32();
                else if (editor is ComboBox choice) choice.SelectedItem = choice.Items.Cast<Choice>().Single(item => item.Item.Value == value.GetString());
            }
            savedLanguage = NativeModSettings.ReadLanguage(engineDirectory); pickedRoms.Clear(); ShowLanguages(savedLanguage.Selected);
            saved = next; syncing = false; apply.Enabled = revert.Enabled = false;
            Report((next.Available.Count == NativeModSettings.Fields.Count ? "Native mod settings loaded. Changes apply on the next launch. All 50 Red Jewels remains an in-game action." :
                "Some controls are unavailable in this engine's catalog. Build its matching engine and catalog to use those features.") +
                (wideView ? "" : " Status display at the screen edges works in Wide view only; Picture is on the Display page."));
        } catch (Exception ex) { syncing = false; apply.Enabled = false; Report(ex.Message, true); }
    }
    // Window tests (tests/ui --language) drive the form without showing it.
    internal string StatusText => status.Text;
    internal IReadOnlyList<string> LanguageChoices => language.Items.Cast<LanguageChoice>().Select(x => x.Label).ToList();
    internal void SelectLanguage(string code) => language.SelectedItem = language.Items.Cast<LanguageChoice>().First(x => x.Code == code);
    internal void ApplyChanges() => Apply();
    private void Apply() {
        try {
            var languageChanged = LanguageDirty;
            // Refuse a language without its ROM before anything is written.
            if (languageChanged) NativeModSettings.CheckLanguage(engineDirectory, SelectedLanguage, pickedRoms);
            NativeModSettings.Apply(engineDirectory, Values(), saved.Revision);
            if (languageChanged) NativeModSettings.ApplyLanguage(engineDirectory, SelectedLanguage, pickedRoms);
            Reload(); Report("Native mod settings saved. Launch the game to use them. Existing saves, soundtrack and button bindings were preserved."); }
        catch (Exception ex) { Report(ex.Message, true); }
    }
    private sealed record Choice(ChoiceItem Item) { public override string ToString() => Item.Label; }
}
