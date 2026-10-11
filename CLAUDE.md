<!-- AI coding config version: 2026-10-11 — sourced from biofool/starter template. -->

# CLAUDE.md

## Project overview

vibe-dictate — offline system-wide dictation daemon replacing Wispr Flow.
RealtimeSTT + faster-whisper; controlled over a Unix socket because
Wayland userland cannot grab global keys.

## Commands

```bash
python3 dictate_daemon.py          # run daemon
python3 dictate_ctl.py ptt|live|stop|status|quit
./install-shortcuts.sh             # GNOME F9/F10 bindings
```

## Conventions

- No GPU on the dev machine — defaults must stay CPU-safe
  (`small.en`/`tiny.en`, `int8`). GPU paths via env vars only.
- Hotkey delivery is via DE shortcuts -> `dictate_ctl.py`; do not add an
  evdev/global-grab path unless explicitly asked (needs root/input group).
- Typing/clipboard helpers must degrade gracefully: `wl-copy` -> `xclip`,
  `wtype` -> `ydotool` -> `xdotool` -> notify-only.
- `0.0.0.0` is a bind address, not a connect address — never use it in URLs.
