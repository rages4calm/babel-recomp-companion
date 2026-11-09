"""Project-local, lossless cold-fixture compaction. No recursive deletion.

Metadata and owner data remain direct files. Archives are private, immutable and
content addressed; restore a complete required prefix before replaying old tests.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import stat
import sys
import time
import threading
import zipfile


POLICY = ".local/cleanup-active.json"
STORE = ".local/project-cleanup"
PLAN_SCHEMA = "gaia cold cleanup plan v1"
INDEX_SCHEMA = "gaia cold cleanup archive v1"
RECEIPT_SCHEMA = "iog-native-route-v1"
CHUNK = 1024 * 1024
SNAPSHOTS = (".wram.bin", ".sram.bin", ".vram.bin", ".cgram.bin",
             ".oam.bin", ".apu-state.bin", ".apu-scheduler.bin", ".fb.bgrx",
             ".fb.bmp", ".fb.ppm", ".fb.tga")
PROTECTED_PARTS = {"tool-versions", "tools", "toolchains", "msu1", "msu",
                   "soundtrack", "soundtracks", "saves", "states", "save",
                   "owner", "archives", "project-cleanup"}
_LOCAL_LEASES = {}
_LOCAL_LEASE_GUARD = threading.Lock()


class CleanupError(RuntimeError):
    pass


@contextmanager
def cleanup_lease(root, label="cleanup/validation"):
    """OS-held project lease; close/exit releases it, never delete a stale PID file.

    Timing wrappers may hold ``cleanup_lease(project_root, 'native timing')``.
    They must not launch another guarded cleanup CLI inside their own lease.
    """
    workspace = root if isinstance(root, Workspace) else Workspace(Path(root))
    rel = STORE + "/run.lock"
    path = workspace.path(rel)
    key = os.path.normcase(str(path))
    message = "Another cleanup/validation operation is running"
    with _LOCAL_LEASE_GUARD:
        if key in _LOCAL_LEASES:
            raise CleanupError(f"{message} ({_LOCAL_LEASES[key]}); wait for it to finish")
        _LOCAL_LEASES[key] = label
    stream = None
    acquired = False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        stream = workspace.path(rel).open("a+b", buffering=0)
        if stream.seek(0, os.SEEK_END) == 0:
            stream.write(b"\0")
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            stream.seek(1)
            holder = stream.read(4096).decode("utf-8", errors="replace").strip()
            raise CleanupError(f"{message}{' (' + holder + ')' if holder else ''}; wait for it to finish") from exc
        # Only byte zero is locked on Windows. The remaining bytes are advisory
        # text, overwritten by the next actual holder; they never grant a lease.
        stream.seek(1)
        stream.truncate()
        stream.write(str(label).encode("utf-8")[:4096])
        yield workspace
    finally:
        if stream is not None:
            try:
                if acquired:
                    stream.seek(0)
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            finally:
                stream.close()
        with _LOCAL_LEASE_GUARD:
            _LOCAL_LEASES.pop(key, None)


def relative(value: str) -> str:
    """Accept a canonical portable relative name, never an ADS or traversal."""
    if not isinstance(value, str) or not value or PureWindowsPath(value).is_absolute():
        raise CleanupError("Expected a relative project path")
    value = value.replace("\\", "/")
    parts = value.split("/")
    for part in parts:
        if (not part or part in {".", ".."} or part[-1:] in {".", " "}
                or any(ord(c) < 32 or c in ':<>"|?*' for c in part)
                or part.split(".")[0].upper() in
                {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
                 *(f"LPT{i}" for i in range(1, 10))}):
            raise CleanupError(f"Unsafe relative path: {value!r}")
    return "/".join(parts)


def under(path: str, prefix: str) -> bool:
    return path.casefold() == prefix.casefold() or path.casefold().startswith(prefix.casefold() + "/")


def reparse(info) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def digest_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while data := stream.read(CHUNK):
            digest.update(data)
            size += len(data)
    return digest.hexdigest(), size


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def plan_digest(plan: dict) -> str:
    return hashlib.sha256(canonical({k: v for k, v in plan.items() if k != "plan_id"})).hexdigest()


class Workspace:
    def __init__(self, root: Path):
        self.root = root.absolute()
        self._check_ancestors(self.root)
        self.path(".local")
        self.policy, self.policy_sha, self.owner_sha, self.owner = self._policy()
        self._policy_stamps = self._stamps()
        self._reset_caches()

    def _reset_caches(self):
        self._classification = {}
        self._receipt_cache = {}
        self._read_directories = {}
        self._started = time.monotonic()
        self._last_progress = 0
        self._phase = None
        self._local_owners = tuple(p for p in self.owner if under(p, ".local"))

    def progress(self, phase, count=0, total=None, byte_count=0, *, final=False):
        now = time.monotonic()
        if final or phase != self._phase or now - self._last_progress >= 1:
            print(json.dumps({"phase": phase, "files": count, "total_files": total,
                "logical_bytes": byte_count, "elapsed_seconds": round(now-self._started, 2)}), flush=True)
            self._phase, self._last_progress = phase, now

    def begin(self):
        # Every public transaction observes fresh policy and classification state.
        self.refresh(force=True)
        self._reset_caches()

    @staticmethod
    def _stamp(path):
        try:
            info = path.lstat()
        except FileNotFoundError:
            return None
        if reparse(info):
            raise CleanupError(f"Reparse point refused: {path}")
        return (info.st_size, info.st_mtime_ns, info.st_ino, info.st_dev)

    def _unchecked(self, rel):
        rel = relative(rel)
        if not under(rel, ".local"):
            raise CleanupError("Paths must stay under project .local")
        return self.root.joinpath(*rel.split("/"))

    def _read_path(self, rel):
        """Cache read-only ancestor checks per unchanged directory, never mutations."""
        path = self._unchecked(rel)
        stamp = self._stamp(path.parent)
        if path.parent not in self._read_directories or self._read_directories[path.parent] != stamp:
            self._check_ancestors(path.parent)
            self._read_directories[path.parent] = stamp
        self._stamp(path)  # A replaced file reparse point is always refused.
        return path

    def _stamps(self):
        return (self._stamp(self.path(POLICY)),
                self._stamp(self.path(self.policy["protected_owner_inventory"])))

    def _after_mutation(self, directory):
        # Account for our own directory mtime change without discarding every
        # fixture cache. Marker files are still separately checked on admission.
        stamp = self._stamp(directory)
        cached = self._classification.get(directory)
        if cached:
            self._classification[directory] = ((stamp, *cached[0][1:]), *cached[1:])
        self._read_directories[directory] = stamp

    @staticmethod
    def _check_ancestors(path: Path):
        stamps = {}
        for ancestor in (*reversed(path.parents), path):
            try:
                info = ancestor.lstat()
            except FileNotFoundError:
                continue
            if reparse(info):
                raise CleanupError(f"Reparse point refused: {ancestor}")
            stamps[ancestor] = (info.st_size, info.st_mtime_ns, info.st_ino, info.st_dev)
        return stamps

    def path(self, rel: str, *, local: bool = True) -> Path:
        rel = relative(rel)
        if local and not under(rel, ".local"):
            raise CleanupError("Mutation/archive paths must stay under project .local")
        result = self.root.joinpath(*rel.split("/"))
        # Components were validated, but also check lexical containment explicitly.
        if not result.is_relative_to(self.root):
            raise CleanupError("Path escaped project")
        stamps = self._check_ancestors(result)
        # Mutating callers always use this uncached walk. A changed ancestor also
        # invalidates inherited receipt/build classifications before admission.
        if hasattr(self, "_classification") and any(
                directory in self._classification and self._classification[directory][0][0] != stamp
                for directory, stamp in stamps.items()):
            self._classification.clear()
            self._read_directories.clear()
        return result

    def read(self, rel: str):
        with self.path(rel).open("r", encoding="utf-8") as stream:
            return json.load(stream, parse_constant=lambda x: (_ for _ in ()).throw(CleanupError(x)))

    def _policy(self):
        try:
            policy = self.read(POLICY)
            if policy.get("schema") != "gaia active cleanup pins v1":
                raise CleanupError("Unsupported cleanup pins schema")
            pins = policy["active_batches"]
            if not isinstance(pins, list) or not pins:
                raise CleanupError("At least one active batch pin is required")
            for pin in pins:
                self.path(pin)
            inventory = relative(policy["protected_owner_inventory"])
            owner_data = self.read(inventory)
            owners = {relative(row["path"]) for row in owner_data["protected_files"]}
            if not owners:
                raise CleanupError("Owner inventory must not be empty")
            return policy, digest_file(self.path(POLICY))[0], digest_file(self.path(inventory))[0], owners
        except (OSError, KeyError, TypeError, ValueError) as exc:
            raise CleanupError(f"Missing/invalid cleanup pins or owner inventory: {exc}") from exc

    def refresh(self, *, force=False):
        stamps = self._stamps()
        if not force and stamps == self._policy_stamps:
            return
        current = self._policy()
        if current[1:3] != (self.policy_sha, self.owner_sha):
            raise CleanupError("Cleanup pins/owner inventory changed; create a fresh preview")
        self._policy_stamps = stamps

    def protected(self, rel: str) -> bool:
        rel = relative(rel)
        parts = rel.casefold().split("/")
        return (not under(rel, ".local") or under(rel, STORE)
                or any(part in PROTECTED_PARTS or part.startswith("owner") for part in parts)
                or any(under(rel, pin) for pin in self.policy["active_batches"])
                or any(under(rel, owner) for owner in self._local_owners))

    def _directory_classification(self, directory):
        """Read receipts/CMake markers once per unchanged directory in this operation."""
        if directory == self.root:
            return False, False, ()
        receipt, cmake = directory / "receipt.json", directory / "CMakeCache.txt"
        stamp = (self._stamp(directory), self._stamp(receipt), self._stamp(cmake))
        cached = self._classification.get(directory)
        if cached and cached[0] == stamp:
            # Inherited receipts can change without changing this child directory.
            if all(self._stamp(p) == old for p, old in cached[3]):
                return cached[1:]
        parent_receipted, parent_build, dependencies = self._directory_classification(directory.parent)
        found = False
        if stamp[1] is not None:
            key = (receipt, stamp[1])
            if key not in self._receipt_cache:
                try:
                    with self._read_path(receipt.relative_to(self.root).as_posix()).open(encoding="utf-8") as stream:
                        self._receipt_cache[key] = json.load(stream).get("schema") == RECEIPT_SCHEMA
                except (OSError, ValueError, TypeError):
                    self._receipt_cache[key] = None
            if self._receipt_cache[key] is None:
                # Malformed child metadata must not inherit an ancestor grant.
                return False, True, ((receipt, stamp[1]),)
            found = self._receipt_cache[key]
        dependencies = dependencies + tuple((p, s) for p, s in ((receipt, stamp[1]), (cmake, stamp[2])) if s is not None)
        value = (parent_receipted or found, parent_build or stamp[2] is not None, dependencies)
        self._classification[directory] = (stamp, *value)
        return value

    def eligible(self, rel: str) -> str | None:
        """Only known raw outputs/assets in an independently receipted run."""
        if self.protected(rel):
            return None
        path = self._unchecked(rel)
        name = path.name.casefold()
        if name.endswith((".ttf", ".otf")):
            kind = "copied-font"
        elif name.endswith(".tsv"):
            kind = "raw-tsv"
        elif name == "final.ppm" or name.endswith(SNAPSHOTS):
            kind = "raw-snapshot"
        elif name.endswith((".ppm", ".bgrx", ".bmp", ".tga")):
            kind = "raw-raster"
        else:
            return None
        path = self._read_path(rel)
        found_receipt, build, _ = self._directory_classification(path.parent)
        return kind if found_receipt and not build else None

    def _write_new(self, rel: str, value):
        path = self.path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path(rel)  # Check again after mkdir and before creating a file.
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

    def preview(self, prefixes: list[str] | None = None) -> tuple[str, dict]:
        self.begin()
        self.progress("preview")
        prefixes = sorted({relative(p) for p in (prefixes or [".local/batch-001"])})
        entries, skipped = {}, 0

        def visit(rel):
            nonlocal skipped
            if self.protected(rel):
                return
            path = self.path(rel)
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise CleanupError("Preview prefixes must be directories")
            with os.scandir(path) as listing:
                for child in listing:
                    child_rel = f"{rel}/{child.name}"
                    info = child.stat(follow_symlinks=False)
                    if reparse(info):
                        skipped += 1
                    elif stat.S_ISDIR(info.st_mode):
                        visit(child_rel)
                    elif stat.S_ISREG(info.st_mode) and (kind := self.eligible(child_rel)):
                        sha, size = digest_file(self._read_path(child_rel))
                        after = self._read_path(child_rel).stat()
                        if (after.st_size, after.st_mtime_ns) != (info.st_size, info.st_mtime_ns):
                            raise CleanupError(f"File changed during preview: {child_rel}")
                        entries[child_rel.casefold()] = {"path": child_rel, "sha256": sha,
                            "bytes": size, "mtime_ns": info.st_mtime_ns, "kind": kind}
                        self.progress("preview/hash", len(entries), byte_count=sum_bytes[0] + size)
                        sum_bytes[0] += size

        sum_bytes = [0]
        for prefix in prefixes:
            self.path(prefix)
            visit(prefix)
        plan = {"schema": PLAN_SCHEMA, "project": str(self.root), "policy_sha256": self.policy_sha,
                "owner_inventory_sha256": self.owner_sha, "prefixes": prefixes,
                "entries": sorted(entries.values(), key=lambda e: e["path"]),
                "skipped_reparse_points": skipped}
        plan["plan_id"] = plan_digest(plan)
        rel = f"{STORE}/plans/{plan['plan_id']}.json"
        if self.path(rel).exists():
            try:
                matches = self.read(rel) == plan
            except (OSError, ValueError):
                matches = False
            if not matches:
                # Keep an interrupted/foreign immutable plan intact, create a
                # fresh named copy with the same content identity instead.
                rel = f"{STORE}/plans/{plan['plan_id']}-preview-{time.time_ns()}.json"
        if not self.path(rel).exists():
            self._write_new(rel, plan)
        self.progress("preview complete", len(entries), len(entries), sum_bytes[0], final=True)
        return rel, plan

    def load_plan(self, rel: str, *, current: bool = True) -> dict:
        if not under(relative(rel), STORE + "/plans"):
            raise CleanupError("Plan must be in the cleanup plan store")
        plan = self.read(rel)
        self.validate_plan(plan, current=current)
        return plan

    def validate_plan(self, plan: dict, *, current: bool = True):
        if (plan.get("schema") != PLAN_SCHEMA or plan.get("project") != str(self.root)
                or plan.get("plan_id") != plan_digest(plan)):
            raise CleanupError("Plan identity mismatch")
        self.refresh()
        if current and (plan.get("policy_sha256"), plan.get("owner_inventory_sha256")) != (self.policy_sha, self.owner_sha):
            raise CleanupError("Plan pins/owner identity is stale; preview again")
        seen = set()
        validated_bytes = 0
        self.progress("validate plan", total=len(plan["entries"]))
        for number, entry in enumerate(plan["entries"], 1):
            rel = relative(entry["path"])
            kind = self.eligible(rel)
            if rel.casefold() in seen or kind is None or kind != entry["kind"]:
                raise CleanupError(f"Unsafe/nonfixture/duplicate plan target: {rel}")
            seen.add(rel.casefold())
            sha = entry["sha256"]
            if (len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha)
                    or type(entry["bytes"]) is not int or entry["bytes"] < 0
                    or type(entry["mtime_ns"]) is not int):
                raise CleanupError("Invalid file identity in plan")
            validated_bytes += entry["bytes"]
            self.progress("validate plan", number, len(plan["entries"]), validated_bytes)

    def locations(self, plan: dict) -> tuple[str, str]:
        base = f"{STORE}/archives/{plan['plan_id']}"
        return base + ".zip", base + ".json"

    def _source(self, entry: dict, *, missing_ok=False, mutation=False) -> bool:
        path = self.path(entry["path"]) if mutation else self._read_path(entry["path"])
        if not path.exists() and missing_ok:
            return False
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or digest_file(path) != (entry["sha256"], entry["bytes"]):
            raise CleanupError(f"Source changed: {entry['path']}")
        return True

    def archive(self, plan_rel: str) -> str:
        self.begin()
        plan = self.load_plan(plan_rel)
        archive_rel, index_rel = self.locations(plan)
        if self.path(index_rel).exists():
            self.verify(index_rel)
            return index_rel
        if self.path(archive_rel).exists():
            raise CleanupError("Archive exists without completed index; preserve it and inspect")
        # The stream copy checks each unique payload against the preview. Other
        # copies of a duplicate are checked individually immediately before unlink.
        self.path(archive_rel).parent.mkdir(parents=True, exist_ok=True)
        unique = {}
        unique_bytes = 0
        with zipfile.ZipFile(self.path(archive_rel), "x", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=1, allowZip64=True) as output:
            for number, entry in enumerate(plan["entries"], 1):
                sha = entry["sha256"]
                if sha in unique:
                    if unique[sha] != entry["bytes"]:
                        raise CleanupError("Conflicting digest sizes")
                    self.progress("archive", number, len(plan["entries"]), unique_bytes)
                    continue
                unique[sha] = entry["bytes"]
                digest, size = hashlib.sha256(), 0
                with self._read_path(entry["path"]).open("rb") as source, output.open("payload/" + sha, "w", force_zip64=True) as dest:
                    while data := source.read(CHUNK):
                        dest.write(data)
                        digest.update(data)
                        size += len(data)
                if (digest.hexdigest(), size) != (sha, entry["bytes"]):
                    raise CleanupError(f"Source changed while archiving: {entry['path']}")
                unique_bytes += size
                self.progress("archive", number, len(plan["entries"]), byte_count=unique_bytes)
        self._verify_payloads(archive_rel, plan)
        index = {"schema": INDEX_SCHEMA, "archive": archive_rel, "plan": plan,
                 "archive_sha256": digest_file(self.path(archive_rel))[0],
                 "payloads": len(unique), "original_bytes": sum(e["bytes"] for e in plan["entries"]),
                 "archive_bytes": self.path(archive_rel).stat().st_size}
        self._write_new(index_rel, index)
        self.verify(index_rel)
        return index_rel

    def _verify_payloads(self, archive_rel: str, plan: dict):
        expected = {"payload/" + e["sha256"]: e["bytes"] for e in plan["entries"]}
        with zipfile.ZipFile(self.path(archive_rel)) as archive:
            infos = archive.infolist()
            if len(infos) != len(expected) or {i.filename for i in infos} != expected.keys():
                raise CleanupError("Archive member set mismatch")
            for number, info in enumerate(infos, 1):
                if info.file_size != expected[info.filename]:
                    raise CleanupError("Archive payload size mismatch")
                digest, size = hashlib.sha256(), 0
                with archive.open(info) as stream:
                    while data := stream.read(CHUNK):
                        digest.update(data)
                        size += len(data)
                if size != info.file_size or digest.hexdigest() != info.filename.removeprefix("payload/"):
                    raise CleanupError("Archive roundtrip SHA256 mismatch")
                self.progress("verify roundtrip", number, len(infos))

    def verify(self, index_rel: str) -> dict:
        self.begin()
        if not under(relative(index_rel), STORE + "/archives"):
            raise CleanupError("Index must be in the cleanup archive store")
        index = self.read(index_rel)
        if index.get("schema") != INDEX_SCHEMA:
            raise CleanupError("Unsupported archive index")
        plan = index["plan"]
        self.validate_plan(plan, current=False)
        archive_rel, expected_index = self.locations(plan)
        if index_rel != expected_index or index["archive"] != archive_rel:
            raise CleanupError("Archive/index path identity mismatch")
        self.progress("verify archive SHA", total=1)
        if digest_file(self.path(archive_rel)) != (index["archive_sha256"], index["archive_bytes"]):
            raise CleanupError("Archive missing/corrupt or changed")
        self._verify_payloads(archive_rel, plan)
        return index

    def apply(self, plan_rel: str) -> dict:
        self.begin()
        plan = self.load_plan(plan_rel)
        _, index_rel = self.locations(plan)
        index = self.verify(index_rel)  # No unlink until a complete verified archive exists.
        # Fail-stop per file: a later changed source remains in place, while
        # earlier verified removals remain recoverable from the complete archive.
        removed, logical_bytes = 0, 0
        skipped_locked = []
        for entry in plan["entries"]:
            self.refresh()
            present = self._source(entry, missing_ok=True, mutation=True)
            if self.eligible(entry["path"]) != entry["kind"]:
                raise CleanupError("Target protection changed")
            if present:
                target = self.path(entry["path"])
                try:
                    target.unlink()
                except OSError as exc:
                    if getattr(exc, "winerror", None) not in {32, 33}:
                        raise
                    skipped_locked.append({"path": entry["path"], "bytes": entry["bytes"],
                                           "winerror": exc.winerror})
                    print(json.dumps({"skipped_locked": skipped_locked[-1], "pending": True}), flush=True)
                    self.progress("apply; locked file retained", removed, len(plan["entries"]), logical_bytes, final=True)
                    continue
                self._after_mutation(target.parent)
                removed += 1
                logical_bytes += entry["bytes"]
            self.progress("apply", removed, len(plan["entries"]), logical_bytes)
        return {"removed_files": removed, "removed_logical_bytes": logical_bytes,
                "archive": index["archive"], "index": index_rel, "roundtrip_verified": True,
                "skipped_locked": skipped_locked, "skipped_locked_files": len(skipped_locked),
                "skipped_locked_bytes": sum(e["bytes"] for e in skipped_locked),
                "pending_locked_files": bool(skipped_locked)}

    def restore(self, index_rel: str, prefix: str) -> dict:
        self.begin()
        prefix = relative(prefix)
        self.path(prefix)
        index = self.verify(index_rel)
        selected = [e for e in index["plan"]["entries"] if under(e["path"], prefix)]
        if not selected:
            raise CleanupError("Prefix matches no archived files")
        # Preflight all names before creating any file. Never overwrite differing data.
        for entry in selected:
            if self.path(entry["path"]).exists():
                self._source(entry)
        restored = 0
        with zipfile.ZipFile(self.path(index["archive"])) as archive:
            for entry in selected:
                self.refresh()
                rel = entry["path"]
                target = self.path(rel)
                if self.eligible(rel) != entry["kind"]:
                    raise CleanupError("Restore target became protected")
                if target.exists():
                    self._source(entry)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open("payload/" + entry["sha256"]) as source, self.path(rel).open("xb") as dest:
                    while data := source.read(CHUNK):
                        dest.write(data)
                self._source(entry)
                os.utime(self.path(rel), ns=(entry["mtime_ns"], entry["mtime_ns"]))
                self._after_mutation(target.parent)
                restored += 1
                self.progress("restore", restored, len(selected))
        return {"restored_files": restored, "matched_files": len(selected), "prefix": prefix}


def summary(plan: dict) -> dict:
    return {"plan_id": plan["plan_id"], "files": len(plan["entries"]),
            "logical_bytes": sum(e["bytes"] for e in plan["entries"]),
            "unique_payloads": len({e["sha256"] for e in plan["entries"]}),
            "skipped_reparse_points": plan["skipped_reparse_points"]}


def report_apply(result: dict) -> int:
    print(json.dumps(result, indent=2), flush=True)
    if result["skipped_locked_files"]:
        print(f"Cleanup pending: {result['skipped_locked_files']} locked files "
              f"({result['skipped_locked_bytes']} bytes) remain. Close their consumer and "
              "resume apply with the same plan; keep the verified archive.", flush=True)
        return 3
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("preview", "clean"):
        child = sub.add_parser(command)
        child.add_argument("--prefix", action="append", help="Restrict to a cold .local directory; repeatable")
    for command in ("archive", "apply"):
        sub.add_parser(command).add_argument("--plan", required=True)
    sub.add_parser("verify").add_argument("--index", required=True)
    restore = sub.add_parser("restore")
    restore.add_argument("--index", required=True)
    restore.add_argument("--prefix", required=True)
    args = parser.parse_args(argv)
    try:
        workspace = Workspace(Path(__file__).absolute().parents[1])
        with cleanup_lease(workspace):
            if args.command in {"preview", "clean"}:
                rel, plan = workspace.preview(args.prefix)
                print(json.dumps({"plan": rel, **summary(plan)}, indent=2), flush=True)
                if args.command == "clean" and plan["entries"]:
                    workspace.archive(rel)
                    return report_apply(workspace.apply(rel))
            elif args.command == "archive":
                print(json.dumps({"index": workspace.archive(args.plan)}, indent=2))
            elif args.command == "apply":
                return report_apply(workspace.apply(args.plan))
            elif args.command == "verify":
                result = workspace.verify(args.index)
                print(json.dumps({"verified": True, "archive": result["archive"], **summary(result["plan"])}, indent=2))
            elif args.command == "restore":
                print(json.dumps(workspace.restore(args.index, args.prefix), indent=2))
        return 0
    except (CleanupError, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
        print(f"Cleanup refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
