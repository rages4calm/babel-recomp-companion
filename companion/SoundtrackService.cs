using System.Buffers.Binary;
using System.Globalization;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

public sealed record SoundtrackProgress(string Phase, string FileName, long BytesCompleted,
    long TotalBytes, int TracksCompleted, int TotalTracks);
public sealed record SoundtrackImportResult(string PackDirectory, string TrackPrefix, int TrackCount,
    long TotalBytes, string Sha256, string? CatalogId, bool AlreadyInstalled = false);
public sealed record SoundtrackStatus(bool IsValid, string Summary, SoundtrackImportResult? Result = null);

/// <summary>Streams owner-supplied music into an isolated verified pack; never patches a ROM or edits settings.</summary>
public static class SoundtrackService
{
    public const string CatalogTitle = "Illusion of Gaia Orchestra";
    public const string Author = "JUD6MENT";
    public const string Credit = "Orchestra pack by JUD6MENT; individual performers and arrangers are credited in Artist Track Credit Link.docx.";
    public const string SourceListingUrl = "https://www.zeldix.net/t1604-illusion-of-gaiatime-gaia-trilogy-ii";
    public const string SourceDownloadUrl = "https://mega.nz/file/6OpyGLIQ#uE3VHjqVNrR-hQjOt1wpknC-1-TT8YQkwRwLbSzAtW0";
    public const string SourcePageUrl = SourceListingUrl;
    public const string DownloadUrl = SourceDownloadUrl;
    public const long MaxTrackBytes = 256L * 1024 * 1024;
    public const long MaxExpandedBytes = 2L * 1024 * 1024 * 1024;
    private const int MaxEntries = 4096;
    private const string CreditsName = "Artist Track Credit Link.docx";
    private const string ReceiptName = "soundtrack-import.json";
    private static readonly JsonSerializerOptions Json = new() { PropertyNameCaseInsensitive = true, WriteIndented = true };
    private static readonly Regex TrackName = new(@"^(.+)-([0-9]{1,5})\.pcm$", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
    public sealed record Track(int Number, long Size, uint LoopStart, string Sha256);
    public sealed record CreditFile(string Name, long Size, string Sha256);
    public sealed record Receipt(int FormatVersion, string ContentId, string? CatalogId, Track[] Tracks, CreditFile? Credits);
    private sealed record Catalog(int FormatVersion, CatalogPack[] Packs);
    private sealed record CatalogPack(string Id, string Title, string Author, Track[] Tracks, CreditFile? Credits);
    private sealed record Input(string Name, long Size, Func<Stream> Open);

    public static Task<SoundtrackImportResult> ImportAsync(string sourceZipOrFolder, string engineDirectory,
        IProgress<SoundtrackProgress>? progress = null, CancellationToken cancellationToken = default) =>
        Task.Run(() => ImportCoreAsync(sourceZipOrFolder, engineDirectory, progress, cancellationToken), cancellationToken);

    private static async Task<SoundtrackImportResult> ImportCoreAsync(string source, string engineDirectory,
        IProgress<SoundtrackProgress>? progress, CancellationToken cancel)
    {
        cancel.ThrowIfCancellationRequested();
        source = Absolute(source); engineDirectory = Absolute(engineDirectory);
        RejectLinks(source); RejectLinks(engineDirectory);
        if (!Directory.Exists(engineDirectory)) throw new DirectoryNotFoundException("Select an existing game folder.");
        var parent = Path.Combine(engineDirectory, "msu1", "companion-packs");
        RejectLinks(parent);
        // Source metadata is validated before creating any destination. Its bytes remain read-only.
        using var zipFile = File.Exists(source) ? new FileStream(source, FileMode.Open, FileAccess.Read, FileShare.Read) : null;
        if (zipFile != null && (!source.EndsWith(".zip", StringComparison.OrdinalIgnoreCase) || zipFile.Length > MaxExpandedBytes))
            throw new InvalidDataException("Select a ZIP soundtrack no larger than 2 GiB, or a folder.");
        using var zip = zipFile == null ? null : new ZipArchive(zipFile, ZipArchiveMode.Read, leaveOpen: true);
        var inputs = zip == null ? FolderInputs(source) : ZipInputs(zip);
        var pcm = inputs.Where(x => x.Name.EndsWith(".pcm", StringComparison.OrdinalIgnoreCase)).ToArray();
        if (pcm.Length is 0 or >31) throw new InvalidDataException("The pack must contain 1–31 Gaia PCM tracks.");
        var tracks = new Dictionary<int, Input>(); string? prefix = null;
        foreach (var input in pcm) {
            var match = TrackName.Match(Path.GetFileName(input.Name));
            if (!match.Success || !int.TryParse(match.Groups[2].Value, out int number) || number is <1 or >31)
                throw new InvalidDataException("Use Gaia track names such as iog_msu1-1.pcm (track numbers 1–31).");
            if (prefix != null && !prefix.Equals(match.Groups[1].Value, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Select one soundtrack pack; multiple PCM filename prefixes were found.");
            prefix = match.Groups[1].Value;
            if (!tracks.TryAdd(number, input)) throw new InvalidDataException($"Duplicate soundtrack track {number}.");
            ValidatePcmLength(input.Size);
        }
        var credits = inputs.Where(x => Path.GetFileName(x.Name).Equals(CreditsName, StringComparison.OrdinalIgnoreCase)).ToArray();
        if (credits.Length > 1 || credits.Any(x => x.Size > 8 * 1024 * 1024))
            throw new InvalidDataException("Duplicate or oversized soundtrack credit document.");
        long total = tracks.Values.Sum(x => x.Size) + credits.Sum(x => x.Size), completed = 0;
        Directory.CreateDirectory(parent); RejectLinks(parent);
        string lockPath = Path.Combine(parent, ".import.lock"); RejectLinks(lockPath);
        using var gate = new FileStream(lockPath, FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None);
        string stage = Path.Combine(parent, ".staging-" + Guid.NewGuid().ToString("N"));
        if (Directory.Exists(stage) || File.Exists(stage)) throw new IOException("Soundtrack staging conflict.");
        Directory.CreateDirectory(stage);
        try {
            var verified = new List<Track>();
            foreach (var pair in tracks.OrderBy(x => x.Key)) {
                cancel.ThrowIfCancellationRequested(); var input = pair.Value;
                await using var stream = input.Open();
                byte[] header = new byte[8]; await stream.ReadExactlyAsync(header, cancel).ConfigureAwait(false);
                if (!header.AsSpan(0, 4).SequenceEqual("MSU1"u8)) throw new InvalidDataException($"Invalid MSU1 header: {input.Name}");
                uint loop = BinaryPrimitives.ReadUInt32LittleEndian(header.AsSpan(4));
                if (loop >= (input.Size - 8) / 4) throw new InvalidDataException($"Loop starts beyond the PCM samples: {input.Name}");
                var hash = await CopyAsync(stream, header, input.Size, Path.Combine(stage, $"gaia-{pair.Key}.pcm"),
                    copied => progress?.Report(new("Importing", input.Name, completed + copied, total, verified.Count, tracks.Count)), cancel).ConfigureAwait(false);
                completed += input.Size; verified.Add(new(pair.Key, input.Size, loop, hash));
            }
            CreditFile? credit = null;
            if (credits.Length == 1) {
                await using var stream = credits[0].Open();
                string hash = await CopyAsync(stream, Array.Empty<byte>(), credits[0].Size, Path.Combine(stage, CreditsName),
                    copied => progress?.Report(new("Preserving credits", CreditsName, completed + copied, total, verified.Count, tracks.Count)), cancel).ConfigureAwait(false);
                credit = new(CreditsName, credits[0].Size, hash);
            }
            string id = ContentId(verified, credit);
            string? catalogId = RecognizeCatalog(verified, credit);
            var receipt = new Receipt(1, id, catalogId, verified.ToArray(), credit);
            await File.WriteAllTextAsync(Path.Combine(stage, ReceiptName), JsonSerializer.Serialize(receipt, Json) + "\n", new UTF8Encoding(false), cancel).ConfigureAwait(false);
            cancel.ThrowIfCancellationRequested(); RejectLinks(parent);
            string destination = Path.Combine(parent, id);
            if (Directory.Exists(destination) || File.Exists(destination)) {
                var existing = await InspectInstalledAsync(destination, cancel).ConfigureAwait(false);
                if (!existing.IsValid || existing.Result?.Sha256 != id)
                    throw new IOException("A conflicting soundtrack folder already exists. Existing files were left unchanged.");
                progress?.Report(new("Already installed", "", total, total, tracks.Count, tracks.Count));
                return existing.Result with { AlreadyInstalled = true };
            }
            // Same-volume directory rename publishes only a completely validated pack. No replacement occurs.
            Directory.Move(stage, destination);
            progress?.Report(new("Imported", "", total, total, tracks.Count, tracks.Count));
            return new(destination, "gaia", tracks.Count, total, id, catalogId);
        } finally {
            // Only this invocation's private staging directory is eligible for rollback.
            if (Directory.Exists(stage)) { RejectLinks(stage); Directory.Delete(stage, recursive: true); }
        }
    }

    public static async Task<SoundtrackStatus> InspectInstalledAsync(string packDirectory, CancellationToken cancellationToken = default)
    {
        try {
            string folder = Absolute(packDirectory); RejectLinks(folder);
            string path = Path.Combine(folder, ReceiptName); RejectLinks(path);
            if (!File.Exists(path) || new FileInfo(path).Length > 64 * 1024) return new(false, "No valid import receipt.");
            var receipt = JsonSerializer.Deserialize<Receipt>(await File.ReadAllTextAsync(path, cancellationToken).ConfigureAwait(false), Json);
            if (receipt == null || receipt.FormatVersion != 1 || receipt.Tracks == null || receipt.Tracks.Length is 0 or >31 ||
                receipt.Tracks.Any(x => x == null || x.Sha256 == null || !Regex.IsMatch(x.Sha256, "^[0-9a-f]{64}$", RegexOptions.CultureInvariant)) ||
                receipt.Tracks.Select(x => x.Number).Distinct().Count() != receipt.Tracks.Length)
                return new(false, "Invalid soundtrack receipt.");
            var expected = new HashSet<string>(StringComparer.OrdinalIgnoreCase) { ReceiptName };
            long bytes = 0;
            foreach (var track in receipt.Tracks) {
                cancellationToken.ThrowIfCancellationRequested(); ValidatePcmLength(track.Size);
                if (track.Number is <1 or >31) return new(false, "Invalid track number.");
                var file = $"gaia-{track.Number}.pcm"; expected.Add(file);
                string full = Path.Combine(folder, file); RejectLinks(full);
                await using var input = new FileStream(full, FileMode.Open, FileAccess.Read, FileShare.Read, 262144, true);
                if (input.Length != track.Size) return new(false, "An imported track changed size.");
                var header = new byte[8]; await input.ReadExactlyAsync(header, cancellationToken).ConfigureAwait(false);
                if (!header.AsSpan(0, 4).SequenceEqual("MSU1"u8) || BinaryPrimitives.ReadUInt32LittleEndian(header.AsSpan(4)) != track.LoopStart ||
                    track.LoopStart >= (track.Size - 8) / 4) return new(false, "An imported track has an invalid header or loop.");
                input.Position = 0;
                string hash = Convert.ToHexString(await SHA256.HashDataAsync(input, cancellationToken).ConfigureAwait(false)).ToLowerInvariant();
                if (!hash.Equals(track.Sha256, StringComparison.Ordinal)) return new(false, "An imported track failed its SHA-256 check.");
                bytes = checked(bytes + track.Size);
            }
            if (receipt.Credits is { } credit) {
                if (credit.Name != CreditsName || credit.Size is <1 or >8388608) return new(false, "Invalid credit-document receipt.");
                expected.Add(CreditsName); string full = Path.Combine(folder, CreditsName); RejectLinks(full);
                await using var input = new FileStream(full, FileMode.Open, FileAccess.Read, FileShare.Read, 65536, true);
                if (input.Length != credit.Size || !Convert.ToHexString(await SHA256.HashDataAsync(input, cancellationToken).ConfigureAwait(false)).Equals(credit.Sha256, StringComparison.OrdinalIgnoreCase))
                    return new(false, "The soundtrack credit document changed.");
                bytes = checked(bytes + credit.Size);
            }
            if (bytes > MaxExpandedBytes || Directory.EnumerateFileSystemEntries(folder).Any(x => !expected.Contains(Path.GetFileName(x)) || Directory.Exists(x)))
                return new(false, "Unexpected files or folders in the imported soundtrack.");
            if (ContentId(receipt.Tracks, receipt.Credits) != receipt.ContentId) return new(false, "Soundtrack receipt identity mismatch.");
            string? catalog = RecognizeCatalog(receipt.Tracks, receipt.Credits);
            var result = new SoundtrackImportResult(folder, "gaia", receipt.Tracks.Length, bytes, receipt.ContentId, catalog);
            return new(true, catalog == null ? $"{result.TrackCount} PCM tracks verified; custom pack." : $"{CatalogTitle} by {Author}: {result.TrackCount} tracks verified.", result);
        } catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException or OverflowException or ArgumentException) {
            return new(false, "Cannot verify soundtrack: " + ex.Message);
        }
    }

    public static async Task<IReadOnlyList<SoundtrackImportResult>> FindInstalledAsync(string engineDirectory, CancellationToken cancellationToken = default)
    {
        string root = Path.Combine(Absolute(engineDirectory), "msu1", "companion-packs"); RejectLinks(root);
        var result = new List<SoundtrackImportResult>(); if (!Directory.Exists(root)) return result;
        var folders = Directory.EnumerateDirectories(root).Take(33).ToArray();
        if (folders.Length > 32) throw new InvalidDataException("Too many imported soundtrack folders to verify.");
        foreach (var path in folders) {
            cancellationToken.ThrowIfCancellationRequested();
            if (!Regex.IsMatch(Path.GetFileName(path), "^[0-9a-f]{64}$", RegexOptions.CultureInvariant)) continue;
            var status = await InspectInstalledAsync(path, cancellationToken).ConfigureAwait(false);
            if (status.Result != null && status.IsValid) result.Add(status.Result);
        }
        return result;
    }

    private static List<Input> ZipInputs(ZipArchive zip)
    {
        if (zip.Entries.Count > MaxEntries) throw new InvalidDataException("Too many ZIP entries.");
        var inputs = new List<Input>(); var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase); long total = 0;
        foreach (var entry in zip.Entries) {
            var name = SafeName(entry.FullName); bool directory = name.EndsWith('/');
            int unixType = (entry.ExternalAttributes >> 16) & 0xF000;
            if (unixType == 0xA000 || (entry.ExternalAttributes & (int)FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("ZIP links are not supported.");
            if (!names.Add(name.TrimEnd('/'))) throw new InvalidDataException("Duplicate ZIP path.");
            total = checked(total + entry.Length);
            if (entry.Length > MaxTrackBytes || total > MaxExpandedBytes) throw new InvalidDataException("Expanded soundtrack exceeds its size limit.");
            if (!directory) inputs.Add(new(name, entry.Length, entry.Open));
        }
        return inputs;
    }
    private static List<Input> FolderInputs(string root)
    {
        if (!Directory.Exists(root)) throw new DirectoryNotFoundException("Soundtrack source does not exist.");
        var inputs = new List<Input>(); var pending = new Stack<string>(); pending.Push(root); int count = 0; long total = 0;
        while (pending.TryPop(out var dir)) foreach (var path in Directory.EnumerateFileSystemEntries(dir)) {
            if (++count > MaxEntries) throw new InvalidDataException("Too many soundtrack files or folders.");
            RejectLinks(path); var name = SafeName(Path.GetRelativePath(root, path).Replace('\\', '/'));
            if (Directory.Exists(path)) { pending.Push(path); continue; }
            long size = new FileInfo(path).Length; total = checked(total + size);
            if (size > MaxTrackBytes || total > MaxExpandedBytes) throw new InvalidDataException("Soundtrack exceeds its size limit.");
            string captured = path;
            inputs.Add(new(name, size, () => { RejectLinks(captured); return new FileStream(captured, FileMode.Open, FileAccess.Read, FileShare.Read, 262144, true); }));
        }
        return inputs;
    }
    private static string SafeName(string name)
    {
        name = name.Replace('\\', '/'); var parts = name.TrimEnd('/').Split('/');
        if (name.Length is 0 or >512 || name.StartsWith('/') || parts.Any(p => p.Length == 0 || p is "." or ".." ||
            p.EndsWith(' ') || p.EndsWith('.') || p.IndexOfAny(new[] { ':', '\0', '<', '>', '"', '|', '?', '*' }) >= 0 || p.Any(char.IsControl)))
            throw new InvalidDataException("Unsafe soundtrack archive path.");
        return name;
    }
    private static string Absolute(string path) => Path.IsPathFullyQualified(path) ? Path.GetFullPath(path) : throw new ArgumentException("Use an absolute path.");
    private static void RejectLinks(string path)
    {
        for (string? current = Path.GetFullPath(path); current != null; current = Path.GetDirectoryName(current)) {
            // LinkTarget also catches dangling links, for which Exists returns false.
            if (new FileInfo(current).LinkTarget != null || new DirectoryInfo(current).LinkTarget != null ||
                ((File.Exists(current) || Directory.Exists(current)) && (File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0))
                throw new InvalidDataException("Soundtrack paths must not contain symbolic links or junctions.");
        }
    }
    private static void ValidatePcmLength(long length)
    {
        if (length < 12 || length > MaxTrackBytes || (length - 8) % 4 != 0)
            throw new InvalidDataException("PCM must contain an MSU1 header and aligned 16-bit stereo samples (256 MiB maximum per track).");
    }
    private static async Task<string> CopyAsync(Stream input, byte[] prefix, long expectedSize, string destination, Action<long> progress, CancellationToken cancel)
    {
        using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        await using var output = new FileStream(destination, FileMode.CreateNew, FileAccess.Write, FileShare.None, 262144, true);
        await output.WriteAsync(prefix, cancel).ConfigureAwait(false); hash.AppendData(prefix); long done = prefix.Length;
        var buffer = new byte[262144]; int read;
        while ((read = await input.ReadAsync(buffer, cancel).ConfigureAwait(false)) != 0) {
            if (read > expectedSize - done) throw new InvalidDataException("Source soundtrack changed size during import.");
            hash.AppendData(buffer, 0, read); await output.WriteAsync(buffer.AsMemory(0, read), cancel).ConfigureAwait(false);
            done += read; progress(done);
        }
        if (done != expectedSize) throw new InvalidDataException("Truncated soundtrack file.");
        await output.FlushAsync(cancel).ConfigureAwait(false); output.Flush(flushToDisk: true);
        return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
    }
    private static string ContentId(IEnumerable<Track> tracks, CreditFile? credit)
    {
        var text = new StringBuilder("MSU1-COMPANION-V1\n");
        foreach (var t in tracks.OrderBy(x => x.Number)) text.Append(CultureInfo.InvariantCulture, $"{t.Number}:{t.Size}:{t.LoopStart}:{t.Sha256}\n");
        if (credit != null) text.Append(CultureInfo.InvariantCulture, $"credits:{credit.Size}:{credit.Sha256}\n");
        return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(text.ToString()))).ToLowerInvariant();
    }
    private static string? RecognizeCatalog(IEnumerable<Track> verified, CreditFile? credit)
    {
        using var stream = typeof(SoundtrackService).Assembly.GetManifestResourceStream("soundtrack-catalog.json");
        if (stream == null) return null;
        var catalog = JsonSerializer.Deserialize<Catalog>(stream, Json);
        if (catalog?.FormatVersion != 1) throw new InvalidDataException("Unsupported soundtrack catalog.");
        var tracks = verified.OrderBy(x => x.Number).ToArray();
        return catalog.Packs.FirstOrDefault(p => p.Tracks.OrderBy(x => x.Number).SequenceEqual(tracks) && p.Credits == credit)?.Id;
    }
}
