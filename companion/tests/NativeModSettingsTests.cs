using System.Text;
using Companion.Launcher.Core;

internal static class NativeModSettingsTests
{
    internal static void Run()
    {
        var root = Path.Combine(Path.GetTempPath(), "GaiaMods-tests-" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(root);
        int checks = 0;
        void Check(bool condition, string name) { if (!condition) throw new Exception(name); checks++; }
        void Throws<T>(Action action, string name) where T : Exception { try { action(); } catch (T) { checks++; return; } throw new Exception(name); }
        try {
            var exe = Path.Combine(root, "babel-recomp.exe"); File.WriteAllText(exe, "synthetic fixture - never executed");
            foreach (var group in NativeModSettings.Fields.GroupBy(f => f.Package)) {
                var dir = Path.Combine(root, "mods/preloaded/packages", group.Key, "1.0.0"); Directory.CreateDirectory(dir);
                File.WriteAllText(Path.Combine(dir, "manifest.toml"), "id = \"" + group.Key + "\"\n" + string.Join("\n", group.Select(f => f.Feature).Distinct().Select(id => "[[feature]]\nid = \"" + id + "\"\n")) +
                    string.Join("\n", group.Where(f => f.ValueKey != null).Select(f => "[[option]]\nfeature = \"" + f.Feature + "\"\nid = \"" + f.ValueKey + "\"\n")));
            }
            var state = Path.Combine(root, "mods/preloaded/state.toml");
            var original = "# owner comment\r\nformat_version = 1\r\n\r\n[[package]]\r\nid = \"iog.enhancements\"\r\nversion = \"1.0.0\"\r\n\r\n[[feature]]\r\npackage_id = \"iog.enhancements\"\r\nid = \"run\"\r\nenabled = true\r\n[feature.values]\r\nbutton = \"Y\"\r\n\r\n[[feature]]\r\npackage_id = \"iog.enhancements\"\r\nid = \"msu1\"\r\nenabled = true\r\n\r\n[[resource]]\r\npackage_id = \"iog.enhancements\"\r\nfeature_id = \"msu1\"\r\nid = \"pack\"\r\npath = \"owner/music#one\"\r\n\r\n[[feature]]\r\npackage_id = \"iog.cheats\"\r\nid = \"stats\"\r\nenabled = false\r\n[feature.values]\r\nstrength = \"10\" # retain comment\r\ndefense = \"11\"\r\ncustom_future_value = \"keep me\"\r\n\r\n[[feature]]\r\npackage_id = \"iog.cheats\"\r\nid = \"room_rewards\"\r\nenabled = false\r\n[feature.values]\r\nmultiplier = \"8\"\r\n";
            File.WriteAllText(state, original, new UTF8Encoding(true));
            var first = NativeModSettings.Read(root);
            Check(first.Available.Count == NativeModSettings.Fields.Count, "supported source catalog declares controls");
            Check(first.Values["cheat.room-rewards"].GetString() == "1", "disabled multiplier reports effective original rate");
            Check(first.Values["cheat.strength"].GetInt32() == 10, "native feature.values reads established stats");
            first.Values["cheat.hp"] = OptionValue.From(true); first.Values["cheat.dp"] = OptionValue.From(true); first.Values["cheat.dp-min"] = OptionValue.From(250);
            first.Values["cheat.room-rewards"] = OptionValue.From("3"); first.Values["mod.stacking"] = OptionValue.From(true);
            NativeModSettings.Apply(root, first.Values, first.Revision);
            var text = File.ReadAllText(state); var current = NativeModSettings.Read(root);
            Check(current.Values["cheat.hp"].GetBoolean() && current.Values["cheat.dp"].GetBoolean(), "native cheat toggles round trip");
            Check(current.Values["cheat.dp-min"].GetInt32() == 250, "native integer option round trips as TOML string");
            Check(current.Values["cheat.room-rewards"].GetString() == "3", "room reward rate is enabled and persistent");
            Check(current.Values["mod.stacking"].GetBoolean(), "convenience feature round trip");
            Check(text.Contains("path = \"owner/music#one\"\r\n"), "soundtrack resource and quoted hash preserved");
            Check(text.Contains("id = \"run\"\r\nenabled = true\r\n[feature.values]\r\nbutton = \"Y\""), "existing movement/run selection unchanged");
            Check(text.Contains("custom_future_value = \"keep me\"") && text.Contains("strength = \"10\" # retain comment"), "unknown options and comments survive");
            Check(File.ReadAllBytes(state).AsSpan().StartsWith(new byte[] {239,187,191}) && text.Contains("\r\n"), "BOM and CRLF retained");
            current.Values["cheat.room-rewards"] = OptionValue.From("1"); NativeModSettings.Apply(root, current.Values, current.Revision);
            Check(NativeModSettings.Read(root).Values["cheat.room-rewards"].GetString() == "1" && File.ReadAllText(state).Contains("multiplier = \"1\""), "original rate disables feature and stores one");
            var stale = NativeModSettings.Read(root); File.AppendAllText(state, "# in-game change\r\n"); var external = File.ReadAllBytes(state);
            stale.Values["cheat.hp"] = OptionValue.From(false);
            Throws<SettingsConflictException>(() => NativeModSettings.Apply(root, stale.Values, stale.Revision), "reject stale in-game edit");
            Check(external.SequenceEqual(File.ReadAllBytes(state)), "stale Apply preserves current owner bytes");
            var range = NativeModSettings.Read(root); range.Values["cheat.room-rewards"] = OptionValue.From("9");
            Throws<SettingsValidationException>(() => NativeModSettings.Apply(root, range.Values, range.Revision), "reject unsupported rate");
            Check(!NativeModSettings.IsEngineRunning(exe), "fixture engine is not running");
            Check(NativeModSettings.IsEngineRunning(Environment.ProcessPath!), "running process gate detects actual process");
            var cheatsManifest = Path.Combine(root, "mods/preloaded/packages/iog.cheats/1.0.0/manifest.toml");
            File.WriteAllText(cheatsManifest, "[[feature]]\nid = \"infinite_hp\"\n");
            var unsupported = NativeModSettings.Read(root); unsupported.Values["cheat.dp-min"] = OptionValue.From(500);
            Check(!unsupported.Available.Contains("cheat.dp-min"), "old catalog disables unsupported options");
            Throws<InvalidOperationException>(() => NativeModSettings.Apply(root, unsupported.Values, unsupported.Revision), "old catalog cannot receive fake settings");
            File.WriteAllText(state, "format_version = 1\n[[feature]]\npackage_id = \"iog.cheats\"\nid = \"dp\"\nenabled = true\n[[feature]]\npackage_id = \"iog.cheats\"\nid = \"dp\"\nenabled = false\n");
            Throws<InvalidDataException>(() => NativeModSettings.Read(root), "duplicate target feature rejected");
            File.WriteAllText(state, "format_version = 1\n[[feature]]\npackage_id = \"iog.cheats\"\nid = \"dp\"\nenabled = true\n[feature.values]\namount = \"12\"\namount = \"14\"\n");
            Throws<InvalidDataException>(() => NativeModSettings.Read(root), "duplicate target option rejected");
            Console.WriteLine($"PASS {checks} native mod settings checks (synthetic state; no game or owner data)");
        } finally { Directory.Delete(root, true); }
    }
}
