"""Publish a Reel to a Facebook Page via the Graph API (video_reels, 3-step upload)."""
from __future__ import annotations
import os, time
import requests


class FBError(RuntimeError):
    pass


def _check(r: requests.Response, what: str) -> dict:
    try:
        data = r.json()
    except ValueError:
        data = {"raw": r.text}
    if not r.ok or "error" in data:
        raise FBError(f"{what} failed [{r.status_code}]: {data}")
    return data


def post_reel(video_path: str, caption: str, page_id: str, token: str, version: str = "v23.0") -> str:
    endpoint = f"https://graph.facebook.com/{version}/{page_id}/video_reels"

    # 1) start
    start = _check(requests.post(endpoint, data={"upload_phase": "start", "access_token": token}, timeout=60),
                   "upload start")
    video_id, upload_url = start["video_id"], start["upload_url"]

    # 2) upload binary
    size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        up = requests.post(upload_url, data=f, timeout=300, headers={
            "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)})
    _check(up, "binary upload")

    # 3) finish + publish
    _check(requests.post(endpoint, timeout=60, data={
        "access_token": token, "video_id": video_id, "upload_phase": "finish",
        "video_state": "PUBLISHED", "description": caption}), "upload finish")

    # optional: wait for processing status
    for _ in range(12):
        time.sleep(5)
        st = requests.get(f"https://graph.facebook.com/{version}/{video_id}",
                          params={"fields": "status", "access_token": token}, timeout=30).json()
        phase = st.get("status", {}).get("video_status")
        if phase in ("ready", "published"):
            break
        if phase == "error":
            raise FBError(f"Facebook processing error: {st}")
    return video_id
