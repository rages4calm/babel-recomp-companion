using System.Text.Json;
using Companion.Launcher.Core;

if (args.Contains("--engine")) { await EngineSmoke.Run(args); return; }
if (args.Contains("--activation")) { ActivationTests.Run(); return; }
if (args.Contains("--soundtrack-tests")) { await SoundtrackTests.RunAsync(); return; }
if (args.Length == 3 && args[0] == "--import-soundtrack") {
    var result = await SoundtrackService.ImportAsync(args[1], args[2]);
    var verified = await SoundtrackService.InspectInstalledAsync(result.PackDirectory);
    if (!verified.IsValid || result.CatalogId != "jud6ment-orchestra" || result.TrackCount != 28)
        throw new InvalidDataException("Owner pack did not match the expected verified JUD6MENT catalog.");
    SoundtrackActivation.Enable(args[2], result.PackDirectory);
    Console.WriteLine(JsonSerializer.Serialize(new { passed = true, result, verified = verified.IsValid,
        enabled = SoundtrackActivation.Read(args[2]).Enabled }));
    return;
}

var root = Path.Combine(Path.GetTempPath(), "GaiaCompanion-tests-" + Guid.NewGuid().ToString("N"));
Directory.CreateDirectory(root);
int checks = 0;
void Check(bool yes, string name) { if (!yes) throw new Exception(name); checks++; }
void Throws<T>(Action action, string name) where T : Exception { try { action(); } catch (T) { checks++; return; } throw new Exception(name); }
try {
    var adapter = new GameAdapter(Path.Combine(root, "preferences")); var profile = adapter.Profiles.Single();
    var exeDir = Path.Combine(root, "game with spaces"); Directory.CreateDirectory(exeDir);
    var exe = Path.Combine(exeDir, "babel-recomp.exe"); File.WriteAllText(exe, "synthetic engine; never executed");
    var config = Path.Combine(exeDir, "config.ini");
    File.WriteAllText(config, "# keep comment\r\n[Graphics]\r\nWidescreen = 1 # native view\r\nVSync = 1\r\nMode7Enabled = 0\r\nEnhancedMode7 = 1\r\nMode7Scale = 16\r\nMode7Supersample = 2\r\nCustom = untouched\r\n[Sound]\r\nVolume = 37\r\n[KeyMap]\r\nControls = custom mapping\r\n[Video]\r\nVsync = 1\r\nLinearFilter = 1\r\n[Emulation]\r\nVsync = 0\r\n");
    var before = File.ReadAllBytes(config);
    var initial = adapter.ReadSettings(profile); initial.Values["engine.path"] = OptionValue.From(exe);
    adapter.ApplySettings(profile, initial.Values, initial.Revision);
    Check(before.SequenceEqual(File.ReadAllBytes(config)), "source selection cannot overwrite native config");
    var native = adapter.ReadSettings(profile);
    Check(native.Values["video.widescreen"].GetBoolean(), "read native widescreen");
    Check(native.Values["video.vsync"].GetString() == "0", "read last native Video alias");
    Check(native.Values["video.filter"].GetBoolean(), "read filtering alias");
    Check(native.Values["audio.volume"].GetInt32() == 37, "read authoritative mixer");
    Check(!native.Values["video.mode7"].GetBoolean(), "shared Mode7Enabled controls visible setting rather than legacy EnhancedMode7");
    native.Values["video.mode7"] = OptionValue.From(true);
    native.Values["audio.volume"] = OptionValue.From(62); native.Values["video.vsync"] = OptionValue.From("1");
    native.Values["video.filter"] = OptionValue.From(false);
    adapter.ApplySettings(profile, native.Values, native.Revision);
    var text = File.ReadAllText(config);
    Check(text.Contains("Custom = untouched\r\n"), "preserve unknown key and CRLF");
    Check(text.Contains("Controls = custom mapping"), "preserve control bindings");
    Check(text.Contains("Widescreen = 1 # native view"), "preserve untouched inline comment");
    Check(text.Contains("Vsync = 1") && text.Contains("LinearFilter = 0"), "write effective aliases");
    Check(adapter.ReadSettings(profile).Values["audio.volume"].GetInt32() == 62, "read applied native setting");
    Check(text.Contains("Mode7Enabled = 1") && text.Contains("EnhancedMode7 = 1"), "apply shared Mode 7 without changing legacy HD-pack setting");
    Check(text.Contains("Mode7Scale = 16") && text.Contains("Mode7Supersample = 2"), "Mode 7 toggle preserves quality and sampling");
    File.WriteAllText(config, text.Replace("Vsync = 1", "Vsync = adaptive"));
    Check(adapter.ReadSettings(profile).Values["video.vsync"].GetString() == "adaptive", "read adaptive VSync");
    File.WriteAllText(config, text.Replace("Vsync = 1", "Vsync = 2"));
    Check(adapter.ReadSettings(profile).Values["video.vsync"].GetString() == "adaptive", "normalize numeric adaptive VSync");
    File.WriteAllText(config, text.Replace("Vsync = 1", "Vsync = true"));
    Check(adapter.ReadSettings(profile).Values["video.vsync"].GetString() == "1", "normalize legacy boolean VSync");
    var rollback = adapter.ReadSettings(profile); var rollbackBytes = File.ReadAllBytes(config);
    rollback.Values["audio.volume"] = OptionValue.From(75);
    Throws<IOException>(() => NativeSettings.Apply(adapter.ReadSettings(profile), rollback.Values, () => { }, () => throw new IOException("synthetic failed commit")), "rollback on preference commit failure");
    Check(rollbackBytes.SequenceEqual(File.ReadAllBytes(config)), "rollback restores exact native bytes");
    var stale = adapter.ReadSettings(profile); File.AppendAllText(config, "# external edit\r\n"); var edited = File.ReadAllBytes(config);
    stale.Values["audio.volume"] = OptionValue.From(12);
    Throws<SettingsConflictException>(() => adapter.ApplySettings(profile, stale.Values, stale.Revision), "reject stale native write");
    Check(edited.SequenceEqual(File.ReadAllBytes(config)), "stale write preserves external edit");
    var bad = Path.Combine(root, "bad.sfc"); File.WriteAllBytes(bad, new byte[2097152]);
    Check(!GameAdapter.VerifyRom(bad), "reject wrong same-size ROM");
    File.WriteAllBytes(bad, new byte[2097152 + 512]); Check(!GameAdapter.VerifyRom(bad), "reject headered wrong ROM");
    var values = adapter.ReadSettings(profile).Values; values["rom.path"] = OptionValue.From(bad);
    Check(!adapter.CheckReady(profile, values).Ready, "wrong ROM disables Play");
    Throws<InvalidOperationException>(() => adapter.BuildLaunchPlan(profile, values, false), "launch validates readiness");
    Throws<NotSupportedException>(() => adapter.BuildLaunchPlan(profile, values, true), "reject unqualified Resume");
    if (args.Length == 2 && args[0] == "--rom") {
        var rom = Path.GetFullPath(args[1]); Check(GameAdapter.VerifyRom(rom), "verify owner ROM read only");
        values["rom.path"] = OptionValue.From(rom); values["launch.mode"] = OptionValue.From("game");
        var direct = adapter.BuildLaunchPlan(profile, values, false);
        Check(direct.Executable == exe && direct.WorkingDirectory == exeDir, "launch anchors native save paths");
        Check(direct.Arguments.SequenceEqual(new[] { "--no-launcher", "--rom", rom }), "structured direct launch arguments");
        values["launch.mode"] = OptionValue.From("babel");
        Check(adapter.BuildLaunchPlan(profile, values, false).Arguments[0] == "--launcher", "retain Babel management path");
        var headered = Path.Combine(root, "owner-headered.sfc");
        using (var target = File.Create(headered)) { target.Write(new byte[512]); using var input = File.OpenRead(rom); input.CopyTo(target); }
        Check(GameAdapter.VerifyRom(headered), "verify header normalization");
    }
    File.WriteAllText(config, "[Sound]\nVolume = 1\nVolume = 2\n");
    Throws<InvalidDataException>(() => adapter.ReadSettings(profile), "duplicate key fails closed");
    File.WriteAllText(config, "[Sound]\nVolume = broken\n");
    Throws<InvalidDataException>(() => adapter.ReadSettings(profile), "unreadable native value fails closed");
    var freshDir = Path.Combine(root, "uninitialized-game"); Directory.CreateDirectory(freshDir);
    var freshExe = Path.Combine(freshDir, "babel-recomp.exe"); File.WriteAllText(freshExe, "synthetic only");
    var freshAdapter = new GameAdapter(Path.Combine(root, "fresh-preferences")); var fresh = freshAdapter.ReadSettings(profile);
    fresh.Values["engine.path"] = OptionValue.From(freshExe); freshAdapter.ApplySettings(profile, fresh.Values, fresh.Revision);
    Check(!File.Exists(Path.Combine(freshDir, "config.ini")), "path selection leaves engine defaults uninitialized");
    fresh = freshAdapter.ReadSettings(profile); fresh.Values["audio.volume"] = OptionValue.From(65);
    Throws<InvalidOperationException>(() => freshAdapter.ApplySettings(profile, fresh.Values, fresh.Revision), "native edits require complete engine initialization");
    Check(!File.Exists(Path.Combine(freshDir, "config.ini")), "blocked native edit cannot create partial config");
    Console.WriteLine(JsonSerializer.Serialize(new { passed = true, checks, synthetic = true, gameLaunched = false }));
} finally { Directory.Delete(root, true); }
