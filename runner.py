#!/usr/bin/env python3
"""Build an ABI-specific observer in the user cache, then start the snap backend."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
BUILD = None


def status(state, message=''):
    print(json.dumps(dict(event='setup', state=state, message=message)), flush=True)


def stop(*_):
    if BUILD is not None and BUILD.poll() is None:
        os.killpg(BUILD.pid, signal.SIGTERM)
        BUILD.wait()
    raise SystemExit(0)


def build_key(root, version):
    digest = hashlib.sha256(json.dumps(version, sort_keys=True).encode())
    for name in ('native/pointer-observer.cpp', 'scripts/build-observer.sh'):
        digest.update((root / name).read_bytes())
    return digest.hexdigest()[:24]


def ensure_observer(root=ROOT, cache=None):
    global BUILD
    version = json.loads(subprocess.check_output(['hyprctl','version','-j'], text=True, timeout=5))
    if not isinstance(version, dict) or not version.get('abiHash'):
        raise RuntimeError('This Hyprland does not report its ABI. Omarchy Edge with Hyprland 0.56.2 is the tested version.')
    cache = Path(cache or os.environ.get('XDG_CACHE_HOME') or Path.home()/'.cache')
    directory = cache / 'omarchy-zones' / 'native' / build_key(root, version)
    directory.mkdir(parents=True, exist_ok=True)
    library = directory / 'observer.so'
    with (directory / '.build.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if library.is_file():
            return library
        status('building', 'Preparing Zones for this Hyprland version…')
        with tempfile.TemporaryFile(mode='w+') as log:
            BUILD = subprocess.Popen(['bash',str(root/'scripts/build-observer.sh'),str(library)],
                                     stdout=log,stderr=log,start_new_session=True)
            try:
                result = BUILD.wait(timeout=120)
            except subprocess.TimeoutExpired:
                os.killpg(BUILD.pid,signal.SIGKILL)
                BUILD.wait()
                raise RuntimeError('The native helper build timed out. Open Zones and choose Retry setup.')
            finally:
                BUILD = None
            if result:
                log.seek(0)
                detail = log.read()[-12000:]
                (directory/'build.log').write_text(detail)
                raise RuntimeError('Could not build the helper. Check that base-devel and the matching Hyprland headers are installed. Build details: '+str(directory/'build.log'))
        if not library.is_file():
            raise RuntimeError('The build completed without producing the helper.')
    return library


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('backend_args', nargs=argparse.REMAINDER)
    args = parser.parse_args().backend_args
    if args[:1] == ['--']: args=args[1:]
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    status('checking')
    try:
        library=ensure_observer()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        status('error',str(error))
        return 78
    status('starting')
    os.execv(sys.executable,[sys.executable,str(ROOT/'zonesd.py'),'--observer',str(library),*args])


if __name__=='__main__': sys.exit(main())
