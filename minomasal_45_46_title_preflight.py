#!/usr/bin/env python3
"""#45/#46 only: local read-only title/scene guard test. No publishing / API calls."""
from pathlib import Path
import ast
import json
import os
import tempfile
import unicodedata

ROOT=Path(__file__).resolve().parent
CASES={
    45: ("Küçük Baykuş Atatürk'ü Öğreniyor", {"Küçük Baykuş Atatürk'ü Öğreniyor", "Küçük Baykuş ve 10 Kasım Anısı"}, 'hikaye_03.json'),
    46: ("Orman Okulunda Atatürk'ü Anma Günü", {"Orman Okulunda Atatürk'ü Anma Günü", "Orman Okulunda Saygı Yürüyüşü"}, 'hikaye_04.json'),
}

def canonical(value):
    if not isinstance(value,str):
        return None
    return unicodedata.normalize('NFC',value).translate(str.maketrans({"’":"'","‘":"'","ʼ":"'","＇":"'"})).strip()

def literal(path,name):
    tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f'{path.name}: {name} bulunamadi')

def get_approved_special(stage):
    tree=ast.parse(stage.read_text(encoding='utf-8-sig'))
    node=next((x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='approved_special'),None)
    assert node is not None,'approved_special bulunamadi'
    ns={'Path':Path,'json':json,'SPECIAL_FILES':{45:'hikaye_03.json',46:'hikaye_04.json'}}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(stage),'exec'),ns)
    return ns['approved_special']

def must_reject(call, what):
    try:
        call()
    except (RuntimeError, ValueError, KeyError):
        return
    raise AssertionError(f'Kabul edilmemesi gereken {what} kabul edildi')

def main():
    stage=ROOT/'minomasal_gunluk_kalite_stage_v3.py'
    topics=literal(ROOT/'minomasal.py','KONULAR')
    special=literal(stage,'SPECIAL_FILES')
    check=get_approved_special(stage)
    original=Path.cwd()
    os.chdir(ROOT)
    try:
        for number,(topic,allowed,filename) in CASES.items():
            assert special.get(number)==filename,(number,'wrong file')
            assert topics[number-1]==topic,(number,'wrong canonical topic',topics[number-1])
            story=json.loads((ROOT/filename).read_text(encoding='utf-8-sig'))
            assert canonical(story.get('title')) in {canonical(x) for x in allowed},(number,'unknown title',story.get('title'))
            assert isinstance(story.get('scenes'),list) and len(story['scenes'])==10,(number,'wrong scene count')
            assert all(isinstance(s,dict) and all(isinstance(s.get(k),str) and s[k].strip() for k in ('narration','visual')) for s in story['scenes']),(number,'empty scene')
            assert check(number,topic)==story,(number,'stage returned wrong story')
            must_reject(lambda:check(number,topic+' FARKLI'),f'#{number} wrong topic')
            print(f'PASS #{number}: {story["title"]!r}; scenes=10; words={sum(len(s["narration"].split()) for s in story["scenes"])}')

            # Test that an ordinary apostrophe and a curly apostrophe work both ways.
            with tempfile.TemporaryDirectory() as td:
                td=Path(td)
                case=dict(story)
                case['title']=next(x for x in allowed if "'" in x).replace("'",'’')
                (td/filename).write_text(json.dumps(case,ensure_ascii=False),encoding='utf-8')
                os.chdir(td)
                assert check(number,topic)==case,(number,'curly apostrophe rejected')
                assert check(number,topic.replace("'",'’'))==case,(number,'curly apostrophe topic rejected')
                case['title']='ILGISIZ BASKA MASAL'
                (td/filename).write_text(json.dumps(case,ensure_ascii=False),encoding='utf-8')
                must_reject(lambda:check(number,topic),f'#{number} wrong JSON title')
                os.chdir(ROOT)
        print('SPECIAL_TITLE_GATE_OK; SMART_APOSTROPHE_OK; NO_PUBLISH')
    finally:
        os.chdir(original)

if __name__=='__main__':main()
