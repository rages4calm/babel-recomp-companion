# Launcher batch 001 — 2026-11-02

- Windows .NET Release build: passed, no warnings/errors.
- Locked restore: Core and Windows CompanionLauncher 0.2.0 package hashes verified.
- Adapter fixtures: 30 checks passed using disposable synthetic configs and files,
  including rejection of partial first-run config creation, shared Mode 7 controls
  preserving quality/legacy settings, and Adaptive/legacy VSync parsing.
- Read-only local owner-ROM option: 5 additional checks passed (35 total), covering
  supported USA digest, header normalization and structured direct/Babel launch plans.
- Shared shell smoke: five pages rendered at 1120×800 client size and visually
  reviewed. Draft edits survive navigation, unapplied edits disable Play, and Revert
  restores saved options. Only one profile exists, so profile-switch testing is skipped.
- Actual adapter launch: passed against a copy of the locally built interpreter-only
  engine in a fresh scratch folder. The real launch plan ran 60 frames with dummy
  SDL video/audio, captured `frame.ppm` and exited successfully at the frame cap.
  Original engine and owner-ROM hashes remained unchanged. This checks process
  handoff and bounded boot only; the graphical launcher was not used to click Play.
  The probe now records nonblack pixel count separately; a captured black frame
  does not qualify visible output. The original receipt predates this extra field.
- No controller hardware, audible output, in-game Apply, save loading, natural
  progression, alternate modes or other platforms are qualified by these checks.

Private smoke images and the shared-shell receipt are retained in the current bounded
scratch batch at `.local/batch-001/launcher-smoke/`; no gameplay images are committed.
The graphics-parity five-page smoke is in `.local/batch-001/launcher-parity-smoke/`.
The real adapter/engine receipt is in `.local/batch-001/launcher-engine-smoke/`.
Native/runtime baseline qualification is recorded separately in the project handoff.
