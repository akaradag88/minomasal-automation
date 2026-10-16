
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
