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
    private const string AchievementEdition = "stock-companion";
    private const string PromptsId = "input.prompts", KeysId = "input.keys", PictureId = "video.picture", ScalingId = "video.scaling";
    // Display reads top to bottom as: where it shows, what it shows, how it is enlarged, then the rest.
    private static IEnumerable<OptionDefinition> OrderedDisplay()
    {
        var native = NativeSettings.Options.ToList();
        var mode = native.Single(x => x.Id == "video.fullscreen");
        yield return mode;
        yield return new OptionDefinition(PictureId, "Display", "Picture", OptionKind.Choice, OptionValue.From("wide"),
            "Pick one; they do not combine. Wide view shows more of each area around the original picture, with square pixels and a sharp status display. Classic 16:9 is the older, simpler widescreen. Original 4:3 is the SNES picture. Takes effect the next time the game starts.",
            Choices: new[] { new ChoiceItem("wide", "Wide view (recommended)"), new ChoiceItem("classic", "Classic 16:9"), new ChoiceItem("original", "Original 4:3") });
        yield return new OptionDefinition(ScalingId, "Display", "Scaling", OptionKind.Choice, OptionValue.From("sharp"),
            "How the picture is enlarged to your screen. Works with every Picture choice. Sharp keeps each pixel a clean square. Smooth edges redraws curves and diagonals at screen resolution. Soft blurs. Plain is unfiltered and can look uneven at odd window sizes.",
            Choices: new[] { new ChoiceItem("sharp", "Sharp pixels (recommended)"), new ChoiceItem("smooth", "Smooth edges (xBR)"), new ChoiceItem("soft", "Soft (blurred)"), new ChoiceItem("plain", "Plain") });
        foreach (var option in native.Where(x => x != mode)) yield return option;
    }
    private static readonly GameDefinition Game = new(
        "illusion-of-gaia", "Illusion of Gaia Companion",
        "Babel Recomp by mr0ta · Companion edition in development",
        new[] {
            new OptionDefinition("engine.path", "Game", "Game program", OptionKind.Text,
                OptionValue.From(DefaultEngine),
                "The full path to babel-recomp.exe. It is already set when the launcher sits in the same folder. Saves, mods and settings live in that folder."),
            new OptionDefinition("rom.path", "Game", "Original USA ROM", OptionKind.Text,
                OptionValue.From(Path.Combine(Project, "Illusion of Gaia (USA).sfc")),
                "The full path to your own Illusion of Gaia (USA) ROM, .sfc or .smc. It is checked, never copied or uploaded."),
            new OptionDefinition("launch.mode", "Game", "When you press Play", OptionKind.Choice, OptionValue.From("game"),
                "Start the game is the normal choice. The setup screen is the game's own menu for changing keys and controller buttons and for the language and randomizer mods; start the game from there afterwards.",
                Choices: new[] { new ChoiceItem("game", "Start the game"), new ChoiceItem("babel", "Open the setup screen (remapping)") })
        }.Concat(OrderedDisplay()).Concat(new[] {
            new OptionDefinition(PromptsId, "Input", "Button prompts", OptionKind.Choice, OptionValue.From("auto"),
                "Which button names the game shows. Auto uses SNES letters and colours on an SNES-style pad (8BitDo, Switch Online) and Xbox letters otherwise. The same setting is in the in-game settings.",
                Choices: new[] { new ChoiceItem("auto", "Auto"), new ChoiceItem("snes", "SNES (classic)"), new ChoiceItem("xbox", "Xbox") }),
            new OptionDefinition(KeysId, "Input", "Keyboard shortcuts", OptionKind.Choice, OptionValue.From("list"),
                "Esc settings (achievements are there) · Enter (Start) area map · F1-F10 load state, Shift+F1-F10 save state · F11 all save states · F12 rewind · Tab fast forward · P pause · Alt+Enter fullscreen · PrtSc screenshot. These are the defaults. To change keys, controller buttons and shortcuts, use Controls in the left column.",
                Choices: new[] { new ChoiceItem("list", "Reference") })
        }).ToArray(),
        HasAchievements: true,
        Branding: new("#101A23", "#1B2B37", "#D7B46A", "#F2EBDD", "#A7B5BD"));

    public GameAdapter(string? dataRoot = null) : base(Game,
        new[] { new ProfileDescriptor("original", "Original USA", "original") }, dataRoot ??
        Environment.GetEnvironmentVariable("COMPANION_DATA_ROOT") ?? CompanionDataPaths.DesktopRoot()) { }

    /// <summary>This launcher's own game program, when the launcher sits in an installed release folder.</summary>
    internal static string? OwnEngine(string? baseDirectory = null)
    {
        var own = Path.Combine(baseDirectory ?? AppContext.BaseDirectory, EngineName);
        return File.Exists(own) ? Path.GetFullPath(own) : null;
    }
    internal string? OwnEngineOverride { get; init; }   // tests: stands in for the launcher's own folder

    /// <summary>
    /// The saved launcher preferences. A saved game program that is missing, not a full path, or no longer
    /// exists (an install folder deleted after a new one was unzipped beside it) is replaced by the
    /// babel-recomp.exe next to this launcher, and that is saved, so Play works again. The ROM path is kept.
    /// </summary>
    private SettingsSnapshot Stored(ProfileDescriptor profile)
    {
        var stored = base.ReadSettings(profile);
        var own = OwnEngineOverride ?? OwnEngine();
        if (own == null) return stored;
        var saved = stored.Values.TryGetValue("engine.path", out var value) && value.ValueKind == JsonValueKind.String ? value.GetString() : null;
        if (saved == null && !stored.Values.ContainsKey("engine.path")) return stored;   // never chosen: the default already is this folder's
        if (saved is { Length: > 0 } && Path.IsPathFullyQualified(saved) && File.Exists(saved)) return stored;
        var repaired = stored.Values.ToDictionary(pair => pair.Key, pair => pair.Value.Clone());
        repaired["engine.path"] = OptionValue.From(own);
        try { Store(profile).Write(repaired, stored.Revision); return base.ReadSettings(profile); }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException) {   // includes SettingsConflictException
            return new(repaired, stored.Revision);   // use it now; saving is tried again next start
        }
    }

    public override SettingsSnapshot ReadSettings(ProfileDescriptor profile)
    {
        var paths = Stored(profile);
        foreach (var option in Definition.Options.Where(x => !NativeSettings.IsNative(x.Id)))
            paths.Values.TryAdd(option.Id, option.DefaultValue.Clone());
        var read = NativeSettings.Read(paths);
        // The game's own mod state holds the prompt style; the launcher copy only mirrors it.
        try { read.Values[PromptsId] = OptionValue.From(NativeModSettings.ReadPrompts(Path.GetDirectoryName(read.Values["engine.path"].GetString()!)!)); }
        catch (Exception error) when (error is IOException or InvalidDataException or UnauthorizedAccessException or ArgumentException) { }
        read.Values[KeysId] = OptionValue.From("list");
        // Picture and Scaling each fold one game setting and one mod selection into a single choice.
        var display = new NativeModSettings.DisplayState(true, true, "sharp");
        try { display = NativeModSettings.ReadDisplay(Path.GetDirectoryName(read.Values["engine.path"].GetString()!)!); }
        catch (Exception error) when (error is IOException or InvalidDataException or UnauthorizedAccessException or ArgumentException) { }
        read.Values[PictureId] = OptionValue.From(display.WideView ? "wide" : read.Values["video.widescreen"].GetBoolean() ? "classic" : "original");
        read.Values[ScalingId] = OptionValue.From(display.Hd ? (display.Filter == "smooth" ? "smooth" : "sharp") : read.Values["video.filter"].GetBoolean() ? "soft" : "plain");
        return read;
    }

    public override AchievementSnapshot ReadAchievements(ProfileDescriptor profile)
    {
        var preferences = Stored(profile);
        var executable = DefaultEngine;
        if (preferences.Values.TryGetValue("engine.path", out var configured))
        {
            if (configured.ValueKind != JsonValueKind.String || configured.GetString() is not { } path ||
                !Path.IsPathFullyQualified(path) || Path.GetFileName(path).Length == 0 || Directory.Exists(path))
                throw new InvalidDataException("Set the game program on the Game page to view achievements.");
            executable = path;
        }
        var catalog = Path.Combine(AppContext.BaseDirectory, "assets", "achievements", "catalog.json");
        var progress = Path.Combine(Path.GetDirectoryName(executable)!, "UserData", "Achievements",
            Definition.Id, AchievementEdition, "unseeded", "progress.json");
        return AchievementJsonReader.Read(catalog, progress, Definition.Id, AchievementEdition);
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
        var prompts = values[PromptsId].GetString()!;
        var picture = values[PictureId].GetString()!; var scaling = values[ScalingId].GetString()!;
        var promptsChanged = prompts != current.Values[PromptsId].GetString();
        var displayChanged = picture != current.Values[PictureId].GetString() || scaling != current.Values[ScalingId].GetString();
        var engineDirectory = Path.GetDirectoryName(values["engine.path"].GetString()!)!;
        if ((promptsChanged || displayChanged) && NativeModSettings.IsEngineRunning(values["engine.path"].GetString()!))
            throw new InvalidOperationException("Close the game before changing Picture, Scaling or Button prompts here. While you play, the in-game settings can change HD scaling and Button prompts; Picture changes only here.");
        // The two hidden game settings follow the visible choices; an unchanged choice leaves them alone.
        var effective = values.ToDictionary(pair => pair.Key, pair => pair.Value.Clone());
        effective["video.widescreen"] = picture == current.Values[PictureId].GetString() ? current.Values["video.widescreen"].Clone() : OptionValue.From(picture != "original");
        effective["video.filter"] = scaling == current.Values[ScalingId].GetString() ? current.Values["video.filter"].Clone() : OptionValue.From(scaling == "soft");
        NativeSettings.Apply(current, effective,
            () => { if (ReadSettings(profile).Revision != expectedRevision) throw new SettingsConflictException(); },
            () => Store(profile).Write(paths, stored.Revision));
        if (promptsChanged) NativeModSettings.ApplyPrompts(engineDirectory, prompts);
        if (displayChanged) NativeModSettings.ApplyDisplay(engineDirectory, new(picture == "wide", scaling is "sharp" or "smooth", scaling == "smooth" ? "smooth" : "sharp"));
    }

    public override Readiness CheckReady(ProfileDescriptor profile, IReadOnlyDictionary<string, JsonElement> values)
    {
        var executable = values["engine.path"].GetString() ?? ""; var rom = values["rom.path"].GetString() ?? "";
        if (!Path.IsPathFullyQualified(executable) || !File.Exists(executable)) return new(false, "Set the game program on the Game page, then Apply.");
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
