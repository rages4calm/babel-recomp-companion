param([switch]$Preview)
# One reviewed, immutable cohort; never discover or recursively delete objects.
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
function Safe([string]$path) {
 $p=[IO.Path]::GetFullPath($path)
 if (!$p.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)) { throw "Outside project: $p" }
 for($q=$p;$q.Length -ge $root.Length;$q=[IO.Path]::GetDirectoryName($q)) {
  if (([IO.File]::Exists($q) -or [IO.Directory]::Exists($q)) -and ([IO.File]::GetAttributes($q) -band [IO.FileAttributes]::ReparsePoint)) { throw "Reparse point refused: $q" }
  if($q -eq $root){break}
 }
 return $p
}
if(!(Test-Path -LiteralPath (Join-Path $root 'HANDOFF.md'))){throw 'Project marker missing.'}
$store=Safe (Join-Path $root '.local/project-cleanup/disposable-20261112')
$plan=Safe (Join-Path $store 'obsolete-objects-proposal.json')
if(!(Test-Path -LiteralPath $plan)){Write-Host 'No reviewed obsolete-object plan in this checkout; skipped.';exit 0}
$planHasher=[Security.Cryptography.SHA256]::Create();$planStream=[IO.File]::OpenRead($plan)
try{$planHash=[BitConverter]::ToString($planHasher.ComputeHash($planStream)).Replace('-','')}
finally{$planStream.Dispose();$planHasher.Dispose()}
if($planHash -ne '94F536D11B7ED5F66FCD81934572E808D41D3858FF3A76882111AB928AEF769F'){throw 'Object plan changed; refusing deletion.'}
$data=Get-Content -LiteralPath $plan -Raw | ConvertFrom-Json
if($data.schema -ne 'gaia proposed obsolete CMake objects metadata v1'){throw 'Wrong object plan schema.'}
Add-Type @'
using System;using System.Runtime.InteropServices;using Microsoft.Win32.SafeHandles;
public static class GaiaObjectCleanup {
 [StructLayout(LayoutKind.Sequential)] public struct Info {public uint Attributes;public System.Runtime.InteropServices.ComTypes.FILETIME C,A,W;public uint Volume,Hi,Lo,Links,IndexHi,IndexLo;}
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]static extern SafeFileHandle CreateFile(string p,uint a,uint s,IntPtr sa,uint d,uint f,IntPtr t);
 [DllImport("kernel32.dll",SetLastError=true)]static extern bool GetFileInformationByHandle(SafeFileHandle h,out Info i);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]static extern uint GetCompressedFileSizeW(string p,out uint hi);
 public static Info Stat(string p){using(var h=CreateFile(p,0x80,7,IntPtr.Zero,3,0,IntPtr.Zero)){Info i;if(h.IsInvalid||!GetFileInformationByHandle(h,out i))throw new System.ComponentModel.Win32Exception();return i;}}
 public static ulong Size(string p){uint hi;uint lo=GetCompressedFileSizeW(p,out hi);if(lo==0xffffffff&&Marshal.GetLastWin32Error()!=0)throw new System.ComponentModel.Win32Exception();return ((ulong)hi<<32)|lo;}
 public static ulong Id(Info i){return ((ulong)i.IndexHi<<32)|i.IndexLo;}
}
'@
$leasePath=Safe (Join-Path $root '.local/project-cleanup/run.lock')
$lease=$null
try {
 # FileShare.None also excludes the archival Python tool's OS-backed lease.
 $lease=[IO.File]::Open($leasePath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
} catch {throw 'Another cleanup/validation operation holds the project lease. Wait; do not delete run.lock.'}
$result=[ordered]@{schema='gaia reviewed obsolete objects removal v1';utc=[DateTime]::UtcNow.ToString('o');preview=[bool]$Preview;plan_sha256='94f536d11b7ed5f66fcd81934572e808d41d3858ff3a76882111ab928aef769f';authorization='Coordinator GO: exact source-bound obsolete objects; preserve masters, JSON, source and all016-019 work';files=@();groups=@();logical_bytes_removed=0L;reported_data_allocation_unlinked_last_link=0L;failed=@()}
try {
 $rows=@($data.files | Where-Object {$_.source_exists -eq $true -and $_.source_binding -eq 'build.ninja'})
 if($rows.Count -ne 5261){throw 'Reviewed source-bound object count changed.'}
 foreach($group in ($rows | Group-Object build_root)) {
  $build=Safe (Join-Path $root $group.Name)
  if($group.Name -notmatch '^\.local\\batch-001\\native-(006|007|008|009|010|011|012|013|015)\\(build[^\\]*|framework-baseline-diagnostic\\build-without-258)$'){throw "Unexpected build root: $($group.Name)"}
  $cache=Safe (Join-Path $build 'CMakeCache.txt')
  $cmakeHomeMatch=Select-String -LiteralPath $cache -Pattern '^CMAKE_HOME_DIRECTORY:INTERNAL=(.+)$'
  if(!$cmakeHomeMatch -or [IO.Path]::GetFullPath($cmakeHomeMatch.Matches[0].Groups[1].Value) -ne $root){throw "CMake source home changed: $build"}
  $prefix=$build+'\'
  $busy=@(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object {
   $_.ProcessId -ne $PID -and (($_.ExecutablePath -and $_.ExecutablePath.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)) -or ($_.CommandLine -and $_.CommandLine.IndexOf($build,[StringComparison]::OrdinalIgnoreCase) -ge 0))
  })
  if($busy.Count){$result.failed += "Running consumer: $($group.Name)";continue}
  Write-Host "$(if($Preview){'Preview'}else{'Retiring'}) $($group.Count) exact objects: $($group.Name)"
  $n=0
  foreach($row in $group.Group){
   $p=Safe (Join-Path $root $row.path)
   if(!$p.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase) -or $p -notmatch '\\CMakeFiles\\.+\.(obj|o)$'){throw "Not an allowlisted object: $p"}
   if(![IO.File]::Exists($p)){$result.files += @{path=$row.path;status='already absent'};continue}
   $record=@{path=$row.path;source=$row.source;status='preview'}
   try{
    $source=Safe $row.source
    if(![IO.File]::Exists($source)){throw 'Retained compilation source missing.'}
    $info=[GaiaObjectCleanup]::Stat($p)
    if([GaiaObjectCleanup]::Id($info) -ne [uint64]$row.file_id -or ([IO.FileInfo]$p).Length -ne $row.bytes){throw 'Object identity/length changed since review.'}
    $record.reported_allocated_bytes=[GaiaObjectCleanup]::Size($p);$record.links_before=$info.Links;$record.logical_bytes=$row.bytes
    if(!$Preview){
     [void](Safe $p)
     Remove-Item -LiteralPath $p -Force -ErrorAction Stop
     $record.status='removed';$result.logical_bytes_removed += $row.bytes
     if($info.Links -eq 1){$result.reported_data_allocation_unlinked_last_link += [long]$record.reported_allocated_bytes}
    }
   }catch{$record.status='retained';$record.error=$_.Exception.Message;$result.failed += $row.path}
   $result.files += $record;$n++
   if(($n % 100) -eq 0){Write-Host "  $n / $($group.Count) objects processed"}
  }
  $result.groups += @{build=$group.Name;objects=$group.Count}
 }
}catch{$result.failed += $_.Exception.Message;Write-Warning $_.Exception.Message}
finally{
 $path=Join-Path $store ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssffffZ')+'-objects-result.json')
 $result|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $path -Encoding UTF8
 $lease.Dispose()
 Write-Host "Receipt: $path"
}
Write-Host "Removed logical bytes: $($result.logical_bytes_removed); last-link reported storage: $($result.reported_data_allocation_unlinked_last_link)"
if($result.failed.Count){Write-Warning 'Retained changed, busy or locked files. No locks/permissions forced. Read receipt and rerun.';exit 3}
