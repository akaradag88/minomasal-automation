#!/usr/bin/env python3
"""Offline fail-closed one-change patch for MinoMasal2 special titles.
No API, no publish, no ledger writes.
Usage: python minomasal_45_46_baslik_onarim.py --check
       python minomasal_45_46_baslik_onarim.py --apply
"""
from pathlib import Path
import argparse
import ast
import json
import sys

TARGET = Path(__file__).resolve().parent / 'minomasal_gunluk_kalite_stage_v3.py'
OLD = '''    if story.get('title') != topic or len(story.get('scenes', [])) != 10:
        raise RuntimeError(f'#{number} onayli JSON basligi/sahnesi uyusmuyor.')'''
NEW = '''    # Topic (canonical queue identity) and approved JSON display title are distinct.
    approved = {
        45: ("Küçük Baykuş Atatürk'ü Öğreniyor", "Küçük Baykuş ve 10 Kasım Anısı"),
        46: ("Orman Okulunda Atatürk'ü Anma Günü", "Orman Okulunda Saygı Yürüyüşü"),
    }[number]
    if topic != approved[0] or story.get('title') != approved[1] or len(story.get('scenes', [])) != 10:
        raise RuntimeError(f'#{number} onayli JSON konusu/basligi/sahnesi uyusmuyor.')'''


def validate_special_files(base):
    spec = {
        45: ("hikaye_03.json", "Küçük Baykuş ve 10 Kasım Anısı"),
        46: ("hikaye_04.json", "Orman Okulunda Saygı Yürüyüşü"),
    }
    for n, (name, expected) in spec.items():
        p=base/name
        if not p.is_file():
            raise RuntimeError(f'#{n} missing: {name}')
        obj=json.loads(p.read_text(encoding='utf-8'))
        if obj.get('title') != expected:
            raise RuntimeError(f'#{n}: unexpected approved title in {name}: {obj.get("title")!r}')
        scenes=obj.get('scenes')
        if not isinstance(scenes,list) or len(scenes) != 10 or any(not isinstance(s,dict) or not s.get('narration') or not s.get('visual') for s in scenes):
            raise RuntimeError(f'#{n}: invalid 10-scene structure')
        print(f'SPECIAL_{n}_JSON_OK title={expected!r} scenes=10')


def main():
    parser=argparse.ArgumentParser()
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--check', action='store_true')
    action.add_argument('--apply', action='store_true')
    a=parser.parse_args()
    if not TARGET.is_file():
        raise RuntimeError('Stage file missing: ' + str(TARGET))
    text=TARGET.read_text(encoding='utf-8')
    if OLD in text and NEW not in text:
        fixed=text.replace(OLD,NEW)
        if text.count(OLD)!=1:
            raise RuntimeError('More than one match; refusing to patch')
    elif OLD not in text and NEW in text:
        fixed=text
    else:
        raise RuntimeError('Original snippet changed or ambiguous; refuse to modify, inspect manually')
    ast.parse(fixed,filename=str(TARGET))
    validate_special_files(TARGET.parent)
    if a.apply and fixed!=text:
        TARGET.write_text(fixed,encoding='utf-8')
        print('PATCH_APPLIED_ONE_CHECK_ONLY')
    elif a.check and fixed != text:
        print('PATCH_AVAILABLE_NO_FILE_MODIFIED')
    else:
        print('PATCH_ALREADY_APPLIED')
    print('SPECIAL_TITLES_PRECHECK_OK_NO_PUBLISH')


if __name__=='__main__':
    try: main()
    except Exception as e:
        print('PREFLIGHT_FAILED:',e,file=sys.stderr)
        sys.exit(1)
