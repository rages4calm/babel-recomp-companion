"""Offline identity contract for Original Gaia and the pending GaiaLabs edition.

This does not enable a game mode, create save folders, migrate owner files or
qualify native code. Detailed receipts belong in the ignored private batch.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from inspect_gaia_modules import InspectionError, json_text, no_links

ROOT = Path(__file__).resolve().parents[1]
STOCK_SHA256 = "32adc048fd89228a4310c03df243e83de7d436cdb2460b4cc83ade20d359b2bd"
STOCK_SIZE = 2097152
PROFILE_SCHEMA = "gaia-edition-profile-v1"
SOURCE_NAMES = {"core", "baserom", "retranslation"}
BUILD_FIELDS = {"rom_sha256", "rom_size", "source_commits", "modules_in_order",
                "dependency_lock_sha256", "module_preflight_sha256"}


class EditionError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise EditionError(message)


def _hash(value, length=64):
    _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{%d}" % length, value),
             f"Expected a lowercase {length}-character hash")
    return value


def _digest(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def _profile(edition, build):
    identity = {"schema": PROFILE_SCHEMA, "edition": edition, "build": build}
    return {**identity, "profile_id": _digest(identity)}


def original_profile():
    """The existing clean USA edition; no caller-supplied identity overrides."""
    return _profile("original", {"rom_sha256": STOCK_SHA256, "rom_size": STOCK_SIZE})


def gaialabs_profile(build=None):
    """Bind an explicit future build recipe, without enabling runtime support."""
    _require(isinstance(build, dict) and set(build) == BUILD_FIELDS,
             "GaiaLabs is pending: supply exact ROM, source, modules, lock and preflight identities")
    _hash(build["rom_sha256"])
    size = build["rom_size"]
    _require(type(size) is int and 0 < size <= 8 * 1024 * 1024 and size % 32768 == 0,
             "Expected a bounded bare HiROM image size in whole 32 KiB banks")
    commits = build["source_commits"]
    _require(isinstance(commits, dict) and set(commits) == SOURCE_NAMES,
             "Pin core, baserom and retranslation source commits separately")
    for commit in commits.values():
        _hash(commit, 40)
    modules = build["modules_in_order"]
    _require(isinstance(modules, list) and modules,
             "An explicit nonempty ordered module list is required")
    for name in modules:
        _require(isinstance(name, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]*", name),
                 "Module names must be plain lower-case names, not paths or aliases")
    _require(len(set(modules)) == len(modules), "Duplicate modules are ambiguous")
    _hash(build["dependency_lock_sha256"])
    _hash(build["module_preflight_sha256"])
    # Copy the validated JSON types so a caller cannot mutate the input through
    # the returned profile. Module order is intentionally never sorted.
    return _profile("gaialabs", json.loads(json.dumps(build)))


def validate_profile(profile):
    _require(isinstance(profile, dict) and set(profile) == {"schema", "edition", "build", "profile_id"},
             "Malformed edition profile or unexpected override fields")
    _require(profile["schema"] == PROFILE_SCHEMA, "Unsupported edition profile schema")
    if profile["edition"] == "original":
        expected = original_profile()
    elif profile["edition"] == "gaialabs":
        expected = gaialabs_profile(profile["build"])
    else:
        raise EditionError("Unknown edition; select original or gaialabs explicitly")
    _require(profile == expected, "Edition/profile identity changed; do not reuse its saves or graph")
    return expected


def namespaces(profile):
    """Future relative provisioning paths, never paths supplied by a manifest."""
    p = validate_profile(profile)
    base = f"editions/{p['edition']}/{p['profile_id']}"
    return {"saves": base + "/saves", "settings": base + "/settings", "native": base + "/native"}


def bind_state(profile, kind):
    _require(kind in {"saves", "settings"}, "Only save/settings state bindings are supported")
    p = validate_profile(profile)
    return {"schema": "gaia-edition-state-binding-v1", "edition": p["edition"],
            "profile_id": p["profile_id"], "kind": kind, "namespace": namespaces(p)[kind]}


def validate_state_binding(profile, binding, kind):
    _require(binding == bind_state(profile, kind), "State belongs to another edition/profile or namespace")


def bind_native_graph(profile, framework_commit, manifest_sha256, generation_digest):
    p = validate_profile(profile)
    _hash(framework_commit, 40)
    _hash(manifest_sha256)
    _hash(generation_digest)
    identity = {"schema": "gaia-edition-native-binding-v1", "edition": p["edition"],
                "profile_id": p["profile_id"], "rom_sha256": p["build"]["rom_sha256"],
                "framework_commit": framework_commit, "manifest_sha256": manifest_sha256,
                "generation_digest": generation_digest}
    # Keep full identities in the binding, with a single digest directory so
    # a normal Windows workspace does not acquire three nested long hashes.
    return {**identity, "namespace": namespaces(p)["native"] + "/" + _digest(identity)}


def validate_native_binding(profile, binding):
    _require(isinstance(binding, dict), "Native binding must be an object")
    fields = ("framework_commit", "manifest_sha256", "generation_digest")
    _require(all(k in binding for k in fields), "Incomplete native binding")
    expected = bind_native_graph(profile, *(binding[k] for k in fields))
    _require(binding == expected, "Native graph belongs to another edition/profile or namespace")


def require_runtime_support(profile):
    """A provenance manifest alone never turns on an unimplemented edition."""
    p = validate_profile(profile)
    _require(p["edition"] == "original",
             "GaiaLabs runtime import and native compatibility remain pending integration")


def verify_gaialabs_inputs(profile, preflight_path, lockfile_path):
    """Bind the actual inspected order/sources/lock, not just their labels."""
    p = validate_profile(profile)
    _require(p["edition"] == "gaialabs", "GaiaLabs inputs cannot be attached to Original")
    build = p["build"]
    preflight_bytes = no_links(Path(preflight_path)).read_bytes()
    lock_bytes = no_links(Path(lockfile_path)).read_bytes()
    _require(hashlib.sha256(preflight_bytes).hexdigest() == build["module_preflight_sha256"],
             "Module preflight bytes changed")
    _require(hashlib.sha256(lock_bytes).hexdigest() == build["dependency_lock_sha256"],
             "Dependency lock bytes changed")
    report = json_text(preflight_bytes.decode("utf-8"))
    _require(isinstance(report, dict) and report.get("schema") == "gaia-module-preflight-v1",
             "Expected the current GaiaLabs module inspector receipt")
    _require(report.get("active_modules_in_order") == build["modules_in_order"],
             "Build module order differs from inspected selection")
    for name in ("baserom", "retranslation"):
        source = report.get(name)
        _require(isinstance(source, dict) and source.get("commit") == build["source_commits"][name],
                 f"Inspected {name} source differs from build identity")
    lock = json_text(lock_bytes.decode("utf-8"))
    _require(isinstance(lock, dict) and isinstance(lock.get("packages"), dict),
             "Expected the exact npm package lock used by this build")
    deps = report.get("dependencies")
    _require(isinstance(deps, dict), "Missing inspected dependency identities")
    for source, package in (("core", "@gaialabs/core"), ("baserom", "@gaialabs/iog-baserom")):
        inspected = deps.get(package)
        _require(isinstance(inspected, dict) and inspected.get("npm_git_head") == build["source_commits"][source],
                 f"Exact {source} package/source identity is missing or differs; review the build recipe")
        locked = lock["packages"].get("node_modules/" + package, {})
        _require(isinstance(locked, dict) and
                 all(isinstance(inspected.get(key), str) and inspected[key] == locked.get(key)
                     for key in ("version", "resolved", "integrity")),
                 f"Inspected and supplied dependency locks differ for {package}")
    return {"module_order_and_sources_match": True, "dependency_lock_matches": True,
            "scope": "Local source/recipe agreement only; no build, runtime or package-byte qualification"}


def verify_rom(profile, path):
    """Read and hash a supplied image; a known profile does not qualify gameplay."""
    p = validate_profile(profile)
    try:
        path = no_links(Path(path))
    except InspectionError as error:
        raise EditionError(str(error)) from error
    expected_size = p["build"]["rom_size"]
    _require(path.is_file() and path.stat().st_size in (expected_size, expected_size + 512),
             "ROM size does not match this exact edition profile")
    with path.open("rb") as stream:
        header = path.stat().st_size == expected_size + 512
        if header:
            stream.read(512)
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    _require(digest == p["build"]["rom_sha256"], "ROM bytes do not match this edition profile")
    return {"normalized_rom_sha256": digest, "rom_size": expected_size,
            "copier_header_stripped": header}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", choices=("original", "gaialabs"), required=True)
    parser.add_argument("--gaialabs-build", type=Path,
                        help="Exact local build-identity JSON; this does not enable GaiaLabs runtime")
    parser.add_argument("--module-preflight", type=Path)
    parser.add_argument("--dependency-lock", type=Path)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.edition == "original":
            _require(all(value is None for value in
                         (args.gaialabs_build, args.module_preflight, args.dependency_lock)),
                     "Original cannot accept GaiaLabs input overrides")
            profile = original_profile()
            source_check = None
        else:
            _require(args.gaialabs_build is not None, "GaiaLabs dev-build identity is still pending")
            build = json_text(no_links(args.gaialabs_build).read_text(encoding="utf-8"))
            profile = gaialabs_profile(build)
            _require(args.module_preflight is not None and args.dependency_lock is not None,
                     "Supply the actual inspected module receipt and dependency lock")
            source_check = verify_gaialabs_inputs(profile, args.module_preflight, args.dependency_lock)
        image = verify_rom(profile, args.rom)
        output = no_links(args.output)
        allowed = no_links(ROOT / ".local" / "batch-001")
        _require(output.is_relative_to(allowed) and output != allowed,
                 "Receipt output must stay beneath this project's ignored .local/batch-001")
        _require(not output.exists(), "Refusing to overwrite an existing receipt")
        report = {"schema": "gaia-edition-preflight-v1", "profile": profile,
                  "namespaces": namespaces(profile), "image": image,
                  "runtime_integration": "existing_original" if args.edition == "original" else "pending",
                  "source_check": source_check, "native_qualified": False, "save_migration_performed": False}
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write("\n")
        print(f"{args.edition}: identity verified; no files migrated and no runtime mode enabled")
        return 0
    except (EditionError, InspectionError, OSError, ValueError, TypeError, KeyError) as error:
        print(f"Edition preflight refused: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
