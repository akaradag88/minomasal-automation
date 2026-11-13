"""Read-only static inventory, no module imports or secret values."""
import ast
import json
from pathlib import Path
import yaml

def inspect(root=Path('.')):
    root=Path(root);workflows=[];python=[]
    for path in sorted((root/'.github/workflows').glob('*.yml')):
        data=yaml.load(path.read_text(),Loader=yaml.BaseLoader)
        row={'path':str(path.relative_to(root)),'events':list(data.get('on',{})),
            'schedules':data.get('on',{}).get('schedule',[]),'permissions':data.get('permissions',{}),
            'concurrency':data.get('concurrency',{}),'jobs':[]}
        for name,job in data.get('jobs',{}).items():
            actions=[s.get('uses','') for s in job.get('steps',[]) if s.get('uses')]
            row['jobs'].append({'name':name,'condition':job.get('if'),'runner':job.get('runs-on'),
                'timeout':job.get('timeout-minutes'),'unpinned_actions':[a for a in actions if '@' in a and len(a.rsplit('@',1)[-1])!=40],
                'publisher_invocations':[s.get('name','unnamed') for s in job.get('steps',[]) if 'publish' in s.get('run','').lower()]})
        workflows.append(row)
    for path in sorted(root.glob('*.py')):
        try:ast.parse(path.read_text());state='syntax_valid'
        except (SyntaxError,UnicodeError):state='syntax_invalid'
        python.append({'path':path.name,'status':state})
    return {'workflow_count':len(workflows),'python_module_count':len(python),'workflows':workflows,'python_modules':python,
        'no_modules_executed':True,'secret_values_inspected':False}

if __name__=='__main__':
    path=Path('engine_output/inventory.json');path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(inspect(),ensure_ascii=False,indent=2)+'\n')
