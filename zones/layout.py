"""Pure layout math. Zones are fraction rects {id,x,y,w,h} in 0-1 of monitor work area."""
import json, os

EDGE_ZONES = {
    "edge-left": {"id": "edge-left", "x": 0, "y": 0, "w": 0.5, "h": 1},
    "edge-right": {"id": "edge-right", "x": 0.5, "y": 0, "w": 0.5, "h": 1},
    "edge-top": {"id": "edge-top", "x": 0, "y": 0, "w": 1, "h": 1},
}
EPS = 1e-6


def load_config(path=None, settings_path=None):
    path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "layouts.json")
    with open(path) as f:
        config = json.load(f)
    if settings_path and os.path.exists(settings_path):
        from settings import validate_patch
        with open(settings_path) as f:
            patch = validate_patch(json.load(f))
        if 'gap_px' in patch: config['gap_px'] = patch['gap_px']
        for key in ('preview', 'monitors', 'workspaces'):
            if key not in patch: continue
            merged = dict(config.get(key) or {}, **patch[key])
            config[key] = {name: value for name, value in merged.items() if value is not None}
    return config


def layout_for_monitor(cfg, monitor_name, override=None, workspace_id=None):
    """Resolve (layout_id, zone_list) for a Hyprland monitor name.

    Precedence: explicit override (CLI) → cfg["monitors"][name] → cfg["default"].
    Unknown ids fall back to default. Edge snaps (EDGE_ZONES) are independent of
    the chosen layout and always apply relative to that monitor's work area.
    """
    layouts = cfg["layouts"]
    default = cfg.get("default")
    if default not in layouts:
        default = next(iter(layouts))

    def resolve(lid):
        if lid and lid in layouts:
            return lid, layouts[lid]
        return default, layouts[default]

    if override:
        return resolve(override)
    monitors = cfg.get("monitors") or {}
    name = monitor_name or ""
    workspaces = cfg.get("workspaces") or {}
    if workspace_id is not None:
        for key in (name + ":" + str(workspace_id), str(workspace_id)):
            if key in workspaces:
                return resolve(workspaces[key])
    return resolve(monitors.get(name))


def zone_to_px(zone, mon, gap_px=4):
    """Map a fraction zone onto a work-area rect.

    `mon` should already be the cushioned work area (monitor − reserved − dock
    strip − gap_px on all four sides). Outer zone edges stay flush to that
    rect; only shared inner edges take half-gap each so adjacent zones are
    separated by gap_px total.
    """
    mx, my, mw, mh = mon["x"], mon["y"], mon["width"], mon["height"]
    x0 = round(mx + zone["x"] * mw); y0 = round(my + zone["y"] * mh)
    x1 = round(mx + (zone["x"] + zone["w"]) * mw)
    y1 = round(my + (zone["y"] + zone["h"]) * mh)
    # Split integer gaps asymmetrically when odd; both sides sum to exactly gap.
    before, after = gap_px // 2, gap_px - gap_px // 2
    if zone["x"] > EPS: x0 += after
    if zone["y"] > EPS: y0 += after
    if zone["x"] + zone["w"] < 1 - EPS: x1 -= before
    if zone["y"] + zone["h"] < 1 - EPS: y1 -= before
    return {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}



def pick_zone(px, py, mon, layout, gap_px=4, edge_px=24):
    """Return (zone_fraction, pixel_rect). Edge strips win; else closest zone center
    among zones containing the pointer (overlaps allowed); else closest center overall.

    `mon` is the cushioned work area (see zone_to_px). Edge strips are measured
    against that same rect — same behavior on every monitor.
    """
    mx, my, mw, mh = mon["x"], mon["y"], mon["width"], mon["height"]
    if py - my < edge_px:
        z = EDGE_ZONES["edge-top"]
    elif px - mx < edge_px:
        z = EDGE_ZONES["edge-left"]
    elif mx + mw - px <= edge_px:
        z = EDGE_ZONES["edge-right"]
    else:
        fx, fy = (px - mx) / mw, (py - my) / mh
        def d2(z):
            cx, cy = z["x"] + z["w"] / 2, z["y"] + z["h"] / 2
            return ((cx - fx) * mw) ** 2 + ((cy - fy) * mh) ** 2
        inside = [z for z in layout if z["x"] <= fx <= z["x"] + z["w"] and z["y"] <= fy <= z["y"] + z["h"]]
        z = min(inside or layout, key=d2)
    return z, zone_to_px(z, mon, gap_px)
