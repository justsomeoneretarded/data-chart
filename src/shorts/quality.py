"""Technical checks on the finished file. Visual/editorial review is still a human job."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def check(out: Path, expected: float, preview: bool = False, silent_ok: bool = False) -> dict:
    video = out / "video.mp4"
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)],
                                      check=True, capture_output=True, text=True).stdout)
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    a = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    scan = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", "blackdetect=d=0.5:pix_th=0.02,freezedetect=n=-60dB:d=4",
                           "-af", "silencedetect=n=-45dB:d=4", "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    # The last ~3s intentionally hold the final standings.
    freezes = [float(x.split("freeze_start:")[1].split()[0]) for x in scan.stderr.splitlines() if "freeze_start:" in x]
    tests = {
        "h264": v["codec_name"] == "h264",
        "aac": a["codec_name"] == "aac",
        "resolution": (v["width"], v["height"]) == ((540, 960) if preview else (1080, 1920)),
        "duration": abs(float(probe["format"]["duration"]) - expected) < 1,
        "decodes": scan.returncode == 0,
        "no_black": "black_start:" not in scan.stderr,
        "no_frozen_animation": all(f >= expected - 5.5 for f in freezes),  # final standings hold
        "no_long_silence": silent_ok or "silence_start:" not in scan.stderr,
    }
    report = {"passed": all(tests.values()), "checks": tests}
    (out / "quality_report.json").write_text(json.dumps(report, indent=2))
    if not report["passed"]:
        raise RuntimeError("Quality check failed: " + ", ".join(k for k, ok in tests.items() if not ok))
    return report
