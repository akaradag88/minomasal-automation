#!/usr/bin/env bash
# No secrets, generation, model downloads or publishing. Fail on any install error.
set -euo pipefail

case "${1:-}" in
  system|system-force)
    # Hosted images often already contain both. Avoid unrelated APT mirrors when
    # the required tools are available; retain the fallback for image changes.
    if [[ "$1" == system ]] && command -v ffmpeg >/dev/null && command -v ffprobe >/dev/null &&
       test -r /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf; then
      printf '%s\n' '[dependencies] Existing FFmpeg, ffprobe and DejaVu font found.'
      exit 0
    fi
    apt_options=(-o Acquire::Retries=2 -o Acquire::http::Timeout=30
                 -o Acquire::https::Timeout=30 -o DPkg::Lock::Timeout=60)
    printf '%s\n' '[dependencies] APT metadata (maximum 2 minutes).'
    timeout --signal=TERM --kill-after=15s 2m sudo -n env DEBIAN_FRONTEND=noninteractive \
      apt-get "${apt_options[@]}" update
    printf '%s\n' '[dependencies] FFmpeg and fonts (maximum 5 minutes).'
    timeout --signal=TERM --kill-after=15s 5m sudo -n env DEBIAN_FRONTEND=noninteractive \
      apt-get "${apt_options[@]}" install --yes --no-install-recommends ffmpeg fonts-dejavu-core
    ;;
  python)
    printf '%s\n' '[dependencies] Python and pip versions.'
    timeout --signal=TERM --kill-after=15s 30s python --version
    timeout --signal=TERM --kill-after=15s 30s python -m pip --version
    printf '%s\n' '[dependencies] Python packages (maximum 8 minutes).'
    timeout --signal=TERM --kill-after=15s 8m python -m pip install \
      --disable-pip-version-check --no-input --timeout 30 --retries 2 \
      --progress-bar off --prefer-binary -r requirements-minomasal-daily.txt
    printf '%s\n' '[dependencies] Installed package consistency.'
    timeout --signal=TERM --kill-after=15s 30s python -m pip check
    ;;
  verify)
    printf '%s\n' '[dependencies] Import and media-tool checks; no model is instantiated.'
    timeout --signal=TERM --kill-after=15s 45s python -c \
      'import edge_tts, numpy, requests; from PIL import Image; from google import genai; from google.auth.transport.requests import Request; from googleapiclient.discovery import build; import google_auth_httplib2; from faster_whisper import WhisperModel'
    timeout --signal=TERM --kill-after=15s 15s ffprobe -version
    timeout --signal=TERM --kill-after=15s 15s ffmpeg -hide_banner -filters | \
      grep -E '(^| )ass( |$)' || { printf '%s\n' 'FFmpeg ass filter check failed'; exit 1; }
    test -r /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
    ;;
  *) printf '%s\n' 'Usage: install-minomasal-dependencies.sh system|system-force|python|verify' >&2; exit 2 ;;
esac
