using System.Text;

internal static class ActivationTests
{
    public static void Run()
    {
        var root = Path.Combine(Path.GetTempPath(), "gaia-activation-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try {
            File.WriteAllText(Path.Combine(root, "babel-recomp.exe"), "synthetic");
            var catalog = Path.Combine(root, "mods/preloaded/packages/iog.enhancements/1.0.0");
            Directory.CreateDirectory(catalog); File.WriteAllText(Path.Combine(catalog, "manifest.toml"), "synthetic");
            var pack = Path.GetFullPath(Path.Combine(root, "msu1/companion-packs/test-pack")); Directory.CreateDirectory(pack);
            var state = Path.Combine(root, "mods/preloaded/state.toml");
            const string other = "# owner comment\r\nformat_version = 1\r\n\r\n[[feature]]\r\npackage_id = \"iog.cheats\"\r\nid = \"stats\"\r\nenabled = false\r\n\r\n[[option]]\r\npackage_id = \"iog.enhancements\"\r\nfeature_id = \"run\"\r\nid = \"button\"\r\nvalue = \"Y\"\r\n";
            File.WriteAllText(state, other, new UTF8Encoding(true));
            SoundtrackActivation.Enable(root, pack);
            var result = SoundtrackActivation.Read(root);
            Assert(result.Enabled && result.PackDirectory == pack, "enable native selection");
            Assert(File.ReadAllText(state).Contains(other), "preserve unrelated mods and comments");
            Assert(File.ReadAllBytes(state).AsSpan().StartsWith(new byte[] {239,187,191}), "preserve BOM");
            var once = File.ReadAllBytes(state); SoundtrackActivation.Enable(root, pack);
            Assert(once.SequenceEqual(File.ReadAllBytes(state)), "idempotent activation");
            SoundtrackActivation.Disable(root); result = SoundtrackActivation.Read(root);
            Assert(!result.Enabled && result.PackDirectory == pack, "original audio keeps selected pack");
            var preserved = File.ReadAllBytes(state);
            try { SoundtrackActivation.Enable(root, Path.GetTempPath()); throw new Exception("external pack accepted"); }
            catch (InvalidDataException) { }
            Assert(preserved.SequenceEqual(File.ReadAllBytes(state)), "reject outside pack without writes");
            File.AppendAllText(state, "\n[[feature]]\npackage_id = \"iog.enhancements\"\nid = \"msu1\"\nenabled = true\n");
            preserved = File.ReadAllBytes(state);
            try { SoundtrackActivation.Disable(root); throw new Exception("duplicate selection accepted"); }
            catch (InvalidDataException) { }
            Assert(preserved.SequenceEqual(File.ReadAllBytes(state)), "duplicate selections fail closed");
            Console.WriteLine("PASS 7 soundtrack activation checks (synthetic native mod state)");
        } finally { Directory.Delete(root, true); }
    }
    private static void Assert(bool condition, string name) { if (!condition) throw new Exception(name); }
}
