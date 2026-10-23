# Brief-driven comparison videos

Run **Actions → Generate Shorts → Run workflow**, enter a brief, and select Race, Versus, or Explainer. Auto chooses Versus when the brief contains “vs” or “versus”; otherwise it chooses Race.

Examples:

- `Male vs female population in the USA, 1960–2025`
- `India vs China unemployment total percent of total labor force national estimate, 2000–2020`
- `Countries by GDP per capita, 1980–2024`
- `Barcelona vs Real Madrid trophies, 1950–2025` — may use the private simulation fallback if real discovery finds no usable source.

## Data discovery

There is no hardcoded metric list, demographic blacklist, country alias map, or topic-specific routing. All formats use the same resolver:

1. Download the live source catalog and country metadata.
2. Infer search terms from the brief and rank catalog entries.
3. Select matching indicators, geography and units from actual metadata IDs.
4. Fetch published observations directly from the source and validate them.
5. If discovery produces no usable comparison, generate a private illustrative simulation and record that provenance in the accompanying files.

The current real-data discovery provider is the World Bank catalog. It supports comparing countries on one indicator, or indicator variants (such as demographic groups) within one country. This removes per-topic adapters, but does **not** yet provide unrestricted web-table research. Topics absent from that source can still fall back to simulation. Topic-specific legacy connectors have been removed.

The model selects metadata, never observations for a real-data run. Unknown IDs, duplicate records, nonfinite or negative values, incompatible declared source units, and insufficient comparable coverage are rejected. Model-assisted semantic selection can still be wrong; inspect the selected definitions. The longest common continuous annual interval is used. Unavailable requested years are omitted rather than invented. Animation interpolates between published annual values.

## Visuals and audio

Race uses a white canvas, one short title, plain moving bars, names, values and the year. Versus uses two simple columns, names, values, proportional symbols and the year. The plan chooses symbols rather than a hardcoded metric-to-icon mapping. National flags are optional when the subjects are countries. Data provenance remains in accompanying files and the description; there are no extra source labels or leader announcements on the comparison video.

Race and Versus use original procedural background music with no speech. Explainer adds neutral Piper narration, captions and a four-scene infographic. All formats use Qwen3 through Ollama for data discovery. Music choices include Electronic, Ambient, Cinematic and None. Duration is 30–90 seconds, default 50.

## Artifacts

Download the completed run's `youtube-short-output-FORMAT-RUN_ID` artifact and extract `video.mp4`. Production videos are 1080×1920, 30fps H.264/AAC. Artifacts are retained for 14 days.

Artifacts include the video, thumbnail, data CSV, research, metadata, original music when enabled, storyboard, source and asset records, quality reports and logs. Real discovery also includes `discovery_candidates.json`, `discovery_selection.json`, `discovered_series.json`, and `discovered_source_response.json`. Simulations include `comparison_plan.json` and identify invented values in `research.json` and the description.

Technical checks cover codecs, dimensions, duration, A/V sync, decode, black frames, unexpected silence and frozen sequences. Opening/final holds are intentional. Infrastructure, model, source and media failures can still fail runs; generation is not guaranteed error-free.

## Local use

Requires Python 3.11+, FFmpeg, DejaVu Sans fonts, and Ollama.

```bash
pip install -e . pytest
ollama serve
# In another shell:
ollama pull qwen3:4b
pytest -q
python -m shorts.main --brief 'Male vs female population in the USA, 1960–2025' --format Race
```

Use a fresh output directory per run. `--preview` generates 540×960 diagnostics. `SHORTS_MODEL` and `OLLAMA_URL` configure the discovery model/server. The seed affects model sampling and music; source revisions and encoders can change output across environments.

For Explainer, install `pip install -e '.[speech]'`. The voice is neutral `en_US-ljspeech-medium`; see [voice setup](assets/voices/README.md). Chatterbox performance and unrestricted narration remain unverified.

## Optional private upload

Generation and artifact delivery are the default; uploading is off. To enable private YouTube upload, configure OAuth secrets `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, and `YOUTUBE_REFRESH_TOKEN`. Channel integration remains unverified. Custom thumbnail upload and automatic pinned comments are not implemented.

## Troubleshooting

- Inspect `pipeline.log`, `failure.json`, and `production_report.md` for failures.
- Inspect `discovery_report.json` to see why real discovery chose simulation.
- Review selected series and units when the comparison is unexpected.
- Missing national flags do not block rendering.
- Ollama is needed for all formats; speech models are needed only for Explainer.
