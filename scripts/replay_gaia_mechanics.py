"""Replay private assisted fixtures against a frozen witness and a new build.

CLI: --binary EXE --rom ROM --plan PLAN --output NEW_PRIVATE_DIRECTORY
Plans and evidence stay private. Passing preserves only the witness's bounded
semantic observations through identical inputs, state snapshots and outputs;
it cannot establish naturally earned abilities, progression or campaign proof.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from check_assisted_routes import ROOT, run
from compare_native_runs import APU_STATE_SUFFIXES, STATE_SUFFIXES, compare

SCHEMA = "gaia mechanics replay v1"
SUFFIXES = STATE_SUFFIXES + (".apu.tsv", ".dma.tsv", ".ppuw.tsv", ".apu-clock.tsv") + APU_STATE_SUFFIXES
NAME = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}\Z")
WINDOWS_DEVICES = {"con", "prn", "aux", "nul"} | {prefix + str(n) for prefix in ("com", "lpt") for n in range(1, 10)}
TAG = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
WRITE = re.compile(r"f([0-9]+)\s+([0-9A-F]{2}):([0-9A-F]{4})=([0-9A-F]{2}|[0-9A-F]{4}) w([12]) ([^\r\n]+)\Z")
WLOG_CAP = 100000  # Same bounded cap requested by check_assisted_routes.run.
SCOPE = ("Assisted bounded replay. Source semantic conditions carry only because the "
         "bound witness, new forced interpreter and new mixed-native run have identical "
         "inputs, traces, state/frame snapshots and outputs under the executed APU-cycle "
         "comparison contract. Attestation metadata alone is not evidence. No naturally "
         "earned effects, physical hardware timing or campaign certification.")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("Non-finite JSON number")
        return number
    def constant(value):
        raise ValueError(f"Non-finite JSON constant: {value}")
    if path.stat().st_size > 16 * 1048576:
        raise ValueError("JSON evidence exceeds 16 MiB")
    result = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                        parse_float=finite, parse_constant=constant)
    if not isinstance(result, dict):
        raise ValueError("JSON object required")
    return result


def private_path(value, *, directory=False, fresh=False) -> Path:
    if not isinstance(value, (str, Path)) or not str(value):
        raise ValueError("Explicit private path required")
    path = Path(value).resolve()
    private = (ROOT / ".local").resolve()
    if not private.is_relative_to(ROOT.resolve()) or not path.is_relative_to(private) or path == private:
        raise ValueError(f"Path must resolve inside project .local: {path}")
    if fresh:
        if path.exists() or path.is_symlink():
            raise ValueError(f"Output must be fresh: {path}")
    elif not (path.is_dir() if directory else path.is_file()):
        raise ValueError(f"Missing private {'directory' if directory else 'file'}: {path}")
    return path


def check_hash(path: Path, expected):
    if not isinstance(expected, str) or not HASH.fullmatch(expected) or sha(path) != expected:
        raise ValueError(f"Missing/invalid or mismatched SHA-256: {path}")


def witness_inventory(witness: Path, receipt: dict) -> dict[str, str]:
    """Hash exactly the artifacts consumed by the cycles/device/state comparator."""
    witness = private_path(witness, directory=True)
    entries = receipt.get("snapshots")
    if not isinstance(entries, list) or not 1 <= len(entries) <= 256:
        raise ValueError("Witness requires 1..256 snapshot entries")
    tags = [entry.get("tag") if isinstance(entry, dict) else None for entry in entries]
    if any(not isinstance(t, str) or len(t) > 128 or not TAG.fullmatch(t) or t in (".", "..") for t in tags):
        raise ValueError("Invalid witness snapshot tag")
    if len(set(t.casefold() for t in tags)) != len(tags):
        raise ValueError("Duplicate witness snapshot tags")
    expected = {"trace.csv", "final.ppm", "mods/preloaded/state.toml"}
    if receipt.get("watch_wram") is not None:
        expected.add("wram-writes.log")
    expected.update("snapshots/" + tag + suffix for tag in tags for suffix in SUFFIXES)
    for suffix in SUFFIXES:
        actual = {p.name for p in (witness / "snapshots").glob("*" + suffix)}
        if actual != {tag + suffix for tag in tags}:
            raise ValueError(f"Witness snapshot inventory mismatch: {suffix}")
    hashes = {}
    for name in sorted(expected):
        path = private_path(witness / name)
        if not path.is_relative_to(witness) or not path.stat().st_size:
            raise ValueError("Empty or escaping witness artifact")
        hashes[name] = sha(path)
    return hashes


def _integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} must be integer {low}..{high}")


def parse_write_line(line: str, frames: int, watch: list[int] | tuple[int, int]) -> dict:
    """Decode stable store facts; function labels are intentionally not identity."""
    match = WRITE.fullmatch(line)
    if not match or len(line) > 4096:
        raise ValueError("Malformed WRAM write-event line")
    frame, bank, address, value, width, context = match.groups()
    event = {"frame": int(frame), "bank": int(bank, 16), "address": int(address, 16),
             "value": int(value, 16), "width": int(width)}
    ipc = re.findall(r"(?:^|\s)IPC=([0-9A-F]{6})(?=\s|$)", context)
    if len(value) != event["width"] * 2 or len(ipc) != 1:
        raise ValueError("Malformed WRAM width/value or IPC context")
    if not 0 <= event["frame"] < frames or not watch[0] <= event["address"] <= watch[1]:
        raise ValueError("WRAM write event outside frame/watch bounds")
    if event["address"] + event["width"] > 65536:
        raise ValueError("WRAM write crosses address boundary")
    return {**event, "ipc": ipc[0]}


def check_write_events(directory: Path, expected: list[dict], frames: int,
                       watch: list[int] | tuple[int, int], reference: bool) -> dict:
    """Require expected stores in THIS run's log, never in historical metadata."""
    directory = private_path(directory, directory=True)
    path = private_path(directory / "wram-writes.log")
    if not path.is_relative_to(directory) or path.stat().st_size > 64 * 1048576:
        raise ValueError("Escaping or oversized WRAM write log")
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or len(lines) >= WLOG_CAP:
        raise ValueError("Empty or possibly capped WRAM write log")
    observed = [parse_write_line(line, frames, watch) for line in lines]
    if any(a["frame"] > b["frame"] for a, b in zip(observed, observed[1:])):
        raise ValueError("WRAM write frames are not ordered")
    matches = []
    for event in expected:
        found = [row for row in observed if all(row[key] == event[key]
                 for key in ("frame", "bank", "address", "value", "width"))
                 and (not reference or event.get("reference_ipc") is None or row["ipc"] == event["reference_ipc"])]
        if not found:
            raise ValueError(f"Required fresh WRAM write event absent: {event}")
        matches.append({"expected": event, "observed": found[0]})
    return {"passed": True, "log": str(path), "sha256": sha(path), "observed_rows": len(observed),
            "matches": matches, "source_ipc_required": reference,
            "scope": "Exact frame/bank/address/value/width. Reference requires supplied original IPC; native function label/IPC may differ. Other state/output parity remains separately required."}


def _write_contract(case: dict) -> tuple[list[int] | None, list[dict]]:
    watch, events = case.get("watch_wram"), case.get("expected_write_events", [])
    if watch is not None:
        if not isinstance(watch, list) or len(watch) != 2:
            raise ValueError("watch_wram requires integer [low,high]")
        for number in watch:
            _integer(number, 0, 65535, "watch_wram")
        if watch[0] > watch[1]:
            raise ValueError("watch_wram bounds reversed")
    if not isinstance(events, list) or len(events) > 64 or (events and watch is None):
        raise ValueError("Up to 64 expected_write_events require a watch range")
    identities = set()
    for event in events:
        if not isinstance(event, dict) or set(event) - {"frame", "bank", "address", "value", "width", "reference_ipc"}:
            raise ValueError("Malformed expected WRAM event")
        for key, low, high in (("frame", 0, case["frames"] - 1), ("bank", 0, 255),
                                ("address", watch[0], watch[1]), ("width", 1, 2)):
            _integer(event.get(key), low, high, key)
        _integer(event.get("value"), 0, (1 << (8 * event["width"])) - 1, "value")
        if event["address"] + event["width"] > 65536:
            raise ValueError("Expected WRAM event crosses address boundary")
        ipc = event.get("reference_ipc")
        if ipc is not None and (not isinstance(ipc, str) or not re.fullmatch(r"[0-9A-F]{6}", ipc)):
            raise ValueError("Expected reference_ipc requires six uppercase hex digits")
        identity = tuple(event.get(key) for key in ("frame", "bank", "address", "value", "width", "reference_ipc"))
        if identity in identities:
            raise ValueError("Duplicate expected WRAM event")
        identities.add(identity)
    return watch, events


def validate_plan(plan: Path, output: Path) -> dict:
    """Validate every case and frozen witness before any output or process exists."""
    plan = private_path(plan)
    output = private_path(output, fresh=True)
    data = read_json(plan)
    cases = data.get("cases")
    if data.get("schema") != SCHEMA or not isinstance(cases, list) or not 1 <= len(cases) <= 64:
        raise ValueError("Expected gaia mechanics replay v1 with 1..64 cases")
    expected_rom = re.search(r"^expected_sha256\s*=\s*([0-9a-f]{64})$",
                             (ROOT / "rom_identity.txt").read_text(), re.M)[1]
    names = set()
    normalized = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Case must be an object")
        name = case.get("name")
        if (not isinstance(name, str) or not NAME.fullmatch(name)
                or name in WINDOWS_DEVICES or name.casefold() in names):
            raise ValueError("Unsafe or duplicate case name")
        names.add(name.casefold())
        for key, low, high in (("frames", 60, 10000), ("rate", 1, 8)):
            _integer(case.get(key), low, high, key)
        for key in ("infinite_hp", "wide"):
            if type(case.get(key)) is not bool:
                raise ValueError(f"Explicit boolean required: {key}")
        watch, events = _write_contract(case)
        if "expect_scene" not in case:
            raise ValueError("Explicit expect_scene (or null) required")
        if case["expect_scene"] is not None:
            _integer(case["expect_scene"], 0, 255, "expect_scene")
        attestation = case.get("semantic_attestation")
        if not isinstance(attestation, dict) or not attestation or len(json.dumps(attestation)) > 65536:
            raise ValueError("Bounded source semantic attestation object required")
        script = private_path(case.get("script"))
        check_hash(script, case.get("script_sha256"))
        seed = private_path(case["seed"]) if case.get("seed") is not None else None
        if seed:
            check_hash(seed, case.get("seed_sha256"))
        elif case.get("seed_sha256") is not None:
            raise ValueError("Seed hash without seed")
        witness = private_path(case.get("witness_dir"), directory=True)
        receipt_path = private_path(witness / "receipt.json")
        if not receipt_path.is_relative_to(witness):
            raise ValueError("Witness receipt escapes its directory")
        check_hash(receipt_path, case.get("witness_receipt_sha256"))
        receipt = read_json(receipt_path)
        checks = receipt.get("checks")
        if (receipt.get("schema") != "iog-native-route-v1" or receipt.get("passed") is not True
                or not isinstance(checks, dict) or not checks or any(v is not True for v in checks.values())):
            raise ValueError("Witness must have an explicitly passed route receipt")
        identities = receipt.get("input_sha256", {})
        if any(not isinstance(identities.get(key), str) or not HASH.fullmatch(identities[key])
               for key in ("rom", "route", "binary")):
            raise ValueError("Missing witness input identity")
        if (identities["rom"] != expected_rom or identities["route"] != case["script_sha256"]
                or identities.get("seed_state") != case.get("seed_sha256")):
            raise ValueError("Witness input identity mismatch")
        if (receipt.get("frames_requested") != case["frames"] or receipt.get("frames_traced") != case["frames"]
                or receipt.get("widescreen") is not case["wide"]
                or receipt.get("infinite_hp", False) is not case["infinite_hp"]
                or receipt.get("room_reward_multiplier", 1) != case["rate"]):
            raise ValueError("Witness options mismatch")
        if receipt.get("watch_wram") != watch:
            raise ValueError("Witness watch_wram mismatch")
        hashes = witness_inventory(witness, receipt)
        if case.get("witness_files_sha256") != hashes:
            raise ValueError("Witness artifact hashes/inventory mismatch")
        if receipt.get("fixture_mod_state_sha256") != hashes["mods/preloaded/state.toml"]:
            raise ValueError("Witness mod-state identity mismatch")
        for snapshot in receipt["snapshots"]:
            if snapshot.get("wram_sha256") != hashes["snapshots/" + snapshot["tag"] + ".wram.bin"]:
                raise ValueError("Witness WRAM receipt hash mismatch")
        if events:
            check_write_events(witness, events, case["frames"], watch, reference=receipt.get("interpret_all") is True)
        normalized.append({**case, "script": str(script), "seed": str(seed) if seed else None,
                           "witness_dir": str(witness)})
    return {**data, "cases": normalized, "plan_path": str(plan), "plan_sha256": sha(plan), "output": str(output)}


def replay(binary: Path, rom: Path, plan: Path, output: Path, timeout: int = 180) -> dict:
    """Execute a fully validated plan; leave every failed comparison in place."""
    _integer(timeout, 1, 300, "timeout")
    binary = private_path(binary)
    rom = Path(rom).resolve()
    if not rom.is_file() or not rom.is_relative_to(ROOT.resolve()):
        raise ValueError("Explicit project-owned stock ROM required (read-only)")
    expected = re.search(r"^expected_sha256\s*=\s*([0-9a-f]{64})$", (ROOT / "rom_identity.txt").read_text(), re.M)[1]
    if rom.stat().st_size != 2097152 or sha(rom) != expected:
        raise ValueError("Verified bare USA ROM required")
    validated = validate_plan(plan, output)
    # Validate witness formats as well as hashes before starting any engine.
    for case in validated["cases"]:
        witness = Path(case["witness_dir"])
        if compare(witness, witness, 0, devices=True, apu_clock="cycles", apu_state=True)["passed"] is not True:
            raise ValueError(f"Malformed/incomplete witness comparison artifacts: {case['name']}")
    output = Path(validated["output"])
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema": SCHEMA, "passed": False, "scope": SCOPE,
              "plan_sha256": validated["plan_sha256"], "binary": str(binary), "binary_sha256": sha(binary),
              "rom_sha256": expected, "runner_source_sha256": sha(Path(__file__)),
              "lineage": validated, "cases": []}
    def save():
        (output / "replay-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    save()
    for case in validated["cases"]:
        folder = output / case["name"]
        folder.mkdir()
        row = {"name": case["name"], "passed": False, "semantic_conditions_carried": False,
               "witness_receipt_sha256": case["witness_receipt_sha256"], "comparisons": {}}
        report["cases"].append(row)
        try:
            paths = {"reference": folder / "reference", "native": folder / "native"}
            for mode, path in paths.items():
                receipt = run(binary, rom, Path(case["script"]), path, case["frames"],
                              Path(case["seed"]) if case["seed"] else None, rate=case["rate"],
                              interpret_all=mode == "reference", expect_scene=case["expect_scene"],
                              timeout=timeout, capture=True, wide=case["wide"], infinite_hp=case["infinite_hp"],
                              watch_wram=tuple(case["watch_wram"]) if case.get("watch_wram") is not None else None)
                row[mode + "_passed"] = receipt.get("passed") is True
                row[mode + "_receipt_sha256"] = sha(path / "receipt.json")
            witness = Path(case["witness_dir"])
            for name, left, right, minimum in (("witness-reference", witness, paths["reference"], 0),
                                                ("reference-native", paths["reference"], paths["native"], .001),
                                                ("witness-native", witness, paths["native"], .001)):
                result = compare(left, right, minimum, devices=True, apu_clock="cycles", apu_state=True)
                target = folder / (name + ".json")
                target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
                row["comparisons"][name] = {"passed": result.get("passed") is True,
                                            "path": str(target), "sha256": sha(target)}
            if case.get("expected_write_events"):
                row["write_events"] = {}
                for mode, path in paths.items():
                    row["write_events"][mode] = check_write_events(
                        path, case["expected_write_events"], case["frames"], case["watch_wram"],
                        reference=mode == "reference")
            # Bind the comparisons to the same artifacts validated before execution.
            check_hash(Path(case["script"]), case["script_sha256"])
            if case["seed"]:
                check_hash(Path(case["seed"]), case["seed_sha256"])
            check_hash(witness / "receipt.json", case["witness_receipt_sha256"])
            if witness_inventory(witness, read_json(witness / "receipt.json")) != case["witness_files_sha256"]:
                raise ValueError("Witness changed during replay")
            row["passed"] = row["reference_passed"] and row["native_passed"] and all(
                x["passed"] for x in row["comparisons"].values())
            row["semantic_conditions_carried"] = row["passed"]
        except Exception as error:
            row["error"] = f"{type(error).__name__}: {error}"
        save()
    report["passed"] = len(report["cases"]) == len(validated["cases"]) and all(x["passed"] for x in report["cases"])
    try:
        validate_plan(plan, output / "unused-fresh-validation-target")
    except Exception as error:
        report["final_validation_error"] = f"{type(error).__name__}: {error}"
        report["passed"] = False
    report["inputs_unchanged"] = sha(binary) == report["binary_sha256"] and sha(rom) == expected and sha(plan) == validated["plan_sha256"]
    report["passed"] = report["passed"] and report["inputs_unchanged"]
    save()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("binary", "rom", "plan", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    result = replay(args.binary, args.rom, args.plan, args.output, args.timeout)
    print(json.dumps({"passed": result["passed"], "cases": len(result["cases"]),
                      "report": str(args.output / "replay-report.json")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
