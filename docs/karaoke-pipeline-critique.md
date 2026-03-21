# Documentation Analysis & PRD Critique

## 1. Documentation vs. Codebase Alignment

### Alignment Status
| Document | Status | Alignment with Codebase |
|----------|--------|-------------------------|
| **README.md** | 🟢 Aligned | Accurately reflects multiple inputs (Local/Ollama) and the core Karaoke feature set. |
| **DEVELOPMENT.md** | 🟢 Aligned | Extremely up-to-date (logs changes up to Jan 2, 2026). Accurately describes the *current* "Local MP4 Ingestion" workaround and the *abandoned* "Bright Data" plan (superseded by PRD). |
| **runpod-demucs-worker/** | 🟡 Partial | Directory exists with a functional `handler.py` for stem separation, but **fails to implement** the "Canonical Multi-Audio MP4" remuxing required by the PRD. |

### Identified Variances
1.  **YouTube Strategy**:
    *   **Current (`DEVELOPMENT.md`)**: Plans to use "Bright Data residential proxy" or "Local file ingestion".
    *   **Future (`PRD`)**: Pivots to a "Home Linux PC Agent" model to perform downloads via residential IP, bypassing the need for commercial proxies.
    *   *Critique*: The PRD effectively deprecates the Bright Data plan found in `DEVELOPMENT.md` without updating `DEVELOPMENT.md` to reflect this strategic shift.

2.  **Processing Strategy**:
    *   **Current (`README`/`DEVELOPMENT`)**: Relies on VPS CPU-based processing (Docker containers `containers/demucs`).
    *   **Future (`PRD`)**: Moves heavy lifting to "Runpod Serverless GPU".
    *   *Codebase*: The `runpod-demucs-worker` code exists but is not currently integrated into the main `n8n` pipeline (which still routes to local containers).

3.  **Missing Functionality in Worker**:
    *   The PRD Section 7.1 "Canonical portable artifact" mandates a single `karaoke_six_stem.mp4` with 6 labeled audio tracks.
    *   The `runpod-demucs-worker/handler.py` **only** produces separate `.m4a` stems and `stems.json`. The `remuxMultiAudioMp4` step (PRD Section 6.1) is missing from the code.

---

## 2. Critique of `Features/01-Karaoke/karaoke-pipeline-prd.md`

### Strategy & Architecture
*   **Assessment**: **Strong**. The pivot to a "Home Linux PC" for downloads is a pragmatic solution to the YouTube blocking issue. Residential IPs are the only reliable long-term way to download from YouTube without fighting a constant cat-and-mouse game or paying high proxy fees.
*   **Offloading to Runpod**: Moving Demucs to GPU (Runpod) is excellent. CPU separation on a VPS is too slow for production-level throughput. S3 as a handoff bus is a standard, robust pattern.

### Gaps & Risks
1.  **Home Agent Reliability**:
    *   *Risk*: The pipeline now depends on a consumer-grade PC and residential ISP availability.
    *   *Mitigation*: The PRD mentions "Lease-based claiming" and "Heartbeat", which are good mitigations, but monitoring this will be critical.

2.  **Implementation Gap (Critical)**:
    *   The PRD claims the "Canonical portable artifact" is a core goal (G4), but the provided reference code (`handler.py`) does not implement it.
    *   *Recommendation*: The `handler.py` needs to be updated to include an `ffmpeg` command that maps the 6 WAV stems into a single MP4 container with metadata tracks.

3.  **Manual Upload Flow**:
    *   The PRD Manual Upload flow (Section 6.2) is complex (Presigned URLs -> S3).
    *   *Contrast*: The current "Local MP4 Ingestion" (Jan 1 update) is simpler for the *user* (just a file path) but requires the file to be on the VPS. The PRD's approach is better for *web users* but harder to implement.

### Recommendations
1.  **Update `handler.py`**: Prioritize implementing the multi-track audio remuxing logic in the Runpod worker to match the PRD contract.
2.  **Harmonize Docs**: Update `DEVELOPMENT.md` to mark the "Bright Data" plan as deprecated in favor of the "Home Agent" plan described in the PRD.
3.  **Home Agent Spec**: The PRD outlines the Home Agent but there is no code for it yet. Building a robust Python/Go agent that respects the "lease" system is the next critical path item.

---

## 3. Summary of Action Items
1.  **Code**: Implement multi-audio remuxing in `runpod-demucs-worker/handler.py`.
2.  **Code**: Create the `HomeLinuxAgent` codebase (new component).
3.  **Docs**: Mark "Bright Data" as deprecated in `DEVELOPMENT.md` and link to the PRD.
