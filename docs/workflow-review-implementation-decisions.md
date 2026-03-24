# Workflow Review: Implementation Decisions

Date: 2026-03-24
Source: `docs/repo-workflow-review-2026-03-24.md` (Codex agent review, 11 findings)
Implementer: Claude Code

## Summary

Of the 11 findings from the Codex workflow review, 5 were implemented and 6 were skipped. This document records each decision with reasoning.

---

## Findings SKIPPED (6)

### #1 — Non-durable job state (in-memory dict)

**Finding**: Job registry is in-memory. Restart loses all status state.

**Decision**: Skip.

**Reasoning**: This is a single-user local tool. The library scan of `data/*/stems.json` already recovers completed jobs on restart — the only state that matters. In-progress jobs that die mid-pipeline leave partial directories that won't have a `stems.json`, so they naturally don't appear in the library. Adding SQLite or JSONL persistence for a local-only tool with one concurrent user is overengineering.

---

### #2 — Single global processing lock

**Finding**: `_pipeline_lock` enforces one job at a time.

**Decision**: Skip.

**Reasoning**: This is correct design, not a shortfall. Multiple Demucs instances competing for the same GPU thrash VRAM and run slower than sequential processing. The lock IS the right concurrency model for a single-GPU local tool.

---

### #4 — Runtime/doc drift (cloud references in docs/UI)

**Finding**: Cloud/n8n/S3/YouTube language still present.

**Decision**: Skip — already addressed.

**Reasoning**: README was rewritten in the same session that produced the review. UI was confirmed clean of YouTube/cloud references. The finding was valid when written but was resolved before implementation began.

---

### #7 — Resumable/background durability

**Finding**: Backend persistence does not survive process restart.

**Decision**: Skip.

**Reasoning**: Same rationale as #1. For a local single-user tool, crash recovery means "restart and re-upload." The processing time (typically 2-5 minutes) doesn't justify the complexity of checkpointing and resume logic.

---

### #9 — Terminology inconsistency (other/shizzle)

**Finding**: `other` vs `shizzle` naming is confusing.

**Decision**: Skip.

**Reasoning**: This is intentional, not inconsistent. Demucs outputs a stem called `other` (its catch-all channel). The UI displays it as "Shizzle" as a fun user-facing label. The mapping is clean and explicit via `STEM_ID_MAP` and `STEM_DISPLAY_NAMES` in `processing.py`. Both directions are covered: Demucs stem name `other` → UI stem ID `shizzle` → display name `Shizzle`.

---

### #11 — Automated test coverage

**Finding**: Limited test coverage increases regression risk.

**Decision**: Skip (out of scope).

**Reasoning**: Valid finding but orthogonal to this implementation task. Test infrastructure should be a dedicated effort, not bolted on as a side effect of fixing specific issues.

---

## Findings IMPLEMENTED (5)

### #3 — Fix dependency check return code

**Priority**: High
**Files changed**: `local-server/src/local_server/processing.py`

**Problem**: `check_dependencies()` ran `subprocess.run([PYTHON, "-m", "demucs", "--help"])` but only caught exceptions. A non-zero return code (e.g., demucs installed but broken) silently passed the check.

**Fix**: Added `if result.returncode != 0: missing.append("demucs")` after the subprocess call.

**Risk**: Zero. One-line addition inside existing try/except block.

---

### #10 — Stage timings for observability

**Priority**: Medium
**Files changed**: `local-server/src/local_server/models.py`, `local-server/src/local_server/routes.py`

**Problem**: No timing data captured during processing. Impossible to diagnose bottlenecks without manual observation.

**Fix**:
- Added `StageTiming` model (stage, start, end, duration_s) to `models.py`
- Added optional `timings` list field to `JobStatus`
- Updated `on_status` callback in `_run_pipeline` to record `time.monotonic()` timestamps per stage transition
- Timings are closed on completion, failure, or stage transition

**Verified**: November Rain (9:17) pipeline timings:

| Stage | Duration |
|-------|----------|
| Audio extraction | 1.99s |
| Video extraction | 1.01s |
| Demucs GPU split | 43.79s |
| Stem copy | 17.43s |
| Stem compression | 109.0s |
| Multi-track MP4 | 77.76s |

---

### #5 — Retention/cleanup policy

**Priority**: Medium
**Files changed**: `local-server/src/local_server/routes.py`

**Problem**: `data/` grows forever. Each job produces ~1GB of artifacts (WAV stems + video + multi-track).

**Fix**:
- Added `MAX_JOBS = 20` constant
- Added `_enforce_retention()` helper: sorts job dirs by mtime, deletes oldest when count exceeds limit
- Called at the start of `upload_file()` before creating new job directory
- Also cleans up the in-memory `jobs` dict for deleted entries

**Design choice**: Retention runs synchronously on upload rather than as a background timer. This is simpler and sufficient — cleanup only matters when new data is being added.

---

### #6 — Upload validation (size + duration)

**Priority**: Medium
**Files changed**: `local-server/src/local_server/routes.py`

**Problem**: No file size or duration limits. A massive upload could fill disk.

**Fix**:
- Added `MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024` (2 GB) and `MAX_DURATION_SECONDS = 1800` (30 min)
- Replaced `shutil.copyfileobj` with chunked 1MB copy loop that tracks bytes written and raises `ValueError` on overflow
- After save, calls `get_duration()` (already existed in `processing.py`) via ffprobe and rejects if over limit
- On rejection, cleans up partial job directory with `shutil.rmtree`
- Returns HTTP 413 with descriptive message on either limit violation
- If ffprobe fails during duration check, the error is swallowed and the pipeline handles it later (avoids rejecting valid files due to ffprobe edge cases)

---

### #8 — Compressed stems for browser playback

**Priority**: Medium
**Files changed**: `local-server/src/local_server/processing.py`, `local-server/src/local_server/routes.py`

**Problem**: Serving six 24-bit WAV stems per track (~140MB each, ~840MB total) to the browser. Huge download before playback can start.

**Fix**:
- Added `compress_stems()` function: ffmpeg WAV → AAC `.m4a` at 256kbps with `+faststart` per stem
- Called in `run_pipeline()` after stem copy, before manifest write
- Updated `write_manifest()` to auto-detect: uses `.m4a` path if the file exists, falls back to `.wav`
- Added `.m4a` → `audio/mp4` to media type map in `serve_track_file()`
- WAV stems preserved for multi-track MP4 muxing and archival

**Measured result** (November Rain, 9:17):
- WAV stems: 6 x 141MB = **846MB**
- M4A stems: 2-16MB each = **48MB total**
- Compression ratio: **~18x**

**Backwards compatibility**: Older jobs that don't have `.m4a` files continue to work — their manifests still reference `.wav` and the server still serves `.wav` with the correct media type. Zero frontend code changes needed; the manifest drives all file paths.
