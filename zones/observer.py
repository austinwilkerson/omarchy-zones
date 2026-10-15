"""Read Zones-only button-state events from Hyprland's existing IPC socket."""
import json
import os
from pathlib import Path
import socket
from . import hypr


class PointerObserver:
    def __init__(self, library=None):
        self.socket=None
        self.owned=False
        self.library=Path(library) if library else Path(__file__).resolve().parents[1]/'native/observer.so'
        self.buffer=b''
        self.state=None
        self.error=None
        try:
            instance=os.environ['HYPRLAND_INSTANCE_SIGNATURE']
            path=Path(os.environ['XDG_RUNTIME_DIR'])/'hypr'/instance/'.socket2.sock'
            self.socket=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            self.socket.settimeout(2)
            self.socket.connect(str(path))
            self.socket.setblocking(False)
            plugins=json.loads(hypr._ctl('plugin','list','-j'))
            if not any(p.get('name')=='omarchy-zones-observer' for p in plugins):
                if not self.library.is_file():
                    raise RuntimeError('Build native/observer.so with scripts/build-observer.sh')
                result=hypr._ctl('plugin','load',str(self.library))
                if not result.strip().lower().startswith('ok'):
                    raise RuntimeError(result.strip())
                self.owned=True
            self.state=dict(left=False,right=False,sequence=0)
        except Exception as error:
            self.error=str(error)
            self.close()

    def read(self):
        if self.state is None or self.socket is None:
            return None
        while True:
            try:
                part=self.socket.recv(16384)
            except BlockingIOError:
                break
            except OSError:
                self.state=None
                break
            if not part:
                self.state=None
                break
            self.buffer+=part
            if len(self.buffer)>262144:
                self.buffer=b''
                self.state=None
                break
            while b'\n' in self.buffer:
                line,self.buffer=self.buffer.split(b'\n',1)
                if not line.startswith(b'omarchy-zones-pointer>>'):
                    continue
                try:
                    msg=json.loads(line.split(b'>>',1)[1])
                    if (isinstance(msg,dict) and type(msg.get('left')) is bool and type(msg.get('right')) is bool
                            and type(msg.get('sequence')) is int):
                        self.state=msg
                except (ValueError,KeyError,TypeError):
                    pass
        return self.state

    def close(self):
        if self.socket is not None:
            self.socket.close()
            self.socket=None
        if self.owned:
            try: hypr._ctl('plugin','unload',str(self.library))
            except Exception: pass
            self.owned=False
