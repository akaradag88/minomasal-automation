"""Deterministic prompt plans; validates intentions, never claims pixel semantics."""
import hashlib
import json
import re

VERSION=1
REVIEW_REQUIRED=('character_identity','actual_entity_counts','object_identity',
                 'unwanted_text_logos_watermarks','scene_action','source_composition')
TRAITS={
    'character':('color','face','eyes','clothing','proportions','accessories'),
    'object':('color','shape','parts','scale'),
}


def text(value):
    return isinstance(value,str) and 1<=len(value)<=800 and not any(ord(c)<32 for c in value)


def validate_profile(profile):
    if (not isinstance(profile,dict) or set(profile)!={'version','style','entities','composition','exclusions'}
            or type(profile['version']) is not int or profile['version']!=VERSION
            or not all(text(profile[k]) for k in ('style','composition','exclusions'))
            or not isinstance(profile['entities'],dict) or not 1<=len(profile['entities'])<=8):
        raise ValueError('invalid_visual_profile')
    for entity_id,entity in profile['entities'].items():
        if (not isinstance(entity_id,str) or not re.fullmatch('[a-z_]{1,32}',entity_id)
                or not isinstance(entity,dict) or set(entity)!={'kind','label','max_count','traits'}
                or not isinstance(entity.get('kind'),str) or entity['kind'] not in TRAITS or not text(entity.get('label'))
                or type(entity.get('max_count')) is not int or not 1<=entity['max_count']<=8):
            raise ValueError('invalid_visual_entity')
        traits=entity['traits']
        if (not isinstance(traits,dict) or set(traits)!=set(TRAITS[entity['kind']])
                or not all(text(value) for value in traits.values())):
            raise ValueError('incomplete_visual_traits')


def profile_digest(profile):
    validate_profile(profile)
    return hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def identity_text(profile):
    validate_profile(profile)
    blocks=[]
    for key in sorted(profile['entities']):
        entity=profile['entities'][key]
        traits='; '.join(entity['traits'][field] for field in TRAITS[entity['kind']])
        blocks.append(entity['label']+': '+traits+'.')
    return ' '.join(blocks)


def build_prompt(profile,scene):
    validate_profile(profile)
    if not isinstance(scene,dict) or set(scene)!={'action','inventory'} or not text(scene['action']):
        raise ValueError('invalid_visual_scene')
    counts=scene['inventory']
    if not isinstance(counts,dict) or set(counts)!=set(profile['entities']):
        raise ValueError('explicit_inventory_required_for_every_entity')
    for entity_id,count in counts.items():
        if type(count) is not int or not 0<=count<=profile['entities'][entity_id]['max_count']:
            raise ValueError('visual_inventory_out_of_bounds')
    if not any(counts.values()):raise ValueError('empty_visual_cast')
    inventory=', '.join(f"{counts[key]} {profile['entities'][key]['label']}" for key in sorted(profile['entities']))
    visible={**profile,'entities':{key:entity for key,entity in profile['entities'].items() if counts[key]}}
    prompt=(f"{profile['style']} Visible inventory, exact counts: {inventory}. "
            f"Fixed design: {identity_text(visible)} Action: {scene['action']} "
            f"Framing: {profile['composition']} Restrictions: {profile['exclusions']}")
    if len(prompt)>2048:raise ValueError('visual_prompt_exceeds_model_limit')
    return prompt


def review_contract():
    return {'automatic_checks':['profile_schema','planned_inventory','prompt_length',
                                'image_integrity','dimensions','nonuniform_pixels','no_crop_geometry'],
            'human_review_required':list(REVIEW_REQUIRED),'semantic_checks_automated':False,
            'automation_quality_approved':False}
