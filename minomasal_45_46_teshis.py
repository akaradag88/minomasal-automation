#!/usr/bin/env python3
"""Read-only diagnostic for special story #45/#46 topic/title/scene mismatches.
No imports from the MinoMasal runtime, no secrets, no network, no mutations.
"""
from pathlib import Path
import ast
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parent
CASES = {
    45: ("Küçük Baykuş Atatürk'ü Öğreniyor", "Küçük Baykuş ve 10 Kasım Anısı", 'hikaye_03.json'),
    46: ("Orman Okulunda Atatürk'ü Anma Günü", "Orman Okulunda Saygı Yürüyüşü", 'hikaye_04.json'),
}

def literal_in_py(path, variable):
    body = ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path)).body
    for item in body:
        if isinstance(item, ast.Assign) and any(isinstance(t, ast.Name) and t.id == variable for t in item.targets):
            return ast.literal_eval(item.value)
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.target.id == variable:
            return ast.literal_eval(item.value)
    raise RuntimeError(f'{path.name}: {variable} not found as a top-level static literal')

def flag(label, actual, expected):
    ok = actual == expected
    print(f'  {"OK" if ok else "UYUSMUYOR"}: {label}')
    print(f'    depoda  = {actual!r}')
    print(f'    beklenen= {expected!r}')
    if not ok and isinstance(actual, str) and isinstance(expected, str):
        print('    depodaki kod noktaları =', ' '.join(f'U+{ord(c):04X}' for c in actual))
        print('    beklenen kod noktaları =', ' '.join(f'U+{ord(c):04X}' for c in expected))
    return ok

def main():
    try:
        topics = literal_in_py(ROOT/'minomasal.py', 'KONULAR')
        special = literal_in_py(ROOT/'minomasal_gunluk_kalite_stage_v3.py','SPECIAL_FILES')
    except Exception as err:
        print('SOURCE_PARSE_ERROR:', type(err).__name__, str(err))
        return 1
    issues=[]
    for n,(canonical,display,filename) in CASES.items():
        print(f'\n===== STORY {n} / SADECE OKUMA =====')
        source = ROOT/filename
        if not source.is_file():
            print('EKSIK:',filename); issues.append(f'{n}:missing'); continue
        try:
            story=json.loads(source.read_text(encoding='utf-8-sig'))
        except Exception as err:
            print('INVALID_JSON:',repr(err));issues.append(f'{n}:json');continue
        print('  kaynak dosya:',filename)
        print('  dosya SHA256:',hashlib.sha256(source.read_bytes()).hexdigest()[:24])
        checks=[flag('SPECIAL_FILES yol eslesmesi',special.get(n),filename),
                flag('KONULAR hikaye konusu',topics[n-1] if len(topics)>=n else None,canonical),
                flag('JSON title',story.get('title'),display),
                flag('JSON sahne sayisi',len(story.get('scenes',[])) if isinstance(story.get('scenes'),list) else None,10)]
        scenes=story.get('scenes',[])
        if isinstance(scenes,list):
            missing=[i for i,s in enumerate(scenes,1) if not isinstance(s,dict) or not str(s.get('narration','')).strip() or not str(s.get('visual','')).strip()]
            print('  bos/eksik anlatim veya gorsel sahneleri:',missing)
            if missing:checks.append(False)
            word_count=sum(len(s.get('narration','').split()) for s in scenes if isinstance(s,dict))
            print('  kelime sayisi (bilgi amaçli):',word_count)
        if all(checks):print(f'  SPECIAL_{n}_VALUES_OK')
        else:issues.append(f'{n}:mismatch')
    if issues:
        print('\nTESHIS_SONUC=UYUSMAZLIK_VAR;YAYIN_YAPILMADI; ' + ','.join(issues))
        # Diagnostics should finish green so user sees the report, mismatch is in output.
        return 0
    print('\nTESHIS_SONUC=DOSYALAR_ESLESIYOR;YAYIN_YAPILMADI')
    print('NOT: Eğer canlı workflow yine hata veriyorsa o run farklı commit veya code branch kullanıyor olabilir.')
    return 0

if __name__ == '__main__':sys.exit(main())
