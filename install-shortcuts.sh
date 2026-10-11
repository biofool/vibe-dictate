#!/usr/bin/env bash
# Install GNOME keyboard shortcuts for vibe-dictate (F9 = push-to-talk,
# F10 = live dictation). Works on Wayland because the shortcut calls the
# ctl client — no global keygrab in the daemon needed.
# Safe to re-run: existing custom keybindings are preserved.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CTL="python3 $HERE/dictate_ctl.py"

python3 - "$CTL" <<'PY'
import json, subprocess, sys

ctl = sys.argv[1]
gs = ["gsettings"]
SCHEMA = "org.gnome.settings-daemon.plugins.media-keys"
CK_SCHEMA = SCHEMA + ".custom-keybinding"
BASE = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/"

def get(key, *schema_args):
    out = subprocess.check_output(gs + ["get", *(schema_args or [SCHEMA]), key], text=True).strip()
    return out

def setv(key, val, *schema_args):
    subprocess.check_call(gs + ["set", *(schema_args or [SCHEMA]), key, val])

raw = get("custom-keybindings")
existing = json.loads(raw.replace("'", '"')) if raw != "@as []" else []

entries = [
    ("vibe-dictate-ptt", "Dictate: push-to-talk", f"{ctl} ptt", "F9"),
    ("vibe-dictate-live", "Dictate: live dictation", f"{ctl} live", "F10"),
]
needed = [f"{BASE}{e[0]}/" for e in entries]
paths = existing + [p for p in needed if p not in existing]
setv("custom-keybindings", str(paths).replace('"', "'"))

for slug, name, command, binding in entries:
    path = BASE + slug + "/"
    setv("name", f"'{name}'", CK_SCHEMA, path)
    setv("command", f"'{command}'", CK_SCHEMA, path)
    setv("binding", f"'{binding}'", CK_SCHEMA, path)
    print(f"bound {binding} -> {command}")
PY

echo "Done. If F9/F10 are taken by another app, rebind in Settings > Keyboard > Custom Shortcuts."
