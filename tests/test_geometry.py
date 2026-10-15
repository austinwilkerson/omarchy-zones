"""Synthetic regressions for logical monitor, chrome and decorated-window geometry."""
import unittest
from unittest.mock import patch

from zones import hypr
from zones.layout import zone_to_px


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.no_live_ctl = patch.object(hypr, '_ctl', side_effect=AssertionError('live hyprctl forbidden'))
        self.no_live_ctl.start()
        self.addCleanup(self.no_live_ctl.stop)

    def monitor(self, **extra):
        return dict(name='TEST-1', x=0, y=0, width=1200, height=800,
                    scale=1, reserved=[0, 0, 0, 0], **extra)

    def layers(self, *items):
        return {'TEST-1': {'levels': {'2': list(items)}}}

    def surface(self, edge, *, inset=0, depth=30, namespace='omarchy-bar'):
        # Global logical coordinates on the default 1200x800 monitor.
        rects = {
            'left': (inset, 0, depth, 800),
            'top': (0, inset, 1200, depth),
            'right': (1200-inset-depth, 0, depth, 800),
            'bottom': (0, 800-inset-depth, 1200, depth),
        }
        x, y, w, h = rects[edge]
        return dict(namespace=namespace, x=x, y=y, w=w, h=h)

    def test_bar_each_edge_including_inset(self):
        for edge in ('left', 'top', 'right', 'bottom'):
            for inset in (0, 8):
                with self.subTest(edge=edge, inset=inset):
                    depth = 30+inset
                    expected = dict(x=depth if edge == 'left' else 0,
                                    y=depth if edge == 'top' else 0,
                                    width=1200-depth if edge in ('left','right') else 1200,
                                    height=800-depth if edge in ('top','bottom') else 800)
                    self.assertEqual(hypr.chrome_work_area(self.monitor(), layers_data=self.layers(
                        self.surface(edge, inset=inset))), expected)

    def test_reserved_and_bar_merge_by_max_not_sum(self):
        for index, edge in enumerate(('left','top','right','bottom')):
            for reserved_depth in (20, 40):
                with self.subTest(edge=edge, reserved=reserved_depth):
                    mon = self.monitor()
                    mon['reserved'][index] = reserved_depth
                    expected = [0,0,0,0]
                    expected[index] = max(38, reserved_depth)
                    self.assertEqual(hypr.bar_insets_for_monitor(mon, self.layers(
                        self.surface(edge, inset=8))), expected)

    def test_all_bar_edges_can_coexist(self):
        data = self.layers(*(self.surface(edge) for edge in ('left','top','right','bottom')))
        self.assertEqual(hypr.chrome_work_area(self.monitor(), layers_data=data),
                         dict(x=30, y=30, width=1140, height=740))

    def test_dock_body_depth_not_large_popup_all_edges(self):
        for index, edge in enumerate(('left','top','right','bottom')):
            for bar_offset in (0, 30):
                with self.subTest(edge=edge, bar_offset=bar_offset):
                    items = [self.surface(edge, depth=260, inset=bar_offset,
                                          namespace='omarchy-dock')]
                    if bar_offset:
                        items.append(self.surface(edge))
                    data = self.layers(*items)
                    expected = [0,0,0,0]
                    expected[index] = bar_offset+56
                    self.assertEqual(hypr.dock_insets_for_monitor(self.monitor(), data,
                        position=edge, depth=56), expected)
                    area = hypr.chrome_work_area(self.monitor(), layers_data=data,
                        dock_position=edge, dock_depth=56)
                    self.assertEqual(area['width'], 1200-(bar_offset+56) if index in (0,2) else 1200)
                    self.assertEqual(area['height'], 800-(bar_offset+56) if index in (1,3) else 800)
                    self.assertEqual(area['x'], bar_offset+56 if index == 0 else 0)
                    self.assertEqual(area['y'], bar_offset+56 if index == 1 else 0)

    def test_hidden_dock_reserves_nothing_on_any_edge(self):
        for edge in ('left','top','right','bottom'):
            with self.subTest(edge=edge):
                data = self.layers(self.surface(edge, depth=260, namespace='omarchy-dock'))
                self.assertEqual(hypr.chrome_work_area(self.monitor(), layers_data=data,
                    dock_position=edge, dock_depth=56, dock_active=False),
                    dict(x=0,y=0,width=1200,height=800))

    def test_scaled_negative_origin_and_rotated_monitor(self):
        mon = dict(name='TEST-1', x=-1280, y=-80, width=1600, height=1000,
                   scale=1.25, reserved=[0,0,0,0])
        self.assertEqual(hypr.logical_monitor(mon), dict(x=-1280,y=-80,width=1280,height=800))
        data = self.layers(dict(namespace='omarchy-bar', x=-1280,y=-74,w=1280,h=30))
        self.assertEqual(hypr.work_area(mon, gap_px=4, layers_data=data),
                         dict(x=-1276,y=-40,width=1272,height=756))
        for transform in (1,3,5,7):
            with self.subTest(transform=transform):
                rotated = dict(mon, transform=transform)
                self.assertEqual(hypr.logical_monitor(rotated),
                                 dict(x=-1280,y=-80,width=800,height=1280))
                self.assertIs(hypr.monitor_at([rotated], -500, 1199), rotated)
                self.assertIsNone(hypr.monitor_at([rotated], -479, 1199))

    def test_decorated_outer_content_round_trip(self):
        metrics = dict(border=2,titlebar=30,enabled=True,tag='floating-workspace')
        client = dict(at=[-998,72],size=[596,366],floating=True,
                      tags=['floating-workspace*'])
        insets = hypr.decoration_insets(client, metrics)
        self.assertEqual(insets, [2,32,2,2])
        outer = hypr.outer_rect(client, insets)
        self.assertEqual(outer, dict(x=-1000,y=40,w=600,h=400))
        self.assertEqual(hypr.content_rect(outer, insets),
                         dict(x=-998,y=72,w=596,h=366))
        for changes in (dict(floating=False),dict(fullscreen=1),dict(tags=['other'])):
            with self.subTest(changes=changes):
                self.assertEqual(hypr.decoration_insets(dict(client, **changes),metrics),[2,2,2,2])

    def test_user_gap_four_independent_of_hyprland_outer_gap(self):
        # Legacy outer_gap input must not override the user's chosen zone gap.
        area = hypr.work_area(self.monitor(), gap_px=4, outer_gap=24, layers_data={})
        self.assertEqual(area, dict(x=4,y=4,width=1192,height=792))
        left = zone_to_px(dict(x=0,y=0,w=.5,h=1),area,4)
        right = zone_to_px(dict(x=.5,y=0,w=.5,h=1),area,4)
        self.assertEqual(right['x']-(left['x']+left['w']),4)
        self.assertEqual(left['x'],4)
        self.assertEqual(right['x']+right['w'],1196)

    def test_monitor_at_does_not_fallback_outside_any_monitor(self):
        mon = self.monitor()
        other = dict(mon,name='TEST-2',x=1400)
        for point in ((-1,200),(1200,200),(1300,200),(300,-1),(300,800),(2600,200)):
            with self.subTest(point=point):
                self.assertIsNone(hypr.monitor_at([mon,other],*point))
        self.assertIsNone(hypr.monitor_at([],0,0))
        self.assertIs(hypr.monitor_at([mon,other],1400,0),other)

    def test_clamp_each_edge_and_oversized_rect(self):
        area = dict(x=-100,y=40,width=800,height=600)
        cases = [
            (dict(x=-200,y=100,w=200,h=100),dict(x=-100,y=100,w=200,h=100)),
            (dict(x=650,y=100,w=200,h=100),dict(x=500,y=100,w=200,h=100)),
            (dict(x=0,y=-20,w=200,h=100),dict(x=0,y=40,w=200,h=100)),
            (dict(x=0,y=620,w=200,h=100),dict(x=0,y=540,w=200,h=100)),
            (dict(x=-500,y=-500,w=1200,h=900),dict(x=-100,y=40,w=800,h=600)),
        ]
        for rect, expected in cases:
            with self.subTest(rect=rect):
                self.assertEqual(hypr.clamp_rect(rect,area),expected)


if __name__ == '__main__':
    unittest.main()
