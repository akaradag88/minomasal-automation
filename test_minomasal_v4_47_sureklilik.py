import copy
import unittest
from minomasal_v4_47_sureklilik_kontrol import check

class StoryContinuityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.errors,cls.story,cls.plan=check()

    def test_base_story_passes(self):
        self.assertFalse(self.errors,self.errors)

    def test_ten_scenes_and_word_count(self):
        self.assertEqual(len(self.story['scenes']),10)
        self.assertEqual(sum(len(x['narration'].split()) for x in self.story['scenes']),89)

    def test_sand_timeline(self):
        self.assertEqual([p['cargo'] for p in self.plan['scenes']], ['loaded']*8+['unloading','empty'])

    def test_bridge_timeline(self):
        self.assertEqual([p['bridge'] for p in self.plan['scenes']], ['hidden']*7+['visible']*3)

    def test_three_way_fork_is_scene_three(self):
        self.assertIn('three distinct branching paths',self.story['scenes'][2]['visual'])

    def test_initial_three_scenes_have_loaded_sand(self):
        for s in self.story['scenes'][:3]:
            self.assertIn('CARGO BED STATE = LOADED:',s['visual'])
            self.assertIn('BRIDGE VISIBILITY = HIDDEN:',s['visual'])

    def test_bed_is_unloaded_only_once(self):
        self.assertIn('CARGO BED STATE = UNLOADING:',self.story['scenes'][8]['visual'])
        self.assertIn('CARGO BED STATE = EMPTY:',self.story['scenes'][9]['visual'])

    def test_no_character_addition_in_plan(self):
        for s in self.story['scenes']:
            self.assertIn('NO RANDOM VEHICLES, NO HUMANS',s['visual'])

if __name__=='__main__':unittest.main()
