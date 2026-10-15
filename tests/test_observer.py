import json
import socket
import unittest
from zones.observer import PointerObserver


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.reader,self.writer=socket.socketpair()
        self.reader.setblocking(False)
        self.observer=object.__new__(PointerObserver)
        self.observer.socket=self.reader
        self.observer.state=dict(left=False,right=False,sequence=0)
        self.observer.buffer=b''
        self.observer.owned=False

    def tearDown(self):
        self.observer.close()
        self.writer.close()

    def test_filters_unrelated_events_and_partial_packets(self):
        self.writer.sendall(b'windowtitle>>private title ignored\nomarchy-zones-pointer>>{"left":true,')
        self.assertFalse(self.observer.read()['left'])
        self.writer.sendall(b'"right":false,"sequence":1}\n')
        self.assertTrue(self.observer.read()['left'])
        self.assertEqual(self.observer.buffer,b'')

    def test_rejects_malformed_and_wrong_typed_state(self):
        self.writer.sendall(b'omarchy-zones-pointer>>not JSON\nomarchy-zones-pointer>>[]\nomarchy-zones-pointer>>{"left":1,"right":false,"sequence":1}\n')
        self.assertFalse(self.observer.read()['left'])

    def test_disconnect_disables_snapping(self):
        self.writer.close()
        self.assertIsNone(self.observer.read())

if __name__=='__main__': unittest.main()
