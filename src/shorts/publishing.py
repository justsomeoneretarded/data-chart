"""YouTube title/description/tags from the dataset, and optional private upload."""
from __future__ import annotations

import json
import os
from pathlib import Path

from .dataset import Dataset


def metadata(ds: Dataset, out: Path, layout: str) -> dict:
    names = [e.name for e in ds.entities]
    if ds.kind == "timeseries":
        span = f" ({ds.years[0]}–{ds.years[-1]})"
    elif ds.as_of:
        span = f" ({ds.as_of})"
    else:
        span = ""
    if len(names) == 2:
        title = f"{names[0]} vs {names[1]}: {ds.title}{span}"
    else:
        title = f"{ds.title}{span}"
    if len(title) > 90:
        title = title[:89].rstrip() + "…"
    description = "\n".join(filter(None, [
        title,
        "",
        ds.source.notes,
        "",
        f"Data: {ds.source.publisher} — {ds.source.title}",
        ds.source.url,
        f"Retrieved {ds.source.retrieved_at[:10]}. License: {ds.source.license}" if ds.source.license else "",
        "Values between published data points are interpolated for smooth animation." if ds.kind == "timeseries" else "",
        "",
        "#Shorts #DataVisualization #" + "".join(w.capitalize() for w in ds.title.split()[:3] if w.isalnum()),
    ]))
    tags = list(dict.fromkeys([ds.title, *names[:8], "data visualization", "bar chart race" if layout == "Race" else "comparison", "statistics"]))
    meta = {"title": title, "description": description, "tags": tags, "categoryId": "27", "privacyStatus": "private"}
    (out / "metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    (out / "youtube_title.txt").write_text(title)
    (out / "youtube_description.txt").write_text(description)
    return meta


def upload(out: Path, meta: dict) -> str:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(token=None, refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token",
                        client_id=os.environ["YOUTUBE_CLIENT_ID"], client_secret=os.environ["YOUTUBE_CLIENT_SECRET"])
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = {"snippet": {"title": meta["title"], "description": meta["description"], "tags": meta["tags"], "categoryId": "27"},
            "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False}}
    request = yt.videos().insert(part="snippet,status", body=body,
                                 media_body=MediaFileUpload(str(out / "video.mp4"), chunksize=8 * 1024 * 1024, resumable=True))
    response = None
    while response is None:
        _, response = request.next_chunk(num_retries=3)
    try:
        yt.thumbnails().set(videoId=response["id"], media_body=MediaFileUpload(str(out / "thumbnail.png"))).execute()
    except Exception:
        pass  # custom thumbnails need a verified channel
    (out / "youtube_upload.json").write_text(json.dumps({"video_id": response["id"], "privacy": "private"}, indent=2))
    return response["id"]
