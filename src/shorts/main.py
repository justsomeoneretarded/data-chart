"""Brief in, finished Short out.

    python -m shorts.main --brief "India vs China population 1960-2024"
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path

log = logging.getLogger("shorts")


def parser() -> argparse.ArgumentParser:
    env = os.getenv
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--brief", default=env("INPUT_BRIEF"))
    p.add_argument("--format", choices=["Auto", "Race", "Versus"], default=env("INPUT_FORMAT") or "Auto")
    p.add_argument("--duration", type=int, default=int(env("INPUT_DURATION") or 50))
    p.add_argument("--theme", choices=["Light", "Dark"], default=env("INPUT_THEME") or "Light")
    p.add_argument("--music", choices=["Auto", "Procedural", "None"], default=env("INPUT_MUSIC") or "Auto")
    p.add_argument("--seed", type=int, default=int(env("INPUT_SEED") or 42))
    p.add_argument("--out", type=Path, default=Path("output"))
    p.add_argument("--dataset", type=Path, help="Re-render an existing dataset.json instead of searching")
    p.add_argument("--preview", action="store_true", help="540x960 quick render")
    p.add_argument("--upload-to-youtube", action="store_true", default=env("INPUT_UPLOAD") == "true")
    return p


def run(args) -> int:
    from .dataset import Dataset, DataError
    out: Path = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(out / "pipeline.log")])
    os.environ["SHORTS_SEED"] = str(args.seed)
    started = time.monotonic()
    stage = "input"
    try:
        if not 30 <= args.duration <= 90:
            raise ValueError("Duration must be 30–90 seconds")
        if args.dataset:
            ds = Dataset.load(args.dataset)
        else:
            if not args.brief or len(args.brief.strip()) < 5:
                raise ValueError("Write a brief of at least 5 characters")
            from .brief import understand
            from .sources import resolve
            stage = "understanding the brief"
            intent = understand(args.brief)
            (out / "intent.json").write_text(intent.model_dump_json(indent=2))
            log.info("Intent: %s", intent.model_dump())
            stage = "finding data"
            ds = resolve(intent, args.brief, out)
        ds.save(out)
        log.info("Data: %s from %s (%d subjects)", ds.kind, ds.source.url, len(ds.entities))

        from .publishing import metadata, upload
        from .quality import check
        from .render import render
        stage = "rendering"
        report = render(ds, out, duration=args.duration, fmt=args.format, theme=args.theme,
                        music=args.music, seed=args.seed, preview=args.preview)
        stage = "quality check"
        check(out, args.duration, args.preview, silent_ok=args.music == "None")
        meta = metadata(ds, out, report["layout"])
        if args.upload_to_youtube and not args.preview:
            stage = "uploading"
            upload(out, meta)
        (out / "production_report.md").write_text(
            f"# ✅ {meta['title']}\n\n"
            f"- Layout: **{report['layout']}**, theme {report['theme']}, {args.duration}s\n"
            f"- Data: {ds.source.publisher} — [{ds.source.title}]({ds.source.url})\n"
            f"- Subjects: {', '.join(e.name for e in ds.entities)}\n"
            f"- Callouts: {'; '.join(c['text'] for c in report['callouts']) or 'none'}\n"
            f"- Music: {report['audio'].get('source')}\n"
            f"- Took {time.monotonic() - started:.0f}s\n\n"
            "Check `dataset.csv` against the source link before publishing.\n")
        log.info("Done: %s", out / "video.mp4")
        return 0
    except Exception as exc:
        honest = isinstance(exc, DataError)
        (out / "failure.json").write_text(json.dumps({"stage": stage, "error": str(exc), "trace": traceback.format_exc()}, indent=2))
        (out / "production_report.md").write_text(
            f"# ❌ No video made\n\nStage: **{stage}**\n\n{exc}\n\n" +
            ("No real data was found, so nothing was invented. Try naming the measure more plainly "
             "(e.g. 'life expectancy' rather than 'how long people live'), or a different year range.\n" if honest else
             "See `pipeline.log` for details.\n") +
            "\nSee `source_attempts.json` for what each source returned.\n")
        log.exception("Failed during %s", stage)
        return 1


def main() -> int:
    return run(parser().parse_args())


if __name__ == "__main__":
    sys.exit(main())
