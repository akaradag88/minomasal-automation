"""Run with python -m unittest -v test_minomasal_v4_mantik_kontrol.py"""
import unittest
from types import SimpleNamespace
from minomasal_v4_mantik_kontrol import audit_story, install_quality_guard


def scenes(text, visual):
    return {'title': 'Pilot', 'scenes': [{'narration': text + f' {i}.', 'visual': visual} for i in range(10)]}


class StoryGuardTests(unittest.TestCase):
    def setUp(self):
        self.monkey = [('maymun', {'name':'Miko','type_tr':'maymun'})]
        self.truck = [('oyuncak_kamyon', {'name':'Tiko','type_tr':'oyuncak kamyon'})]

    def test_child_absent_from_cast_rejected(self):
        s = scenes('Miko çocukla alay etti', 'Miko the monkey alone in the forest.')
        self.assertTrue(any('cocuk' in e for e in audit_story(s, self.monkey, 47)))

    def test_child_present_in_visual_but_not_approved_rejected(self):
        s = scenes('Miko çocukla konuştu', 'Miko the monkey and a boy in the forest.')
        self.assertTrue(any('cocuk' in e for e in audit_story(s, self.monkey, 47)))

    def test_approved_single_actor_and_object_pass(self):
        s = scenes('Tiko oyuncak taşları dikkatle taşıdı', 'Tiko the toy dump truck transports stones in a small toy construction site.')
        self.assertEqual(audit_story(s, self.truck, 47), [])

    def test_approved_45_46_unchanged(self):
        s = scenes('Miko çocukla alay etti', 'Miko alone.')
        for n in (45,46):
            self.assertEqual(audit_story(s, self.monkey, n), [])

    def test_duplicate_story_lines_fail(self):
        s = {'scenes': [{'narration': 'Tiko bekledi', 'visual': 'Tiko toy truck'} for _ in range(10)]}
        self.assertTrue(any('tekrar' in e for e in audit_story(s, self.truck, 47)))

    def test_monkey_relational_action_rejected(self):
        s = scenes('Miko özür diledi', 'Miko the monkey alone in forest.')
        self.assertTrue(any('iki kisi' in e for e in audit_story(s, self.monkey, 47)))

    def test_dynamic_hook_is_fail_closed_and_preserves_old_flows(self):
        topics = ['T'] * 60
        topics[46] = 'Kamyon'; topics[44] = 'Onayli'
        q = SimpleNamespace(
            prompt_rules=lambda topic, all_topics: 'eski kurallar',
            verify_and_enrich=lambda s,t,a: s,
            number_for_topic=lambda t,a: a.index(t)+1,
            dictionary_entry=lambda t,a: (a.index(t)+1, self.truck, None),
        )
        install_quality_guard(q)
        self.assertEqual(q.verify_and_enrich(scenes('Tiko oyuncak taşları taşıdı','Tiko toy truck'), 'Kamyon', topics)['title'], 'Pilot')
        self.assertIn('MANTIK', q.prompt_rules('Kamyon', topics))
        self.assertEqual(q.prompt_rules('Onayli', topics), 'eski kurallar')
        with self.assertRaisesRegex(ValueError,'anlatim/gorsel'):
            q.verify_and_enrich(scenes('Tiko çocukla alay etti', 'Tiko the toy truck alone'), 'Kamyon', topics)

if __name__ == '__main__':
    unittest.main()
