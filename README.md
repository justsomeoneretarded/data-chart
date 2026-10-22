# Fieldnotes — dynamic data videos

Create music-first animated comparisons from a brief in GitHub Actions. The default is now a **plain bar-chart race**, with an alternative **simple two-column icon comparison** inspired by the supplied examples. The earlier narrated explainer remains selectable.

## Run manually

1. Open **Actions → Generate Shorts → Run workflow**.
2. Enter a brief, for example:
   - `Religion race`
   - `Country wise population from 1960 to 2024`
   - `India vs China population from 1960 to 2024`
   - `Show how the largest economies changed over the last 50 years`
3. Keep **format = Auto** and **music = Auto**, then start the run.
4. Open the completed run and download its **youtube-short-output-FORMAT-RUN_ID** artifact. Extract `video.mp4` and `thumbnail.png`.

Only the brief is required. Duration defaults to 50 seconds, accepts 30–90. No API key is needed for generation. Standard public-repository GitHub-hosted runners may be free under GitHub's terms; private-repository quotas and artifact retention still apply. Artifacts expire after 14 days.

## Formats

| Format | What moves | Audio |
|---|---|---|
| **Auto** | Race by default; Versus when the brief says “vs” or “versus” | Original music |
| **Race** | Plain solid bars, country names, values and the year; one short title | Original music |
| **Versus** | Two flat columns with country names/flags, totals, icons and the year; one short title | Original music |
| **Explainer** | Earlier four-scene, speech-led infographic | Neutral Piper narration, captions and quiet ambience |

Race and Versus are continuous visual comparisons. They skip Qwen, TTS and transcription, reducing downloads and runner overhead. They intentionally contain no spoken narration or speech-caption files. Music is synthesized from code: 124 BPM kick, clap, hats, bass, arpeggios and pads; it does not reuse the uploaded reference tracks. Music **None** intentionally produces silence. **Ambient** removes percussion; **Cinematic** uses half-time percussion. The canvas is plain: no channel branding, source captions, ranking badges, leader announcements, progress bars or audio meters. Styles change race-bar colors; Versus keeps its two simple column colors. See [visual direction](docs/VISUAL_DIRECTION.md).

## Simple visual layout

Race displays a white canvas, a short title such as **Population race**, 15 plain bars with country labels and values, and the current year. Versus displays a short metric title, two flat comparison columns, names/flags, totals and proportional icons, and the year. Source and methodology details remain in downloadable files and the YouTube description, not over the video. No source badges, channel branding, leader callouts or footer labels are shown.

For a more provocative supported topic, use `India vs China fertility rates from 1960 to 2024` in Auto mode. This compares births per woman. Sexual-frequency surveys are not implemented and will produce a research error rather than invented rankings.

## Clean sample videos

- [Religion race — download MP4 and source files](https://github.com/justsomeoneretarded/data-chart/actions/runs/39837215411/artifacts/12451043351).
- [Population race — download MP4 and source files](https://github.com/justsomeoneretarded/data-chart/actions/runs/39837215411/artifacts/12450673919).
- [Latest sample run and its artifacts](https://github.com/justsomeoneretarded/data-chart/actions/runs/39837215411) also includes the India–China fertility comparison when its job finishes.

The religion and population generation jobs passed their hosted quality gates and artifact upload. All three plain-format samples passed local media checks. [The GitHub test workflow passed all 57 tests](https://github.com/justsomeoneretarded/data-chart/actions/runs/39837215497), including a frozen-video regression test with and without a declared animation window. Download an artifact ZIP and play `video.mp4`. Artifacts expire after 14 days.

## Supported real data

World Bank annual series for **population, GDP in current US dollars, life expectancy, fertility, and internet use**.

**Religion race** uses Pew Research Center global affiliation estimates, processed by Our World in Data. Its observed benchmarks are **2010 and 2020**, with seven categories: Christianity, Islam, Hinduism, Buddhism, Judaism, other religions, and unaffiliated. Unaffiliated is not a religion. The animation interpolates between these two estimates and does not invent annual observations, older history, later years or projections. Raw estimates and source URLs remain in the artifact. This adapter currently supports global Race only.

For World Bank metrics: Country/territory aggregates are excluded. The default period begins with available continuous annual coverage from 1960 and ends with the latest sufficiently covered source year. Explicit date ranges must be available; “last 50 years” is anchored to the latest available year, not an invented present-year observation.

In Versus, two explicitly named countries are used in brief order. Without country names, the two largest latest-year values are selected and identified in the report. Regional subsets, per-capita variants, sports trophies, youngest-population rankings, sexual-frequency surveys and divorce comparisons require other verified adapters and fail with a diagnostic report. The system does not silently replace them with population data.

`dataset.csv` preserves actual source observations: annual records for World Bank metrics, or the two benchmark years for religion. `source_response.json`, `sources.json`, `research.json`, and `analysis.json` record source URLs, definitions, units, retrieval time, response hash, annual coverage and leader changes. During animation, values are linearly interpolated **between source anchors**. World Bank series require adjacent observed years; religion explicitly uses the 2010 and 2020 benchmarks. Missing values are excluded, never zero. Row positions transition between annual endpoint ranks; these positions are animation, not observed intra-year rankings. This distinction is printed on the video and recorded in reports.

Flags are optional downloads from Flagcdn/Flagpedia; `asset_sources.json` records their provenance. If unavailable, readable ISO3 badges replace them. National-flag reuse restrictions vary by jurisdiction. The supplied inspiration footage, soundtrack and athlete portraits are not redistributed.

## Output

Music-first runs include `video.mp4` (1080×1920, 30fps, H.264/AAC), `thumbnail.png`, original `music.wav` when enabled, SEO metadata, title/description/keywords, storyboard, data/source/asset manifests, audio report, quality report, production report and logs. Failed jobs retain diagnostic artifacts and remain failed. Music-only videos do not fabricate speech transcripts or subtitle files.

Technical gates probe codecs, geometry, duration, A/V sync, full decode, black sequences, frozen sections and unexpected silence. Frozen-frame detection runs over the declared active-animation interval; the 1.2-second opening and 2.5-second final hold are intentional. Full-video decode, black-frame, duration and audio checks still cover the complete file. A regression test encodes a deliberately frozen video and confirms rejection. Editorial value, visual taste and monetization eligibility still require human review; there is no guaranteed monetization score.

## Local use

Requires Python 3.11+, FFmpeg and DejaVu Sans fonts (`apt-get install ffmpeg fonts-dejavu-core` on Ubuntu).

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e . pytest
pytest -q
python -m shorts.main --brief 'Country wise population from 1960 to 2024'
python -m shorts.main --brief 'India vs China population from 1960 to 2024' --format Versus --out output-versus
```

Use a fresh output directory per run. `--preview` produces a diagnostic 540×960 file; normal output is 1080×1920. Seed controls the score; upstream source revisions and encoder versions prevent byte-for-byte reproducibility across environments. Rendering streams frames to FFmpeg with bounded memory.

For the older narrated format:

```bash
pip install -e '.[speech]'
# Install/start Ollama separately and download its model:
ollama pull qwen3:4b
python -m shorts.main --brief 'Which countries have the highest life expectancy?' --format Explainer
```

In Explainer, Qwen generates title/headings; narration is composed from audited facts, then Piper generates speech and faster-whisper checks/aligns it. `--planner editorial` explicitly bypasses Qwen for diagnostics. The voice is `en_US-ljspeech-medium`, whose model card identifies its dataset as public domain. Named presets require authorized references for the experimental Chatterbox backend; the lightweight workflow discloses its neutral Piper fallback. See [voice rights](assets/voices/README.md). Chatterbox CPU performance and unrestricted model-written narration remain unverified.

## Optional private YouTube upload

Generation and artifact delivery are the default. To enable `upload_to_youtube`, configure Google OAuth refresh credentials with upload and uploads-playlist read scopes in GitHub secrets `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`. Enable the YouTube Data API and ensure adequate quota and any required Google verification. The integration requests **private** visibility, records its returned video ID and checks recent uploads for the run marker. It is not an atomic deduplication guarantee and remains unverified against your channel. Custom thumbnail upload and automatic pinned comments are not implemented; generated files are supplied for manual use.

## Troubleshooting

| Problem | Where to look |
|---|---|
| Unsupported topic or year | `failure.json` and `production_report.md`; use a supported metric/range |
| World Bank outage | Retry after recovery; source requests have bounded retries |
| Missing flag | ISO3 fallback is expected; see `asset_sources.json` |
| FFmpeg or quality failure | `pipeline.log`, `ffmpeg_qa.log`, `quality_report.json` |
| No speech | Expected in Race/Versus; choose Explainer for narration |
| Ollama/Piper/Whisper error | Applies only to Explainer; check model/network/disk and speech report |
| Disk/timeout | `runner-resources.txt`; avoid storing model weights in Git |
| Workflow missing | Ensure workflow is on the repository default branch and Actions is enabled |
| YouTube failure | Check OAuth scopes, consent, refresh token and quota; generated artifact remains available |

This remains a curated data-video engine. Broad web research, reliable football-award acquisition, portrait licensing, and unrestricted original AI scripts are additional work, not implied by the visual presets.
