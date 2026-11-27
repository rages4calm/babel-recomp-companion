using System.Diagnostics;
using System.IO.Compression;
using System.Net;
using System.Net.Http.Headers;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;

/// <summary>A release version ordered by Semantic Versioning 2.0 precedence (beta.21 is newer than beta.9).</summary>
public sealed class ReleaseVersion : IComparable<ReleaseVersion>, IEquatable<ReleaseVersion>
{
    private static readonly Regex Pattern = new(@"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?(?:\+[0-9A-Za-z.-]+)?$", RegexOptions.CultureInvariant);
    public int Major { get; } public int Minor { get; } public int Patch { get; }
    public IReadOnlyList<string> Prerelease { get; }
    private ReleaseVersion(int major, int minor, int patch, string[] pre) { Major = major; Minor = minor; Patch = patch; Prerelease = pre; }

    public static bool TryParse(string? text, out ReleaseVersion version)
    {
        version = null!;
        var match = Pattern.Match(text?.Trim() ?? "");
        if (!match.Success || !int.TryParse(match.Groups[1].Value, out var a) || !int.TryParse(match.Groups[2].Value, out var b) || !int.TryParse(match.Groups[3].Value, out var c)) return false;
        var pre = match.Groups[4].Success ? match.Groups[4].Value.Split('.') : Array.Empty<string>();
        if (pre.Any(id => id.Length > 1 && id[0] == '0' && id.All(char.IsAsciiDigit))) return false;   // no leading zeros in numeric identifiers
        version = new ReleaseVersion(a, b, c, pre); return true;
    }
    public static ReleaseVersion Parse(string text) => TryParse(text, out var v) ? v : throw new FormatException("Not a release version: " + text);

    public int CompareTo(ReleaseVersion? other)
    {
        if (other is null) return 1;
        int core = Major != other.Major ? Major.CompareTo(other.Major) : Minor != other.Minor ? Minor.CompareTo(other.Minor) : Patch.CompareTo(other.Patch);
        if (core != 0) return core;
        if (Prerelease.Count == 0 || other.Prerelease.Count == 0)   // a release outranks its own pre-releases
            return Prerelease.Count == other.Prerelease.Count ? 0 : Prerelease.Count == 0 ? 1 : -1;
        for (int i = 0; i < Math.Min(Prerelease.Count, other.Prerelease.Count); i++) {
            string x = Prerelease[i], y = other.Prerelease[i];
            bool xn = x.All(char.IsAsciiDigit), yn = y.All(char.IsAsciiDigit);
            int step = xn && yn ? (x.Length != y.Length ? x.Length.CompareTo(y.Length) : string.CompareOrdinal(x, y))
                : xn ? -1 : yn ? 1 : string.CompareOrdinal(x, y);
            if (step != 0) return Math.Sign(step);
        }
        return Prerelease.Count.CompareTo(other.Prerelease.Count);
    }
    public bool Equals(ReleaseVersion? other) => CompareTo(other) == 0;
    public override bool Equals(object? obj) => obj is ReleaseVersion v && Equals(v);
    public override int GetHashCode() => ToString().GetHashCode();
    public override string ToString() => $"{Major}.{Minor}.{Patch}" + (Prerelease.Count == 0 ? "" : "-" + string.Join('.', Prerelease));
    /// <summary>"beta 22" for 0.2.0-beta.22, otherwise the full version.</summary>
    public string ShortLabel => Prerelease.Count == 2 && Prerelease[1].All(char.IsAsciiDigit) ? $"{Prerelease[0]} {Prerelease[1]}" : ToString();
    public static bool operator >(ReleaseVersion a, ReleaseVersion b) => a.CompareTo(b) > 0;
    public static bool operator <(ReleaseVersion a, ReleaseVersion b) => a.CompareTo(b) < 0;
}

public sealed record UpdateAsset(string Name, Uri Url, long Size, string? Sha256);
public sealed record UpdateRelease(ReleaseVersion Version, string Tag, string Title, string Notes, UpdateAsset Zip, UpdateAsset? ChecksumFile, Uri? Page)
{
    /// <summary>The single top folder inside the zip, which is also the zip's name.</summary>
    public string TopFolder => Zip.Name[..^4];
    public string FolderName => "v" + Version;
}
public sealed record UpdateCheck(ReleaseVersion? Current, UpdateRelease? Latest)
{
    public bool IsNewer => Latest != null && (Current == null || Latest.Version > Current);
}
public sealed record UpdateProgress(string Phase, long Done, long Total);
public sealed record InstallResult(string NewDirectory, int FilesCarried, IReadOnlyList<string> MovedFolders, IReadOnlyList<string> Shortcuts, IReadOnlyList<string> Warnings);
public sealed record FinishResult(string State, string? OldDirectory, IReadOnlyList<string> Kept, string Message);

/// <summary>Clear, player-facing failure; the message is shown as is.</summary>
public sealed class UpdateException : Exception { public UpdateException(string message, Exception? inner = null) : base(message, inner) { } }

/// <summary>
/// Finds, verifies and installs a newer Companion build beside the current one.
/// Nothing is installed unless the player asks; all writes stay inside the
/// folder that holds the install (plus the player's own shortcuts that point at it).
/// Test hooks: GAIA_UPDATE_FEED (http(s) URL or file path of a releases JSON;
/// loopback http allowed only then), GAIA_UPDATE_SHORTCUT_DIRS (';'-separated).
/// </summary>
public static class UpdateService
{
    public const string DefaultFeed = "https://api.github.com/repos/rages4calm/babel-recomp-companion/releases?per_page=50";
    public const string FeedVariable = "GAIA_UPDATE_FEED", ShortcutVariable = "GAIA_UPDATE_SHORTCUT_DIRS";
    public const string LauncherName = "illusion-of-gaia.Companion.exe", EngineName = "babel-recomp.exe";
    public const string ManifestName = ".companion-package.json", MarkerName = ".companion-update.json";
    private const string WorkPrefix = ".companion-update-", OldPrefix = ".companion-old-", LockName = ".companion-update.lock";
    private const string UserAgent = "IllusionOfGaiaCompanion-Updater";
    private static readonly string[] PlayerFolders = { "UserData", "saves", "msu1", "screenshots", "diagnostics", "logs" };
    private static readonly string[] PlayerFiles = { "config.ini", "keybinds.ini", "rom.cfg", "gaia-launcher.ico", "mods/preloaded/state.toml" };
    /// <summary>Text files that may store absolute paths into the install (the soundtrack pack, the ROM).</summary>
    private static readonly string[] PathFiles = { "config.ini", "rom.cfg", "mods/preloaded/state.toml" };
    private static readonly string[] AlwaysMoved = { "msu1" };
    private const long MoveThreshold = 64L << 20;
    private const long MaxPackageBytes = 2L << 30;
    private static readonly JsonSerializerOptions Json = new() { WriteIndented = true };

    // ---------- version ----------

    /// <summary>The running build: the launcher's stamped version, else the version string inside the engine.</summary>
    public static ReleaseVersion? CurrentVersion(string installDirectory, Assembly? launcher = null)
    {
        var informational = (launcher ?? Assembly.GetEntryAssembly())?.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion;
        if (ReleaseVersion.TryParse(informational, out var stamped) && stamped.ToString() != "1.0.0") return stamped;
        return EngineVersion(Path.Combine(installDirectory, EngineName));
    }

    /// <summary>Release engines carry "&lt;rom id&gt;\0&lt;VERSION&gt;\0" (the lobby pin); "dev" builds have none.</summary>
    public static ReleaseVersion? EngineVersion(string engine)
    {
        try {
            if (!File.Exists(engine)) return null;
            var data = File.ReadAllBytes(engine);
            var marker = Encoding.ASCII.GetBytes("illusionofgaiausa-usa\0");
            var at = data.AsSpan().IndexOf(marker);
            if (at < 0) return null;
            var start = at + marker.Length; var end = Array.IndexOf(data, (byte)0, start, Math.Min(64, data.Length - start));
            return end > start && ReleaseVersion.TryParse(Encoding.ASCII.GetString(data, start, end - start), out var v) ? v : null;
        } catch (Exception error) when (error is IOException or UnauthorizedAccessException) { return null; }
    }

    // ---------- feed ----------

    public static bool UsingTestFeed => !string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable(FeedVariable));
    /// <summary>
    /// A test feed on another host may serve from anywhere (loopback, a fixture); one that is GitHub's own
    /// HTTPS API keeps the production host policy, so a test run against GitHub proves where redirects land.
    /// </summary>
    public static bool RelaxedHosts => UsingTestFeed && !(Uri.TryCreate(Environment.GetEnvironmentVariable(FeedVariable), UriKind.Absolute, out var feed)
        && feed.Scheme == Uri.UriSchemeHttps && feed.IsDefaultPort && string.Equals(feed.Host, "api.github.com", StringComparison.OrdinalIgnoreCase));
    /// <summary>Test hook: each HTTP request as (requested URL, final URL after redirects, status).</summary>
    public static Action<Uri, Uri?, int>? Trace;

    /// <summary>The newest non-draft release (pre-releases included) that carries this platform's zip.</summary>
    public static UpdateRelease? PickLatest(string feedJson)
    {
        using var document = JsonDocument.Parse(feedJson);
        if (document.RootElement.ValueKind != JsonValueKind.Array) throw new UpdateException("The release list had an unexpected shape.");
        UpdateRelease? best = null;
        foreach (var release in document.RootElement.EnumerateArray()) {
            if (Bool(release, "draft")) continue;
            var tag = Text(release, "tag_name");
            if (!ReleaseVersion.TryParse(tag, out var version)) continue;
            var expected = $"babel-recomp-{version}-windows-x86_64.zip";
            UpdateAsset? zip = null, sums = null;
            if (release.TryGetProperty("assets", out var assets) && assets.ValueKind == JsonValueKind.Array)
                foreach (var asset in assets.EnumerateArray()) {
                    var name = Text(asset, "name");
                    if (!Uri.TryCreate(Text(asset, "browser_download_url"), UriKind.Absolute, out var url)) continue;
                    var size = asset.TryGetProperty("size", out var s) && s.TryGetInt64(out var n) ? n : 0;
                    var digest = Text(asset, "digest");
                    var sha = digest.StartsWith("sha256:", StringComparison.OrdinalIgnoreCase) && Regex.IsMatch(digest[7..], "^[0-9a-fA-F]{64}$") ? digest[7..].ToLowerInvariant() : null;
                    if (string.Equals(name, expected, StringComparison.Ordinal)) zip = new(name, url, size, sha);
                    else if (string.Equals(name, expected + ".sha256", StringComparison.Ordinal)) sums = new(name, url, size, sha);
                }
            if (zip == null || (best != null && !(version > best.Version))) continue;
            Uri.TryCreate(Text(release, "html_url"), UriKind.Absolute, out var page);
            var title = Text(release, "name");
            best = new(version, tag, title.Length == 0 ? tag : title, PlainText(Text(release, "body")), zip, sums, page);
        }
        return best;
    }
    private static string Text(JsonElement e, string name) => e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() ?? "" : "";
    private static bool Bool(JsonElement e, string name) => e.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.True;

    /// <summary>Release notes are Markdown; show them as readable plain text.</summary>
    public static string PlainText(string markdown)
    {
        var text = markdown.Replace("\r\n", "\n");
        text = Regex.Replace(text, @"!\[([^\]]*)\]\([^)]*\)", "$1");
        text = Regex.Replace(text, @"\[([^\]]+)\]\(([^)\s]+)\)", "$1");
        text = Regex.Replace(text, @"(?m)^#{1,6}[ \t]+", "");
        text = Regex.Replace(text, @"(\*\*|__)(.+?)\1", "$2");
        text = Regex.Replace(text, @"(?m)^([ \t]*)[*+][ \t]+", "$1- ");
        text = text.Replace("`", "");
        text = Regex.Replace(text, @"<[^>\n]+>", "");
        text = Regex.Replace(text, @"\n{3,}", "\n\n");
        return text.Trim().Replace("\n", "\r\n");
    }

    public static HttpClient CreateClient()
    {
        var handler = new HttpClientHandler { AllowAutoRedirect = true, MaxAutomaticRedirections = 5, UseCookies = false, CheckCertificateRevocationList = false };
        var client = new HttpClient(handler) { Timeout = Timeout.InfiniteTimeSpan };
        client.DefaultRequestHeaders.UserAgent.Add(new ProductInfoHeaderValue(UserAgent, "1"));
        return client;
    }

    /// <summary>Only HTTPS to GitHub. A test feed may also use plain HTTP on this computer (loopback).</summary>
    public static void RequireAllowed(Uri url)
    {
        if (url.Scheme == Uri.UriSchemeHttps) {
            var host = url.Host.ToLowerInvariant();
            if (RelaxedHosts) return;
            if (url.IsDefaultPort && (host is "api.github.com" or "github.com" || host.EndsWith(".githubusercontent.com", StringComparison.Ordinal))) return;
        }
        if (RelaxedHosts && url.Scheme == Uri.UriSchemeHttp && url.IsLoopback) return;
        throw new UpdateException($"Refused to download from {url.Scheme}://{url.Host}: updates only come over HTTPS from GitHub.");
    }

    public static async Task<UpdateCheck> CheckAsync(string installDirectory, HttpClient? client = null, CancellationToken cancel = default)
    {
        var current = CurrentVersion(installDirectory);
        var feed = Environment.GetEnvironmentVariable(FeedVariable);
        string json;
        if (!string.IsNullOrWhiteSpace(feed) && !feed.Contains("://")) json = await File.ReadAllTextAsync(feed, cancel).ConfigureAwait(false);
        else {
            var url = new Uri(string.IsNullOrWhiteSpace(feed) ? DefaultFeed : feed);
            RequireAllowed(url);
            var owned = client == null; client ??= CreateClient();
            try {
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancel); timeout.CancelAfter(TimeSpan.FromSeconds(20));
                using var request = new HttpRequestMessage(HttpMethod.Get, url);
                request.Headers.Accept.ParseAdd("application/vnd.github+json"); request.Headers.Add("X-GitHub-Api-Version", "2022-11-28");
                using var response = await Send(client, request, timeout.Token, cancel).ConfigureAwait(false);
                await RequireSuccess(response).ConfigureAwait(false);
                json = await response.Content.ReadAsStringAsync(timeout.Token).ConfigureAwait(false);
            } finally { if (owned) client.Dispose(); }
        }
        try { return new(current, PickLatest(json)); }
        catch (JsonException error) { throw new UpdateException("The release list could not be read. Try again later.", error); }
    }

    private static async Task<HttpResponseMessage> Send(HttpClient client, HttpRequestMessage request, CancellationToken token, CancellationToken player)
    {
        var requested = request.RequestUri!;   // HttpClient rewrites RequestUri when it follows a redirect
        try {
            var response = await client.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, token).ConfigureAwait(false);
            Trace?.Invoke(requested, response.RequestMessage?.RequestUri, (int)response.StatusCode);
            if (response.RequestMessage?.RequestUri is { } final) RequireAllowed(final);
            return response;
        } catch (OperationCanceledException) when (!player.IsCancellationRequested) {
            throw new UpdateException("GitHub did not answer in time. Check your internet connection and try again.");
        } catch (HttpRequestException error) {
            throw new UpdateException("Could not reach GitHub. Check your internet connection and try again.", error);
        }
    }

    private static async Task RequireSuccess(HttpResponseMessage response)
    {
        if (response.IsSuccessStatusCode) return;
        var limited = response.Headers.TryGetValues("X-RateLimit-Remaining", out var left) && left.FirstOrDefault() == "0";
        if (limited || response.StatusCode == (HttpStatusCode)429) {
            var when = response.Headers.TryGetValues("X-RateLimit-Reset", out var reset) && long.TryParse(reset.FirstOrDefault(), out var epoch)
                ? " after " + DateTimeOffset.FromUnixTimeSeconds(epoch).ToLocalTime().ToString("t") : " in a little while";
            throw new UpdateException($"GitHub is limiting update checks from this network right now. Try again{when}.");
        }
        await Task.CompletedTask;
        throw new UpdateException($"GitHub answered {(int)response.StatusCode} {response.ReasonPhrase}. Try again later.");
    }

    // ---------- download and verification ----------

    /// <summary>Downloads the zip and refuses it unless it matches every checksum GitHub publishes for it.</summary>
    public static async Task<string> DownloadAsync(UpdateRelease release, string destination, IProgress<UpdateProgress>? progress = null, HttpClient? client = null, CancellationToken cancel = default)
    {
        var owned = client == null; client ??= CreateClient();
        try {
            string? published = null;
            if (release.ChecksumFile != null) {
                RequireAllowed(release.ChecksumFile.Url);
                using var request = new HttpRequestMessage(HttpMethod.Get, release.ChecksumFile.Url);
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancel); timeout.CancelAfter(TimeSpan.FromSeconds(30));
                using var response = await Send(client, request, timeout.Token, cancel).ConfigureAwait(false);
                await RequireSuccess(response).ConfigureAwait(false);
                published = ParseChecksumFile(await response.Content.ReadAsStringAsync(timeout.Token).ConfigureAwait(false), release.Zip.Name);
            }
            if (release.Zip.Sha256 == null && published == null)
                throw new UpdateException("This release has no published checksum, so the download cannot be verified. It was not installed.");
            if (release.Zip.Sha256 != null && published != null && release.Zip.Sha256 != published)
                throw new UpdateException("The release's two published checksums disagree. Nothing was installed; please report this.");

            RequireAllowed(release.Zip.Url);
            string actual;
            var partial = destination + ".partial";
            try {
                using var request = new HttpRequestMessage(HttpMethod.Get, release.Zip.Url);
                request.Headers.Accept.ParseAdd("application/octet-stream");
                using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancel); timeout.CancelAfter(TimeSpan.FromMinutes(30));
                using var response = await Send(client, request, timeout.Token, cancel).ConfigureAwait(false);
                await RequireSuccess(response).ConfigureAwait(false);
                var total = response.Content.Headers.ContentLength ?? release.Zip.Size;
                if (total > MaxPackageBytes) throw new UpdateException("The download is far larger than a Companion build. It was refused.");
                using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
                await using (var input = await response.Content.ReadAsStreamAsync(timeout.Token).ConfigureAwait(false))
                await using (var output = new FileStream(partial, FileMode.CreateNew, FileAccess.Write, FileShare.None, 1 << 16, true)) {
                    var buffer = new byte[1 << 16]; long done = 0; int read;
                    while ((read = await input.ReadAsync(buffer, timeout.Token).ConfigureAwait(false)) > 0) {
                        hash.AppendData(buffer, 0, read); await output.WriteAsync(buffer.AsMemory(0, read), timeout.Token).ConfigureAwait(false);
                        done += read; if (done > MaxPackageBytes) throw new UpdateException("The download is far larger than a Companion build. It was refused.");
                        progress?.Report(new("Downloading", done, total));
                    }
                    await output.FlushAsync(timeout.Token).ConfigureAwait(false);
                }
                actual = Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
            } catch (OperationCanceledException) when (!cancel.IsCancellationRequested) {
                throw new UpdateException("The download stalled. Check your connection and try again.");
            } catch (IOException error) {
                throw new UpdateException("The download was interrupted: " + error.Message, error);
            } catch (HttpRequestException error) {
                throw new UpdateException("The download was interrupted. Check your connection and try again.", error);
            }
            var expected = release.Zip.Sha256 ?? published!;
            if (!string.Equals(actual, expected, StringComparison.Ordinal)) {
                TryDelete(partial);
                throw new UpdateException($"The download does not match its published checksum (expected {expected[..12]}…, got {actual[..12]}…). It was deleted and nothing was installed.");
            }
            File.Move(partial, destination, false);
            return actual;
        } finally { if (owned) client.Dispose(); TryDelete(destination + ".partial"); }
    }

    /// <summary>Reads "&lt;hex&gt; *name" (sha256sum) or a bare hash.</summary>
    public static string ParseChecksumFile(string text, string zipName)
    {
        foreach (var line in text.Split('\n').Select(x => x.Trim()).Where(x => x.Length > 0)) {
            var match = Regex.Match(line, @"^([0-9a-fA-F]{64})(?:\s+\*?(.+))?$");
            if (match.Success && (!match.Groups[2].Success || match.Groups[2].Value.Trim() == zipName)) return match.Groups[1].Value.ToLowerInvariant();
        }
        throw new UpdateException("The release's .sha256 file could not be read, so the download cannot be verified.");
    }

    // ---------- zip validation ----------

    /// <summary>
    /// Extracts into <paramref name="staging"/> after checking every entry: one top folder named
    /// <paramref name="topFolder"/>, no absolute paths, drive letters or "..", the required programs present.
    /// Returns the package's files relative to the top folder ('/'-separated).
    /// </summary>
    public static IReadOnlyList<string> ExtractVerified(string zipPath, string staging, string topFolder)
    {
        var root = Path.GetFullPath(staging); Directory.CreateDirectory(root);
        var rootPrefix = root.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        using var zip = ZipFile.OpenRead(zipPath);
        var files = new List<string>(); var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase); long total = 0;
        foreach (var entry in zip.Entries) {
            var name = entry.FullName.Replace('\\', '/');
            var parts = name.Split('/');
            if (name.StartsWith('/') || name.Contains(':') || parts.Any(p => p is ".." or ".") || Path.IsPathRooted(name) || name.Contains('\0'))
                throw new UpdateException($"The package contains an unsafe path ({entry.FullName}). It was refused.");
            if (parts[0] != topFolder || parts.Length < 2)
                throw new UpdateException($"The package is not laid out as expected (found {entry.FullName}). It was refused.");
            var relative = string.Join('/', parts.Skip(1));
            if (relative.Length == 0 || name.EndsWith('/')) continue;
            if (parts.Skip(1).Any(p => p.Length == 0)) throw new UpdateException($"The package contains an unsafe path ({entry.FullName}). It was refused.");
            if (!seen.Add(relative)) throw new UpdateException($"The package lists {relative} twice. It was refused.");
            total += entry.Length; if (total > MaxPackageBytes) throw new UpdateException("The package unpacks to far more than a Companion build. It was refused.");
            var target = Path.GetFullPath(Path.Combine(root, name));
            if (!target.StartsWith(rootPrefix, StringComparison.OrdinalIgnoreCase)) throw new UpdateException($"The package contains an unsafe path ({entry.FullName}). It was refused.");
            files.Add(relative);
        }
        foreach (var required in new[] { EngineName, LauncherName, "illusion-of-gaia.Companion.dll" })
            if (!seen.Contains(required)) throw new UpdateException($"The package is missing {required}. It was refused.");
        foreach (var entry in zip.Entries) {
            var name = entry.FullName.Replace('\\', '/');
            if (name.EndsWith('/')) continue;
            var target = Path.GetFullPath(Path.Combine(root, name));
            Directory.CreateDirectory(Path.GetDirectoryName(target)!);
            entry.ExtractToFile(target, false);
        }
        return files;
    }

    // ---------- install ----------

    public static string InstallDirectory => Path.GetFullPath(AppContext.BaseDirectory).TrimEnd(Path.DirectorySeparatorChar);
    public static bool IsInstalledRelease(string directory) => File.Exists(Path.Combine(directory, EngineName)) && File.Exists(Path.Combine(directory, LauncherName));

    public static bool IsGameRunning(string installDirectory)
    {
        return RunningImage.IsRunning(Path.Combine(installDirectory, EngineName));
    }

    private sealed record PackageManifest(string Version, List<string> Files);
    private sealed record Marker(string From, string FromVersion, string Version, int LauncherProcess, List<string> Carried);
    private sealed record CarryPlan(List<string> Files, List<string> MoveEntries, List<string> Rewrite);

    /// <summary>Decides what in the old install belongs to the player rather than the package.</summary>
    private static CarryPlan PlanCarryOver(string oldDir, ISet<string> newPackage)
    {
        HashSet<string>? oldPackage = null;
        try {
            var manifest = Path.Combine(oldDir, ManifestName);
            if (File.Exists(manifest)) oldPackage = new(JsonSerializer.Deserialize<PackageManifest>(File.ReadAllText(manifest))?.Files ?? new(), StringComparer.OrdinalIgnoreCase);
        } catch (JsonException) { oldPackage = null; }
        var plan = new CarryPlan(new(), new(), new());
        var always = new HashSet<string>(PlayerFiles, StringComparer.OrdinalIgnoreCase);
        void Visit(DirectoryInfo dir, string relative) {
            foreach (var entry in dir.EnumerateFileSystemInfos()) {
                var rel = relative.Length == 0 ? entry.Name : relative + "/" + entry.Name;
                if (relative.Length == 0 && (entry.Name is ManifestName or MarkerName or LockName || entry.Name.StartsWith(WorkPrefix, StringComparison.OrdinalIgnoreCase))) continue;
                var playerTree = PlayerFolders.Any(f => rel.Equals(f, StringComparison.OrdinalIgnoreCase) || rel.StartsWith(f + "/", StringComparison.OrdinalIgnoreCase));
                if ((entry.Attributes & FileAttributes.ReparsePoint) != 0) {
                    // A link (often a soundtrack kept on another drive): move the link itself, never read through it.
                    if (!newPackage.Contains(rel) && !newPackage.Any(p => p.StartsWith(rel + "/", StringComparison.OrdinalIgnoreCase))) plan.MoveEntries.Add(rel);
                    continue;
                }
                if (entry is DirectoryInfo sub) {
                    var topMove = relative.Length == 0 && playerTree && !newPackage.Any(p => p.StartsWith(rel + "/", StringComparison.OrdinalIgnoreCase))
                        && (AlwaysMoved.Contains(entry.Name, StringComparer.OrdinalIgnoreCase) || Size(sub) > MoveThreshold);
                    if (topMove) plan.MoveEntries.Add(rel); else Visit(sub, rel);
                    continue;
                }
                if (newPackage.Contains(rel)) continue;                              // the new build's own file wins
                if (!playerTree && !always.Contains(rel) && oldPackage != null && oldPackage.Contains(rel)) continue;   // a file the old package shipped
                plan.Files.Add(rel);
                if (PathFiles.Contains(rel, StringComparer.OrdinalIgnoreCase)) plan.Rewrite.Add(rel);
            }
        }
        Visit(new DirectoryInfo(oldDir), "");
        return plan;
    }
    private static long Size(DirectoryInfo dir)
    {
        long total = 0;
        foreach (var e in dir.EnumerateFileSystemInfos()) {
            if ((e.Attributes & FileAttributes.ReparsePoint) != 0) continue;
            total += e is FileInfo f ? f.Length : Size((DirectoryInfo)e);
            if (total > MoveThreshold) return total;
        }
        return total;
    }

    /// <summary>Copies a player text file, pointing paths that named the old folder at the new one.
    /// mods/preloaded/state.toml is always written without a BOM, which is how the game writes it.</summary>
    public static byte[] RewriteText(byte[] bytes, string oldDir, string newDir, bool stripBom)
    {
        var bom = bytes.AsSpan().StartsWith(new byte[] { 239, 187, 191 });
        string text;
        try { text = new UTF8Encoding(false, true).GetString(bytes, bom ? 3 : 0, bytes.Length - (bom ? 3 : 0)); }
        catch (DecoderFallbackException) { return bytes; }   // not UTF-8 text: carry the exact bytes
        var forms = new[] {
            (oldDir, newDir),
            (oldDir.Replace("\\", "\\\\"), newDir.Replace("\\", "\\\\")),
            (oldDir.Replace('\\', '/'), newDir.Replace('\\', '/'))
        }.Distinct();
        foreach (var (from, to) in forms)
            text = Regex.Replace(text, Regex.Escape(from) + @"(?=[\\/""'\r\n]|$)", to.Replace("$", "$$"), RegexOptions.IgnoreCase);
        var encoding = new UTF8Encoding(bom && !stripBom);
        return encoding.GetPreamble().Concat(encoding.GetBytes(text)).ToArray();
    }

    public sealed class InstallOptions
    {
        public IReadOnlyList<string>? ShortcutDirectories { get; init; }
        /// <summary>Test hook: called before each step ("copy:&lt;path&gt;", "move:&lt;path&gt;", "marker"); throwing simulates a failure there.</summary>
        public Action<string>? Step { get; init; }
        public int LauncherProcess { get; init; } = Environment.ProcessId;
    }

    /// <summary>
    /// Unpacks a verified zip beside <paramref name="oldDir"/> as v&lt;version&gt;, carries the player's data over
    /// and retargets shortcuts. Any failure before the end puts everything back: the current install keeps working.
    /// </summary>
    public static InstallResult Install(string oldDir, UpdateRelease release, string zipPath, string workDir, InstallOptions? options = null, IProgress<UpdateProgress>? progress = null, CancellationToken cancel = default)
    {
        options ??= new();
        oldDir = Path.GetFullPath(oldDir).TrimEnd(Path.DirectorySeparatorChar);
        var parent = Path.GetDirectoryName(oldDir) ?? throw new UpdateException("The game cannot be updated from a drive's root folder.");
        var target = Path.Combine(parent, release.FolderName);
        if (string.Equals(target, oldDir, StringComparison.OrdinalIgnoreCase)) throw new UpdateException("This build is already installed here.");
        if (Directory.Exists(target) || File.Exists(target))
            throw new UpdateException($"A folder named {release.FolderName} already exists next to this install. Rename or remove it, then try again.");
        if (IsGameRunning(oldDir)) throw new UpdateException("Close the game first. It must not be running while it is updated.");
        if (!Path.GetFullPath(workDir).StartsWith(parent + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) throw new UpdateException("Internal error: the update folder must sit beside the install.");

        progress?.Report(new("Unpacking", 0, 1));
        var extract = Path.Combine(workDir, "extract");
        var files = ExtractVerified(zipPath, extract, release.TopFolder);
        var package = new HashSet<string>(files, StringComparer.OrdinalIgnoreCase);
        var staged = Path.Combine(extract, release.TopFolder);
        File.WriteAllText(Path.Combine(staged, ManifestName), JsonSerializer.Serialize(new PackageManifest(release.Version.ToString(), files.ToList()), Json), new UTF8Encoding(false));
        var plan = PlanCarryOver(oldDir, package);
        long need = plan.Files.Sum(f => new FileInfo(Path.Combine(oldDir, f)).Length) + (32L << 20);
        try { if (new DriveInfo(parent).AvailableFreeSpace < need) throw new UpdateException("There is not enough free disk space to copy your saves and settings."); }
        catch (ArgumentException) { }
        cancel.ThrowIfCancellationRequested();

        var moved = new List<string>(); bool created = false;
        try {
            Directory.Move(staged, target); created = true;
            int done = 0;
            foreach (var rel in plan.Files) {
                cancel.ThrowIfCancellationRequested();
                options.Step?.Invoke("copy:" + rel);
                var source = Path.Combine(oldDir, rel); var destination = Path.Combine(target, rel);
                Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
                if (plan.Rewrite.Contains(rel)) {
                    var bytes = RewriteText(File.ReadAllBytes(source), oldDir, target, rel.Equals("mods/preloaded/state.toml", StringComparison.OrdinalIgnoreCase));
                    using (var output = new FileStream(destination, FileMode.CreateNew, FileAccess.Write, FileShare.None)) { output.Write(bytes); output.Flush(true); }
                    File.SetLastWriteTimeUtc(destination, File.GetLastWriteTimeUtc(source));
                } else File.Copy(source, destination, false);
                progress?.Report(new("Copying your saves and settings", ++done, plan.Files.Count));
            }
            options.Step?.Invoke("marker");
            File.WriteAllText(Path.Combine(target, MarkerName), JsonSerializer.Serialize(
                new Marker(oldDir, CurrentVersion(oldDir)?.ToString() ?? "", release.Version.ToString(), options.LauncherProcess, plan.Files.Concat(plan.MoveEntries).ToList()), Json), new UTF8Encoding(false));
            // Large folders last, by rename on the same drive: instant, and reversible.
            foreach (var rel in plan.MoveEntries) {
                cancel.ThrowIfCancellationRequested();
                options.Step?.Invoke("move:" + rel);
                var source = Path.Combine(oldDir, rel); var destination = Path.Combine(target, rel);
                Directory.CreateDirectory(Path.GetDirectoryName(destination)!);
                if (Directory.Exists(source)) Directory.Move(source, destination); else File.Move(source, destination);
                moved.Add(rel);
                options.Step?.Invoke("moved:" + rel);
                progress?.Report(new("Moving " + rel, moved.Count, plan.MoveEntries.Count));
            }
        } catch (Exception error) {
            var problems = new List<string>();
            for (int i = moved.Count - 1; i >= 0; i--) {
                try {
                    var from = Path.Combine(target, moved[i]); var back = Path.Combine(oldDir, moved[i]);
                    if (Directory.Exists(from)) Directory.Move(from, back); else File.Move(from, back);
                } catch (Exception undo) { problems.Add($"{moved[i]} is still in {target} ({undo.Message})"); }
            }
            if (created && problems.Count == 0) { try { DeleteTree(target); } catch (Exception undo) { problems.Add($"remove {target} by hand ({undo.Message})"); } }
            if (error is OperationCanceledException && problems.Count == 0) throw;
            var why = error is UpdateException ? error.Message : error.Message.TrimEnd('.') + ".";
            throw new UpdateException(problems.Count == 0
                ? $"The update could not be installed: {why} Your current install was left exactly as it was."
                : $"The update failed ({why}) and could not be fully undone: {string.Join("; ", problems)}.", error);
        }

        var warnings = new List<string>(); var shortcuts = new List<string>();
        try { shortcuts.AddRange(RetargetShortcuts(oldDir, target, options.ShortcutDirectories ?? ShortcutDirectories())); }
        catch (Exception error) { warnings.Add("Shortcuts could not be updated: " + error.Message); }
        return new(target, plan.Files.Count, moved, shortcuts, warnings);
    }

    /// <summary>Holds the update lock, works in a folder beside the install, and always cleans that folder up.</summary>
    public static async Task<InstallResult> DownloadAndInstallAsync(string oldDir, UpdateRelease release, IProgress<UpdateProgress>? progress = null, InstallOptions? options = null, HttpClient? client = null, CancellationToken cancel = default)
    {
        oldDir = Path.GetFullPath(oldDir).TrimEnd(Path.DirectorySeparatorChar);
        if (!IsInstalledRelease(oldDir)) throw new UpdateException("This launcher is not running from an installed release folder, so it cannot update itself.");
        var parent = Path.GetDirectoryName(oldDir) ?? throw new UpdateException("The game cannot be updated from a drive's root folder.");
        if (IsGameRunning(oldDir)) throw new UpdateException("Close the game first. It must not be running while it is updated.");
        FileStream gate;
        try { gate = new FileStream(Path.Combine(parent, LockName), FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.None, 1, FileOptions.DeleteOnClose); }
        catch (UnauthorizedAccessException) { throw new UpdateException($"The launcher cannot write to {parent}. Move the game folder somewhere you own (for example your Games folder) to use updates. Administrator rights are never needed."); }
        catch (IOException) { throw new UpdateException("Another update is already running."); }
        var work = Path.Combine(parent, WorkPrefix + Guid.NewGuid().ToString("N")[..8]);
        try {
            Directory.CreateDirectory(work);
            var zip = Path.Combine(work, release.Zip.Name);
            await DownloadAsync(release, zip, progress, client, cancel).ConfigureAwait(false);
            return await Task.Run(() => Install(oldDir, release, zip, work, options, progress, cancel), cancel).ConfigureAwait(false);
        } finally {
            try { if (Directory.Exists(work)) DeleteTree(work); } catch (Exception) { }
            gate.Dispose();
        }
    }

    // ---------- first start of the new build ----------

    public static bool HasPendingFinish(string newDir) => File.Exists(Path.Combine(newDir, MarkerName));
    public static string? PendingSource(string newDir)
    {
        try { return JsonSerializer.Deserialize<Marker>(File.ReadAllText(Path.Combine(newDir, MarkerName)))?.From; }
        catch (Exception error) when (error is IOException or JsonException or UnauthorizedAccessException) { return null; }
    }

    /// <summary>
    /// Run by the new launcher on start: removes the old folder only when everything left in it is a package
    /// file or an identical copy of something now in the new folder. Otherwise it stays, and the player is told.
    /// </summary>
    public static FinishResult FinishPending(string newDir, TimeSpan? wait = null)
    {
        newDir = Path.GetFullPath(newDir).TrimEnd(Path.DirectorySeparatorChar);
        var markerPath = Path.Combine(newDir, MarkerName);
        if (!File.Exists(markerPath)) return new("none", null, Array.Empty<string>(), "");
        Marker? marker;
        try { marker = JsonSerializer.Deserialize<Marker>(File.ReadAllText(markerPath)); }
        catch (JsonException) { marker = null; }
        if (marker == null || string.IsNullOrWhiteSpace(marker.From)) { TryDelete(markerPath); return new("none", null, Array.Empty<string>(), ""); }
        var oldDir = Path.GetFullPath(marker.From).TrimEnd(Path.DirectorySeparatorChar);
        if (!string.Equals(Path.GetDirectoryName(oldDir), Path.GetDirectoryName(newDir), StringComparison.OrdinalIgnoreCase) || string.Equals(oldDir, newDir, StringComparison.OrdinalIgnoreCase)) {
            TryDelete(markerPath); return new("refused", oldDir, Array.Empty<string>(), "The previous folder is not beside this one, so it was left alone.");
        }
        if (!Directory.Exists(oldDir)) { TryDelete(markerPath); return new("gone", oldDir, Array.Empty<string>(), ""); }
        WaitForExit(marker.LauncherProcess, Path.Combine(oldDir, LauncherName), wait ?? TimeSpan.FromSeconds(20));
        if (IsGameRunning(oldDir)) return new("busy", oldDir, Array.Empty<string>(), "The previous version is still running, so its folder was kept for now. It is removed the next time the launcher starts.");

        var package = ReadManifest(newDir); var oldPackage = ReadManifest(oldDir);
        var kept = new List<string>();
        void Visit(string dir, string relative) {
            foreach (var entry in new DirectoryInfo(dir).EnumerateFileSystemInfos()) {
                var rel = relative.Length == 0 ? entry.Name : relative + "/" + entry.Name;
                if ((entry.Attributes & FileAttributes.ReparsePoint) != 0) { kept.Add(rel); continue; }
                if (entry is DirectoryInfo sub) { Visit(sub.FullName, rel); continue; }
                if (relative.Length == 0 && entry.Name is ManifestName or MarkerName) continue;
                if (package.Contains(rel) || oldPackage.Contains(rel)) continue;
                var copy = Path.Combine(newDir, rel);
                if (File.Exists(copy) && SameContent(((FileInfo)entry).FullName, copy, PathFiles.Contains(rel, StringComparer.OrdinalIgnoreCase))) continue;
                kept.Add(rel);
            }
        }
        try { Visit(oldDir, ""); }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException) { return new("busy", oldDir, Array.Empty<string>(), "The previous folder could not be checked yet; it is checked again next time. " + error.Message); }
        if (kept.Count > 0) {
            TryDelete(markerPath);
            var list = string.Join(", ", kept.Take(5)) + (kept.Count > 5 ? $" and {kept.Count - 5} more" : "");
            return new("kept", oldDir, kept, $"The previous folder {oldDir} was kept because it holds files that are not part of the game and were not copied: {list}. Move anything you want, then delete that folder yourself.");
        }
        var doomed = Path.Combine(Path.GetDirectoryName(oldDir)!, OldPrefix + Guid.NewGuid().ToString("N")[..8]);
        try { Directory.Move(oldDir, doomed); }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException) {
            return new("busy", oldDir, Array.Empty<string>(), "The previous folder is still in use, so it was kept for now. It is removed the next time the launcher starts.");
        }
        TryDelete(markerPath);
        try { DeleteTree(doomed); } catch (Exception) { /* hidden leftover; removed by the next update's sweep */ }
        return new("removed", oldDir, Array.Empty<string>(), $"The previous folder {Path.GetFileName(oldDir)} was removed.");
    }

    private static HashSet<string> ReadManifest(string dir)
    {
        try {
            var path = Path.Combine(dir, ManifestName);
            if (File.Exists(path)) return new(JsonSerializer.Deserialize<PackageManifest>(File.ReadAllText(path))?.Files ?? new(), StringComparer.OrdinalIgnoreCase);
        } catch (Exception error) when (error is IOException or JsonException) { }
        return new(StringComparer.OrdinalIgnoreCase);
    }
    private static bool SameContent(string a, string b, bool rewritten)
    {
        if (rewritten) return true;   // carried with paths rewritten; the new copy is the one in use
        var x = new FileInfo(a); var y = new FileInfo(b);
        if (x.Length != y.Length) return false;
        using var sa = x.OpenRead(); using var sb = y.OpenRead();
        return SHA256.HashData(sa).AsSpan().SequenceEqual(SHA256.HashData(sb));
    }
    private static void WaitForExit(int pid, string launcher, TimeSpan wait)
    {
        if (pid <= 0 || pid == Environment.ProcessId) return;
        try {
            using var process = Process.GetProcessById(pid);
            string? path = null; try { path = process.MainModule?.FileName; } catch (Exception) { }
            if (path == null || string.Equals(path, launcher, StringComparison.OrdinalIgnoreCase)) process.WaitForExit((int)wait.TotalMilliseconds);
        } catch (ArgumentException) { } catch (InvalidOperationException) { }
    }

    /// <summary>Old launcher preference values (engine, ROM) that pointed into the previous folder.</summary>
    public static string? Retarget(string? path, string oldDir, string newDir)
    {
        if (string.IsNullOrEmpty(path) || !Path.IsPathFullyQualified(path)) return null;
        var full = Path.GetFullPath(path);
        var prefix = oldDir.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        return full.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) ? Path.Combine(newDir, full[prefix.Length..]) : null;
    }

    // ---------- shortcuts ----------

    public static IReadOnlyList<string> ShortcutDirectories()
    {
        var custom = Environment.GetEnvironmentVariable(ShortcutVariable);
        if (custom != null) return custom.Split(';', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        return new[] { Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), Environment.GetFolderPath(Environment.SpecialFolder.Programs) }
            .Where(d => d.Length > 0).ToArray();
    }

    /// <summary>Points the player's own .lnk files (target, start-in folder, icon) from the old folder to the new one.</summary>
    public static IReadOnlyList<string> RetargetShortcuts(string oldDir, string newDir, IEnumerable<string> directories)
    {
        var changed = new List<string>();
        if (!OperatingSystem.IsWindows()) return changed;
        foreach (var dir in directories.Where(Directory.Exists)) {
            IEnumerable<string> links;
            try { links = Directory.EnumerateFiles(dir, "*.lnk", new EnumerationOptions { RecurseSubdirectories = true, MaxRecursionDepth = 3, IgnoreInaccessible = true, AttributesToSkip = FileAttributes.ReparsePoint }); }
            catch (Exception error) when (error is IOException or UnauthorizedAccessException) { continue; }
            foreach (var link in links) {
                try { if (Shortcut.Retarget(link, oldDir, newDir)) changed.Add(link); }
                catch (Exception error) when (error is COMException or IOException or UnauthorizedAccessException or InvalidCastException) { }
            }
        }
        return changed;
    }

    [System.Runtime.Versioning.SupportedOSPlatform("windows")]
    internal static class Shortcut
    {
        [ComImport, Guid("00021401-0000-0000-C000-000000000046")] private class ShellLink { }
        [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("000214F9-0000-0000-C000-000000000046")]
        private interface IShellLinkW
        {
            void GetPath([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder file, int max, IntPtr data, int flags);
            void GetIDList(out IntPtr list); void SetIDList(IntPtr list);
            void GetDescription([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder name, int max);
            void SetDescription([MarshalAs(UnmanagedType.LPWStr)] string name);
            void GetWorkingDirectory([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder dir, int max);
            void SetWorkingDirectory([MarshalAs(UnmanagedType.LPWStr)] string dir);
            void GetArguments([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder args, int max);
            void SetArguments([MarshalAs(UnmanagedType.LPWStr)] string args);
            void GetHotkey(out short key); void SetHotkey(short key);
            void GetShowCmd(out int cmd); void SetShowCmd(int cmd);
            void GetIconLocation([Out, MarshalAs(UnmanagedType.LPWStr)] StringBuilder path, int max, out int index);
            void SetIconLocation([MarshalAs(UnmanagedType.LPWStr)] string path, int index);
            void SetRelativePath([MarshalAs(UnmanagedType.LPWStr)] string path, int reserved);
            void Resolve(IntPtr hwnd, int flags);
            void SetPath([MarshalAs(UnmanagedType.LPWStr)] string file);
        }
        private const int SLGP_RAWPATH = 4, STGM_READ = 0;

        public static void Create(string link, string target, string workingDirectory, string icon)
        {
            var shell = (IShellLinkW)new ShellLink();
            try {
                shell.SetPath(target); shell.SetWorkingDirectory(workingDirectory); shell.SetIconLocation(icon, 0);
                ((IPersistFile)shell).Save(link, true);
            } finally { Marshal.FinalReleaseComObject(shell); }
        }
        public static (string Target, string WorkingDirectory, string Icon) Read(string link)
        {
            var shell = (IShellLinkW)new ShellLink();
            try {
                ((IPersistFile)shell).Load(link, STGM_READ);
                var a = new StringBuilder(1024); var b = new StringBuilder(1024); var c = new StringBuilder(1024);
                shell.GetPath(a, a.Capacity, IntPtr.Zero, SLGP_RAWPATH); shell.GetWorkingDirectory(b, b.Capacity); shell.GetIconLocation(c, c.Capacity, out _);
                return (a.ToString(), b.ToString(), c.ToString());
            } finally { Marshal.FinalReleaseComObject(shell); }
        }
        public static bool Retarget(string link, string oldDir, string newDir)
        {
            var shell = (IShellLinkW)new ShellLink();
            try {
                ((IPersistFile)shell).Load(link, STGM_READ);
                var path = new StringBuilder(1024); var work = new StringBuilder(1024); var icon = new StringBuilder(1024);
                shell.GetPath(path, path.Capacity, IntPtr.Zero, SLGP_RAWPATH); shell.GetWorkingDirectory(work, work.Capacity); shell.GetIconLocation(icon, icon.Capacity, out var index);
                bool Inside(string p) => p.Length > 0 && (string.Equals(p.TrimEnd('\\'), oldDir, StringComparison.OrdinalIgnoreCase) || UpdateService.Retarget(Environment.ExpandEnvironmentVariables(p), oldDir, newDir) != null);
                string Move(string p) { var e = Environment.ExpandEnvironmentVariables(p); return string.Equals(e.TrimEnd('\\'), oldDir, StringComparison.OrdinalIgnoreCase) ? newDir : UpdateService.Retarget(e, oldDir, newDir)!; }
                if (!Inside(path.ToString())) return false;
                shell.SetPath(Move(path.ToString()));
                if (Inside(work.ToString())) shell.SetWorkingDirectory(Move(work.ToString()));
                if (Inside(icon.ToString())) shell.SetIconLocation(Move(icon.ToString()), index);
                ((IPersistFile)shell).Save(link, true);
                return true;
            } finally { Marshal.FinalReleaseComObject(shell); }
        }
    }

    // ---------- settings ----------

    private sealed record Settings(bool CheckOnStart);
    private static string SettingsPath(string installDir) => Path.Combine(installDir, "UserData", "Companion", "updates.json");
    public static bool ReadCheckOnStart(string installDir)
    {
        try { return JsonSerializer.Deserialize<Settings>(File.ReadAllText(SettingsPath(installDir)))?.CheckOnStart ?? true; }
        catch (Exception) { return true; }
    }
    public static void WriteCheckOnStart(string installDir, bool value)
    {
        var path = SettingsPath(installDir); Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, JsonSerializer.Serialize(new Settings(value)) + "\n", new UTF8Encoding(false));
    }

    // ---------- helpers ----------

    private static void TryDelete(string path) { try { if (File.Exists(path)) File.Delete(path); } catch (Exception) { } }
    /// <summary>Deletes a tree without following links out of it.</summary>
    public static void DeleteTree(string path)
    {
        var root = new DirectoryInfo(path);
        if (!root.Exists) return;
        if ((root.Attributes & FileAttributes.ReparsePoint) != 0) { root.Delete(false); return; }
        foreach (var entry in root.EnumerateFileSystemInfos()) {
            if (entry is DirectoryInfo sub) {
                if ((sub.Attributes & FileAttributes.ReparsePoint) != 0) sub.Delete(false); else DeleteTree(sub.FullName);
            } else { entry.Attributes &= ~FileAttributes.ReadOnly; entry.Delete(); }
        }
        root.Delete(false);
    }
}
