import json
import zipfile
from dataclasses import dataclass
from typing import Any


@dataclass
class DiffItem:
    category: str   # "channels", "roles", "emojis", "settings"
    change_type: str  # "added", "removed", "modified"
    name: str
    detail: str = ""


def load_backup(path: str) -> dict:
    with zipfile.ZipFile(path, "r") as zf:
        with zf.open("backup.json") as f:
            return json.loads(f.read())


def compare_backups(path_a: str, path_b: str) -> list[DiffItem]:
    """Compare backup A (older) to backup B (newer). Returns list of changes."""
    a = load_backup(path_a)
    b = load_backup(path_b)
    diffs: list[DiffItem] = []

    # --- Settings ---
    sa = a.get("settings", {})
    sb = b.get("settings", {})
    for key in ("name", "verification_level", "explicit_content_filter", "default_message_notifications"):
        va, vb = sa.get(key), sb.get(key)
        if va != vb:
            diffs.append(DiffItem("settings", "modified", key, f"{va!r} → {vb!r}"))

    # --- Roles ---
    roles_a = {r["name"]: r for r in a.get("roles", []) if not r.get("everyone")}
    roles_b = {r["name"]: r for r in b.get("roles", []) if not r.get("everyone")}

    for name in set(roles_a) - set(roles_b):
        diffs.append(DiffItem("roles", "removed", name))
    for name in set(roles_b) - set(roles_a):
        diffs.append(DiffItem("roles", "added", name))
    for name in set(roles_a) & set(roles_b):
        ra, rb = roles_a[name], roles_b[name]
        changes = []
        if ra.get("color") != rb.get("color"):
            changes.append(f"color #{rb.get('color', 0):06X}")
        if ra.get("permissions") != rb.get("permissions"):
            changes.append("permissions changed")
        if ra.get("hoist") != rb.get("hoist"):
            changes.append(f"hoist → {rb.get('hoist')}")
        if changes:
            diffs.append(DiffItem("roles", "modified", name, ", ".join(changes)))

    # --- Channels ---
    ch_a = {c["name"]: c for c in a.get("channels", [])}
    ch_b = {c["name"]: c for c in b.get("channels", [])}

    type_names = {0: "text", 2: "voice", 4: "category", 5: "announcement", 13: "stage", 15: "forum"}

    for name in set(ch_a) - set(ch_b):
        t = type_names.get(ch_a[name].get("type", 0), "channel")
        diffs.append(DiffItem("channels", "removed", name, t))
    for name in set(ch_b) - set(ch_a):
        t = type_names.get(ch_b[name].get("type", 0), "channel")
        diffs.append(DiffItem("channels", "added", name, t))
    for name in set(ch_a) & set(ch_b):
        ca, cb = ch_a[name], ch_b[name]
        changes = []
        if ca.get("topic") != cb.get("topic"):
            changes.append("topic changed")
        if ca.get("nsfw") != cb.get("nsfw"):
            changes.append(f"nsfw → {cb.get('nsfw')}")
        if ca.get("slowmode") != cb.get("slowmode"):
            changes.append(f"slowmode → {cb.get('slowmode')}s")
        if ca.get("parent_name") != cb.get("parent_name"):
            changes.append(f"moved to {cb.get('parent_name', 'none')}")
        if ca.get("type") != cb.get("type"):
            changes.append(f"type → {type_names.get(cb.get('type', 0), '?')}")
        ow_a = {o["label"] for o in ca.get("permission_overwrites", [])}
        ow_b = {o["label"] for o in cb.get("permission_overwrites", [])}
        if ow_a != ow_b:
            changes.append("permission overwrites changed")
        if changes:
            diffs.append(DiffItem("channels", "modified", name, ", ".join(changes)))

    # --- Emojis ---
    em_a = {e["name"] for e in a.get("emojis", [])}
    em_b = {e["name"] for e in b.get("emojis", [])}
    for name in em_a - em_b:
        diffs.append(DiffItem("emojis", "removed", f":{name}:"))
    for name in em_b - em_a:
        diffs.append(DiffItem("emojis", "added", f":{name}:"))

    return diffs
