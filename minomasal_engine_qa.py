"""Media checks for a real prepared video; no uploader or API calls."""
import json
import math
from pathlib import Path
import re
import subprocess

class QualityBlocked(RuntimeError):pass

def run(args,timeout=240):
    try:return subprocess.run([str(x) for x in args],capture_output=True,text=True,timeout=timeout,check=False)
    except (OSError,subprocess.TimeoutExpired):raise QualityBlocked('media_tool_unavailable_or_timed_out') from None

def probe_video(path):
    path=Path(path)
    if not path.is_file() or not path.stat().st_size:raise QualityBlocked('video_missing')
    response=run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',path],30)
    try:
        info=json.loads(response.stdout);streams=info['streams']
        video=[s for s in streams if s['codec_type']=='video'];audio=[s for s in streams if s['codec_type']=='audio']
        if response.returncode or len(video)!=1 or len(audio)!=1:raise ValueError()
        v,a=video[0],audio[0];duration=float(info['format']['duration'])
        if not math.isfinite(duration) or not 3<=duration<=180:raise ValueError()
        if (v['width'],v['height'],v['codec_name'],v.get('pix_fmt'))!=(1080,1920,'h264','yuv420p'):raise ValueError()
        if a['codec_name']!='aac' or int(a['sample_rate']) not in (44100,48000) or int(a['channels']) not in (1,2):raise ValueError()
        vd=float(v['duration']);ad=float(a['duration'])
        if not all(math.isfinite(x) and x>0 for x in (vd,ad)) or abs(vd-ad)>.25:raise ValueError()
        starts=[float(s.get('start_time',0)) for s in (v,a)]
        if not all(math.isfinite(x) and -.05<=x<=.15 for x in starts) or abs(starts[0]-starts[1])>.12:raise ValueError()
        numerator,denominator=(float(n) for n in v['avg_frame_rate'].split('/'))
        fps=numerator/denominator
        if not math.isfinite(fps) or not 24<=fps<=60:raise ValueError()
    except (ValueError,KeyError,TypeError,ZeroDivisionError):raise QualityBlocked('mp4_dimensions_codecs_duration_or_sync_invalid') from None
    decoded=run(['ffmpeg','-hide_banner','-v','error','-xerror','-i',path,'-f','null','-'])
    if decoded.returncode:raise QualityBlocked('mp4_full_decode_failed')
    return {'resolution':[1080,1920],'video_codec':'h264','pixel_format':'yuv420p','audio_codec':'aac',
            'duration':round(duration,3),'fps':round(fps,3),'stream_duration_delta':round(abs(vd-ad),3),'full_decode_passed':True}

def signal_checks(path):
    result=run(['ffmpeg','-hide_banner','-i',path,'-af','volumedetect','-vf','blackdetect=d=0.5:pix_th=0.05','-f','null','-'])
    try:
        mean=float(re.search(r'mean_volume:\s*(-?[\d.]+) dB',result.stderr)[1])
        peak=float(re.search(r'max_volume:\s*(-?[\d.]+) dB',result.stderr)[1])
        if result.returncode or not all(math.isfinite(x) for x in (mean,peak)) or not -38<=mean<=-8 or peak>-.3:raise ValueError()
    except (ValueError,TypeError):raise QualityBlocked('audio_silent_clipping_or_level_unverified') from None
    gaps=[float(value) for value in re.findall(r'black_duration:([\d.]+)',result.stderr)]
    if any(gap>.5 for gap in gaps):raise QualityBlocked('extended_black_frames_detected')
    return {'mean_dbfs':mean,'peak_dbfs':peak,'extended_black_frames':False,
            'speech_intelligibility_and_background_balance':'human_listening_required'}

def validate_subtitles(path,total_seconds):
    path=Path(path)
    if not path.is_file():raise QualityBlocked('subtitles_missing')
    text=path.read_text();blocks=text.strip().split('\n\n');last=0
    def seconds(value):
        h,m,s,ms=map(int,re.split('[:,]',value));return 3600*h+60*m+s+ms/1000
    try:
        for index,block in enumerate(blocks,1):
            rows=block.splitlines()
            if int(rows[0])!=index or len(rows)<3 or not ''.join(rows[2:]).strip():raise ValueError()
            start,end=map(seconds,rows[1].split(' --> '))
            if not last<=start<end<=total_seconds+.15:raise ValueError()
            last=end
        if last<total_seconds-.75:raise ValueError()
    except (ValueError,IndexError):raise QualityBlocked('subtitle_timeline_invalid') from None
    return {'subtitle_cues':len(blocks),'last_subtitle_end':last,'timeline_passed':True}

def check(video,subtitles):
    media=probe_video(video);signals=signal_checks(video)
    return {**media,**signals,**validate_subtitles(subtitles,media['duration']),
            'visual_identity_text_logos_and_story_action':'human_review_required',
            'publication_approved':False}
