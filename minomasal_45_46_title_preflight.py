#!/usr/bin/env python3
"""Offline check of the CURRENT staging function and 45/46 data. No publish."""
from pathlib import Path
import ast
import json
import tempfile
import os
ROOT=Path(__file__).resolve().parent
CASES={
  45:("Küçük Baykuş Atatürk'ü Öğreniyor",{"Küçük Baykuş Atatürk'ü Öğreniyor","Küçük Baykuş ve 10 Kasım Anısı"},'hikaye_03.json'),
  46:("Orman Okulunda Atatürk'ü Anma Günü",{"Orman Okulunda Atatürk'ü Anma Günü","Orman Okulunda Saygı Yürüyüşü"},'hikaye_04.json'),
}
def get_literal(path, name):
    tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(name+' not found')
def get_function(path):
    tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    node=next((x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='approved_special'),None)
    assert node is not None,'approved_special function not found'
    ns={'Path':Path,'json':json,'SPECIAL_FILES':{45:'hikaye_03.json',46:'hikaye_04.json'}}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns)
    return ns['approved_special']
def main():
    stage=ROOT/'minomasal_gunluk_kalite_stage_v3.py'
    topics=get_literal(ROOT/'minomasal.py','KONULAR')
    actual_files=get_literal(stage,'SPECIAL_FILES')
    check=get_function(stage)
    cwd=Path.cwd()
    os.chdir(ROOT)
    try:
      for number,(topic,allowed,filename) in CASES.items():
        assert actual_files.get(number)==filename,(number,'wrong file path')
        assert topics[number-1]==topic,(number,'wrong topic')
        data=json.loads((ROOT/filename).read_text(encoding='utf-8-sig'))
        assert data.get('title') in allowed,(number,'unknown title',data.get('title'))
        assert isinstance(data.get('scenes'),list) and len(data['scenes'])==10,(number,'wrong scenes')
        result=check(number,topic)
        assert result==data,(number,'returned other story')
        print(f'PASS #{number}: {data["title"]!r}; scenes=10; words={sum(len(s["narration"].split()) for s in data["scenes"])}')
      # Wrong topic must never be accepted (even when story data is valid)
      for number,(topic,_,__) in CASES.items():
        try:check(number,topic+' DİĞER')
        except RuntimeError:pass
        else:raise AssertionError('wrong topic accepted '+str(number))
      # Wrong JSON title must fail. Save and restore fixture in an isolated directory.
      with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp)
        for number,(topic,_,filename) in CASES.items():
          data=json.loads((ROOT/filename).read_text(encoding='utf-8-sig'))
          data['title']='BAŞKA BİR HİKÂYE'
          (tmp/filename).write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
        os.chdir(tmp)
        for number,(topic,_,filename) in CASES.items():
          try:check(number,topic)
          except RuntimeError:pass
          else:raise AssertionError('wrong title accepted '+str(number))
      print('SPECIAL_TITLE_GATE_OK; NO_PUBLISH; no secrets or API calls')
    finally:os.chdir(cwd)
if __name__=='__main__':main()
