"""Free-only text routing. #47 is always the canonical local story, never LLM.

A human account attestation is required before Gemini inference; catalogue access
is not proof of a free account. HTTP errors never include raw upstream text.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import time
import requests
from minomasal_kalite_v2 import dictionary_entry,verify_and_enrich
from minomasal_daily_live import choose

ROOT=Path(__file__).resolve().parent
TEXT_MODEL='gemini-3.8-flash'
class StoryBlocked(RuntimeError):pass

def fingerprint(story):
    text=' '.join(s['narration'] for s in story['scenes'])
    normalized=re.sub(r'\W+',' ',text.casefold()).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()

def validate_story(story,number,topic):
    # Existing quality guard checks scene count, word count, cast names and
    # narration/visual object alignment without mutating the original input.
    from minomasal import KONULAR
    if number<1 or KONULAR[number-1]!=topic:raise StoryBlocked('story_identity_mismatch')
    _,cast,_=dictionary_entry(topic,KONULAR)
    if not 1<=len(cast)<=4:raise StoryBlocked('cast_missing_or_over_four')
    try:verify_and_enrich(story,topic,KONULAR)
    except (ValueError,KeyError,TypeError):raise StoryBlocked('local_story_quality_failed') from None
    texts=[' '.join(s['narration'].casefold().split()) for s in story['scenes']]
    if len(set(texts))!=len(texts):raise StoryBlocked('repeated_scene_narration')
    narration=' '.join(texts)
    if not any(c in narration for c in 'çğıöşü') or sum(narration.split().count(w) for w in ('bir','ve','bu','için','sonra','ama','yolunu','gördü','kum'))<2:
        raise StoryBlocked('turkish_language_heuristic_failed')
    if re.search(r'\b(intihar|öldürmek|tecavüz|pornografi)\b',narration):raise StoryBlocked('unsafe_story_terms')
    return story

def local_story(number,topic,root=ROOT):
    root=Path(root).resolve();catalog=json.loads((root/'story_queue/catalog.json').read_text())
    entry=catalog.get('stories',{}).get(str(number),{})
    if entry.get('approved') is not True or not entry.get('approval_source') or entry.get('topic')!=topic:
        raise StoryBlocked('approved_local_story_missing')
    path=(root/entry.get('path','')).resolve()
    if not path.is_relative_to(root) or not path.is_file():raise StoryBlocked('local_story_path_invalid')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=entry.get('sha256'):raise StoryBlocked('local_story_changed_since_approval')
    story=json.loads(path.read_text())
    if number==47:
        canonical=root/'minomasal_v4_47_revize_hikaye.json'
        if path!=canonical or entry['sha256']!=hashlib.sha256(canonical.read_bytes()).hexdigest():
            raise StoryBlocked('canonical_47_required')
    return validate_story(story,number,topic)

def gemini_story(topic,*,transport=requests.post,sleep=time.sleep):
    if os.environ.get('MINOMASAL_GEMINI_FREE_TIER_CONFIRMED')!='true':raise StoryBlocked('gemini_free_account_not_attested')
    key=os.environ.get('GEMINI_API_KEY','')
    if not key:raise StoryBlocked('gemini_key_missing')
    from minomasal_kalite_v2 import prompt_rules
    from minomasal import KONULAR
    prompt=('Özgün Türkçe çocuk masalı üret. 10 farklı sahne, toplam 75–110 anlatım kelimesi. '
        'Her sahne narration (Türkçe), visual (English), sfx=none içerir. title, moral, characters, scenes alanlarıyla yalnız JSON döndür. '
        'Korkutucu/uygunsuz içerik ve ek karakter ekleme. Konu: '+topic+'\n'+prompt_rules(topic,KONULAR))
    body={'contents':[{'parts':[{'text':prompt}]}],
          'generationConfig':{'temperature':0.75,'maxOutputTokens':2400,'responseMimeType':'application/json'}}
    for attempt in range(3):
        try:r=transport(f'https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent',
            headers={'x-goog-api-key':key},json=body,timeout=(10,60))
        except requests.RequestException:
            # An inference timeout can have consumed quota. Do not replay it.
            raise StoryBlocked('gemini_text_network_ambiguous_no_replay') from None
        if r.status_code==200:
            try:return json.loads(''.join(p.get('text','') for p in r.json()['candidates'][0]['content']['parts']))
            except (ValueError,KeyError,IndexError,TypeError):raise StoryBlocked('gemini_text_invalid_json') from None
        if r.status_code not in (429,500,502,503,504) or attempt==2:
            raise StoryBlocked(f'gemini_text_http_{r.status_code}')
        sleep((1,2)[attempt])
    raise StoryBlocked('gemini_text_unavailable')

def select_story(ledger,root=ROOT):
    number=choose(ledger)
    if number is None:raise StoryBlocked('queue_complete')
    from minomasal import KONULAR
    topic=KONULAR[number-1];fallback=None
    if number==47:
        story=local_story(number,topic,root);provider='canonical_local_queue'
    else:
        try:
            story=validate_story(gemini_story(topic),number,topic);provider='gemini_free_attested'
        except StoryBlocked as error:
            fallback=str(error);story=local_story(number,topic,root);provider='approved_local_queue'
    sha=fingerprint(story)
    if any(row.get('narration_sha256')==sha for row in ledger['stories'].values()):
        raise StoryBlocked('narration_already_in_ledger')
    return number,topic,story,{'provider':provider,'fallback_reason':fallback,'narration_sha256':sha,
        'word_count':sum(len(s['narration'].split()) for s in story['scenes']),
        'semantic_originality_and_child_suitability':'human_review_required'}
