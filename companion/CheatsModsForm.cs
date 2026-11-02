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
    private static readonly Color Background = ColorTranslator.FromHtml("#101A23");
    private static readonly Color Surface = ColorTranslator.FromHtml("#1B2B37");
    private static readonly Color Accent = ColorTranslator.FromHtml("#D7B46A");
    private static readonly Color TextColor = ColorTranslator.FromHtml("#F2EBDD");
    private static readonly Color Muted = ColorTranslator.FromHtml("#A7B5BD");

    internal CheatsModsForm(string engineDirectory)
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
        heading.Controls.Add(Label("Cheats change gameplay and disable local achievement eligibility for the session. Movement and running keep their existing settings.", 10, Muted), 0, 1);
        layout.Controls.Add(heading, 0, 0);
        var tabs = new TabControl { Dock = DockStyle.Fill, Font = new Font("Segoe UI", 11) };
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
        layout.Controls.Add(tabs, 0, 1);
        status.ReadOnly = true; status.Multiline = true; status.Dock = DockStyle.Fill; status.BorderStyle = BorderStyle.None;
        status.BackColor = Background; status.ForeColor = Muted; status.AccessibleName = "Mods status"; status.Margin = new Padding(0, 12, 0, 8); layout.Controls.Add(status, 0, 2);
        var footer = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.RightToLeft, WrapContents = false };
        var close = Button("Close", Close, 100); apply = Button("Apply changes", Apply, 168, true); revert = Button("Revert", Reload, 112);
        footer.Controls.AddRange(new Control[] { close, apply, revert }); layout.Controls.Add(footer, 0, 3);
        Reload();
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
        var current = Values(); bool dirty = current.Any(pair => pair.Value.GetRawText() != saved.Values[pair.Key].GetRawText());
        apply.Enabled = revert.Enabled = dirty;
        if (dirty) Report("Unapplied changes. Apply to use them on the next launch, or Revert to reload native settings.");
    }
    private void Report(string text, bool error = false) { status.Text = text; status.ForeColor = error ? Color.FromArgb(255,166,162) : Muted; }
    private void Reload() {
        try {
            var next = NativeModSettings.Read(engineDirectory); syncing = true;
            foreach (var field in NativeModSettings.Fields) {
                var editor = editors[field.Option.Id]; var value = next.Values[field.Option.Id]; editor.Enabled = next.Available.Contains(field.Option.Id);
                if (editor is CheckBox check) check.Checked = value.GetBoolean();
                else if (editor is NumericUpDown number) number.Value = value.GetInt32();
                else if (editor is ComboBox choice) choice.SelectedItem = choice.Items.Cast<Choice>().Single(item => item.Item.Value == value.GetString());
            }
            saved = next; syncing = false; apply.Enabled = revert.Enabled = false;
            Report(next.Available.Count == NativeModSettings.Fields.Count ? "Native mod settings loaded. Changes apply on the next launch. All 50 Red Jewels remains an in-game action." :
                "Some controls are unavailable in this engine's catalog. Build its matching engine and catalog to use those features.");
        } catch (Exception ex) { syncing = false; apply.Enabled = false; Report(ex.Message, true); }
    }
    private void Apply() {
        try { NativeModSettings.Apply(engineDirectory, Values(), saved.Revision); Reload(); Report("Native mod settings saved. Launch the game to use them. Existing saves, soundtrack and movement settings were preserved."); }
        catch (Exception ex) { Report(ex.Message, true); }
    }
    private sealed record Choice(ChoiceItem Item) { public override string ToString() => Item.Label; }
}
