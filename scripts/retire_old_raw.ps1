param([switch]$Preview)
# Targeted, irreversible retirement of one reviewed historical raw-output cohort.
# JSON/source/state/owner paths are never selected. No discovery, archives or ACL changes.
function Assert-RawRelative([string]$relative) {
 if ([IO.Path]::IsPathRooted($relative) -or $relative.Contains(':')) { throw 'Absolute/stream path refused.' }
 $parts=$relative -split '[\\/]'
 if (@($parts | Where-Object {$_ -eq '..' -or $_ -eq '.' -or $_ -eq ''}).Count) { throw 'Traversal/empty path component refused.' }
 $p=$relative.Replace('\','/')
 if ($p -notmatch '^\.local/batch-001/native-(015|017)/qualification-final/.+') { throw 'Outside reviewed raw roots.' }
 if ($p -match '/(saves|seeds|inputs|reference-inputs|mods|assets)/') { throw 'Input/owner subtree refused.' }
 $ext=[IO.Path]::GetExtension($relative).ToLowerInvariant()
 if ($ext -eq '.bin') { if ($p -notmatch '/snapshots/[^/]+\.bin$') { throw 'Non-snapshot binary refused.' } }
 elseif ($ext -notin @('.ppm','.bmp','.bgrx','.tsv') -and [IO.Path]::GetFileName($relative) -ne 'trace.csv') { throw 'Metadata/state/source extension refused.' }
}
function Assert-ProofSummary([string]$kind,$doc,[string]$binary) {
 if ($doc.passed -isnot [bool] -or !$doc.passed) { throw "Unpassed proof: $kind" }
 switch ($kind) {
  'native105' { if ($doc.pairs -ne 105 -or $doc.captures -ne 210 -or $doc.identity.build_digest -ne $binary -or $doc.schema -ne 'gaia019 fresh105 official capture and native-counter closure v1') { throw 'Native105 closure mismatch.' } }
  'renderer82' { if ($doc.pairs -ne 82 -or $doc.captures -ne 164 -or $doc.complete -isnot [bool] -or !$doc.complete -or $doc.binary_sha256 -ne $binary) { throw 'Renderer82 closure mismatch.' } }
  'rendererIndependent' { if ($doc.pairs -ne 82 -or $doc.captures -ne 164) { throw 'Renderer independent closure mismatch.' } }
  'classroom5' { if ($doc.pairs -ne 5 -or $doc.captures -ne 10 -or $doc.binary_sha256 -ne $binary) { throw 'Classroom closure mismatch.' } }
  'classroomIndependent' { if ($doc.pairs -ne 5 -or $doc.captures -ne 10 -or $doc.binary_sha256 -ne $binary) { throw 'Classroom independent closure mismatch.' } }
  'SDK' { if ($doc.tests_passed -ne 877 -or $doc.skipped -ne 2 -or $doc.warnings -ne 0) { throw 'SDK closure mismatch.' } }
  'engine' { if ($doc.binary_sha256 -ne $binary -or $doc.new_upstream_debug_screenshot.tests_passed -ne 29) { throw 'Core engine closure mismatch.' } }
  default { throw 'Unknown proof kind.' }
 }
}
function Get-RawSha([string]$path) {
 $hash=[Security.Cryptography.SHA256]::Create();$stream=[IO.File]::OpenRead($path)
 try { return [BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
 finally {$stream.Dispose();$hash.Dispose()}
}
# Dot-sourcing exposes only pure contract functions for ROM-free tests.
if ($MyInvocation.InvocationName -eq '.') { return }
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$store=Join-Path $root '.local/project-cleanup/disposable-20261112'
$goPath=Join-Path $store 'RAW-RETIREMENT-GO.json'
if (![IO.File]::Exists($goPath)) { Write-Host 'Skipping old raw retirement: no completed019 coordinator GO marker.';exit 0 }
if (![IO.File]::Exists((Join-Path $root 'HANDOFF.md'))) { throw 'Project marker missing.' }
$completedPath=Join-Path $store 'RAW-RETIREMENT-COMPLETED.json'
if ([IO.File]::Exists($completedPath)) {
 $done=Get-Content -LiteralPath $completedPath -Raw|ConvertFrom-Json
 $closedPath=Join-Path $store 'RAW-FINAL-RECEIPT.json'
 if ($done.schema -ne 'gaia verified raw retirement completion v1' -or $done.plan_sha256 -ne 'f7eceb57257047c58476093f0ac8817d113876af34f7cd414a43f38a8bb09d49' -or (Get-RawSha $closedPath) -ne $done.closeout_sha256) { throw 'Completed-retirement marker changed.' }
 $closed=Get-Content -LiteralPath $closedPath -Raw|ConvertFrom-Json
 if ($closed.passed -isnot [bool] -or !$closed.passed -or $closed.raw_files_all_absent -isnot [bool] -or !$closed.raw_files_all_absent -or $closed.removed_raw_files -ne 34308 -or $closed.plan_sha256 -ne $done.plan_sha256) { throw 'Completed retirement was not verified.' }
 Write-Host 'Old raw retirement already completed and verified; no further scan or deletion.';exit 0
}
Add-Type @'
using System;using System.IO;using System.Runtime.InteropServices;using Microsoft.Win32.SafeHandles;
public static class GaiaRawRetirement {
 [StructLayout(LayoutKind.Sequential)] public struct Info {public uint Attr;public System.Runtime.InteropServices.ComTypes.FILETIME C,A,W;public uint Volume,Hi,Lo,Links,IdHi,IdLo;}
 public class Result {public string Status;public long Bytes;public ulong Storage;public uint Links;}
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]static extern uint GetFileAttributesW(string p);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]static extern SafeFileHandle CreateFile(string p,uint a,uint s,IntPtr sa,uint d,uint f,IntPtr t);
 [DllImport("kernel32.dll",SetLastError=true)]static extern bool GetFileInformationByHandle(SafeFileHandle h,out Info i);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]static extern uint GetCompressedFileSizeW(string p,out uint hi);
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]static extern bool DeleteFileW(string p);
 static string Win(string p){return @"\\?\"+p;}
 static Exception Error(){return new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());}
 public static string Safe(string path,string root){
  string p=Path.GetFullPath(path);if(!p.StartsWith(root+"\\",StringComparison.OrdinalIgnoreCase))throw new Exception("Outside project.");
  for(string q=p;q.Length>=root.Length;q=Path.GetDirectoryName(q)){
   uint a=GetFileAttributesW(Win(q));if(a==0xffffffff){int e=Marshal.GetLastWin32Error();if(e!=2&&e!=3)throw Error();}
   else if((a&0x400)!=0)throw new Exception("Reparse point refused: "+q);
   if(string.Equals(q,root,StringComparison.OrdinalIgnoreCase))break;
  }return p;
 }
 public static Result Unlink(string path,string root,ulong id,long bytes,long mtime,bool remove){
  string p=Safe(path,root);Result r=new Result();
  // Deny writers while checking and unlinking; permit other harmless readers.
  using(var h=CreateFile(Win(p),0x80,5,IntPtr.Zero,3,0,IntPtr.Zero)){
   if(h.IsInvalid){int e=Marshal.GetLastWin32Error();if(e==2||e==3){r.Status="already absent";return r;}throw Error();}
   Info i;if(!GetFileInformationByHandle(h,out i))throw Error();
   ulong actualId=((ulong)i.IdHi<<32)|i.IdLo;long actualBytes=(long)(((ulong)i.Hi<<32)|i.Lo);
   long wt=((long)(uint)i.W.dwHighDateTime<<32)|(uint)i.W.dwLowDateTime;long ns=(wt-116444736000000000L)*100;
   if(actualId!=id||actualBytes!=bytes||ns!=mtime)throw new Exception("Raw file identity/size/mtime changed.");
   uint hi;uint lo=GetCompressedFileSizeW(Win(p),out hi);if(lo==0xffffffff&&Marshal.GetLastWin32Error()!=0)throw Error();
   r.Bytes=actualBytes;r.Storage=((ulong)hi<<32)|lo;r.Links=i.Links;r.Status=remove?"removed":"preview";
   if(remove){Safe(p,root);if(!DeleteFileW(Win(p)))throw Error();}
  }return r;
 }
}
'@
function Safe-RawPath([string]$p) { return [GaiaRawRetirement]::Safe($p,$root) }
$planPath=Safe-RawPath (Join-Path $store 'raw-retirement-plan.json')
$planHash='f7eceb57257047c58476093f0ac8817d113876af34f7cd414a43f38a8bb09d49'
if ((Get-RawSha $planPath) -ne $planHash) { throw 'Raw retirement plan changed.' }
$plan=Get-Content -LiteralPath $planPath -Raw|ConvertFrom-Json
$go=Get-Content -LiteralPath (Safe-RawPath $goPath) -Raw|ConvertFrom-Json
if ($go.schema -ne 'gaia completed019 raw-retirement authorization v1' -or $go.approved -isnot [bool] -or !$go.approved -or $go.plan_sha256 -ne $planHash) { throw 'Closedproof GO marker invalid.' }
if ($plan.schema -ne 'gaia reviewed old raw retirement v1' -or $plan.files.Count -ne 34308) { throw 'Reviewed raw selection changed.' }
$binary=$plan.replacement_binary_sha256
$required=@{
 native105='.local/batch-001/native-019/counter-audit/FINAL-COHORT-AUDIT.json'
 renderer82='.local/batch-001/native-019/renderer-qualification/final001/FINAL-RECEIPT.json'
 rendererIndependent='.local/batch-001/native-019/renderer-qualification/final001/INDEPENDENT-CLOSEOUT.json'
 classroom5='.local/batch-001/native-019/classroom/runtime/FINAL-RECEIPT-v3.json'
 classroomIndependent='.local/batch-001/native-019/classroom/INDEPENDENT-CLOSEOUT.json'
 SDK='.local/batch-001/native-019/sdk-regression/FINAL-RECEIPT.json'
 engine='.local/batch-001/native-019/native-gap/FROZEN-ENGINE-PROOF.json'
}
if ($go.proofs.Count -ne $required.Count) { throw 'Missing closedproof gates.' }
$seen=@{};$proofs=@{}
foreach ($proof in $go.proofs) {
 if (!$required.ContainsKey($proof.kind) -or $seen.ContainsKey($proof.kind) -or $proof.path.Replace('\','/') -ne $required[$proof.kind]) { throw 'Unexpected/duplicate proof gate.' }
 $p=Safe-RawPath (Join-Path $root $proof.path)
 if ((Get-RawSha $p) -ne $proof.sha256) { throw "Closedproof hash changed: $($proof.kind)" }
 $doc=Get-Content -LiteralPath $p -Raw|ConvertFrom-Json
 Assert-ProofSummary $proof.kind $doc $binary
 $seen[$proof.kind]=$true;$proofs[$proof.kind]=$doc
}
if ($proofs.rendererIndependent.final_receipt_sha256 -ne ($go.proofs|Where-Object kind -eq renderer82).sha256 -or $proofs.classroomIndependent.runtime_receipt_sha256 -ne ($go.proofs|Where-Object kind -eq classroom5).sha256) { throw 'Independent closeout lineage mismatch.' }
if ((Get-RawSha (Safe-RawPath (Join-Path $root '.local/batch-001/native-019/babel-final-v1.exe'))) -ne $binary) { throw 'Selected replacement binary changed.' }
$prepPath=Safe-RawPath (Join-Path $root $plan.preparation_path)
if ((Get-RawSha $prepPath) -ne $plan.preparation_sha256) { throw 'Input consumer preparation changed.' }
$prep=Get-Content -LiteralPath $prepPath -Raw|ConvertFrom-Json
if (!$prep.passed -or $prep.active_input_raw_intersections.Count -or $prep.active_input_raw_directory_refs.Count) { throw 'Unresolved raw input consumer.' }
# Rebind all inspected JSON and019driver inputs, not the historical raw outputs.
foreach($source in @($prep.JSON_provenance_files)+@($prep.scripts_inspected)) {
 if((Get-RawSha (Safe-RawPath (Join-Path $root $source.path))) -ne $source.sha256){throw "Consumer input changed: $($source.path)"}
}
$lease=[IO.File]::Open((Safe-RawPath (Join-Path $root '.local/project-cleanup/run.lock')),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
$report=[ordered]@{schema='gaia exact historical raw retirement result v1';utc=[DateTime]::UtcNow.ToString('o');preview=[bool]$Preview;plan_sha256=$planHash;go_sha256=(Get-RawSha $goPath);files=@();logical_bytes_removed=0L;reported_storage_unlinked_last_link_bytes=0L;hardlink_names_removed=0;failed=@();raw_golden_retired=$false}
function Assert-NoOldRawConsumers {
 $prefixes=@('.local\batch-001\native-015\qualification-final','.local\batch-001\native-017\qualification-final')
 $busy=@(Get-CimInstance Win32_Process -ErrorAction Stop|Where-Object {
  $text=((([string]$_.ExecutablePath)+' '+([string]$_.CommandLine)).Replace('/','\'))
  $_.ProcessId -ne $PID -and ($text.IndexOf($prefixes[0],[StringComparison]::OrdinalIgnoreCase) -ge 0 -or $text.IndexOf($prefixes[1],[StringComparison]::OrdinalIgnoreCase) -ge 0)
 })
 if($busy.Count){throw 'Running old-raw consumer detected; close it and retry.'}
}
$records=[Collections.Generic.List[object]]::new()
try {
 Assert-NoOldRawConsumers
 $n=0
 foreach($row in $plan.files) {
  Assert-RawRelative $row.path
  $record=@{path=$row.path;status='retained'}
  try {
   $p=Join-Path $root $row.path
   $r=[GaiaRawRetirement]::Unlink($p,$root,[uint64]$row.file_id,[long]$row.logical_bytes,[long]$row.mtime_ns,!$Preview)
   $record.status=$r.Status;$record.logical_bytes=$r.Bytes;$record.reported_storage_bytes=$r.Storage;$record.links_before=$r.Links
   if($r.Status -eq 'removed'){$report.logical_bytes_removed+=$r.Bytes;if($r.Links -eq 1){$report.reported_storage_unlinked_last_link_bytes += [long]$r.Storage}else{$report.hardlink_names_removed++}}
  }catch{$record.error=$_.Exception.Message;$report.failed+=$row.path}
  $records.Add($record);$n++
  if(($n % 500) -eq 0){Write-Host "$n / $($plan.files.Count) exact raw files processed";Assert-NoOldRawConsumers}
 }
 $report.files=$records.ToArray();$report.raw_golden_retired=!$Preview -and !$report.failed.Count
}catch{$report.failed+=$_.Exception.Message;Write-Warning $_.Exception.Message}
finally {
 $report.files=$records.ToArray()
 $resultPath=Join-Path $store ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssffffZ')+'-raw-result.json')
 $report|ConvertTo-Json -Depth 7|Set-Content -LiteralPath $resultPath -Encoding UTF8
 $lease.Dispose();Write-Host "Receipt: $resultPath"
}
Write-Host "Removed logical bytes: $($report.logical_bytes_removed); last-link reported storage: $($report.reported_storage_unlinked_last_link_bytes)"
if($report.failed.Count){Write-Warning 'Retained busy/changed/locked paths; close consumers and rerun the same CMD. No permissions forced.';exit 3}
