using System.Buffers.Binary;
using System.IO.Compression;
using System.Security.Cryptography;

public static class SoundtrackTests
{
    private sealed class InlineProgress(Action<SoundtrackProgress> action) : IProgress<SoundtrackProgress>
    { public void Report(SoundtrackProgress value) => action(value); }

    public static async Task RunAsync()
    {
        string root = Path.Combine(Path.GetTempPath(), "gaia-soundtrack-tests-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root); int checks = 0;
        void Check(bool value, string name) { if (!value) throw new Exception("Soundtrack: " + name); checks++; }
        async Task Reject(string name, params (string Name, byte[] Data)[] files) {
            var zip = Path.Combine(root, name + ".zip"); WriteZip(zip, files);
            string engine = Path.Combine(root, name); Directory.CreateDirectory(engine);
            try { await SoundtrackService.ImportAsync(zip, engine); } catch (InvalidDataException) {
                checks++; Check(!Directory.Exists(Path.Combine(engine, "msu1", "companion-packs")) ||
                    !Directory.EnumerateDirectories(Path.Combine(engine, "msu1", "companion-packs")).Any(), name + " leaves no published or staged pack"); return;
            }
            throw new Exception("Soundtrack accepted " + name);
        }
        try {
            string zip = Path.Combine(root, "valid.zip");
            WriteZip(zip, ("nested/orchestra-1.pcm", Pcm(32, 2)), ("nested/orchestra-31.pcm", Pcm(8)),
                ("nested/Artist Track Credit Link.docx", "test credits; never opened"u8.ToArray()), ("unrelated.ips", new byte[] { 1, 2, 3 }));
            byte[] sourceHash = SHA256.HashData(File.ReadAllBytes(zip));
            string engine = Path.Combine(root, "game with spaces"); Directory.CreateDirectory(engine);
            File.WriteAllText(Path.Combine(engine, "owner-file.txt"), "keep owner data");
            var imported = await SoundtrackService.ImportAsync(zip, engine);
            Check(imported.TrackCount == 2 && imported.TrackPrefix == "gaia", "import normalizes tracks");
            Check(imported.CatalogId == null, "custom pack is not misidentified as the catalog");
            Check(File.Exists(Path.Combine(imported.PackDirectory, "gaia-31.pcm")), "high numbered track retained");
            Check(File.Exists(Path.Combine(imported.PackDirectory, "Artist Track Credit Link.docx")), "credit document retained");
            Check(!File.Exists(Path.Combine(imported.PackDirectory, "unrelated.ips")), "patches never imported or applied");
            Check(sourceHash.SequenceEqual(SHA256.HashData(File.ReadAllBytes(zip))), "source ZIP unchanged");
            Check(File.ReadAllText(Path.Combine(engine, "owner-file.txt")) == "keep owner data", "owner data untouched");
            Check((await SoundtrackService.InspectInstalledAsync(imported.PackDirectory)).IsValid, "installed bytes verified");
            Check((await SoundtrackService.FindInstalledAsync(engine)).Count == 1, "find installed validates receipt and tracks");
            var repeated = await SoundtrackService.ImportAsync(zip, engine);
            Check(repeated.AlreadyInstalled && repeated.PackDirectory == imported.PackDirectory, "repeat import is idempotent");
            var damaged = Path.Combine(imported.PackDirectory, "gaia-1.pcm");
            var bytes = File.ReadAllBytes(damaged); bytes[^1] ^= 0x40; File.WriteAllBytes(damaged, bytes);
            Check(!(await SoundtrackService.InspectInstalledAsync(imported.PackDirectory)).IsValid, "same-size corruption detected");
            try { await SoundtrackService.ImportAsync(zip, engine); throw new Exception("Conflict was overwritten"); }
            catch (IOException) { checks++; }
            Check(File.ReadAllBytes(damaged).SequenceEqual(bytes), "conflicting existing bytes protected");
            Check(!Directory.EnumerateDirectories(Path.GetDirectoryName(imported.PackDirectory)!, ".staging-*").Any(), "conflict rolls back staging");

            await Reject("traversal", ("../rom.sfc", new byte[4]), ("pack-1.pcm", Pcm(2)));
            await Reject("windows-traversal", ("..\\escape.pcm", Pcm(2)), ("pack-1.pcm", Pcm(2)));
            await Reject("absolute-path", ("C:/escape.pcm", Pcm(2)), ("pack-1.pcm", Pcm(2)));
            await Reject("duplicate-path", ("pack-1.pcm", Pcm(2)), ("PACK-1.PCM", Pcm(2)));
            await Reject("duplicate-track", ("a/pack-1.pcm", Pcm(2)), ("b/pack-01.pcm", Pcm(2)));
            await Reject("multiple-packs", ("a-1.pcm", Pcm(2)), ("b-2.pcm", Pcm(2)));
            await Reject("bad-header", ("pack-1.pcm", new byte[16]));
            await Reject("unaligned", ("pack-1.pcm", new byte[13]));
            await Reject("empty-audio", ("pack-1.pcm", Pcm(0)));
            await Reject("invalid-loop", ("pack-1.pcm", Pcm(2, 2)));
            await Reject("unsupported-track", ("pack-32.pcm", Pcm(2)));
            await Reject("no-pcm", ("game.sfc", new byte[16]));
            string linkZip = Path.Combine(root, "link.zip");
            using (var archive = ZipFile.Open(linkZip, ZipArchiveMode.Create)) {
                var entry = archive.CreateEntry("pack-1.pcm"); entry.ExternalAttributes = unchecked((int)0xA1FF0000);
                using var stream = entry.Open(); stream.Write(Pcm(2));
            }
            string linkEngine = Path.Combine(root, "link-game"); Directory.CreateDirectory(linkEngine);
            try { await SoundtrackService.ImportAsync(linkZip, linkEngine); throw new Exception("ZIP symlink accepted"); }
            catch (InvalidDataException) { checks++; }

            string folder = Path.Combine(root, "folder-source"); Directory.CreateDirectory(folder);
            File.WriteAllBytes(Path.Combine(folder, "music-2.pcm"), Pcm(2));
            string folderGame = Path.Combine(root, "folder-game"); Directory.CreateDirectory(folderGame);
            var folderPack = await SoundtrackService.ImportAsync(folder, folderGame);
            Check(folderPack.TrackCount == 1 && File.Exists(Path.Combine(folder, "music-2.pcm")), "read-only folder import");
            string folderReceipt = Path.Combine(folderPack.PackDirectory, "soundtrack-import.json");
            string oldReceipt = File.ReadAllText(folderReceipt);
            File.WriteAllText(folderReceipt, "{\"formatVersion\":1,\"contentId\":\"invalid\",\"tracks\":[null]}");
            Check(!(await SoundtrackService.InspectInstalledAsync(folderPack.PackDirectory)).IsValid, "damaged receipt handled without crashing");
            File.WriteAllText(folderReceipt, oldReceipt);
            string linkedFolder = Path.Combine(root, "linked-source");
            bool madeLink = false;
            try { Directory.CreateSymbolicLink(linkedFolder, folder); madeLink = true; }
            catch (Exception ex) when (ex is UnauthorizedAccessException or IOException or PlatformNotSupportedException) {
                Console.WriteLine("Soundtrack folder-link check skipped: OS does not permit creating the synthetic link.");
            }
            if (madeLink) {
                try { await SoundtrackService.ImportAsync(linkedFolder, folderGame); throw new Exception("Source symlink accepted"); }
                catch (InvalidDataException) { checks++; }
                finally { Directory.Delete(linkedFolder); }
            }

            string cancelZip = Path.Combine(root, "cancel.zip"); WriteZip(cancelZip, ("pack-1.pcm", Pcm(200000)));
            string cancelEngine = Path.Combine(root, "cancel-game"); Directory.CreateDirectory(cancelEngine);
            using var cancelled = new CancellationTokenSource(); cancelled.Cancel();
            try { await SoundtrackService.ImportAsync(cancelZip, cancelEngine, cancellationToken: cancelled.Token); throw new Exception("Pre-cancel ignored"); }
            catch (OperationCanceledException) { checks++; }
            Check(!Directory.Exists(Path.Combine(cancelEngine, "msu1")), "pre-cancel writes nothing");
            using var midCancel = new CancellationTokenSource();
            try {
                await SoundtrackService.ImportAsync(cancelZip, cancelEngine, new InlineProgress(_ => midCancel.Cancel()), midCancel.Token);
                throw new Exception("Mid-import cancellation ignored");
            } catch (OperationCanceledException) { checks++; }
            Check(!Directory.EnumerateDirectories(Path.Combine(cancelEngine, "msu1", "companion-packs")).Any(), "mid-cancel publishes no partial pack");

            // Alter only the ZIP's declared uncompressed size: it must be rejected before extraction.
            string capped = Path.Combine(root, "oversized.zip"); WriteZip(capped, ("pack-1.pcm", Pcm(2)));
            var raw = File.ReadAllBytes(capped); int central = Find(raw, new byte[] { 0x50, 0x4b, 0x01, 0x02 });
            BinaryPrimitives.WriteUInt32LittleEndian(raw.AsSpan(central + 24, 4), (uint)SoundtrackService.MaxTrackBytes + 4); File.WriteAllBytes(capped, raw);
            try { await SoundtrackService.ImportAsync(capped, cancelEngine); throw new Exception("Size cap ignored"); }
            catch (InvalidDataException) { checks++; }
            Console.WriteLine($"Soundtrack: {checks} checks passed (synthetic ZIP/folder imports, corruption, conflicts, rollback and cancellation).");
        } finally { Directory.Delete(root, recursive: true); }
    }

    public static async Task<SoundtrackImportResult> ImportRealAsync(string source, string freshEngineDirectory)
    {
        if (Directory.Exists(freshEngineDirectory)) throw new IOException("Real-pack validation requires a fresh isolated engine directory.");
        Directory.CreateDirectory(freshEngineDirectory);
        var result = await SoundtrackService.ImportAsync(source, freshEngineDirectory);
        if (result.CatalogId != "jud6ment-orchestra" || result.TrackCount != 28 || !(await SoundtrackService.InspectInstalledAsync(result.PackDirectory)).IsValid)
            throw new InvalidDataException("Local JUD6MENT pack did not match the verified catalog.");
        Console.WriteLine($"Real soundtrack verified: {result.TrackCount} tracks, {result.TotalBytes} bytes, content {result.Sha256}.");
        return result;
    }
    private static byte[] Pcm(int frames, uint loop = 0)
    {
        var data = new byte[8 + frames * 4]; "MSU1"u8.CopyTo(data); BinaryPrimitives.WriteUInt32LittleEndian(data.AsSpan(4), loop);
        for (int i = 8; i < data.Length; i++) data[i] = (byte)(i * 19);
        return data;
    }
    private static void WriteZip(string path, params (string Name, byte[] Data)[] files)
    {
        using var archive = ZipFile.Open(path, ZipArchiveMode.Create);
        foreach (var file in files) { using var output = archive.CreateEntry(file.Name).Open(); output.Write(file.Data); }
    }
    private static int Find(byte[] source, byte[] value)
    { for (int i = 0; i <= source.Length - value.Length; i++) if (source.AsSpan(i, value.Length).SequenceEqual(value)) return i; throw new Exception("ZIP central record absent"); }
}
