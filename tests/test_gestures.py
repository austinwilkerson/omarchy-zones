import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zones.drag import PointerGesture
from zones.hypr import workspace_mode
from zones.layout import load_config, layout_for_monitor


def client(address='0x1',at=(100,100),size=(400,300)):
    return dict(address=address,at=list(at),size=list(size))


def pointer(left=False,right=False,sequence=0):
    return dict(left=left,right=right,sequence=sequence)


class Gestures(unittest.TestCase):
    def test_move_waits_for_actual_release(self):
        tracker=PointerGesture()
        tracker.update(pointer(),client())
        tracker.update(pointer(left=True),client())
        self.assertTrue(tracker.update(pointer(left=True),client(at=(150,100)))['moving'])
        for _ in range(20):
            state=tracker.update(pointer(left=True),client(at=(150,100)))
            self.assertFalse(state['snap'])
        self.assertTrue(tracker.update(pointer(),client(at=(150,100)))['snap'])
        self.assertFalse(tracker.update(pointer(),client(at=(150,100)))['snap'])

    def test_resize_stays_cancelled_through_position_only_frames(self):
        tracker=PointerGesture()
        tracker.update(pointer(left=True),client())
        tracker.update(pointer(left=True),client(at=(90,90),size=(410,310)))
        state=tracker.update(pointer(left=True),client(at=(89,90),size=(410,310)))
        self.assertTrue(state['resized'])
        self.assertFalse(tracker.update(pointer(),client(at=(89,90),size=(410,310)))['snap'])
        tracker.update(pointer(left=True),client(at=(89,90),size=(410,310)))
        tracker.update(pointer(left=True),client(at=(120,90),size=(410,310)))
        self.assertTrue(tracker.update(pointer(),client(at=(120,90),size=(410,310)))['snap'])

    def test_right_button_does_not_snap(self):
        tracker=PointerGesture()
        tracker.update(pointer(right=True),client())
        tracker.update(pointer(right=True),client(at=(150,100)))
        self.assertFalse(tracker.update(pointer(),client(at=(150,100)))['snap'])

    def test_focus_change_cancels_target(self):
        tracker=PointerGesture()
        tracker.update(pointer(left=True),client())
        tracker.update(pointer(left=True),client(at=(150,100)))
        tracker.update(pointer(left=True),client(address='0x2',at=(150,100)))
        self.assertFalse(tracker.update(pointer(),client(address='0x2',at=(150,100)))['snap'])

    def test_bridge_loss_cancels(self):
        tracker=PointerGesture()
        tracker.update(pointer(left=True),client())
        tracker.update(pointer(left=True),client(at=(150,100)))
        tracker.update(None,client(at=(150,100)))
        self.assertFalse(tracker.update(pointer(),client(at=(150,100)))['snap'])

    def test_idle_foreign_movement_does_not_snap(self):
        tracker=PointerGesture()
        tracker.update(pointer(),client())
        tracker.update(pointer(),client(at=(150,100)))
        self.assertFalse(tracker.update(pointer(),client(at=(150,100)))['snap'])

    def test_saved_mode_overrides_default_and_excludes_special(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'default.lua').write_text('o.workspace_mode({ default = "floating" })')
            self.assertEqual(workspace_mode({'id':1,'tiledLayout':'dwindle'},root),'floating')
            (root/'1.lua').write_text('o.workspace_mode({ id = 1, mode = "scrolling" })')
            self.assertEqual(workspace_mode({'id':1,'tiledLayout':'dwindle'},root),'scrolling')
            self.assertEqual(workspace_mode({'id':-99,'tiledLayout':'dwindle'},root),'dwindle')

    def test_workspace_layout_precedence(self):
        cfg=load_config()
        cfg['workspaces']={'2':'thirds','DP-4:2':'halves'}
        self.assertEqual(layout_for_monitor(cfg,'DP-4',workspace_id=2)[0],'halves')
        self.assertEqual(layout_for_monitor(cfg,'eDP-1',workspace_id=2)[0],'thirds')
        self.assertEqual(layout_for_monitor(cfg,'DP-4',override='grid-2x2',workspace_id=2)[0],'grid-2x2')

if __name__=='__main__': unittest.main()
