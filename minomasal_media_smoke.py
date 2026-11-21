"""Real FFmpeg diagnostic, NOT a story/video acceptance or publishing artifact."""
import json
from pathlib import Path
import tempfile
from minomasal_engine_qa import run,check,QualityBlocked

def main():
    out=Path('engine_output');out.mkdir(exist_ok=True)
    report={'synthetic_diagnostic_only':True,'story_video_created':False,'published':False,'passed':False}
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);video=root/'DIAGNOSTIC_NOT_A_STORY.mp4'
            result=run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=0x334455:s=1080x1920:r=30:d=3',
                '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=3','-c:v','libx264','-preset','ultrafast',
                '-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2','-shortest','-movflags','+faststart',video])
            if result.returncode:raise QualityBlocked('diagnostic_encoding_failed')
            subtitle=root/'diagnostic.srt';subtitle.write_text('1\n00:00:00,000 --> 00:00:03,000\nDIAGNOSTIC ONLY\n')
            report.update(passed=True,media=check(video,subtitle))
    except QualityBlocked as error:report['reason']=str(error)
    (out/'ffmpeg-diagnostic.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'diagnostic_passed':report['passed'],'real_story_mp4':False}))
    return int(not report['passed'])

if __name__=='__main__':raise SystemExit(main())
