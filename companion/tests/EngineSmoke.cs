using System.Diagnostics;
using System.Security.Cryptography;
using System.Text.Json;
using Companion.Launcher.Core;

internal static class EngineSmoke
{
    internal static async Task Run(string[] args)
    {
        string Value(string flag) { var i = Array.IndexOf(args, flag); if (i < 0 || i + 1 >= args.Length) throw new ArgumentException("Missing " + flag); return Path.GetFullPath(args[i + 1]); }
        var source = Value("--engine"); var rom = Value("--rom"); var output = Value("--output");
        if (Directory.Exists(output) || File.Exists(output)) throw new IOException("Engine smoke requires a fresh output directory.");
        if (!GameAdapter.VerifyRom(rom)) throw new InvalidDataException("Owner ROM did not match the supported USA digest.");
        string Digest(string path) { using var f = File.OpenRead(path); return Convert.ToHexString(SHA256.HashData(f)); }
        var engineHash = Digest(source); var romHash = Digest(rom);
        Directory.CreateDirectory(output); var engineDir = Path.Combine(output, "game"); Directory.CreateDirectory(engineDir);
        var exe = Path.Combine(engineDir, Path.GetFileName(source)); File.Copy(source, exe);
        var sourceDir = Path.GetDirectoryName(source)!;
        foreach (var library in Directory.EnumerateFiles(sourceDir, "*.dll")) File.Copy(library, Path.Combine(engineDir, Path.GetFileName(library)));
        foreach (var name in new[] { "assets", "mods", "i18n" }) {
            var tree = Path.Combine(sourceDir, name); if (!Directory.Exists(tree)) continue;
            foreach (var file in Directory.EnumerateFiles(tree, "*", SearchOption.AllDirectories)) {
                if (Path.GetFileName(file).Equals("state.toml", StringComparison.OrdinalIgnoreCase) || Path.GetExtension(file).Equals(".token", StringComparison.OrdinalIgnoreCase)) continue;
                if (new[] { ".sfc", ".smc", ".srm", ".sav", ".pcm", ".msu", ".ips", ".bps" }.Contains(Path.GetExtension(file).ToLowerInvariant())) continue;
                var destination = Path.Combine(engineDir, name, Path.GetRelativePath(tree, file));
                Directory.CreateDirectory(Path.GetDirectoryName(destination)!); File.Copy(file, destination);
            }
        }
        File.WriteAllText(Path.Combine(engineDir, "config.ini"), "[Graphics]\nOutputMethod = SDL-Software\nNewRenderer = 1\nWindowScale = 3\nWidescreen = 0\n[General]\nDisableFrameDelay = 1\nRetroAchievements = 0\n[Sound]\nEnableAudio = 0\nVolume = 20\n[GamepadMap]\nEnableGamepad1 = false\nEnableGamepad2 = false\n");
        var adapter = new GameAdapter(Path.Combine(output, "preferences")); var profile = adapter.Profiles.Single();
        var select = adapter.ReadSettings(profile); select.Values["engine.path"] = OptionValue.From(exe); select.Values["rom.path"] = OptionValue.From(rom);
        adapter.ApplySettings(profile, select.Values, select.Revision);
        var current = adapter.ReadSettings(profile); var plan = adapter.BuildLaunchPlan(profile, current.Values, false);
        var info = new ProcessStartInfo(plan.Executable) { WorkingDirectory = plan.WorkingDirectory, UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true };
        foreach (var argument in plan.Arguments) info.ArgumentList.Add(argument);
        foreach (var key in info.Environment.Keys.ToArray())
            if (key.StartsWith("SNESRECOMP_", StringComparison.Ordinal) || key.StartsWith("IOG_", StringComparison.Ordinal) || key.StartsWith("IOGR_", StringComparison.Ordinal)) info.Environment.Remove(key);
        info.Environment["SDL_VIDEODRIVER"] = "dummy"; info.Environment["SDL_AUDIODRIVER"] = "dummy";
        info.Environment["SNESRECOMP_RUN_FRAMES"] = "60"; info.Environment["SNESRECOMP_HOST_PROFILE"] = "1";
        info.Environment["SNESRECOMP_SCREENSHOT"] = Path.Combine(output, "frame.ppm"); info.Environment["SNESRECOMP_SCREENSHOT_FRAME"] = "50";
        using var process = Process.Start(info) ?? throw new IOException("Engine process did not start.");
        var stdout = process.StandardOutput.ReadToEndAsync(); var stderr = process.StandardError.ReadToEndAsync();
        using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(30));
        try { await process.WaitForExitAsync(timeout.Token); } catch { process.Kill(entireProcessTree: true); throw; }
        var log = await stdout + "\n" + await stderr; File.WriteAllText(Path.Combine(output, "engine.log"), log);
        var image = Path.Combine(output, "frame.ppm"); int nonblackPixels = 0;
        if (File.Exists(image)) {
            var ppm = File.ReadAllBytes(image); int headerEnd = 0;
            for (int lines = 0; headerEnd < ppm.Length && lines < 3; headerEnd++) if (ppm[headerEnd] == '\n') lines++;
            for (int i = headerEnd; i + 2 < ppm.Length; i += 3) if (ppm[i] != 0 || ppm[i + 1] != 0 || ppm[i + 2] != 0) nonblackPixels++;
        }
        bool untouched = Digest(source) == engineHash && Digest(rom) == romHash;
        bool passed = process.ExitCode == 0 && log.Contains("IOG_EXECUTION=interpreter-only;rom-derived-code=none") &&
            log.Contains("RUN_FRAMES reached after 60 frames") && File.Exists(Path.Combine(output, "frame.ppm")) && untouched;
        var receipt = JsonSerializer.Serialize(new {
            passed, schema = "gaia-companion-engine-smoke-v1", framesRequested = 60, exitCode = process.ExitCode,
            execution = "interpreter-only", binarySha256 = engineHash, romSha256 = romHash, ownerFilesUnchanged = untouched,
            launchArguments = plan.Arguments, workingDirectory = plan.WorkingDirectory,
            frameCaptured = File.Exists(image), nonblackPixels, visualQualified = nonblackPixels > 0,
            evidenceScope = "Actual adapter launch plan to copied built engine, dummy video/audio; bounded boot only, no physical controller or campaign"
        }, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(Path.Combine(output, "receipt.json"), receipt); Console.WriteLine(receipt);
        if (!passed) throw new InvalidOperationException("Engine launch smoke did not qualify; retain failed receipt and engine.log.");
    }
}
