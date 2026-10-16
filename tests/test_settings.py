import json
from pathlib import Path
import tempfile
import unittest

from settings import update, validate_patch
from zones.layout import zone_to_px, load_config, layout_for_monitor, pick_zone
from zones.hypr import work_area


class SettingsTests(unittest.TestCase):
    def test_preserve_layouts_and_merge_color_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'layouts.json'
            config = dict(default='halves', layouts={'halves': []}, monitors={'DP-4':'halves'}, gap_px=4,
                          preview={'color':'accent','custom':'#123456','opacity':.35})
            path.write_text(json.dumps(config))
            update(path, {'preview': {'color':'custom'}})
            result = update(path, {'gap_px':5,'preview':{'opacity':.5}})
            self.assertEqual(result['layouts'], config['layouts'])
            self.assertEqual(result['monitors'], config['monitors'])
            self.assertEqual(result['preview'],dict(color='custom',custom='#123456',opacity=.5))
            self.assertEqual(json.loads(path.read_text()), result)
            self.assertEqual(result['gap_px'],5)

    def test_create_preferences_and_load_backend_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / 'layouts.json'
            base.write_text(json.dumps(dict(gap_px=4,layouts={'halves':[]},default='halves')))
            preferences = Path(directory) / 'state/zones/settings.json'
            self.assertEqual(load_config(base,preferences)['gap_px'],4)
            update(preferences, {'gap_px':7,'preview':{'color':'foreground'}})
            self.assertEqual(load_config(base,preferences)['gap_px'],7)
            self.assertEqual(load_config(base)['gap_px'],4)
            self.assertEqual(load_config(base,preferences)['layouts'],{'halves':[]})

    def test_invalid_override_does_not_rewrite_base(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / 'layouts.json'
            original = '{"gap_px":4,"layouts":{}}'
            base.write_text(original)
            preferences = Path(directory) / 'settings.json'
            preferences.write_text('{"gap_px":-1}')
            with self.assertRaises(ValueError): load_config(base,preferences)
            self.assertEqual(base.read_text(),original)

    def test_layout_choices_preserve_colors_and_other_monitors(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / 'layouts.json'
            config = load_config()
            base.write_text(json.dumps(config))
            path = Path(directory) / 'settings.json'
            update(path, {'preview':{'color':'custom','custom':'#aabbcc','opacity':.45}})
            update(path, {'monitors':{'DP-4':'grid-2x2'}})
            update(path, {'monitors':{'eDP-1':'thirds'}})
            update(path, {'workspaces':{'DP-4:1':'quarters-cols'}})
            merged = load_config(base,path)
            self.assertEqual(layout_for_monitor(merged,'DP-4',workspace_id=1)[0],'quarters-cols')
            self.assertEqual(layout_for_monitor(merged,'DP-4',workspace_id=2)[0],'grid-2x2')
            self.assertEqual(layout_for_monitor(merged,'eDP-1',workspace_id=1)[0],'thirds')
            self.assertEqual(merged['preview']['custom'],'#aabbcc')
            update(path, {'workspaces':{'DP-4:1':None}})
            self.assertEqual(layout_for_monitor(load_config(base,path),'DP-4',workspace_id=1)[0],'grid-2x2')
            self.assertEqual(json.loads(base.read_text()),config)

    def test_eight_presets_and_overlapping_center_selection(self):
        config = load_config()
        expected = {'halves':2,'halves-vertical':2,'thirds':3,'thirds-vertical':3,'25-50-25':3,'quarters-cols':4,'grid-2x2':4,'columns-mid50':5}
        for name,count in expected.items():
            self.assertEqual(len(config['layouts'][name]),count)
            validate_patch({'monitors':{'DP-4':name}})
        area = dict(x=0,y=0,width=1600,height=900)
        for fraction,zone in [(0.125,'q1'),(.375,'q2'),(.5,'mid50'),(.625,'q3'),(.875,'q4')]:
            with self.subTest(fraction=fraction):
                picked,_ = pick_zone(fraction*1600,450,area,config['layouts']['columns-mid50'],4,0)
                self.assertEqual(picked['id'],zone)

    def test_reject_invalid_settings(self):
        for patch in [{'monitors':[]}, {'monitors':{'DP-4':'unknown'}}, {'workspaces':{'<img>':'halves'}}, {'monitors':{'DP-4':[]}}, [], {'layouts':{}}, {'gap_px':True}, {'gap_px':-1}, {'gap_px':1.5}, {'gap_px':65},
                      {'preview':[]}, {'preview':{'color':'nope'}}, {'preview':{'custom':'red'}},
                      {'preview':{'custom':'<img src="https://invalid">'}}, {'preview':{'opacity':True}},
                      {'preview':{'opacity':float('nan')}}, {'preview':{'opacity':1}}]:
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                validate_patch(patch)

    def test_uniform_outer_and_shared_gaps_at_odd_boundaries(self):
        # All four outside edges, and both axes of a 2x2 grid, including odd gaps
        # and monitor sizes with half-pixel zone boundaries.
        for gap in (0,1,3,4,5,7,16):
            for width,height in ((1200,800),(1201,801),(1517,923)):
                mon=dict(x=-1517,y=30,width=width,height=height,scale=1,transform=0,reserved=[0,0,0,0])
                area=work_area(mon,gap_px=gap,layers_data={})
                zones=[zone_to_px(dict(x=x,y=y,w=.5,h=.5),area,gap) for y in (0,.5) for x in (0,.5)]
                tl,tr,bl,br=zones
                with self.subTest(gap=gap,width=width,height=height):
                    self.assertEqual(tl['x']-mon['x'],gap)
                    self.assertEqual(tl['y']-mon['y'],gap)
                    self.assertEqual(mon['x']+width-tr['x']-tr['w'],gap)
                    self.assertEqual(mon['y']+height-bl['y']-bl['h'],gap)
                    self.assertEqual(tr['x']-tl['x']-tl['w'],gap)
                    self.assertEqual(bl['y']-tl['y']-tl['h'],gap)
                    self.assertEqual(br['x']-bl['x']-bl['w'],gap)

if __name__ == '__main__':
    unittest.main()
