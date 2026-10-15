#!/usr/bin/env python3
"""Opt-in integration checks in a disposable nested Hyprland.

No command targets the user's compositor. Requires Hyprland, Quickshell, foot,
a compatible installed titlebars.so, and an existing parent Wayland session.
Run: python tests/verify_nested.py --artifacts /tmp/zones-nested-check
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from zones import hypr
from zones.layout import zone_to_px


def wait_for(predicate, description, seconds=8):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        result = predicate()
        if result:
            return result
        time.sleep(.08)
    raise AssertionError('Timed out: ' + description)


def run(args):
    parent_runtime = Path(os.environ['XDG_RUNTIME_DIR'])
    parent_signature = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')
    parent_socket = Path(os.environ['WAYLAND_DISPLAY'])
    if not parent_socket.is_absolute():
        parent_socket = parent_runtime / parent_socket
    evidence = []
    args.artifacts.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='zones-nested-') as scratch_name:
        scratch = Path(scratch_name)
        env = dict(os.environ, XDG_RUNTIME_DIR=str(scratch), WAYLAND_DISPLAY=str(parent_socket),
                   AQ_BACKEND='wayland', HYPRLAND_NO_SD_NOTIFY='1', HYPRLAND_NO_SD_VARS='1',
                   XDG_CONFIG_HOME=str(scratch/'config'), XDG_STATE_HOME=str(scratch/'state'))
        env.pop('HYPRLAND_INSTANCE_SIGNATURE', None)
        # Independent state makes both saved Floating-mode checks and shell
        # startup incapable of using the real user's configuration.
        (scratch/'config').mkdir()
        (scratch/'state/omarchy/workspace-layouts').mkdir(parents=True)
        (scratch/'state/omarchy/workspace-layouts/1.lua').write_text('return { mode = "floating" }\n')
        config = scratch/'hyprland.lua'
        config.write_text('''
hl.monitor({ output = "", mode = "1280x800@60", position = "0x0", scale = 1 })
hl.config({ general = { gaps_in = 0, gaps_out = 0, border_size = 2, resize_on_border = true, extend_border_grab_area = 8 }, animations = { enabled = false }, input = { follow_mouse = 0 }, misc = { disable_hyprland_logo = true, disable_splash_rendering = true } })
hl.window_rule({ name = "zones-nested-float", match = { class = ".*" }, float = true, size = { 500, 300 }, center = true })
if hl.plugin and hl.plugin.hyprbars then
    hl.config({ plugin = { hyprbars = { enabled = true, bar_height = 30, bar_part_of_window = true } } })
end
''')
        log = (args.artifacts/'compositor.log').open('w')
        children = []
        compositor = subprocess.Popen(['Hyprland', '--config', str(config)], env=env, stdout=log, stderr=log)

        def ctl(*argv):
            signature = env.get('HYPRLAND_INSTANCE_SIGNATURE')
            if not signature or signature == parent_signature or env['XDG_RUNTIME_DIR'] != str(scratch):
                raise RuntimeError('Refusing a command outside the isolated compositor')
            result = subprocess.run(['hyprctl', *argv], env=env, text=True, capture_output=True, check=True, timeout=5)
            if result.stdout.startswith('Err') or "Couldn't" in result.stdout:
                raise RuntimeError(result.stdout)
            return result.stdout

        def start_nested():
            if compositor.poll() is not None:
                raise RuntimeError('Nested compositor exited; see compositor.log')
            result = subprocess.run(['hyprctl', 'instances', '-j'], env=env, text=True, capture_output=True, timeout=3)
            try:
                instances = json.loads(result.stdout)
            except ValueError:
                return False
            if not instances:
                return False
            # All discoverable sockets live inside our private runtime.
            env['HYPRLAND_INSTANCE_SIGNATURE'] = instances[0]['instance']
            env['WAYLAND_DISPLAY'] = instances[0]['wl_socket']
            return True

        def qjson(*argv):
            return json.loads(ctl(*argv, '-j'))

        def client():
            windows = qjson('clients')
            return windows[0] if windows else None

        def setbar(side):
            anchors = {name: name != {'top':'bottom', 'bottom':'top', 'left':'right', 'right':'left'}[side]
                       for name in ('left','right','top','bottom')}
            props = '\n'.join(f'anchors.{name}: {str(value).lower()}' for name, value in anchors.items())
            dimension = 'implicitHeight' if side in ('top','bottom') else 'implicitWidth'
            qml = scratch/(side+'.qml')
            qml.write_text('import Quickshell\nimport Quickshell.Wayland\nPanelWindow {\n'
                           + props + f'\n{dimension}: 40\nexclusiveZone: 0\n'
                           + 'WlrLayershell.namespace: "omarchy-bar"\ncolor: "#334466"\n}\n')
            process = subprocess.Popen(['qs', '-p', str(qml)], env=env, stdout=log, stderr=log)
            children.append(process)
            def current_layer():
                mon = qjson('monitors')[0]
                data = qjson('layers')
                found = list(hypr._iter_monitor_layers(data, mon['name']))
                return (mon,data) if any(hypr._namespace(item,'omarchy-bar') for item in found) else False
            mon,data = wait_for(current_layer, side+' bar mapped')
            return process,mon,data

        try:
            wait_for(start_nested, 'nested compositor startup')
            assert not ctl('configerrors').strip(), ctl('configerrors')
            ctl('plugin','load',str(args.titlebars.resolve()))
            ctl('reload')
            assert not ctl('configerrors').strip(), ctl('configerrors')
            terminal = subprocess.Popen(['foot','--app-id=zones-isolated-test','--title=Zones isolated verification','sleep','300'], env=env, stdout=log, stderr=log)
            children.append(terminal)
            wait_for(client,'floating test client')
            # Functions under test query the nested compositor, never the parent.
            original_ctl = hypr._ctl
            hypr._ctl = ctl
            metrics = hypr.decoration_metrics()
            assert metrics['border'] == 2 and metrics['titlebar'] == 30 and metrics['enabled'], metrics
            insets = hypr.decoration_insets(client(),metrics)
            assert insets == [2,32,2,2], insets
            for scale in (1,1.25):
                ctl('eval', f'hl.monitor({{ output = "", mode = "1280x800@60", position = "0x0", scale = {scale} }})')
                wait_for(lambda: qjson('monitors')[0]['scale'] == scale, 'monitor scaling')
                for side in ('top','right','bottom','left'):
                    bar,mon,data = setbar(side)
                    try:
                        assert mon['reserved'] == [0,0,0,0], mon['reserved']
                        area = hypr.work_area(mon,gap_px=8,layers_data=data)
                        box = hypr.logical_monitor(mon)
                        expected = dict(x=8,y=8,width=int(box['width'])-16,height=int(box['height'])-16)
                        if side in ('left','right'):
                            expected['width'] -= 40
                            if side == 'left': expected['x'] += 40
                        else:
                            expected['height'] -= 40
                            if side == 'top': expected['y'] += 40
                        assert area == expected, (side,scale,area,expected,data)
                        # Whole-area maximize and half/quarter zones must all fit
                        # with outer decorations included in their zone bounds.
                        for fraction in ((0,0,1,1),(0,0,.5,1),(.5,0,.5,1),(.25,0,.5,1),(0,.5,.5,.5)):
                            zone = dict(zip(('x','y','w','h'),fraction))
                            outer = zone_to_px(zone,area,gap_px=8)
                            content = hypr.content_rect(outer,insets)
                            hypr.move_resize(client()['address'],**content)
                            def fitted():
                                current = client()
                                return current if hypr.outer_rect(current,insets) == outer else False
                            window = wait_for(fitted, f'{side} {scale} content/outer geometry')
                            assert window['floating'] and window['fullscreen'] == 0, window
                        record = dict(scale=scale,bar=side,monitor=mon,area=area,insets=insets,client=window)
                        evidence.append(record)
                        print(f'PASS scale={scale} bar={side}: layer-aware fit and five decorated zones',flush=True)
                    finally:
                        bar.terminate()
                        bar.wait(timeout=5)
                        wait_for(lambda: not any(hypr._namespace(item,'omarchy-bar') for item in hypr._iter_monitor_layers(qjson('layers'),mon['name'])), 'bar removed')
            if args.pointer_helper:
                # Run actual compositor gestures through a nested-only virtual
                # pointer. The externally built protocol helper is test tooling,
                # never loaded or installed with the plugin.
                ctl('eval', 'hl.monitor({ output = "", mode = "1280x800@60", position = "0x0", scale = 1 })')
                bar,mon,data = setbar('top')
                daemon_log_path = args.artifacts/'daemon.log'
                daemon_log = daemon_log_path.open('w')
                daemon = subprocess.Popen([sys.executable,str(ROOT/'zonesd.py')],env=env,stdout=daemon_log,stderr=daemon_log)
                children.append(daemon)
                pointer = subprocess.Popen([str(args.pointer_helper.resolve()),'1280','800'],env=env,
                                           stdin=subprocess.PIPE,text=True,stdout=log,stderr=log)
                children.append(pointer)
                def commands(lines):
                    pointer.stdin.write('\n'.join(lines)+'\n')
                    pointer.stdin.flush()
                def events(kind):
                    found = []
                    for line in daemon_log_path.read_text().splitlines():
                        try: event = json.loads(line)
                        except ValueError: continue
                        if event.get('event') == kind: found.append(event)
                    return found
                def place():
                    hypr.move_resize(client()['address'],320,260,500,300)
                    time.sleep(.35)
                    return client()
                def drag_start(target_x,target_y):
                    before = client()
                    start_x,start_y = before['at'][0]+100,before['at'][1]-15
                    lines = [f'move {start_x} {start_y}','wait 150','down','wait 150']
                    for step in range(1,21):
                        lines += [f'move {round(start_x+(target_x-start_x)*step/20)} {round(start_y+(target_y-start_y)*step/20)}','wait 25']
                    commands(lines)
                    time.sleep(1.05)
                    return before
                try:
                    time.sleep(.5)
                    if daemon.poll() is not None: raise AssertionError(daemon_log_path.read_text())
                    before = place()
                    ctl("dispatch", f'hl.dsp.focus({{ window = "address:{before["address"]}" }})')
                    drag_start(430,360)
                    (args.artifacts/'gesture-debug.json').write_text(json.dumps(dict(before=before,after=client(),cursor=qjson('cursorpos'),workspace=qjson('activeworkspace'),active=qjson('activewindow'),plugins=qjson('plugin','list'),bindings=qjson('binds')),indent=2))
                    subprocess.run(['grim','-o',mon['name'],str(args.artifacts/'gesture.png')],env=env,check=True)
                    preview = wait_for(lambda: events('preview'), 'drag preview')[-1]
                    time.sleep(.5)
                    assert client()['size'] == before['size'], ('snapped before release',client(),before)
                    assert not events('snap-candidate'), events('snap-candidate')
                    commands(['up'])
                    snapped = wait_for(lambda: events('snap-candidate'), 'release snap')[-1]
                    rect = snapped['rect']
                    wait_for(lambda: hypr.outer_rect(client(),insets) == rect,'release decorated fit')
                    print('PASS real drag remains unsnapped while held, snaps on release with full decorations',flush=True)
                    evidence.append(dict(gesture='hold-release',event=snapped,client=client()))
                    # A real resize must not turn into a zone snap on release.
                    before = place()
                    count = len(events('snap-candidate'))
                    x,y = before['at'][0]+before['size'][0]+1,before['at'][1]+before['size'][1]+1
                    lines = [f'move {x} {y}','wait 200','down','wait 150']
                    for step in range(1,16):
                        lines += [f'move {x+step*4} {y+step*3}','wait 30']
                    lines += ['wait 150','up']
                    commands(lines)
                    time.sleep(1.6)
                    after = client()
                    assert after['size'] != before['size'], ('real resize did not resize',before,after)
                    assert len(events('snap-candidate')) == count, ('resizing caused snap',events('snap-candidate'))
                    print('PASS real border resize retains manual size after release',flush=True)
                    evidence.append(dict(gesture='resize',before=before,after=after))
                    # Floating individual clients in a saved tiling workspace
                    # must not enable Zones (strict Omarchy Floating-mode gate).
                    (scratch/'state/omarchy/workspace-layouts/1.lua').write_text('return { mode = "dwindle" }\n')
                    before = place()
                    count = len(events('snap-candidate'))
                    drag_start(650,390)
                    commands(['up'])
                    time.sleep(.5)
                    assert client()['size'] == before['size'] and len(events('snap-candidate')) == count
                    print('PASS floating client in a saved tiling workspace does not snap',flush=True)
                    evidence.append(dict(gesture='tiling-disabled',client=client()))
                finally:
                    for process in (pointer,daemon,bar):
                        if process.poll() is None:
                            process.terminate()
                            process.wait(timeout=5)
                    daemon_log.close()
            hypr._ctl = original_ctl
        finally:
            for child in reversed(children):
                if child.poll() is None:
                    child.terminate()
                    try: child.wait(timeout=3)
                    except subprocess.TimeoutExpired: child.kill(); child.wait()
            compositor.terminate()
            try: compositor.wait(timeout=5)
            except subprocess.TimeoutExpired: compositor.kill(); compositor.wait()
            log.close()
            (args.artifacts/'geometry.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('PASS isolated compositor exited; no parent config or plugins changed',flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts',type=Path,default=Path('/tmp/omarchy-zones-nested-check'))
    parser.add_argument('--pointer-helper',type=Path,help='Externally built wlr virtual-pointer helper accepting move/down/up/wait lines')
    parser.add_argument('--titlebars',type=Path,default=Path('/usr/lib/omarchy-hyprland-titlebars/titlebars.so'))
    run(parser.parse_args())
