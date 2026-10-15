#!/usr/bin/env python3
"""Floating-mode zone snapping with decorated-frame bounds and release tracking."""
import argparse
import json
import os
from pathlib import Path
import sys
import signal
import time
from zones.layout import load_config, pick_zone, layout_for_monitor
from zones.drag import SnapGuard, PointerGesture
from zones import hypr
from zones.observer import PointerObserver


def emit(obj):
    print(json.dumps(obj), flush=True)


def resolve_work_area(mon, gap_px, layers_data, shell_cfg, dock_depth, workspace):
    dock=shell_cfg.get('dock',{})
    return hypr.work_area(mon,gap_px=gap_px,layers_data=layers_data,
        dock_position=dock.get('position','bottom'),dock_depth=dock_depth,
        dock_active=hypr.workspace_mode(workspace)=='floating')


def frame_eligible(client, workspace):
    return (hypr.workspace_mode(workspace)=='floating' and client.get('floating')
            and client.get('mapped',True) and not client.get('hidden')
            and not client.get('fullscreen') and client.get('workspace',{}).get('id',-1)>=1)


def fit_client(client, area, metrics):
    insets=hypr.decoration_insets(client,metrics)
    outer=hypr.outer_rect(client,insets)
    # Don't retrieve intentionally parked/off-output windows as a side effect.
    if (outer['x']+outer['w'] <= area['x'] or outer['x'] >= area['x']+area['width']
            or outer['y']+outer['h'] <= area['y'] or outer['y'] >= area['y']+area['height']):
        return None
    fitted=hypr.clamp_rect(outer,area)
    if fitted==outer or area['width']<=sum(insets[::2]) or area['height']<=insets[1]+insets[3]:
        return None
    return hypr.content_rect(fitted,insets)


def apply_rect(address, rect):
    return hypr.move_resize(address,rect['x'],rect['y'],rect['w'],rect['h'])


def run_loop(args, initial_cfg, observer):
    if not os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        raise SystemExit('Run inside Hyprland, or use --dry-run.')
    cfg=initial_cfg
    guard=SnapGuard()
    gesture=PointerGesture()
    preview=None
    geometry_at=0
    last_adjusted={}
    last_activity={}
    monitors=[]; workspaces={}; layer_data={}; shell_cfg={}; metrics={}
    warning_shown=False
    cfg_mtime=0
    held=False
    emit({'event':'ready','snap':not args.no_snap,'mode':'floating-only'})
    while True:
        try:
            now=time.monotonic()
            if now-geometry_at>=0.5:
                monitors=hypr.monitors()
                workspaces={w['id']:w for w in json.loads(hypr._ctl('workspaces','-j'))}
                layer_data=hypr.layers()
                shell_cfg=hypr.shell_config()
                metrics=hypr.decoration_metrics()
                geometry_at=now
                try:
                    mtime=(Path(args.config).stat().st_mtime_ns,
                           Path(args.settings).stat().st_mtime_ns if args.settings and Path(args.settings).exists() else 0)
                    if mtime!=cfg_mtime:
                        cfg=load_config(args.config,args.settings)
                        cfg_mtime=mtime
                except (OSError,ValueError,KeyError) as error:
                    emit({'event':'warning','message':'Keeping previous config: '+str(error)})
            gap=cfg['gap_px'] if args.gap is None else args.gap
            edge=cfg.get('edge_px',24) if args.edge is None else args.edge
            all_clients=hypr.clients()
            active=json.loads(hypr._ctl('activewindow','-j') or '{}')
            ptr=observer.read()
            gest=gesture.update(ptr,active)
            held=gest['held']
            released=gest['released']
            if released and gest['snap']:
                # A bar may have moved since the last periodic snapshot.
                monitors=hypr.monitors()
                workspaces={w['id']:w for w in json.loads(hypr._ctl('workspaces','-j'))}
                layer_data=hypr.layers()
                shell_cfg=hypr.shell_config()
                metrics=hypr.decoration_metrics()
                geometry_at=now
            if ptr is None and not warning_shown:
                emit({'event':'warning','message':'Pointer observer unavailable; snapping disabled. '+str(observer.error)})
                warning_shown=True
            if ptr is not None: warning_shown=False
            addr=active.get('address')
            ws=workspaces.get(active.get('workspace',{}).get('id'),{})
            eligible=bool(addr and frame_eligible(active,ws))
            state=None
            if eligible:
                state=guard.update(addr,active.get('at'),active.get('size'),now)
                if state['move_started'] or state['resized']:
                    last_activity[addr]=now
            candidate=None
            if eligible and ptr and not gest['cancelled'] and gest['moving'] and not gest['resized'] and gest['address']==addr and (held or gest['snap']):
                cursor=json.loads(hypr._ctl('cursorpos','-j'))
                mon=hypr.monitor_at(monitors,cursor['x'],cursor['y'])
                if mon:
                    target_ws=workspaces.get(mon.get('activeWorkspace',{}).get('id'),ws)
                    area=resolve_work_area(mon,gap,layer_data,shell_cfg,args.dock_depth,target_ws)
                    if hypr.workspace_mode(target_ws)=='floating' and area['width']>0 and area['height']>0:
                        lid,layout=layout_for_monitor(cfg,mon['name'],override=args.layout,workspace_id=target_ws.get('id'))
                        zone,rect=pick_zone(cursor['x'],cursor['y'],area,layout,gap,edge)
                        candidate=(lid,zone,rect,mon)
                        key=(addr,lid,zone['id'],tuple(rect.values()))
                        if key!=preview and not released:
                            emit({'event':'preview','zone':zone['id'],'layout':lid,'monitor':mon['name'],
                                  'rect':rect,'address':addr})
                            preview=key
            if released:
                if candidate and gest['snap']:
                    lid,zone,outer,mon=candidate
                    rect=hypr.content_rect(outer,hypr.decoration_insets(active,metrics))
                    if not args.no_snap:
                        apply_rect(addr,rect)
                        guard.note_snap_applied(addr,(rect['w'],rect['h']))
                    emit({'event':'snap-candidate','zone':zone['id'],'rect':outer,'contentRect':rect,
                          'address':addr,'applied':not args.no_snap})
                if addr: guard.clear_moving(addr)
            if preview and (released or not held or not eligible or gest['resized'] or gest['cancelled'] or gest['address']!=addr):
                emit({'event':'preview-clear'})
                preview=None
            if not held and not released:
                if addr: guard.clear_moving(addr)
                if not args.no_snap:
                    by_monitor={m['id']:m for m in monitors}
                    active_workspaces={m.get('activeWorkspace',{}).get('id') for m in monitors}
                    alive={c['address'] for c in all_clients}
                    for stale in set(guard.last_at)-alive:
                        guard.forget(stale); last_adjusted.pop(stale,None); last_activity.pop(stale,None)
                    for client in all_clients:
                        address=client['address']
                        workspace=workspaces.get(client.get('workspace',{}).get('id'),{})
                        if not frame_eligible(client,workspace) or workspace.get('id') not in active_workspaces:
                            continue
                        if now-last_activity.get(address,-10)<0.35:
                            continue
                        mon=by_monitor.get(client.get('monitor'))
                        if not mon: continue
                        area=resolve_work_area(mon,gap,layer_data,shell_cfg,args.dock_depth,workspace)
                        rect=fit_client(client,area,metrics)
                        if rect:
                            # Rate-limit applications that refuse the requested size.
                            key=tuple(rect.values())
                            previous=last_adjusted.get(address)
                            if previous and previous[0]==key and now-previous[1]<2:
                                continue
                            apply_rect(address,rect)
                            last_adjusted[address]=(key,now)
                            guard.note_snap_applied(address,(rect['w'],rect['h']))
        except Exception as error:
            # A stale client or transient compositor reply must not kill the service.
            emit({'event':'warning','message':str(error)})
            if preview: emit({'event':'preview-clear'}); preview=None
            time.sleep(0.3)
        time.sleep(0.08 if held else 0.15)


def live(args, cfg):
    observer=PointerObserver(args.observer)
    try:
        run_loop(args,cfg,observer)
    finally:
        observer.close()


def dry_run(args,cfg):
    width,height=map(int,args.monitor.lower().split('x'))
    px,py=map(int,args.pointer.split(','))
    gap=cfg['gap_px'] if args.gap is None else args.gap
    edge=cfg.get('edge_px',24) if args.edge is None else args.edge
    area=hypr.work_area(dict(name=args.monitor_name or '',x=0,y=0,width=width,height=height,scale=1,
                             reserved=[0,0,0,0]),gap_px=gap,layers_data={})
    lid,layout=layout_for_monitor(cfg,args.monitor_name,override=args.layout,workspace_id=args.workspace)
    zone,rect=pick_zone(px,py,area,layout,gap,edge)
    print(json.dumps({'layout':lid,'zone':zone['id'],'rect':rect,'work_area':area},indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default=str(Path(__file__).with_name('layouts.json')))
    parser.add_argument('--settings',help='Separate padding and preview preferences file')
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--observer',help='Locally compiled read-only Hyprland observer library')
    parser.add_argument('--snap',action='store_true',help='Compatibility: snapping is enabled by default')
    parser.add_argument('--no-snap',action='store_true')
    parser.add_argument('--dock-depth',type=int,default=51,help='Actual dock body depth from the shell theme')
    parser.add_argument('--layout')
    parser.add_argument('--monitor-name')
    parser.add_argument('--workspace',type=int)
    parser.add_argument('--pointer',default='2560,720')
    parser.add_argument('--monitor',default='5120x1440')
    parser.add_argument('--gap',type=int)
    parser.add_argument('--edge',type=int)
    args=parser.parse_args()
    cfg=load_config(args.config,args.settings)
    if args.gap is not None and args.gap<0: parser.error('--gap must be nonnegative')
    signal.signal(signal.SIGTERM,lambda *_: sys.exit(0))
    dry_run(args,cfg) if args.dry_run else live(args,cfg)


if __name__=='__main__': main()
