param([switch]$Preview)
# Deliberately fixed allowlist. Never broaden this to all of .local or build.
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if (!(Test-Path -LiteralPath (Join-Path $root 'HANDOFF.md')) -or
    !(Test-Path -LiteralPath (Join-Path $root 'docs/PROJECT-CLEANUP.md'))) {
    throw 'Project markers missing. Run the script from its original project.'
}
$relativeTargets = @('.local/batch-001/native-018/classroom-preview/nightclub',
    '.local/batch-001/native-018/build/babel-classroom-nightclub-v1.exe',
    '.local/batch-001/native-018/build/babel-classroom-nightclub-v2.exe',
    '.local/batch-001/native-018/build/babel-renderer-prelim-v1.exe',
    '.local/batch-001/native-018/build/babel-owner-diagnostic-v1.exe')
# Coordinator authorized these superseded private experiments; the classroom
# worker confirmed that only snapshots/source, not these executables, are used.
1..17 | ForEach-Object { $relativeTargets += ".local/batch-001/native-018/build/babel-classroom-preview-v$_.exe" }
function Assert-SafePath([string]$path) {
    $full = [IO.Path]::GetFullPath($path)
    if (!$full.StartsWith($root + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw "Outside project: $full" }
    $cursor = $full
    while ($cursor.Length -ge $root.Length) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point refused: $cursor" }
        }
        if ($cursor -eq $root) { break }
        $cursor = [IO.Path]::GetDirectoryName($cursor)
    }
    return $full
}
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class GaiaCleanupStorage {
 [StructLayout(LayoutKind.Sequential)] public struct Info {
  public uint Attributes; public System.Runtime.InteropServices.ComTypes.FILETIME Creation,Access,Write;
  public uint Volume, SizeHigh, SizeLow, Links, IndexHigh, IndexLow;
 }
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern SafeFileHandle CreateFile(string p,uint a,uint s,IntPtr sa,uint d,uint f,IntPtr t);
 [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetFileInformationByHandle(SafeFileHandle h,out Info i);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern uint GetCompressedFileSizeW(string p,out uint high);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool GetDiskFreeSpaceEx(string p,out ulong available,out ulong total,out ulong free);
 public static Info Stat(string p) { using(var h=CreateFile(p,0x80,7,IntPtr.Zero,3,0,IntPtr.Zero)) { Info i; if(h.IsInvalid||!GetFileInformationByHandle(h,out i)) throw new System.ComponentModel.Win32Exception();return i; } }
 public static ulong Allocated(string p) { uint hi; uint lo=GetCompressedFileSizeW(p,out hi); if(lo==0xffffffff && Marshal.GetLastWin32Error()!=0) throw new System.ComponentModel.Win32Exception();return ((ulong)hi<<32)|lo; }
 public static ulong Free(string p) { ulong a,t,f;if(!GetDiskFreeSpaceEx(p,out a,out t,out f))throw new System.ComponentModel.Win32Exception();return f; }
}
'@
$receiptDir = Join-Path $root '.local/project-cleanup/disposable-20261112'
[void](Assert-SafePath $receiptDir)
[void][IO.Directory]::CreateDirectory($receiptDir)
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssffffZ')
$receiptPath = Join-Path $receiptDir "$stamp-result.json"
$leasePath = Assert-SafePath (Join-Path $root '.local/project-cleanup/run.lock')
try { $lease = [IO.File]::Open($leasePath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None) }
catch { throw 'Another cleanup/validation operation holds the project lease. Wait; do not delete run.lock.' }
$before = [GaiaCleanupStorage]::Free($root)
$result = [ordered]@{ schema='gaia explicit disposable cleanup v1'; utc=[DateTime]::UtcNow.ToString('o'); project=$root; preview=[bool]$Preview; allowlist=$relativeTargets; files=@(); targets=@(); logical_bytes_removed=0L; reported_data_allocation_unlinked_last_link=0L; hardlink_names_removed=0; failed=@(); free_before=$before }
$currentPid = $PID
function Get-Consumers([string]$target) {
    # Failure to inspect process metadata is a refusal, not permission to delete.
    $prefix = $target.TrimEnd('\') + '\'
    @(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
        $_.ProcessId -ne $currentPid -and (
          ($_.ExecutablePath -and ($_.ExecutablePath -eq $target -or $_.ExecutablePath.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase))) -or
          ($_.CommandLine -and $_.CommandLine.IndexOf($target,[StringComparison]::OrdinalIgnoreCase) -ge 0))
    } | Select-Object ProcessId,Name)
}
try {
 foreach ($relative in $relativeTargets) {
    $target = Assert-SafePath (Join-Path $root $relative)
    if (!(Test-Path -LiteralPath $target)) { $result.targets += @{path=$relative;status='already absent'}; continue }
    $consumers = @(Get-Consumers $target)
    if ($consumers.Count) { $result.targets += @{path=$relative;status='running consumer; skipped';processes=$consumers};$result.failed += $relative;continue }
    Write-Host "$(if($Preview){'Preview'}else{'Removing'}): $relative"
    # Explicit traversal rejects junctions before descending; no recursive delete.
    $files = [Collections.Generic.List[string]]::new()
    $dirs = [Collections.Generic.List[string]]::new()
    $todo = [Collections.Generic.Stack[string]]::new();$todo.Push($target)
    while ($todo.Count) {
        $path=Assert-SafePath $todo.Pop();$item=Get-Item -LiteralPath $path -Force
        if ($item.PSIsContainer) {
            $dirs.Add($path)
            foreach($child in Get-ChildItem -LiteralPath $path -Force) { $todo.Push($child.FullName) }
        } else { $files.Add($path) }
    }
    $n=0
    foreach ($path in $files) {
        [void](Assert-SafePath $path)
        $item=Get-Item -LiteralPath $path -Force
        $info=[GaiaCleanupStorage]::Stat($path);$allocated=[GaiaCleanupStorage]::Allocated($path)
        $record=@{path=$path.Substring($root.Length+1);logical_bytes=$item.Length;reported_allocated_bytes=$allocated;links_before=$info.Links;file_id=('{0:X8}:{1:X8}{2:X8}' -f $info.Volume,$info.IndexHigh,$info.IndexLow);status='preview'}
        if (!$Preview) {
            try {
                [void](Assert-SafePath $path)
                # Recheck consumer and link metadata immediately before unlink.
                if (@(Get-Consumers $target).Count) { throw 'Target acquired a running consumer.' }
                $info=[GaiaCleanupStorage]::Stat($path);$record.links_before=$info.Links
                Remove-Item -LiteralPath $path -Force -ErrorAction Stop
                $record.status='removed';$result.logical_bytes_removed += $item.Length
                if ($info.Links -eq 1) { $result.reported_data_allocation_unlinked_last_link += [long]$allocated }
                else { $result.hardlink_names_removed++ }
            } catch { $record.status='retained';$record.error=$_.Exception.Message;$result.failed += $record.path }
        }
        $result.files += $record;$n++
        if (($n % 50) -eq 0) { Write-Host "  $n / $($files.Count) files processed" }
    }
    if (!$Preview) {
        foreach ($dir in ($dirs | Sort-Object Length -Descending)) {
            [void](Assert-SafePath $dir)
            try { [IO.Directory]::Delete($dir,$false) } catch { $result.failed += $dir.Substring($root.Length+1) }
        }
    }
    $result.targets += @{path=$relative;status=$(if($Preview){'previewed'}elseif(Test-Path -LiteralPath $target){'leftovers retained'}else{'removed'});files=$files.Count}
 }
} catch { $result.failed += $_.Exception.Message; Write-Warning $_.Exception.Message }
$result.free_after=[GaiaCleanupStorage]::Free($root)
$result.observed_volume_free_delta=[long]$result.free_after-[long]$before
$result.allocation_note='Last-link NTFS reported file-data allocation only; hardlink removals with surviving names count zero. Volume delta includes concurrent activity; neither measure claims exact total physical disk reclamation.'
$result | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
$lease.Dispose()
Write-Host "Receipt: $receiptPath"
Write-Host "Removed logical bytes: $($result.logical_bytes_removed); last-link reported allocation: $($result.reported_data_allocation_unlinked_last_link); surviving-hardlink names removed: $($result.hardlink_names_removed)"
if ($result.failed.Count) { Write-Warning "Some paths remain. Close their consumers and rerun this same allowlist. No permissions or locks were forced.";exit 3 }
