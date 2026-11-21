"""Build a review packet from existing #47 sources, completely offline.

No generation, OAuth, publishing, lock reservation or ledger writes. A packet is
not a production receipt and is deliberately outside staging.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil
from PIL import Image
from minomasal_daily_live import choose
from minomasal_v4_47_sureklilik_kontrol import check

ROOT=Path(__file__).resolve().parent

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build_package(output,*,root=ROOT):
    root=Path(root);output=Path(output)
    if output.exists():raise ValueError('review_packet_exists_no_overwrite')
    ledger=root/'minomasal_platform_durumu.json'
    before=digest(ledger)
    number=choose(json.loads(ledger.read_text()))
    if number!=47:raise ValueError('story_47_not_current_ledger_candidate_no_reuse')
    source=root/'minomasal_v4_47_revize_hikaye.json'
    plan_path=root/'minomasal_v4_47_sureklilik_plani.json'
    reference=root/'tonton_referans.png'
    problems,story,plan=check(source,plan_path)
    if problems:raise ValueError('canonical_storyboard_failed_no_packet')
    if plan['reference']!=reference.name:raise ValueError('reference_mismatch')
    with Image.open(reference) as image:
        image.verify()
    with Image.open(reference) as image:reference_info={'size':list(image.size),'mode':image.mode}
    packet={
        'status':'blocked_review_packet_only','number':number,'topic':'Kaybolan Oyuncak Kamyon',
        'ready_for_publication':False,'publication_approved':False,'production_receipt':False,
        'network_calls':0,'new_images':0,'new_audio':False,'new_video':False,
        'story_source':source.name,'story_sha256':digest(source),'plan_sha256':digest(plan_path),
        'ledger_sha256':before,'reference_sha256':digest(reference),'reference':reference_info,
        'scene_count':len(story['scenes']),
        'narration_words':sum(len(s['narration'].split()) for s in story['scenes']),
        'text_storyboard_checks_passed':True,'visual_scene_checks_passed':False,
        'platform_history_verification':'youtube_read_consent_required',
        'known_reference_limitations':{'method':'assistant_visual_inspection_not_production_approval',
            'opaque_background':True,'truck_intersects_right_and_bottom_edges':True,
            'usable_as_identity_reference':True,'usable_as_complete_rgba_production_sprite':False},
        'blockers':['youtube_recent_uploads_not_verified','complete_hash_reviewed_truck_views_missing',
                    'story_specific_scene_images_missing','free_speech_quota_not_verified',
                    'narration_missing','decoded_mp4_and_sync_checks_missing','final_human_publication_approval_missing'],
        'never_do':['regenerate_45_or_46','use_fox_trial_for_story_47','claim_flux_schnell_supports_reference_edits',
                    'pay_or_upgrade','reserve_before_quality_pass','publish_from_this_packet']}
    if digest(ledger)!=before:raise ValueError('ledger_changed_during_review_preparation')
    output.mkdir(parents=True)
    shutil.copyfile(reference,output/'reference.png')
    shutil.copyfile(source,output/'story.json')
    shutil.copyfile(plan_path,output/'storyboard.json')
    (output/'narration.txt').write_text('\n\n'.join(s['narration'] for s in story['scenes'])+'\n')
    (output/'quality-report.json').write_text(json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
    rows=[]
    for scene,state in zip(story['scenes'],plan['scenes']):
        rows.append('<tr><td>'+str(state['number'])+'</td><td>'+html.escape(scene['narration'])+'</td><td>'+html.escape(state['cargo'])+'</td><td>'+html.escape(state['bridge'])+'</td><td>'+html.escape(state['action'])+'</td></tr>')
    page='''<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>MinoMasal #47 inceleme paketi</title>
<style>body{font:17px system-ui;max-width:1100px;margin:30px auto;padding:16px;color:#182536;background:#faf8f3}img{max-width:280px;height:auto}table{border-collapse:collapse;width:100%}td,th{border:1px solid #aaa;padding:12px;text-align:left;vertical-align:top}.blocked{padding:18px;background:#ffebc4}code{overflow-wrap:anywhere}</style>
<h1>#47 — Kaybolan Oyuncak Kamyon</h1><p class="blocked">YAYINA HAZIR DEĞİL. Bu paket video veya yayın onayı değildir. API çağrısı, ücretli üretim ve yayın yapılmadı.</p>
<h2>Mevcut Tonton referansı</h2><img src="reference.png" alt="Mevcut mavi Tonton kamyonu; nihai sahne değildir"><p>Bu referans yeniden üretim değildir. Kaynak opak ve kamyon sağ/alt kenarlarda kesiliyor. Tam, temiz maskeli sahne varlığı olarak kabul edilmedi. Tilki ve kırmızı kamyon test profili bu masala ait değildir.</p>
<h2>Hazır metin ve sahne planı</h2><p>10 sahne, 89 anlatım kelimesi. Kum: 1–8 yüklü, 9 boşaltma, 10 boş. Köprü: 1–7 görünmez, 8–10 görünür. Bunlar metin kontrolleridir; görseller henüz yoktur.</p>
<table><thead><tr><th>Sahne</th><th>Anlatım</th><th>Kum</th><th>Köprü</th><th>Görselde gereken olay</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table>
<h2>Sonraki sıra</h2><ol><li>YouTube yükleme izni korunarak salt okunur izin eklenir.</li><li>Bu referansa uygun tam ve onaylı kamyon varlıkları ile sahne görselleri hazırlanır.</li><li>Mevcut Sami sesinin ücretsiz kotası doğrulanır; ancak bundan sonra ses üretilir.</li><li>Ses, görüntü ve MP4 doğrulanır; gerçek video incelendikten sonra yayın onayı istenir.</li></ol><p>Kaynak ve defter özetleri quality-report.json dosyasında bulunur. Yalnız bu paketi görmek yayın izni vermez.</p></html>'''
    (output/'review.html').write_text(page)
    return packet

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',default='recovery_package')
    args=parser.parse_args()
    try:report=build_package(args.output)
    except (OSError,ValueError,KeyError,RuntimeError,AssertionError):raise SystemExit('Review preparation blocked; no generation, ledger write or publishing.') from None
    print(json.dumps({k:report[k] for k in ('status','number','scene_count','narration_words','ready_for_publication','network_calls')}))

if __name__=='__main__':main()
