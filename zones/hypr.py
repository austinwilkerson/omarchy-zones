"""Hyprland geometry in global logical pixels; no desktop configuration writes."""
import json
import math
import os
from pathlib import Path
import re
import subprocess

BAR_NAMESPACE = 'omarchy-bar'
DOCK_NAMESPACE = 'omarchy-dock'


def _ctl(*args):
    return subprocess.run(['hyprctl', *args], capture_output=True, text=True,
                          check=True, timeout=3).stdout


def monitors(raw=None):
    return json.loads(raw if raw is not None else _ctl('monitors', '-j'))


def clients(raw=None):
    return json.loads(raw if raw is not None else _ctl('clients', '-j'))


def active_workspace(raw=None):
    return json.loads(raw if raw is not None else _ctl('activeworkspace', '-j'))


def layers(raw=None):
    return json.loads(raw if raw is not None else _ctl('layers', '-j'))


def shell_config():
    root = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home()/'.config')))
    try:
        return json.loads((root/'omarchy/shell.json').read_text())
    except (OSError, ValueError):
        return {}


def workspace_mode(workspace, state_dir=None):
    if workspace.get('tiledLayout') == 'floating':
        return 'floating'
    root = Path(state_dir) if state_dir else Path(os.environ.get(
        'XDG_STATE_HOME', str(Path.home()/'.local/state')))/'omarchy/workspace-layouts'
    wid = workspace.get('id', -1)
    if isinstance(wid, int) and wid >= 1:
        for name,key in ((str(wid)+'.lua','mode'), ('default.lua','default')):
            try:
                match = re.search(r'\b'+key+r'\s*=\s*"([a-z]+)"', (root/name).read_text())
                if match:
                    return match[1]
            except OSError:
                pass
    return workspace.get('tiledLayout', 'dwindle')


def logical_monitor(mon):
    scale = float(mon.get('scale') or 1)
    width, height = float(mon['width']), float(mon['height'])
    if int(mon.get('transform', 0)) in (1, 3, 5, 7):
        width, height = height, width
    return dict(x=mon['x'], y=mon['y'], width=width/scale, height=height/scale)


def _iter_monitor_layers(data, name):
    entry = (data or {}).get(name, {})
    for items in entry.get('levels', entry).values():
        if isinstance(items, list):
            yield from (item for item in items if isinstance(item, dict))


def _namespace(item, name):
    ns = item.get('namespace', '')
    return ns == name or ns.endswith('/'+name)


def bar_insets_for_monitor(mon, layers_data=None):
    """Merge reserved edges and actual bar footprints, without double counting."""
    data = layers() if layers_data is None else layers_data
    box = logical_monitor(mon)
    mx, my, mw, mh = (box[k] for k in ('x', 'y', 'width', 'height'))
    insets = [max(0, float(n)) for n in (mon.get('reserved') or [0,0,0,0])]
    for item in _iter_monitor_layers(data, mon.get('name', '')):
        if not _namespace(item, BAR_NAMESPACE):
            continue
        x, y, w, h = (float(item.get(k, 0)) for k in ('x','y','w','h'))
        if w <= 0 or h <= 0:
            continue
        if w >= mw/2 and w >= h:
            edge = 1 if abs(y-my) <= abs(my+mh-y-h) else 3
            inset = y+h-my if edge == 1 else my+mh-y
        elif h >= mh/2 and h > w:
            edge = 0 if abs(x-mx) <= abs(mx+mw-x-w) else 2
            inset = x+w-mx if edge == 0 else mx+mw-x
        else:
            continue
        limit = mh/2 if edge in (1,3) else mw/2
        if 0 <= inset < limit:
            insets[edge] = max(insets[edge], inset)
    return insets


def dock_insets_for_monitor(mon, layers_data, *, position='bottom', depth=0, active=True):
    """Use the dock BODY depth supplied by QML, not its large popup hit surface."""
    result = [0,0,0,0]
    if not active or position not in ('left','top','right','bottom') or depth <= 0:
        return result
    box = logical_monitor(mon)
    edge = ('left','top','right','bottom').index(position)
    for item in _iter_monitor_layers(layers_data, mon.get('name', '')):
        if not _namespace(item, DOCK_NAMESPACE):
            continue
        # The dock surface is positioned clear of any bar on the same edge.
        x, y, w, h = (float(item.get(k,0)) for k in ('x','y','w','h'))
        offset = (x-box['x'], y-box['y'], box['x']+box['width']-x-w,
                  box['y']+box['height']-y-h)[edge]
        result[edge] = max(result[edge], max(0, offset)+depth)
    return result


def chrome_work_area(mon, dock_bottom_px=0, layers_data=None, *, dock_position='bottom',
                     dock_depth=0, dock_active=True):
    data = layers() if layers_data is None else layers_data
    box = logical_monitor(mon)
    insets = bar_insets_for_monitor(mon, data)
    dock = dock_insets_for_monitor(mon, data, position=dock_position, depth=dock_depth, active=dock_active)
    # Compatibility for synthetic callers that supply an explicit dock inset.
    dock[3] = max(dock[3], max(0, dock_bottom_px))
    left, top, right, bottom = [max(a,b) for a,b in zip(insets,dock)]
    return dict(x=box['x']+left, y=box['y']+top,
                width=max(0,box['width']-left-right), height=max(0,box['height']-top-bottom))


def work_area(mon, gap_px=0, dock_bottom_px=0, layers_data=None, outer_gap=None, **kwargs):
    box = chrome_work_area(mon, dock_bottom_px, layers_data, **kwargs)
    gap = max(0, int(gap_px))
    x0, y0 = math.ceil(box['x']+gap), math.ceil(box['y']+gap)
    x1, y1 = math.floor(box['x']+box['width']-gap), math.floor(box['y']+box['height']-gap)
    return dict(x=x0, y=y0, width=max(0,x1-x0), height=max(0,y1-y0))


def monitor_at(mons, px, py):
    for mon in mons:
        box = logical_monitor(mon)
        if box['x'] <= px < box['x']+box['width'] and box['y'] <= py < box['y']+box['height']:
            return mon
    return None


def should_snap(workspace, client):
    return not client.get('fullscreen') and workspace.get('omarchyMode', workspace.get('tiledLayout')) == 'floating'


def decoration_metrics():
    defaults = {'border': 0, 'titlebar': 0, 'enabled': False, 'tag': ''}
    options = {'border':('general:border_size','int'), 'titlebar':('plugin:hyprbars:bar_height','int'),
               'enabled':('plugin:hyprbars:enabled','bool'), 'tag':('plugin:hyprbars:workspace_tag','str')}
    for name,(option,kind) in options.items():
        try:
            defaults[name] = json.loads(_ctl('getoption', option, '-j')).get(kind, defaults[name])
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    return defaults


def decoration_insets(client, metrics):
    border = max(0, int(metrics.get('border',0)))
    tags = {str(tag).rstrip('*') for tag in client.get('tags',[])}
    tag = metrics.get('tag','')
    height = max(0,int(metrics.get('titlebar',0))) if (
        metrics.get('enabled') and client.get('floating') and not client.get('fullscreen')
        and (not tag or tag in tags)) else 0
    return [border, border+height, border, border]


def outer_rect(client, insets):
    left,top,right,bottom = insets
    x,y = client['at']; width,height = client['size']
    return dict(x=x-left, y=y-top, w=width+left+right, h=height+top+bottom)


def content_rect(outer, insets):
    left,top,right,bottom = insets
    return dict(x=outer['x']+left, y=outer['y']+top,
                w=max(1,outer['w']-left-right), h=max(1,outer['h']-top-bottom))


def clamp_rect(rect, area):
    width, height = min(rect['w'],area['width']), min(rect['h'],area['height'])
    return dict(x=max(area['x'], min(rect['x'],area['x']+area['width']-width)),
                y=max(area['y'], min(rect['y'],area['y']+area['height']-height)),
                w=width, h=height)


def move_resize_lua(address, x, y, w, h):
    if not re.fullmatch(r'0x[0-9a-fA-F]+', str(address)):
        raise ValueError('Invalid window address')
    return (
        f'local want="{address}"; local win=nil; '
        f'for _,v in pairs(hl.get_windows()) do '
        f'if tostring(v.address)==want then win=v; break end end; '
        f'if not win then error("zones: window not found "..want) end; '
        f'hl.dispatch(hl.dsp.window.resize({{ x = {int(w)}, y = {int(h)}, exact = true, window = win }})); '
        f'hl.dispatch(hl.dsp.window.move({{ x = {int(x)}, y = {int(y)}, relative = false, window = win }}))'
    )


def move_resize_cmds(address, x, y, w, h):
    return [move_resize_lua(address,x,y,w,h)]


def move_resize(address,x,y,w,h,dry_run=False):
    lua = move_resize_lua(address,x,y,w,h)
    return f'hyprctl eval {lua!r}' if dry_run else _ctl('eval',lua)
