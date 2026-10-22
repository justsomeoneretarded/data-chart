# Fieldnotes — data to YouTube Shorts

Manually generate narrated vertical explainers from GitHub Actions using free local inference and public World Bank data. This is a working, deliberately limited first release, **not yet the unrestricted automated research studio described in the original brief**.

## Run it on GitHub

1. Open **Actions → Generate Shorts → Run workflow** on the default branch.
2. Enter `Which countries have the highest life expectancy?` in **brief**.
3. Leave the other fields at their defaults and run it.
4. Open the completed run and download **youtube-short-output-RUN_ID** under Artifacts. Extract `video.mp4`, `thumbnail.png`, captions, metadata, and source/quality reports.

No API keys are required to generate a video. The workflow must be present on the default branch for manual dispatch to appear. Public repository standard hosted runners may be free under GitHub's terms; private repositories have quota limits. Model and dataset downloads require network access. Artifacts expire after 14 days. Failed runs upload diagnostic artifacts and remain failed.

## What works and what is limited

- Global highest-value comparisons for **life expectancy, GDP (current US dollars), fertility, internet usage, and population**.
- Live World Bank API retrieval, response hashing, country/territory filtering, common-year coverage selection, CSV and machine-readable sources.
- Qwen3 4B via Ollama supplies presentation headings and title, validated with Pydantic and bounded retries. **Narration is currently composed by an audited editorial routine from the evidence.** This intentionally sacrifices unrestricted AI prose for numerical reliability. Arbitrary creative scripting, automated evidence-backed causal explanations, and universal web research are not implemented.
- Four animated scene families: typography opening, ranking bars, gap comparison, definition/takeaway. This is a reusable visual template; material narrative originality across repeated runs is **not** automatically guaranteed or verified. Maps, race charts, historical comparisons remain future work. Advisory cross-run script/topic/hook similarity checks use GitHub Actions cache; cache eviction or concurrent runs can limit history coverage.
- Piper neutral English narration, per-scene generation, measured speech timing, bounded tempo adaptation, normalization, faster-whisper CPU INT8 speech checks, word timestamps, SRT/VTT/ASS karaoke captions.
- Streaming Pillow/FFmpeg rendering at 1080×1920, 30fps H.264/AAC, original quiet procedural music with speech ducking, thumbnail, SEO/source text.
- FFprobe and full FFmpeg decode, duration, A/V sync, black/frozen-frame and long-silence gates. Label legibility and editorial quality still need review.
- Ambiguous survey topics, divorce comparisons, youngest populations, geographic subsets, and unsupported metric variants fail honestly with a research report. No silent substitute dataset.

**Chatterbox is optional experimental code, not the default.** A runner benchmark has not established Turbo as reliable on free CPUs; Nano is not implemented. Piper is used to keep the default job small and runnable. Named voice choices are retained as requested labels, but the report explicitly discloses the neutral fallback. Authorized reference handling is documented in [assets/voices/README.md](assets/voices/README.md). Do not assume this reproduces Warguy, Kit Laser, or any other identity.

For truly different scripts and broad research coverage, add reviewed source adapters and an evidence-constrained editorial planner before treating this as a production publishing studio. No monetization guarantee is made.

## Verification status

- **22 tests passed**, including an actual FFmpeg encoding/FFprobe integration test and numeric speech-equivalence checks. [Successful test run](https://github.com/justsomeoneretarded/data-chart/actions/runs/39801874182).
- The hosted **Live data smoke test** exercised the same reusable workflow as manual **Generate Shorts**. Its generation job completed successfully with Qwen3 4B, the shipping Piper LJ Speech voice, faster-whisper, rendering, quality gates, and artifact upload. [Generation run](https://github.com/justsomeoneretarded/data-chart/actions/runs/39800724808).
- The artifact was downloaded and inspected: **50.07 seconds, 1080×1920, H.264 video, AAC audio**. All implemented media gates passed. The pipeline reported **310.1 seconds** elapsed; speech generation reported **6.0 seconds** on that runner. These are one-run measurements, not performance guarantees.
- [Download the example output artifact](https://github.com/justsomeoneretarded/data-chart/actions/runs/39800724808/artifacts/12434399954). GitHub authentication may be required; retention is 14 days. It contains the MP4, thumbnail, captions, script, data/source manifests and reports.
- The ambiguous sexual-frequency brief was tested and correctly produced a research failure report without a video.
- Chatterbox inference, voice cloning, broad research connectors, and optional YouTube uploads remain unverified or incomplete as described above. This is not full completion of the unrestricted original specification.

## Local run

Requires Python 3.11+, FFmpeg with libass, and DejaVu Sans fonts (Ubuntu: `apt-get install ffmpeg fonts-dejavu-core`).

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e . pytest
pytest -q
# Start Ollama separately, then:
ollama pull qwen3:4b
python -m shorts.main --brief 'Compare life expectancy across countries'
```

To exercise the full media pipeline without downloading Qwen, explicitly select `--planner editorial`. The production report will disclose this. `--preview` produces a diagnostic 540×960 video. `--duration` accepts 30–90; if speech would need unnatural speed the run fails with a suggested duration. Default scripts best fit 50–70 seconds; the full 30–90 range does not yet guarantee successful narration fitting.

`--style` changes the palette (Auto, Cinematic, Minimal, Energetic, Documentary). Music supports Auto, Electronic, Ambient, Cinematic, None. The first four use a quiet procedural tonal score; they are not a professional music-generation model. Seed controls the planner and score; external dataset revisions, model versions, and encoder details prevent byte-for-byte reproducibility. Customize typography and geometry in `src/shorts/visuals.py`; subtitle styles are in `captions.py`.

Models are loaded sequentially. Ollama is requested to unload after each response; speech and ASR models exist only in their stage. Video frames are streamed rather than retained in memory. No large model cache is uploaded to GitHub. A small script-history cache supports advisory duplicate checks. The workflow records CPU/RAM/disk in its artifact. Dependency major versions are bounded; full transitive dependency locking remains a maintenance improvement.

## Source and claim audit

`source_response.json` preserves the API payload. `sources.json` records URL, dataset, definition, unit, common year, retrieval timestamp, and SHA-256. `dataset.csv` contains all comparable observations; `analysis.json` contains the top five and named source-backed claims. Storyboard `claim_ids` map to these claims. Ranking includes territories according to World Bank coverage and does not treat missing records as zero. One-decimal narration is an explicit display rounding; raw values remain in the CSV.

Model headings still need editorial review for misleading implications. The script currently explains measurement and limitations rather than inventing why a pattern occurs. Licensing: World Bank data generally use CC BY 4.0 with possible third-party exceptions; inspect each indicator metadata page. The default voice is Piper en_US-ljspeech-medium; its model card identifies the LJ Speech source dataset as public domain and is included in the output. Procedural music is original synthesis from this code.

## Optional private YouTube upload

Keep `upload_to_youtube` false unless configured. Create a Google Cloud project, enable YouTube Data API v3, configure an OAuth consent screen, obtain your own refresh token with `youtube.upload` and a read scope for your uploads playlist, then add GitHub repository secrets `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`. Upload uses the official API and always requests **private** visibility. Your project must have sufficient quota and any required Google verification. The run ID is recorded in description metadata and checked against the latest 50 uploads to reduce duplicate retries; it is not an atomic cross-run deduplication guarantee. Custom thumbnail upload and automatic pinned comments are not implemented. Generated files are supplied for manual use. This integration needs validation against your configured channel.

## Troubleshooting

| Failure | Action |
|---|---|
| Research blocked | Read failure.json; use a supported metric. Unsupported requests intentionally fail. |
| World Bank/API errors | Rerun after service recovery; requests retry bounded transient errors. |
| Ollama install/pull | Inspect ollama.log, available disk and network. Qwen is ~several GB. |
| Chatterbox import/CPU | Optional backend requires a separate compatible install; use tested default Piper. |
| Missing reference | Neutral Piper fallback is disclosed; references require explicit rights. |
| Speech mismatch | Read speech_check.json and listen to retained chunks; do not publish failed output. |
| Pacing rejected | Use the suggested duration; 50–70 seconds is best supported currently. |
| FFmpeg error | Check pipeline.log, FFmpeg libass support, and DejaVu fonts. |
| Disk/timeout | Check runner-resources.txt, remove old artifacts, rerun on standard Ubuntu runner. |
| Dependency conflict | Use a fresh Python 3.11 environment. |
| GitHub permission | Enable Actions; workflow files must be on default branch and repository access granted. |
| YouTube failure | Check OAuth scopes, refresh token, quota and consent configuration. Video artifact is retained. |

Review the video, sources, voice rights, synthetic-content disclosure and audience settings before public publication. The workflow never publishes publicly.
