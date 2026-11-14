"""Inspect a privately received GaiaLabs build without enabling runtime support.

Verifies the supplied archive against separately pinned ROM/BSO bytes and
inventories candidate public module inputs. No extraction, game execution,
asset import, package installation or native binding occurs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

import gaia_editions as editions
from inspect_gaia_modules import checkout, no_links, record, selected_modules, text

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def pinned_file(path, expected, limit):
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("Expected an explicit lowercase SHA-256 pin")
    path = no_links(Path(path))
    if not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("Missing or oversized input")
    data = path.read_bytes()
    if digest(data) != expected:
        raise ValueError("Input does not match its supplied SHA-256")
    return path, data


def inspect_received(archive, archive_sha256, rom, rom_sha256, bso, bso_sha256):
    archive, _ = pinned_file(archive, archive_sha256, 16 << 20)
    rom, image = pinned_file(rom, rom_sha256, (8 << 20) + 512)
    bso, overrides = pinned_file(bso, bso_sha256, 4096)
    if rom.suffix.lower() not in (".smc", ".sfc") or bso.name != rom.stem + ".bso":
        raise ValueError("ROM and BSO must have the same basename")
    bare = image[512:] if len(image) % 32768 == 512 else image
    if len(bare) < 65536 or len(bare) % 32768 or len(bare) > 8 << 20:
        raise ValueError("Expected a bounded bare HiROM image in 32 KiB banks")
    if bare[0xFFD5] & 15 != 1 or int.from_bytes(bare[0xFFFC:0xFFFE], "little") < 0x8000:
        raise ValueError("Input does not have the expected HiROM header/reset shape")
    expected = {rom.name: image, bso.name: overrides}
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        if len(entries) != 2 or {e.filename for e in entries} != set(expected):
            raise ValueError("Expected exactly the pinned ROM and matching BSO archive members")
        for entry in entries:
            path = PurePosixPath(entry.filename)
            if path.name != entry.filename or "\\" in entry.filename or stat.S_ISLNK(entry.external_attr >> 16):
                raise ValueError("Archive paths and links are not accepted")
            if entry.flag_bits & 1 or entry.file_size != len(expected[entry.filename]):
                raise ValueError("Encrypted or unexpected-size archive member")
            if source.read(entry) != expected[entry.filename]:
                raise ValueError("Archive member differs from pinned external input")
    return {"archive": {"path": str(archive), "sha256": archive_sha256},
            "rom": {"path": str(rom), "sha256": rom_sha256, "bytes": len(image),
                    "bare_sha256": digest(bare), "bare_bytes": len(bare)},
            "bso": {"path": str(bso), "sha256": bso_sha256, "bytes": len(overrides)},
            "archive_members_match": True}


def inspect_source(source, commit):
    repo = checkout(Path(source), commit)
    active, commented = selected_modules(text(repo, "scripts/index.ts"))
    files = []
    for relative in sorted(repo["tracked"]):
        if relative.startswith("modules/") and relative.endswith((".map", ".asm")):
            row = record(repo, relative)
            row["module"] = relative.split("/")[1]
            files.append(row)
    return {"root": str(repo["root"]), "commit": repo["commit"], "tree": repo["tree"],
            "declared_active_modules_in_order": active, "declared_commented_modules": commented,
            "dependency_lock": record(repo, "package-lock.json"),
            "candidate_map_inputs": [r for r in files if r["path"].endswith(".map")],
            "associated_assembly_inputs": [r for r in files if r["path"].endswith(".asm")],
            "matches_received_build_recipe": None}


def inspect(archive, archive_sha256, rom, rom_sha256, bso, bso_sha256, source, source_commit):
    received = inspect_received(archive, archive_sha256, rom, rom_sha256, bso, bso_sha256)
    inputs = inspect_source(source, source_commit)
    return {"schema": "gaialabs-received-content-inspection-v1", "passed": True,
            "received": received, "candidate_source_inputs": inputs,
            "intended_product": "Built-in main Retranslation content with approved expanded maps",
            "edition_contract": {"schema": editions.PROFILE_SCHEMA,
                                 "stock_comparison_profile_id": editions.original_profile()["profile_id"],
                                 "gaialabs_profile": None,
                                 "missing_matching_recipe_fields": sorted(editions.BUILD_FIELDS - {"rom_sha256", "rom_size"})},
            "runtime_support_enabled": False, "native_graph_bound": False,
            "source_recipe_reproduced": False, "asset_bytes_copied": False,
            "scope": "Identity/member verification and candidate source inventory only. Public module selection is not proof of the private developer build's selection. No runtime/native compatibility or distribution permission is inferred."}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "rom", "bso", "source", "output"):
        p.add_argument("--" + name, type=Path, required=True)
    for name in ("archive-sha256", "rom-sha256", "bso-sha256", "source-commit"):
        p.add_argument("--" + name, required=True)
    a = p.parse_args(argv)
    output = no_links(a.output)
    if not output.is_relative_to((ROOT / ".local").resolve()) or output.exists():
        p.error("Use a new diagnostic output beneath this project's ignored .local/")
    result = inspect(a.archive, a.archive_sha256, a.rom, a.rom_sha256,
                     a.bso, a.bso_sha256, a.source, a.source_commit)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as f:
        json.dump(result, f, indent=2); f.write("\n")
    print(json.dumps({"passed": True, "runtime_support_enabled": False,
                      "candidate_maps": len(result["candidate_source_inputs"]["candidate_map_inputs"]),
                      "receipt": str(output)}))


if __name__ == "__main__":
    main()
