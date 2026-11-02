using System.Security.Cryptography;
using System.Text.Json;
using Companion.Launcher.Core;

// UI and process lifetime come from the pinned shared packages.
public sealed class GameAdapter : JsonGameAdapterBase
{
    private static string FindProject()
    {
        for (var dir = new DirectoryInfo(AppContext.BaseDirectory); dir != null; dir = dir.Parent)
            if (File.Exists(Path.Combine(dir.FullName, "rom_identity.txt"))) return dir.FullName;
        return AppContext.BaseDirectory;
    }
    private static readonly string Project = FindProject();
    private static readonly string EngineName = OperatingSystem.IsWindows() ? "babel-recomp.exe" : "babel-recomp";
    private static readonly string DefaultEngine = File.Exists(Path.Combine(AppContext.BaseDirectory, EngineName))
        ? Path.Combine(AppContext.BaseDirectory, EngineName) : Path.Combine(Project, "build", EngineName);
    private static readonly GameDefinition Game = new(
        "illusion-of-gaia", "Illusion of Gaia Companion",
        "Babel Recomp by mr0ta · Companion edition in development",
        new[] {
            new OptionDefinition("engine.path", "Game", "Babel executable", OptionKind.Text,
                OptionValue.From(DefaultEngine),
                "Select the built Babel executable. Its folder retains saves, mods and native settings."),
            new OptionDefinition("rom.path", "Game", "Original USA ROM", OptionKind.Text,
                OptionValue.From(Path.Combine(Project, "Illusion of Gaia (USA).sfc")),
                "Your own USA ROM; a 512-byte copier header is accepted. Nothing is copied or downloaded."),
            new OptionDefinition("launch.mode", "Game", "Launch destination", OptionKind.Choice, OptionValue.From("game"),
                "Babel tools retain mod management and full remapping. In game: Esc / LT+R3 settings; I / LT+L3 companion screen.",
                Choices: new[] { new ChoiceItem("game", "Play directly"), new ChoiceItem("babel", "Babel tools and remapping") })
        }.Concat(NativeSettings.Options).ToArray(),
        Branding: new("#101A23", "#1B2B37", "#D7B46A", "#F2EBDD", "#A7B5BD"));

    public GameAdapter(string? dataRoot = null) : base(Game,
        new[] { new ProfileDescriptor("original", "Original USA", "original") }, dataRoot ??
        Environment.GetEnvironmentVariable("COMPANION_DATA_ROOT") ?? CompanionDataPaths.DesktopRoot()) { }

    public override SettingsSnapshot ReadSettings(ProfileDescriptor profile)
    {
        var paths = base.ReadSettings(profile);
        foreach (var option in Definition.Options.Where(x => !NativeSettings.IsNative(x.Id)))
            paths.Values.TryAdd(option.Id, option.DefaultValue.Clone());
        return NativeSettings.Read(paths);
    }

    public override IReadOnlyList<string> ValidateCustom(ProfileDescriptor profile, IReadOnlyDictionary<string, JsonElement> values) =>
        new[] { "engine.path", "rom.path" }.Where(key => !Path.IsPathFullyQualified(values[key].GetString() ?? ""))
            .Select(key => $"{key}: enter an absolute path.").ToArray();

    public override void ApplySettings(ProfileDescriptor profile, IReadOnlyDictionary<string, JsonElement> values, string expectedRevision)
    {
        var errors = OptionValidation.Validate(Definition, values).Concat(ValidateCustom(profile, values)).ToArray();
        if (errors.Length != 0) throw new SettingsValidationException(errors);
        Directory.CreateDirectory(ProfileDirectory(profile));
        using var gate = new FileStream(Path.Combine(ProfileDirectory(profile), "native-settings.lock"), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        var current = ReadSettings(profile);
        if (current.Revision != expectedRevision) throw new SettingsConflictException();
        var stored = base.ReadSettings(profile);
        var paths = stored.Values.Where(x => !NativeSettings.IsNative(x.Key)).ToDictionary(x => x.Key, x => x.Value.Clone());
        foreach (var pair in values.Where(x => !NativeSettings.IsNative(x.Key))) paths[pair.Key] = pair.Value.Clone();
        // Select the new source before reading its settings; do not overwrite it with old drafts.
        if (values["engine.path"].GetString() != current.Values["engine.path"].GetString()) {
            NativeSettings.Read(new(new(paths), stored.Revision));
            Store(profile).Write(paths, stored.Revision); return;
        }
        NativeSettings.Apply(current, values,
            () => { if (ReadSettings(profile).Revision != expectedRevision) throw new SettingsConflictException(); },
            () => Store(profile).Write(paths, stored.Revision));
    }

    public override Readiness CheckReady(ProfileDescriptor profile, IReadOnlyDictionary<string, JsonElement> values)
    {
        var executable = values["engine.path"].GetString() ?? ""; var rom = values["rom.path"].GetString() ?? "";
        if (!Path.IsPathFullyQualified(executable) || !File.Exists(executable)) return new(false, "Select the Babel executable, then Apply.");
        if (!Path.IsPathFullyQualified(rom) || !File.Exists(rom)) return new(false, "Select your original USA ROM, then Apply.");
        try { return VerifyRom(rom) ? new(true, "USA ROM verified · Babel runtime; native coverage under audit.") : new(false, "ROM does not match the supported USA revision."); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { return new(false, "Cannot verify ROM: " + ex.Message); }
    }
    public static bool VerifyRom(string path)
    {
        using var stream = File.OpenRead(path);
        if (stream.Length == 2097152 + 512) stream.Position = 512; else if (stream.Length != 2097152) return false;
        return Convert.ToHexString(SHA256.HashData(stream)).Equals("32ADC048FD89228A4310C03DF243E83DE7D436CDB2460B4CC83ADE20D359B2BD", StringComparison.Ordinal);
    }
    public override LaunchPlan BuildLaunchPlan(ProfileDescriptor profile, IReadOnlyDictionary<string, JsonElement> values, bool resume)
    {
        if (resume) throw new NotSupportedException("Resume is not qualified for this integration.");
        var ready = CheckReady(profile, values); if (!ready.Ready) throw new InvalidOperationException(ready.Summary);
        var executable = values["engine.path"].GetString()!;
        return new(executable, Path.GetDirectoryName(executable)!, new[] {
            values["launch.mode"].GetString() == "babel" ? "--launcher" : "--no-launcher", "--rom", values["rom.path"].GetString()! });
    }
}
