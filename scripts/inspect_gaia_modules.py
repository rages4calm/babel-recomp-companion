"""Read-only provenance preflight for external GaiaLabs source checkouts.

No upstream JavaScript is run and no upstream implementation/assets are copied.
Detailed receipts must stay in this project's ignored .local/batch-001 tree.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess


class InspectionError(ValueError):
    pass


def fail(message: str):
    raise InspectionError(message)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def no_links(path: Path) -> Path:
    path = path.absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            fail(f"Symlink/junction path refused: {part}")
    return path.resolve()


def safe_path(root: Path, relative: str) -> Path:
    if not relative or "\\" in relative or ":" in relative:
        fail(f"Malformed relative path: {relative!r}")
    parts = relative.split("/")
    if any(p in ("", ".", "..") for p in parts):
        fail(f"Malformed relative path: {relative!r}")
    result = no_links(root.joinpath(*parts))
    if not result.is_relative_to(root):
        fail(f"Path escapes checkout: {relative!r}")
    return result


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        fail(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def checkout(path: Path, commit: str) -> dict:
    root = no_links(path)
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        fail("Expected a full 40-character source commit")
    if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        fail(f"Expected checkout root, not a subdirectory: {root}")
    head = git(root, "rev-parse", "HEAD")
    if head.lower() != commit.lower():
        fail(f"Checkout commit mismatch: expected {commit}, got {head}")
    if git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        fail(f"Dirty checkout refused: {root}")
    entries = git(root, "ls-files", "--stage", "-z").split("\0")
    tracked = {}
    for entry in entries:
        if not entry:
            continue
        metadata, relative = entry.split("\t", 1)
        mode, blob, stage = metadata.split()
        if stage != "0":
            fail("Unmerged checkout index")
        tracked[relative] = {"mode": mode, "git_blob": blob}
    return {"root": root, "commit": head, "tree": git(root, "rev-parse", "HEAD^{tree}"),
            "tracked": tracked}


def record(repo: dict, relative: str) -> dict:
    entry = repo["tracked"].get(relative)
    if not entry or entry["mode"] not in ("100644", "100755"):
        fail(f"Expected tracked regular file: {relative}")
    path = safe_path(repo["root"], relative)
    if not path.is_file():
        fail(f"Missing regular file: {relative}")
    return {"path": relative, "bytes": path.stat().st_size,
            "sha256": sha256(path), "git_blob": entry["git_blob"]}


def text(repo: dict, relative: str) -> str:
    record(repo, relative)
    path = safe_path(repo["root"], relative)
    if path.stat().st_size > 8 * 1024 * 1024:
        fail(f"Metadata too large: {relative}")
    return path.read_text(encoding="utf-8-sig")


def json_text(value: str):
    def pairs(items):
        result = {}
        for key, val in items:
            if key in result:
                fail(f"Duplicate JSON key: {key}")
            result[key] = val
        return result
    def finite(number):
        parsed = float(number)
        if not math.isfinite(parsed):
            fail(f"Non-finite JSON number: {number}")
        return parsed
    return json.loads(value, object_pairs_hook=pairs, parse_float=finite,
                      parse_constant=lambda val: fail(f"Non-finite JSON number: {val}"))


def module_name(name: str) -> str:
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        fail(f"Malformed module name: {name!r}")
    return name


def selected_modules(source: str) -> tuple[list[str], list[str]]:
    # Mask comments and string contents without changing offsets. This keeps
    # commented examples and quoted code from becoming an apparent selection.
    token = re.compile(r"//[^\n]*|/\*.*?\*/|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:\\.|[^`\\])*`", re.S)
    def mask_token(match):
        value = match.group()
        if value.startswith("`") and "${" in value:
            fail("Dynamic template expression requires manual review")
        return re.sub(r"[^\n]", " ", value)
    mask = token.sub(mask_token, source)
    matches = list(re.finditer(r"\bconst\s+modules\s*=\s*\[(.*?)\]\s*;", mask, re.S))
    if len(matches) != 1:
        fail("Expected one literal const modules array")
    selected, disabled = [], []
    for line in source[matches[0].start(1):matches[0].end(1)].splitlines():
        line = line.strip()
        if not line:
            continue
        inactive = line.startswith("//")
        if inactive:
            line = line[2:].strip()
        item = re.fullmatch(r"(['\"])(\./modules/[a-z0-9][a-z0-9-]*)\1\s*,?\s*(?://.*)?", line)
        if not item:
            if inactive and "modules/" not in line:
                continue
            fail(f"Unsupported or malformed module array entry: {line!r}")
        name = module_name(item.group(2).removeprefix("./modules/"))
        if name in selected or name in disabled:
            fail(f"Duplicate/ambiguous module selection: {name}")
        (disabled if inactive else selected).append(name)
    tail = mask[matches[0].end():]
    # Deliberately accept only the current simple forwarding shape. A changed
    # script needs review; a static inspector must not guess dynamic selection.
    forwarding = re.findall(r"\brebuildInternal\s*\([^;]*?\bmodules\b[^;]*?\)\s*;", tail, re.S)
    without_forward = tail
    for call in forwarding:
        without_forward = without_forward.replace(call, "")
    if len(forwarding) != 1 or re.search(r"\bmodules\b", without_forward):
        fail("Module selection is not forwarded once without later mutation")
    if not selected:
        fail("Empty active module selection")
    return selected, disabled


def manifest_modules(manifest: dict) -> list[str]:
    names = set()
    if not isinstance(manifest, dict) or not isinstance(manifest.get("modules"), list):
        fail("Malformed module manifest")
    for category in manifest["modules"]:
        if not isinstance(category, dict) or not isinstance(category.get("groups"), list):
            fail("Malformed manifest category")
        for group in category["groups"]:
            if not isinstance(group, dict) or not isinstance(group.get("options"), list):
                fail("Malformed manifest option group")
            for option in group["options"]:
                if not isinstance(option, dict) or "module" not in option:
                    fail("Malformed manifest option")
                if option["module"] is not None:
                    names.add(module_name(option["module"]))
    return sorted(names)


def module_files(repo: dict, name: str) -> list[dict]:
    prefix = "modules/" + module_name(name)
    folder = safe_path(repo["root"], prefix)
    if not folder.is_dir():
        fail(f"Missing module directory: {name}")
    files = []
    for path in sorted(folder.rglob("*")):
        no_links(path)
        if path.is_file():
            files.append(record(repo, path.relative_to(repo["root"]).as_posix()))
    if not files:
        fail(f"Empty module directory: {name}")
    return files


def dependencies(repo: dict, metadata: dict | None) -> dict:
    package = json_text(text(repo, "package.json"))
    lock = json_text(text(repo, "package-lock.json"))
    if not isinstance(package, dict) or not isinstance(lock, dict):
        fail("Expected package and lock objects")
    locked = lock.get("packages", {})
    if not isinstance(locked, dict) or not isinstance(locked.get(""), dict):
        fail("Expected root package lock entry")
    output = {}
    for name in ("@gaialabs/core", "@gaialabs/iog-baserom"):
        declared = {section[name] for key in ("dependencies", "devDependencies")
                    if isinstance((section := package.get(key)), dict) and name in section}
        if len(declared) != 1:
            fail(f"Missing/ambiguous exact dependency declaration: {name}")
        version = next(iter(declared))
        if not re.fullmatch(r"\d+\.\d+\.\d+", version):
            fail(f"Dependency is not pinned exactly: {name}")
        entry = locked.get("node_modules/" + name)
        if not isinstance(entry, dict) or entry.get("version") != version:
            fail(f"Dependency lock version mismatch: {name}")
        root_lock = locked.get("", {})
        lock_declared = {section[name] for key in ("dependencies", "devDependencies")
                         if isinstance((section := root_lock.get(key)), dict) and name in section}
        if lock_declared != {version}:
            fail(f"Root dependency lock declaration mismatch: {name}")
        integrity = entry.get("integrity", "")
        try:
            digest = base64.b64decode(integrity.removeprefix("sha512-"), validate=True)
        except (ValueError, TypeError):
            fail(f"Malformed dependency integrity: {name}")
        if not integrity.startswith("sha512-") or len(digest) != 64:
            fail(f"Expected SHA-512 dependency integrity: {name}")
        expected_url = f"https://registry.npmjs.org/{name}/-/{name.split('/')[-1]}-{version}.tgz"
        if entry.get("resolved") != expected_url:
            fail(f"Unexpected dependency registry URL: {name}")
        out = {key: entry[key] for key in ("version", "resolved", "integrity")}
        out["declared_license"] = entry.get("license")
        if metadata is not None:
            published = metadata.get(name)
            if not isinstance(published, dict) or published.get("name") != name or published.get("version") != version:
                fail(f"Supplied npm metadata version/name mismatch: {name}")
            dist = published.get("dist", {})
            if dist.get("integrity") != integrity or dist.get("tarball") != expected_url:
                fail(f"Supplied npm metadata integrity/URL mismatch: {name}")
            out["npm_git_head"] = published.get("gitHead")
            out["npm_declared_license"] = published.get("license")
        output[name] = out
    return output


def inspect(retranslation: Path, retranslation_commit: str, baserom: Path,
            baserom_commit: str, metadata: dict | None = None) -> dict:
    translation = checkout(retranslation, retranslation_commit)
    base = checkout(baserom, baserom_commit)
    source = text(translation, "scripts/index.ts")
    active, disabled = selected_modules(source)
    listed = manifest_modules(json_text(text(translation, "modules/manifest.json")))
    names = sorted(set(active + disabled + listed))
    inventory = {name: module_files(translation, name) for name in names}
    # Check every module tree, including optional modules not exposed in manifest.
    modules_root = safe_path(translation["root"], "modules")
    for folder in sorted(modules_root.iterdir()):
        no_links(folder)
        if folder.is_dir() and folder.name not in inventory:
            name = module_name(folder.name)
            inventory[name] = module_files(translation, name)
    deps = dependencies(translation, metadata)
    types = json_text(text(base, "db-us/fileTypes.json"))
    tilemap = types.get("Tilemap")
    if not isinstance(tilemap, dict) or tilemap.get("extension") != "map" or tilemap.get("header") != 2 or tilemap.get("compressed") is not True:
        fail("Upstream raw-map contract changed; review required")
    # Inventory base inputs as well: source pin alone must not conceal ignored
    # added files that rebuildAllContent would ingest.
    base_inputs = []
    base_folder = safe_path(base["root"], "baserom")
    if not base_folder.is_dir():
        fail("Missing baserom content directory")
    for path in sorted(base_folder.rglob("*")):
        no_links(path)
        if path.is_file():
            base_inputs.append(record(base, path.relative_to(base["root"]).as_posix()))
    def identity(repo, paths):
        return {"root": str(repo["root"]), "commit": repo["commit"], "tree": repo["tree"],
                "files": [record(repo, p) for p in paths]}
    report = {
        "schema": "gaia-module-preflight-v1", "proof": "source_inspection_only",
        "build_executed": False, "native_qualified": False,
        "retranslation": identity(translation, ["scripts/index.ts", "modules/manifest.json", "package.json", "package-lock.json", "LICENSE"]),
        "baserom": identity(base, ["src/index.ts", "db-us/fileTypes.json", "package.json", "LICENSE"]),
        "active_modules_in_order": active, "commented_modules": disabled,
        "manifest_modules": listed,
        "active_not_named_by_manifest": [n for n in active if n not in listed],
        "module_files": inventory, "baserom_files": base_inputs,
        "dependencies": deps, "tilemap_file_type": tilemap,
        "build_order_to_review": ["extracted", "baserom", *["modules/" + n for n in active]],
        "limits": ["No upstream code executed or assets copied",
                   "Manifest choices are not the actual rebuild selection",
                   "Later same-name/type inputs override earlier inputs in the inspected upstream implementation",
                   "Supplied npm metadata is compared to the lock; package bytes are not downloaded or verified",
                   "Current source commits do not prove identity with published npm packages or the developer's offered build",
                   "Root license notices and package license declarations require review before importing implementation"],
    }
    for repo in (translation, base):
        if git(repo["root"], "rev-parse", "HEAD") != repo["commit"] or git(repo["root"], "status", "--porcelain=v1", "--untracked-files=all"):
            fail("Checkout changed during inspection")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retranslation", type=Path, required=True)
    parser.add_argument("--retranslation-commit", required=True)
    parser.add_argument("--baserom", type=Path, required=True)
    parser.add_argument("--baserom-commit", required=True)
    parser.add_argument("--npm-metadata", type=Path, help="Optional local JSON keyed by package name; no network request")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        project = Path(__file__).resolve().parents[1]
        allowed = no_links(project / ".local" / "batch-001")
        out = no_links(args.output)
        if not out.is_relative_to(allowed) or out == allowed:
            fail("Detailed receipt output must be under .local/batch-001")
        if out.exists():
            fail("Refusing to overwrite an existing receipt")
        metadata = json_text(no_links(args.npm_metadata).read_text(encoding="utf-8")) if args.npm_metadata else None
        if metadata is not None and not isinstance(metadata, dict):
            fail("Expected npm metadata object keyed by package name")
        report = inspect(args.retranslation, args.retranslation_commit, args.baserom,
                         args.baserom_commit, metadata)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
        print(f"Source inspection passed: {len(report['active_modules_in_order'])} selected modules; no build executed")
        print(out)
        return 0
    except (InspectionError, OSError, ValueError, TypeError, KeyError) as error:
        print(f"Inspection refused: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
