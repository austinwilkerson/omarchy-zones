"""Drag vs resize tracking: skip snap after a manual resize until a move-only drag."""


class SnapGuard:
    """Per-window dirty flag after user resize; cleared on move-only gesture.

    Call note_snap_applied(addr, size) immediately after we apply a snap so the
    following size change is not treated as a user resize. Do not update
    last_size there — the next poll that observes the new size acknowledges it.
    """

    def __init__(self):
        self.last_at = {}       # addr -> (x, y)
        self.last_size = {}     # addr -> (w, h)
        self.dirty = set()      # addresses that must not snap
        self.pending_snap = {}  # addr -> (w, h) we just applied
        self.moving = {}        # addr -> bool
        self.stable_since = {}  # addr -> timestamp when last position change seen

    def note_snap_applied(self, addr, size):
        size = tuple(size)
        self.pending_snap[addr] = size
        self.moving[addr] = False
        self.stable_since.pop(addr, None)
        self.dirty.discard(addr)

    def update(self, addr, at, size, now):
        """Ingest one poll frame. Returns dict with keys:
        dirty, moving, stable_since, move_started, resized, ack_snap.
        """
        at = tuple(at) if at and None not in at else None
        size = tuple(size) if size and None not in size else None
        prev_at = self.last_at.get(addr)
        prev_size = self.last_size.get(addr)
        move_started = False
        resized = False
        ack_snap = False

        pending = self.pending_snap.get(addr)
        if size is not None and pending is not None and size == pending:
            # Our snap landed (size matches what we applied).
            self.pending_snap.pop(addr, None)
            ack_snap = True
        elif size is not None and prev_size is not None and size != prev_size:
            # Manual (or foreign) resize — block snap until a move-only drag.
            self.dirty.add(addr)
            self.moving[addr] = False
            self.stable_since.pop(addr, None)
            self.pending_snap.pop(addr, None)
            resized = True

        if (
            at is not None
            and prev_at is not None
            and at != prev_at
            and size is not None
            and prev_size is not None
            and size == prev_size
            and not ack_snap
        ):
            # Move-only: position changed, size stable → allow snap again.
            if addr in self.dirty:
                self.dirty.discard(addr)
            self.moving[addr] = True
            self.stable_since[addr] = now
            move_started = True
        elif (
            at is not None
            and prev_at is not None
            and at != prev_at
            and size is not None
            and prev_size is not None
            and size != prev_size
            and not ack_snap
        ):
            # Move+resize together (corner drag): treat as resize, stay dirty.
            self.dirty.add(addr)
            self.moving[addr] = False
            self.stable_since.pop(addr, None)

        if at is not None:
            self.last_at[addr] = at
        if size is not None:
            self.last_size[addr] = size

        return {
            "dirty": addr in self.dirty,
            "moving": bool(self.moving.get(addr)),
            "stable_since": self.stable_since.get(addr),
            "move_started": move_started,
            "resized": resized,
            "ack_snap": ack_snap,
        }

    def clear_moving(self, addr):
        self.moving[addr] = False
        self.stable_since.pop(addr, None)

    def forget(self, addr):
        self.last_at.pop(addr, None)
        self.last_size.pop(addr, None)
        self.dirty.discard(addr)
        self.pending_snap.pop(addr, None)
        self.moving.pop(addr, None)
        self.stable_since.pop(addr, None)


class PointerGesture:
    """Latch a target and resize cancellation for one real pointer gesture."""
    def __init__(self):
        self.held = False
        self.address = None
        self.last_at = None
        self.last_size = None
        self.moving = False
        self.resized = False
        self.cancelled = False

    def update(self, pointer, client):
        held = bool(pointer and (pointer['left'] or pointer['right']))
        released = self.held and pointer is not None and not held
        address = client.get('address')
        at, size = tuple(client.get('at', [])), tuple(client.get('size', []))
        if held and not self.held:
            self.address = address
            self.last_at, self.last_size = at, size
            self.moving = False
            self.resized = bool(pointer['right'])
            self.cancelled = not bool(address)
        if (held or released) and self.held:
            if address != self.address:
                self.cancelled = True
            if size != self.last_size:
                self.resized = True
            elif at != self.last_at:
                self.moving = True
            if pointer and pointer['right']:
                self.resized = True
            self.last_at, self.last_size = at, size
        if pointer is None:
            self.cancelled = True
        result = dict(held=held, released=released, moving=self.moving,
                      resized=self.resized, cancelled=self.cancelled, address=self.address,
                      snap=released and self.moving and not self.resized and not self.cancelled)
        self.held = held
        if not held:
            self.moving = False
        return result
