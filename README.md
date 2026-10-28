# data-chart — brief in, data Short out

Type one line, get a 1080×1920 YouTube Short built from **real published data**.

**Actions → Generate Short → Run workflow**, then enter a brief:

| Brief | What you get |
|---|---|
| `India vs China population 1960–2024` | Head-to-head: two live counters + a line chart drawing over time |
| `Countries by GDP, 1990–2023` | Bar-chart race of the top 10 |
| `Countries with the highest life expectancy` | Countdown reveal, #10 → #1 |
| `Male vs female population in the USA, 1960–2024` | Head-to-head of two groups inside one country |
| `Barcelona vs Real Madrid trophies` | Category-by-category duel with running totals |

Download the `short-<run id>` artifact when the run finishes. It contains `video.mp4`, `thumbnail.png`, `youtube_title.txt`, `youtube_description.txt`, `dataset.csv` (every value with its source text) and `production_report.md`.

## How it works

```
brief ──► understand (LLM: who, what metric, which years)
      ──► find data   Our World in Data search  → model picks one real chart → download its CSV
                      Wikipedia search          → extract every table       → model points at columns
      ──► dataset.json / dataset.csv            (values come from the source, never the model)
      ──► layout chosen by the data's shape     race · countdown · versus timeline · versus categories
      ──► render (Pillow → FFmpeg) + callouts computed from the data (overtakes, big jumps, final gap)
      ──► quality checks → metadata → optional private upload
```

- Country statistics try **Our World in Data** first (thousands of indicators, public search API, CC BY), then Wikipedia.
- Everything else (clubs, companies, people, cities, records) uses **Wikipedia tables**.
- The model only interprets the brief and *chooses* among real search results / table columns. Numbers are parsed from the source by code.
- **If no real data is found, no video is made.** The run fails with a report explaining what each source returned. Nothing is invented.

## Layouts

The data decides the layout; the **format** input only breaks ties.

- **Race** — yearly data, 3+ subjects. Top 10, smooth rank swaps with anti-flicker, flags, animated axis, watermark year, dimmed end state with the #1 called out.
- **Countdown** — one value per subject (no years). Reveals from last place to #1.
- **Versus timeline** — yearly data, 2 subjects. Two big live counters, “ahead” marker, line chart with the gap shaded in the leader's color.
- **Versus categories** — 2 subjects across categories (e.g. competitions). Mirrored bars revealed one by one, running totals.

All layouts keep content inside the Shorts safe area (clear of the caption bar and side buttons), use a fixed color per subject (never per rank), and show the source under the title.

## Inputs

| Input | Default | Notes |
|---|---|---|
| brief | — | Plain English. Naming the measure plainly works best. |
| format | Auto | Auto / Race / Versus |
| duration | 50 | 30–90 seconds |
| theme | Light | Light / Dark |
| music | Auto | Uses a random track from `assets/music/` if you add any (royalty-free, e.g. YouTube Audio Library), otherwise generated music. `None` for silence. |
| upload_to_youtube | off | Private upload; needs `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` secrets |

The workflow runs `qwen3:8b` through Ollama on the free GitHub runner (model is cached between runs). Change `SHORTS_MODEL` in the workflow to trade speed for accuracy.

## Local use

```bash
pip install -e '.[dev]'
ollama serve & ollama pull qwen3:8b
python -m shorts.main --brief "Countries by CO2 emissions per capita, 1990-2022" --out runs/co2
python -m shorts.main --dataset runs/co2/dataset.json --theme Dark --out runs/co2-dark   # re-render, no search
SHORTS_OFFLINE=1 pytest -q
```

## Limits

- Coverage is whatever OWID and Wikipedia publish. Very niche or very recent topics may have no table.
- The model can still choose the wrong chart or column. Check `dataset.csv` against the source link (in the description) before publishing.
- Timeline animation interpolates between published yearly values.

Fonts: Inter (SIL Open Font License, `assets/fonts/LICENSE.txt`).
