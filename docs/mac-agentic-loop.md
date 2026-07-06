# Mac agentic loop — Claude Code + Xcode side-by-side

> **What this is.** How to run an AI coding assistant on the Mac that can build the
> apps, launch the iOS Simulator, read the errors, and iterate — while staying in
> sync with the same `main` trunk the web sessions push to. Counterpart: the web
> session workflow in `CLAUDE.md` "Branch & sync protocol"; this doc is the Mac
> analog.

## Why this shape, not "AI inside Xcode"

Nothing runs *inside* Xcode as an agent today (Xcode 16's Coding Intelligence is
chat + inline edit — no build/run/fix loop, no goals). The pattern that works:

- **Xcode stays open** for breakpoints, Instruments, real-device deploys.
- **A Claude Code CLI session runs in a terminal next to it**, edits Swift files
  directly, drives `xcodebuild` + `xcrun simctl` in a loop, reads the output, fixes.
- **The repo is the sync point** — same `main` as the web sessions.

The alternative (Cursor + Sweetpad, giving Cursor Agent Mode xcodebuild/simctl
inside the editor) has equivalent capability but a second UX to keep in your head.
This project already lives in Claude Code on the web, so the CLI on the Mac
inherits the same `CLAUDE.md`, skills, and workflow.

## One-time setup

```bash
# 1. Claude Code CLI
npm i -g @anthropic-ai/claude-code

# 2. Xcode + tools (once)
xcode-select --install
brew install xcodegen

# 3. Repo
git clone <origin> vbt && cd vbt
xcodegen generate
open VBT.xcodeproj    # keep this open for the whole session

# 4. Start Claude Code from the repo root
claude
```

First-time first-build gotchas (signing, developer mode, watch pairing) live in
`README.md` → "First-build checklist" — those still apply.

## The loop

Inside Claude Code, the commands you'll ask it to run:

```bash
# Build for the simulator (fast; no signing)
xcodebuild build \
  -project VBT.xcodeproj \
  -scheme VBTPhone \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro'

# Same for the watch app (paired-sim setup requires the phone build to already succeed)
xcodebuild build \
  -project VBT.xcodeproj \
  -scheme VBTWatch \
  -destination 'platform=watchOS Simulator,name=Apple Watch Ultra 2 (49mm)'

# Run the VBTCore Swift package tests (no simulator needed — fastest signal)
xcodebuild test \
  -project VBT.xcodeproj \
  -scheme VBTCore \
  -destination 'platform=macOS'

# Boot a simulator + take a screenshot Claude can look at
xcrun simctl boot "iPhone 16 Pro" || true
xcrun simctl install booted /path/to/VBTPhone.app
xcrun simctl launch booted com.vbt.app
xcrun simctl io booted screenshot /tmp/vbt-phone.png

# Simulator logs (streamable)
xcrun simctl spawn booted log stream --predicate 'subsystem == "com.vbt.app.watchkitapp"'
```

**Prompt shape that converges fast.** Vague goals ("make it work") burn build
cycles. Sharp goals produce clean loops:

- ✅ "Get the `VBTCore` package tests green after the gyro-schema change."
- ✅ "Make `VBTPhone` build for iPhone 16 Pro sim; fix any type errors."
- ✅ "The Capture tab should show a red RECORD button; take a screenshot to
  confirm." (Claude runs simctl screenshot and inspects the PNG.)
- ❌ "Fix the app."

## Pre-approving the shell commands

Otherwise Claude Code prompts on every `xcodebuild`. Repo-local overrides go in
`.claude/settings.local.json` (git-ignored — safe for personal preferences):

```json
{
  "permissions": {
    "allow": [
      "Bash(xcodebuild:*)",
      "Bash(xcrun simctl:*)",
      "Bash(xcodegen:*)",
      "Bash(swift build:*)",
      "Bash(swift test:*)"
    ]
  }
}
```

After a session, running the `/fewer-permission-prompts` skill will scan your
transcript and suggest a further tightened allowlist.

## Staying in sync with the web sessions

The `CLAUDE.md` "Branch & sync protocol" applies verbatim on the Mac. The only
Mac-specific note is which subtrees belong to which side:

| Side | Owns | Rationale |
|---|---|---|
| Mac (Claude Code CLI + Xcode) | `Watch/`, `iOS/`, `Packages/`, `Config/`, `project.yml`, `.xcconfig` | Only side that can build & run Swift. |
| Web (Claude Code) | `analysis/`, `dataset/`, `docs/` (mostly), `scripts/`, `tests/` | Python + data + writing. |

Neither side is forbidden from the other's subtree, but if both sides touch the
same one in the same day, expect a rebase. The `dataset/` rule from CLAUDE.md —
one session at a time — is unchanged; it just tends to be the web side by
default.

**Every session (Mac OR web) still:**

1. Starts by syncing `main`: `git fetch origin --prune && git checkout main && git pull --ff-only origin main`.
2. Works on `main` for routine changes; short-lived `session/<topic>` branch for
   larger/riskier work, **merged back to `main` same session.**
3. Ends by pushing `main`.

The Mac's advantage over a web session: your local container is persistent, so a
half-finished loop isn't lost if you close the terminal. The Mac's obligation:
push before opening a web session (or the web session sees stale trunk), and
pull before starting a Mac session (or you rebase later).

## What the sim CAN'T tell you

The agentic loop covers SwiftUI/plumbing/type-checks/tests/UI. It CANNOT
validate:

- **`CMBatchedSensorManager` at ~200 Hz** — the simulator has no motion. Needs a
  real Apple Watch Ultra (per the 2026-06-15 validation).
- **`HKWorkout` persistence + Athlytic ingest** — sim HealthKit exists but
  Athlytic isn't installed there and HK behavior differs. Real paired
  phone + watch.
- **`WatchConnectivity` file transfer** — reliable only on real paired hardware;
  sim WCSession is flaky.
- **Camera capture / `AVCaptureEventInteraction` (BT clicker)** — no camera, no
  Bluetooth HID in the sim.

Rule of thumb: the sim + agentic loop takes any change from "written" to
"compiles + tests pass + UI renders." Everything sensor/HK/BT still needs a
15-minute real-device deploy at the end. Don't skip that step just because the
loop said green.
