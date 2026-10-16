
"""Create a Facebook-only MP4 with a cover frame at the start."""

import subprocess
from pathlib import Path


def create_facebook_cover_video(source_video, output_video):
    source_video = Path(source_video)
    output_video = Path(output_video)

    if not source_video.is_file():
        raise RuntimeError("Kaynak video bulunamadı.")

    cover = output_video.with_suffix(".cover.jpg")

    # Extract the frame at 2 seconds.
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", "2",
        "-i", str(source_video),
        "-frames:v", "1",
        str(cover)
    ], check=True)

    # Show the cover for the first 0.5 seconds.
    # Keep the original audio timeline unchanged.
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(source_video),
        "-loop", "1", "-i", str(cover),
        "-filter_complex",
        "[0:v][1:v]overlay=0:0:enable='lt(t,0.5)'[v]",
        "-map", "[v]",
        "-map", "0:a:0",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-c:a", "copy",
        "-movflags", "+faststart",
        "-shortest",
        str(output_video)
    ], check=True)

    print("Facebook kapaklı video hazır:", output_video)

def upload_facebook_cover_asset(number, video_path):
    """Add a separate Facebook MP4 to an existing GitHub Release."""
    import os
    import subprocess

    if number < 22:
        raise RuntimeError("Yalnızca yeni videolar için kullanılabilir.")

    video_path = Path(video_path)
    if not video_path.is_file():
        raise RuntimeError("Facebook video dosyası bulunamadı.")

    tag = f"minomasal-story-{number}"
    filename = f"minomasal-{number}-facebook.mp4"

    token = os.environ["MINOMASAL_HOSTING_TOKEN"]
    env = {**os.environ, "GH_TOKEN": token}
    repo = "akaradag88/minomasal-video-hosting"
    
    # Mevcut dosyanin uzerine yazilmasini engelle.
    result = subprocess.run(
        [
            "gh", "release", "view", tag,
            "--repo", repo,
            "--json", "assets",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    import json
    assets = json.loads(result.stdout).get("assets", [])

    if any(asset.get("name") == filename for asset in assets):
        raise RuntimeError(
            f"Facebook video dosyasi zaten mevcut: {filename}. "
            "Uzerine yazma veya yeniden yukleme yasak."
        )


    subprocess.run([
        "gh", "release", "upload", tag,
        f"{video_path}#{filename}",
        "--repo", repo
    ], env=env, check=True)

    return (
        f"https://github.com/{repo}/releases/download/"
        f"{tag}/{filename}"
    )

def prepare_facebook_cover_asset(number, source_url):
    """Download original MP4, add cover frame, host Facebook copy."""
    import urllib.request
    from tempfile import TemporaryDirectory

    if number < 22:
        raise RuntimeError("Yalnızca 22 ve sonraki videolar için.")

    expected = (
        "https://github.com/akaradag88/"
        "minomasal-video-hosting/releases/download/"
        f"minomasal-story-{number}/minomasal-{number}.mp4"
    )

    if source_url != expected:
        raise RuntimeError("Beklenmeyen kaynak video bağlantısı.")

    with TemporaryDirectory() as temp:
        folder = Path(temp)
        original = folder / "original.mp4"
        facebook = folder / "facebook.mp4"

        urllib.request.urlretrieve(source_url, original)

        create_facebook_cover_video(original, facebook)

        if not facebook.is_file() or facebook.stat().st_size == 0:
            raise RuntimeError("Facebook MP4 oluşturulamadı.")

        return upload_facebook_cover_asset(number, facebook)
