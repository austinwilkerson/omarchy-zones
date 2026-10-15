import unittest
from zones.layout import load_config, pick_zone, zone_to_px, layout_for_monitor
from zones.drag import SnapGuard
from zones import hypr

CFG = load_config()
GAP = CFG["gap_px"]
# Raw monitor geometry used only where we are testing zone_to_px flush/half-gap
# against an already-cushioned work area.
MON = {"x": 0, "y": 0, "width": 5120, "height": 1440}
L = CFG["layouts"]

class T(unittest.TestCase):
    def pick(self, x, y, lay="columns-mid50", mon=None):
        return pick_zone(x, y, mon or MON, L[lay], GAP, 24)

    def test_default_gap_is_four(self):
        self.assertEqual(CFG["gap_px"], 4)

    def test_edges(self):
        # Against a pre-cushioned work area, outer edges are flush (no extra gap).
        self.assertEqual(self.pick(5, 700)[0]["id"], "edge-left")
        self.assertEqual(self.pick(5115, 700)[0]["id"], "edge-right")
        z, r = self.pick(2000, 3)
        self.assertEqual(z["id"], "edge-top")
        self.assertEqual(r, {"x": 0, "y": 0, "w": 5120, "h": 1440})

    def test_edges_same_on_offset_monitor(self):
        # Edge snaps are relative to that monitor's work area, not global origin.
        mon2 = {"x": 4096, "y": 0, "width": 2048, "height": 1280}
        z, r = pick_zone(4096 + 5, 700, mon2, L["halves"], GAP, 24)
        self.assertEqual(z["id"], "edge-left")
        self.assertEqual(r, {"x": 4096, "y": 0, "w": 1022, "h": 1280})
        z, r = pick_zone(4096 + 2048 - 3, 700, mon2, L["halves"], GAP, 24)
        self.assertEqual(z["id"], "edge-right")
        self.assertEqual(r["x"], 4096 + 1026)
        z, r = pick_zone(4096 + 1000, 2, mon2, L["halves"], GAP, 24)
        self.assertEqual(z["id"], "edge-top")
        self.assertEqual(r, {"x": 4096, "y": 0, "w": 2048, "h": 1280})

    def test_mid_overlap(self):
        self.assertEqual(self.pick(2560, 720)[0]["id"], "mid50")

    def test_quarter(self):
        self.assertEqual(self.pick(1500, 720)[0]["id"], "q2")

    def test_outer_quarter(self):
        self.assertEqual(self.pick(600, 720)[0]["id"], "q1")

    def test_grid(self):
        self.assertEqual(self.pick(4000, 1200, "grid-2x2")[0]["id"], "br")

    def test_gaps(self):
        # Work area already gap-inset: outer flush, half-gap on the shared inner edge.
        # Left half of 5120 loses 2px on the right when gap=4 → w=2558.
        r = zone_to_px(L["halves"][0], MON, 4)
        self.assertEqual(r, {"x": 0, "y": 0, "w": 2558, "h": 1440})
        r = zone_to_px(L["quarters-cols"][1], MON, 4)
        self.assertEqual(r["x"], 1282)
        self.assertEqual(r["w"], 1276)

    def test_gap_changeable(self):
        tight = zone_to_px(L["halves"][0], MON, 0)
        wide = zone_to_px(L["halves"][0], MON, 20)
        self.assertEqual(tight["w"], 2560)
        self.assertEqual(wide["w"], 2550)

    def test_work_area_gap_cushions_then_zone_flush(self):
        # Full pipeline: chrome → gap shrink → zone_to_px half-gap inner only.
        mon = {
            "name": "DP-4", "x": 0, "y": 0,
            "width": 5120, "height": 1440, "scale": 1,
            "reserved": [0, 26, 0, 0],
        }
        area = hypr.work_area(mon, gap_px=4, dock_bottom_px=56, layers_data={}, outer_gap=4)
        # chrome: y=26, h=1440-26-56=1358; then gap 4 → y=30, h=1350, x=4, w=5112
        self.assertEqual(area, {"x": 4, "y": 30, "width": 5112, "height": 1350})
        left = zone_to_px(L["halves"][0], area, 4)
        self.assertEqual(left["x"], 4)
        self.assertEqual(left["y"], 30)
        self.assertEqual(left["h"], 1350)
        # half of 5112 = 2556, minus half-gap 2 on the right
        self.assertEqual(left["w"], 2554)

    def test_all_layouts_valid(self):
        for name, zs in L.items():
            for z in zs:
                self.assertTrue(0 <= z["x"] and z["x"] + z["w"] <= 1.0001, name)
        self.assertIn(CFG["default"], L)

    def test_monitor_layout_map(self):
        cfg = dict(CFG, monitors={"DP-4":"columns-mid50", "eDP-1":"halves"})
        lid, zs = layout_for_monitor(cfg, "DP-4")
        self.assertEqual(lid, "columns-mid50")
        self.assertEqual(zs, L["columns-mid50"])
        lid, zs = layout_for_monitor(cfg, "eDP-1")
        self.assertEqual(lid, "halves")
        self.assertEqual(zs, L["halves"])
        # Unknown monitor → default
        lid, _ = layout_for_monitor(cfg, "HDMI-A-1")
        self.assertEqual(lid, CFG["default"])
        # CLI override wins
        lid, _ = layout_for_monitor(cfg, "eDP-1", override="thirds")
        self.assertEqual(lid, "thirds")
        # Bad override falls back to default
        lid, _ = layout_for_monitor(cfg, "DP-4", override="nope")
        self.assertEqual(lid, CFG["default"])

    def test_gate(self):
        self.assertTrue(hypr.should_snap({"tiledLayout": "floating"}, {"floating": False}))
        self.assertFalse(hypr.should_snap({"tiledLayout": "dwindle"}, {"floating": True}))
        self.assertTrue(hypr.should_snap({"omarchyMode": "floating", "tiledLayout": "dwindle"}, {"floating": True}))
        self.assertFalse(hypr.should_snap({"tiledLayout": "dwindle"}, {"floating": False}))

    def test_hypr_parse(self):
        m = hypr.monitors('[{"name":"DP-4","x":0,"y":0,"width":5120,"height":1440,"scale":1,"reserved":[0,26,0,0]}]')
        empty = {}
        self.assertEqual(
            hypr.chrome_work_area(m[0], layers_data=empty),
            {"x": 0, "y": 26, "width": 5120, "height": 1414},
        )
        self.assertEqual(
            hypr.work_area(m[0], layers_data=empty, outer_gap=0),
            {"x": 0, "y": 26, "width": 5120, "height": 1414},
        )
        self.assertEqual(
            hypr.work_area(m[0], gap_px=4, dock_bottom_px=56, layers_data=empty, outer_gap=4),
            {"x": 4, "y": 30, "width": 5112, "height": 1350},
        )
        layers = {
            "DP-4": {
                "levels": {
                    "2": [
                        {"namespace": "omarchy-bar", "x": 0, "y": 0, "w": 5120, "h": 30},
                        {"namespace": "omarchy-dock", "x": 0, "y": 1300, "w": 5120, "h": 140},
                    ]
                }
            },
            "eDP-1": {"levels": {"2": []}},
        }
        # layer bar taller than reserved → use 30
        self.assertEqual(
            hypr.chrome_work_area(m[0], layers_data=layers),
            {"x": 0, "y": 30, "width": 5120, "height": 1410},
        )
        self.assertEqual(hypr.dock_insets_for_monitor(m[0], layers, depth=56)[3], 56)
        self.assertEqual(hypr.dock_insets_for_monitor({**m[0], "name":"eDP-1"}, layers, depth=56)[3], 0)
        cmd = hypr.move_resize("0x1", 1, 2, 10, 20, dry_run=True)
        self.assertIn("hl.dsp.window.resize", cmd)
        self.assertIn("hl.dsp.window.move", cmd)
        self.assertIn("exact = true", cmd)
        self.assertIn("hl.get_windows()", cmd)
        self.assertIn("0x1", cmd)

    def test_snap_guard_resize_then_move(self):
        g = SnapGuard()
        addr = "0xabc"
        # Seed
        g.update(addr, (10, 10), (400, 300), 0.0)
        # Move-only starts tracking
        st = g.update(addr, (20, 10), (400, 300), 1.0)
        self.assertTrue(st["moving"])
        self.assertFalse(st["dirty"])
        self.assertTrue(st["move_started"])
        # User resizes → dirty, not moving; must not snap on release
        st = g.update(addr, (20, 10), (500, 300), 2.0)
        self.assertTrue(st["dirty"])
        self.assertFalse(st["moving"])
        self.assertTrue(st["resized"])
        # Still dirty if only size settles (pure resize release)
        st = g.update(addr, (20, 10), (500, 300), 2.2)
        self.assertTrue(st["dirty"])
        self.assertFalse(st["moving"])
        # Move-only again clears dirty
        st = g.update(addr, (40, 10), (500, 300), 3.0)
        self.assertFalse(st["dirty"])
        self.assertTrue(st["moving"])

    def test_snap_guard_our_snap_not_dirty(self):
        g = SnapGuard()
        addr = "0xabc"
        g.update(addr, (10, 10), (400, 300), 0.0)
        g.update(addr, (20, 10), (400, 300), 1.0)
        g.note_snap_applied(addr, (800, 600))
        # Size jumps to our snap result → ack, not dirty
        st = g.update(addr, (0, 0), (800, 600), 1.2)
        self.assertTrue(st["ack_snap"])
        self.assertFalse(st["dirty"])
        self.assertFalse(st["moving"])

if __name__ == "__main__":
    unittest.main()
