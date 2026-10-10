"""Read-only cross-platform publication planner. Never calls publishing APIs."""
import argparse
import json
from pathlib import Path
import ast

def topics():
    tree = ast.parse(Path("minomasal.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "KONULAR" for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError("KONULAR missing from minomasal.py")
from minomasal_ledger import read, validate


def build(ledger, number):
    validate(ledger)
    KONULAR = topics()
    stories = ledger['stories']
    key = str(number)
    if not 1 <= number <= len(KONULAR):
        raise ValueError('Story number outside the known topics')
    row = stories.get(key)
    if row and row.get('topic') != KONULAR[number - 1]:
        raise ValueError('Topic mismatch: manual review required')
    if row is None:
        return {'number': number, 'topic': KONULAR[number-1], 'action': 'new_story_requires_manual_approval', 'youtube': 'pending', 'instagram': 'pending', 'can_publish': False}
    yt = row['youtube']['status']
    ig = row['instagram']['status']
    # Existing rows may be ambiguous. No automatic retry without reconciliation.
    return {'number': number, 'topic': row['topic'], 'action': 'review_existing_record', 'youtube': yt, 'instagram': ig, 'can_publish': False}

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--ledger', type=Path, default=Path('minomasal_platform_durumu.json'))
    p.add_argument('--number', type=int, default=16)
    p.add_argument('--output', type=Path, default=Path('minomasal_publish_plan.json'))
    args = p.parse_args()
    result = build(read(args.ledger), args.number)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print('DRY RUN: no video generation or publishing; all publishing remains disabled.')

if __name__ == '__main__':
    main()
