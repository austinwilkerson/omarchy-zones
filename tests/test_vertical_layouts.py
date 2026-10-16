import json
from pathlib import Path
import tempfile
import unittest

from settings import update
from zones.layout import load_config, layout_for_monitor, pick_zone, zone_to_px


class VerticalLayoutTests(unittest.TestCase):
    def test_full_width_rows_and_exact_shared_gaps(self):
        cfg=load_config()
        for name,count in [('halves-vertical',2),('thirds-vertical',3)]:
            for gap in (0,1,4,5,8):
                area=dict(x=-1500,y=34,width=1193,height=1071)
                rows=[zone_to_px(z,area,gap) for z in cfg['layouts'][name]]
                with self.subTest(layout=name,gap=gap):
                    self.assertEqual(len(rows),count)
                    self.assertTrue(all(r['x']==area['x'] and r['w']==area['width'] for r in rows))
                    self.assertEqual(rows[0]['y'],area['y'])
                    self.assertEqual(rows[-1]['y']+rows[-1]['h'],area['y']+area['height'])
                    for before,after in zip(rows,rows[1:]):
                        self.assertEqual(after['y']-before['y']-before['h'],gap)
                    for zone in cfg['layouts'][name]:
                        x=area['x']+area['width']/2
                        y=area['y']+(zone['y']+zone['h']/2)*area['height']
                        picked,_=pick_zone(x,y,area,cfg['layouts'][name],gap,24)
                        self.assertEqual(picked['id'],zone['id'])

    def test_persist_vertical_selections_by_monitor_and_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'settings.json'
            base=Path(directory)/'layouts.json'
            base.write_text(json.dumps(load_config()))
            update(path,{'monitors':{'DP-1':'halves-vertical'},'workspaces':{'DP-1:2':'thirds-vertical'}})
            cfg=load_config(base,path)
            self.assertEqual(layout_for_monitor(cfg,'DP-1',workspace_id=1)[0],'halves-vertical')
            self.assertEqual(layout_for_monitor(cfg,'DP-1',workspace_id=2)[0],'thirds-vertical')


if __name__=='__main__':unittest.main()
