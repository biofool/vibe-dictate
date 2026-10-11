# Architecture — vibe-dictate

- `dictate_daemon.py` — holds the Whisper model in memory, listens on a Unix
  socket (`$XDG_STATE_HOME/vibe-dictate/ctl.sock`).
- `dictate_ctl.py` — thin client your desktop shortcuts call.
- `install-shortcuts.sh` — binds **F9** (push-to-talk) and **F10** (live
  dictation) as GNOME custom shortcuts.

> Wayland note: a userland daemon cannot grab global keys without root, so
> hotkeys are delivered by the desktop environment calling `dictate_ctl.py`.
> Works on any DE — on KDE/Sway/Hyprland bind the same commands yourself.

## Top-level layout


**Key files:** `CLAUDE.md`, `LICENSE`, `README.md`, `dictate_ctl.py`, `dictate_daemon.py`, `install-shortcuts.sh`, `requirements.txt`
