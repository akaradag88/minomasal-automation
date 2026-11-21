"""MinoMasal V4 narrative/visual actor guard.

Cautious, rule-based supplement to existing quality checks; does not claim
complete semantic understanding. Enabled only for newly GENERATED stories >=47.
Never edits canonical JSON, publisher, ledger, media or approved #45/#46.
"""
from __future__ import annotations

import re
import unicodedata

PROTECTED = {33, 34, 45, 46}


def norm(s):
    s = str(s).replace('İ', 'i').replace('I', 'ı').casefold()
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c)).replace('ı', 'i')

# Each role is a meaningful second visible actor, not background scenery.
# Narrow intentionally: uncertain references should be reviewed, not invented.
ROLES = {
    'cocuk': {
        'tr': [r'\bcocuk\w*', r'\bcocug\w*', r'\bbebek\w*', r'\boglan\w*', r'\bkiz\s+cocug\w*'],
        'en': [r'\bchild\b', r'\bchildren\b', r'\bkid\b', r'\bkids\b', r'\bboy\b', r'\bgirl\b', r'\btoddler\b', r'\bbaby\b'],
        'cast': ['cocuk', 'efe', 'mert', 'lina', 'astronot']
    },
    'ogretmen': {
        'tr': [r'\bogretmen\w*'],
        'en': [r'\bteacher\b'],
        'cast': ['ogretmen', 'cocuk', 'insan']
    },
    'maymun': {
        'tr': [r'\bmaymun\w*'],
        'en': [r'\bmonkey\b'],
        'cast': ['maymun']
    },
    'tavsan': {
        'tr': [r'\btavsan\w*'],
        'en': [r'\brabbit\b', r'\bbunny\b'],
        'cast': ['tavsan']
    },
    'fil': {
        'tr': [r'\bfil\b', r'\bfilin\b', r'\bfile\b', r'\bfile\w*'],
        'en': [r'\belephant\b'],
        'cast': ['fil']
    },
    'kedi': {
        'tr': [r'\bkedi\w*'],
        'en': [r'\bcat\b', r'\bkitten\b'],
        'cast': ['kedi']
    },
    'kopek': {
        'tr': [r'\bkopek\w*', r'\bkopeg\w*'],
        'en': [r'\bdog\b', r'\bpuppy\b'],
        'cast': ['kopek']
    },
    'adam_kadin': {
        'tr': [r'\badam\w*', r'\bkadin\w*', r'\binsan\w*'],
        'en': [r'\bman\b', r'\bwoman\b', r'\bperson\b', r'\bpeople\b', r'\bworker\b'],
        'cast': ['insan', 'cocuk', 'adam', 'kadin', 'iscia', 'isci']
    },
}

# These actions imply interacting with another agent. With only one approved
# character, the narrative must be rewritten or the cast explicitly approved.
SECOND_ACTOR_ACTIONS = [
    r'\balay\s+et\w*',
    r'\bozur\s+dile\w*',
    r'\btesekkur\s+et\w*',
    r'\barkadas\w*\s+yardim\s+et\w*',
]


def _hits(patterns, text):
    return any(re.search(p, text, re.UNICODE) for p in patterns)


def _cast_allows(role, cast):
    # Cast entries are tuples of (dictionary key, full character descriptor).
    for key, person in cast:
        tokens = ' '.join([str(key), str(person.get('name','')), str(person.get('type_tr',''))])
        current = norm(tokens)
        if any(alias in current for alias in ROLES[role]['cast']):
            return True
    return False


def audit_story(story, cast, story_number):
    """Return human-readable errors; no changes, no network calls."""
    if int(story_number) < 47 or int(story_number) in PROTECTED:
        return []
    errors = []
    scenes = story.get('scenes') if isinstance(story, dict) else None
    if not isinstance(scenes, list) or len(scenes) != 10:
        return ['10 sahne bekleniyor.']
    prev = None
    for index, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            errors.append(f'Sahne {index}: JSON sahnesi nesne degil.')
            continue
        narration = norm(scene.get('narration', ''))
        visual = norm(scene.get('visual', ''))
        if not narration.strip() or not visual.strip():
            errors.append(f'Sahne {index}: bos narration veya visual.')
            continue
        if narration == prev:
            errors.append(f'Sahne {index}: bir onceki sahnenin anlatisi tekrar ediyor.')
        prev = narration
        for role, patterns in ROLES.items():
            in_narration = _hits(patterns['tr'], narration)
            in_visual = _hits(patterns['en'], visual)
            if (in_narration or in_visual) and not _cast_allows(role, cast):
                errors.append(f'Sahne {index}: {role} var ama onayli karakter kadrosunda yok; metni/gorseli duzelt ya da kadroyu bilincli onayla.')
            elif in_narration and not in_visual:
                # May be described by a proper name instead of an English noun;
                # only flag if name is also missing from the visual description.
                has_named_actor = any(norm(p.get('name', '')) in visual for _, p in cast if norm(p.get('name', '')))
                if not has_named_actor:
                    errors.append(f'Sahne {index}: anlatilan {role} gorsel tarifinde bulunamadi.')
        if len(cast) == 1 and _hits(SECOND_ACTOR_ACTIONS, narration):
            errors.append(f'Sahne {index}: iki kisi gerektiren eylem var, fakat sozlukte tek karakter var.')
    return list(dict.fromkeys(errors))


def install_quality_guard(quality_module=None):
    """Call after V4 prompt guidance; patches only generated story quality.

    Prior approved-story paths bypass create_story_v2, so remain unchanged.
    """
    if quality_module is None:
        import minomasal_kalite_v2 as quality_module
    if getattr(quality_module, '_v4_mantik_guard_installed', False):
        return
    previous_rules = quality_module.prompt_rules
    previous_verify = quality_module.verify_and_enrich

    def extended_rules(topic, all_topics):
        baseline = previous_rules(topic, all_topics)
        number = quality_module.number_for_topic(topic, all_topics)
        if number < 47 or number in PROTECTED:
            return baseline
        return baseline + (
            '\nV4 HIKAYE MANTIK VE GORSEL UYUMU (zorunlu):'
            '\n- 10 sahne tek bir neden-sonuc zinciri olsun. Her sahne onceki olaydan dogal bicimde dogsun.'
            '\n- Sesli anlatimda sozu edilen her gorunur canli/insan/arac gorsel tarifinde aynen bulunmali.'
            '\n- Karakter sozlugunde bulunmayan cocuk, insan, hayvan, arac veya yan karakteri anlatima da gorsele de ekleme.'
            '\n- Yalnizca 1 karakter onayliysa alay etme, birinden ozur dileme gibi ikinci karakter gerektiren olaylar yazma.'
            '\n- Her narration kisa, dilbilgisel ve oznesi belli bir Turkce cumle olsun; belirsiz zamirler kullanma.'
            '\n- Her English visual tam olarak AYNI anda anlatilan somut eylemi gostersin.'
            '\n- Tek sahne 1 ana eylem, en fazla 2 gorunen onayli karakter; ek figuran yok.'
        )

    def guarded_verify(story, topic, all_topics):
        number, cast, _ = quality_module.dictionary_entry(topic, all_topics)
        issues = audit_story(story, cast, number)
        if issues:
            raise ValueError('V4 anlatim/gorsel mantik kontrolu basarisiz: ' + ' | '.join(issues[:7]))
        return previous_verify(story, topic, all_topics)

    quality_module.prompt_rules = extended_rules
    quality_module.verify_and_enrich = guarded_verify
    quality_module._v4_mantik_guard_installed = True
