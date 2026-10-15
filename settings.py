#!/usr/bin/env python3
"""Validate and atomically update the user-facing settings, preserving layouts."""
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import re
import tempfile


def validate_patch(patch):
    if not isinstance(patch, dict) or set(patch) - {'gap_px', 'preview', 'monitors', 'workspaces'}:
        raise ValueError('Unsupported settings')
    layouts = {'halves', 'thirds', '25-50-25', 'quarters-cols', 'grid-2x2', 'columns-mid50'}
    for key in ('monitors', 'workspaces'):
        if key not in patch: continue
        values = patch[key]
        if not isinstance(values, dict) or len(values) > 128:
            raise ValueError('Invalid layout selections')
        for target, layout in values.items():
            if not isinstance(target, str) or not re.fullmatch(r'[A-Za-z0-9_.:+-]{1,128}', target):
                raise ValueError('Invalid monitor or workspace')
            if layout is not None and (not isinstance(layout, str) or layout not in layouts):
                raise ValueError('Unknown layout')
    if 'gap_px' in patch:
        gap = patch['gap_px']
        if type(gap) is not int or not 0 <= gap <= 64:
            raise ValueError('Padding must be a whole number from 0 to 64')
    if 'preview' in patch:
        preview = patch['preview']
        if not isinstance(preview, dict) or set(preview) - {'color', 'custom', 'opacity'}:
            raise ValueError('Unsupported preview setting')
        if 'color' in preview and preview['color'] not in ('accent', 'foreground', 'urgent', 'custom'):
            raise ValueError('Unknown color choice')
        if 'custom' in preview and not re.fullmatch(r'#[0-9a-fA-F]{6}', str(preview['custom'])):
            raise ValueError('Use a color in #RRGGBB format')
        if 'opacity' in preview:
            value = preview['opacity']
            if type(value) not in (int, float) or not math.isfinite(value) or not .05 <= value <= .8:
                raise ValueError('Opacity must be from 5% to 80%')
    return patch


def update(path, patch):
    validate_patch(patch)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name('.settings.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        config = json.loads(path.read_text()) if path.exists() else {}
        if 'gap_px' in patch:
            config['gap_px'] = patch['gap_px']
        for key in ('preview', 'monitors', 'workspaces'):
            if key in patch: config[key] = dict(config.get(key) or {}, **patch[key])
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.settings-', delete=False) as stream:
                temporary = stream.name
                json.dump(config, stream, indent=2)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, path.stat().st_mode & 0o777 if path.exists() else 0o600)
            os.replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
    return config


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('patch')
    args = parser.parse_args()
    try:
        print(json.dumps(update(args.config, json.loads(args.patch))))
    except (OSError, ValueError, TypeError) as error:
        parser.exit(1, str(error) + '\n')
