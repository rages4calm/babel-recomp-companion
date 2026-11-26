"""Package a verified build, with notices and no player data.

The default is an interpreter-only build with no ROM-derived code. --native
packages a build that contains compiled game code instead; the owner decided
on November 26, 2026 to publish those as binaries. Generated source, ROMs and
player data stay out of the package either way."""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ID = b"IOG_EXECUTION=interpreter-only;rom-derived-code=none"
PRIVATE_ID = b"IOG_EXECUTION=mixed-aot;rom-derived-code=private"
FORBIDDEN_SUFFIXES = {".sfc", ".smc", ".srm", ".sav", ".state", ".thumb",
                      ".pcm", ".msu", ".ips", ".bps", ".ppm", ".rpl"}
FORBIDDEN_NAMES = {"rom.cfg", "config.ini", "config.local.ini", "ra.ini",
                   "keybinds.ini", "input.ini", "last_run_report.json", "state.toml", "retroachievements.token"}


def validate_build(build: Path, native: bool = False) -> Path:
    cache = (build / "CMakeCache.txt").read_text(encoding="utf-8")
    interpreter = re.search(r"^SNESRECOMP_INTERPRETER_ONLY:BOOL=(ON|TRUE|1)$", cache, re.M)
    if native and interpreter:
        raise ValueError("--native needs a build with SNESRECOMP_INTERPRETER_ONLY=OFF")
    if not native and not interpreter:
        raise ValueError("Public packages require SNESRECOMP_INTERPRETER_ONLY=ON (or pass --native)")
    for name in ("babel-recomp.exe", "babel-recomp", "babel-recomp.nro", "babel-recomp.3dsx"):
        binary = build / name
        if binary.is_file():
            data = binary.read_bytes()
            if native:
                if PRIVATE_ID not in data or PUBLIC_ID in data:
                    raise ValueError("Binary lacks the native execution identity")
            elif PUBLIC_ID not in data or PRIVATE_ID in data:
                raise ValueError("Binary lacks public execution identity; rebuild interpreter-only")
            return binary
    raise ValueError("No supported executable; VPK/APK need their own verified pipeline")


def validate_payload(stage: Path) -> None:
    for path in stage.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Symlink in package: {path.relative_to(stage)}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES or path.name.lower() in FORBIDDEN_NAMES:
            raise ValueError(f"Private/player data in package: {path.relative_to(stage)}")


def package(build: Path, tag: str, root: Path = ROOT, companion: Path | None = None,
            gaialabs: Path | None = None, native: bool = False) -> Path:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", tag):
        raise ValueError("Invalid platform tag")
    binary = validate_build(build, native)
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_-]*", version):
        raise ValueError("Invalid VERSION")
    name = f"babel-recomp-{version}-{tag}"
    dist = root / "dist"
    dist.mkdir(exist_ok=True)
    destination = dist / f"{name}.zip"
    # Unique staging is removed on success/failure; replace an existing archive
    # only after the whole payload passes validation.
    with tempfile.TemporaryDirectory(prefix=".package-", dir=dist) as tmp:
        stage = Path(tmp) / name
        stage.mkdir()
        dest = stage
        if binary.suffix == ".nro":
            dest /= "switch/babel-recomp"
        elif binary.suffix == ".3dsx":
            dest /= "3ds/babel-recomp"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(binary, dest)
        for directory in ("assets", "i18n", "mods/preloaded"):
            # Runtime mod state is written beside the built executable.
            # Packages must use the reviewed source catalog instead.
            source = (root if directory == "mods/preloaded" else build) / directory
            if not source.is_dir():
                raise ValueError(f"Required staged assets missing: {directory}")
            if source.is_symlink():
                raise ValueError(f"Symlink in staged assets: {directory}")
            validate_payload(source)
            shutil.copytree(source, dest / directory)
        if gaialabs is not None:
            # Generated from the public GPL-3.0 Retranslation source; shipped
            # as separate data with its notice and license.
            for filename in ("gaialabs-dialogue.tsv", "gaialabs-world-map.bin"):
                source = gaialabs / filename
                if source.is_symlink() or not source.is_file():
                    raise ValueError(f"Missing or linked GaiaLabs data: {filename}")
                shutil.copy2(source, dest / "i18n" / filename)
            for filename in ("GAIALABS-NOTICE.md", "GPL-3.0.txt"):
                shutil.copy2(root / "res/release" / filename, dest / "i18n" / filename)
        if (root / "res/release/START HERE.txt").is_file():
            shutil.copy2(root / "res/release/START HERE.txt", stage)
        for document in ("LICENSE", "README.md", "MODS.md"):
            shutil.copy2(root / document, stage)
        if (root / "README.es.md").is_file():
            shutil.copy2(root / "README.es.md", stage)
        # Player-facing guides only; development records stay in the repository.
        (stage / "docs").mkdir()
        for document in ("MSU1.md", "CHEATS-AND-MODS.md", "ACHIEVEMENTS-INTEGRATION.md"):
            if (root / "docs" / document).is_file():
                shutil.copy2(root / "docs" / document, stage / "docs")
        if (root / "companion/README.md").is_file():
            (stage / "companion").mkdir()
            shutil.copy2(root / "companion/README.md", stage / "companion")
            if (root / "companion/soundtrack-catalog.json").is_file():
                shutil.copy2(root / "companion/soundtrack-catalog.json", stage / "companion")
        for document in ("snesrecomp/THIRD_PARTY_ATTRIBUTION.md", "scripts/toolchains/README.md"):
            if (root / document).is_file():
                target = stage / document
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root / document, target)
        if companion is not None:
            if binary.name != "babel-recomp.exe":
                raise ValueError("Companion launcher currently supports Windows only")
            # Explicit managed-app allowlist; exclude PDBs, caches and profiles.
            for filename in ("illusion-of-gaia.Companion.exe", "illusion-of-gaia.Companion.dll",
                             "illusion-of-gaia.Companion.deps.json", "illusion-of-gaia.Companion.runtimeconfig.json",
                             "Companion.Launcher.Core.dll", "Companion.Launcher.Windows.dll",
                             "assets/achievements/catalog.json"):
                source = companion / filename
                if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(companion.resolve()):
                    raise ValueError(f"Missing or linked Companion artifact: {filename}")
                target = dest / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            shutil.copy2(root / "companion/LICENSE-CompanionLauncher.txt", stage)
        notice_roots = [root / "snesrecomp", root / "recomp-ui",
                        build / "_deps/sdl3-src", build / "_deps/sdl2-src"]
        notice_count = 0
        for base in notice_roots:
            if not base.exists():
                continue
            for source in sorted(base.rglob("*")):
                if source.is_file() and (source.name.upper().startswith(("LICENSE", "NOTICE"))
                                         or source.name == "THIRD_PARTY_ATTRIBUTION.md"):
                    label = base.name if base.parent == root else f"dependencies/{base.name}"
                    target = stage / "licenses" / label / source.relative_to(base)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    notice_count += 1
        for required in ("snesrecomp/LICENSE", "snesrecomp/THIRD_PARTY_ATTRIBUTION.md", "recomp-ui/LICENSE"):
            if not (stage / "licenses" / required).is_file():
                raise ValueError(f"Required license missing: {required}")
        # CIA/VPK contain opaque payloads: a verified neighboring binary does
        # not establish their provenance, so do not silently copy them.
        validate_payload(stage)
        archive = Path(tmp) / "verified.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for source in sorted(stage.rglob("*")):
                if source.is_file():
                    z.write(source, source.relative_to(stage.parent).as_posix())
        archive.replace(destination)
    print(f"{destination} ({notice_count} dependency notices)")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build", type=Path)
    parser.add_argument("tag")
    parser.add_argument("--companion", type=Path, help="Windows managed launcher output directory")
    parser.add_argument("--gaialabs", type=Path, help="folder holding the generated GaiaLabs dialogue pack and map data")
    parser.add_argument("--native", action="store_true",
                        help="package a build that contains compiled game code (owner decision, November 26, 2026)")
    args = parser.parse_args()
    try:
        package(args.build.resolve(), args.tag, companion=args.companion.resolve() if args.companion else None,
                gaialabs=args.gaialabs.resolve() if args.gaialabs else None, native=args.native)
    except (ValueError, OSError) as error:
        parser.exit(1, f"package_release: {error}\n")
