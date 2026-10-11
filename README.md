# vibe-dictate

A Wispr Flow replacement: system-wide, offline speech-to-text you own.
Push-to-talk into any app, or stream live dictation — powered by
[RealtimeSTT](https://github.com/KoljaB/RealtimeSTT) + faster-whisper.
No cloud, no subscription. Transcripts are saved locally as timestamped
`.wav` + `.txt` pairs and copied to the clipboard.

## Replaces

- **Wispr Flow** (~$144/yr) — a paid wrapper around open-source Whisper.

## Architecture

- `dictate_daemon.py` — holds the Whisper model in memory, listens on a Unix
  socket (`$XDG_STATE_HOME/vibe-dictate/ctl.sock`).
- `dictate_ctl.py` — thin client your desktop shortcuts call.
- `install-shortcuts.sh` — binds **F9** (push-to-talk) and **F10** (live
  dictation) as GNOME custom shortcuts.

> Wayland note: a userland daemon cannot grab global keys without root, so
> hotkeys are delivered by the desktop environment calling `dictate_ctl.py`.
> Works on any DE — on KDE/Sway/Hyprland bind the same commands yourself.

## Install

```bash
sudo apt install portaudio19-dev python3-dev
# optional but recommended on Wayland:
sudo apt install wtype wl-clipboard ydotool

python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

./install-shortcuts.sh            # GNOME only; other DEs: bind manually
```

## Run

```bash
python3 dictate_daemon.py         # or run via systemd --user, see below
python3 dictate_ctl.py status     # check model/device/tool detection
```

| Shortcut | Action |
|---|---|
| F9 | Start recording → press again: transcribe, save `~/dictation/<ts>.wav/.txt`, copy to clipboard, type into the focused field |
| F10 | Live dictation: stabilized phrases stream into the focused field as you speak; press again to stop |

If no typing tool (`wtype`/`ydotool`/`xdotool`) is found, the transcript
still lands on the clipboard and you get a notification to paste manually.

## Configuration (env)

| Var | Default | Purpose |
|---|---|---|
| `VIBE_MODEL` | `small.en` | faster-whisper model |
| `VIBE_REALTIME_MODEL` | `tiny.en` | live-preview model |
| `VIBE_DEVICE` | `cpu` | `cuda` for GPU (6 GB VRAM is enough) |
| `VIBE_COMPUTE` | `int8` | `float16` on GPU |
| `VIBE_DICTATE_DIR` | `~/dictation` | output folder |

CPU `small.en`/int8 is usable (~1–2 s latency per phrase). With a GPU set
`VIBE_DEVICE=cuda VIBE_MODEL=medium.en` for near-Wispr latency.

## systemd --user (optional)

```ini
# ~/.config/systemd/user/vibe-dictate.service
[Unit]
Description=vibe-dictate daemon

[Service]
ExecStart=%h/projects/github/vibe-dictate/.venv/bin/python %h/projects/github/vibe-dictate/dictate_daemon.py
Restart=on-failure

[Install]
WantedBy=default.target
```

`systemctl --user enable --now vibe-dictate`

## Limitations

- Wayland typing requires `wtype`/`ydotool`; without one you get
  clipboard + manual paste.
- No GPU → noticeable latency on live dictation; PTT is fine.
- Wake-word / always-listening mode intentionally omitted (battery + mic
  hygiene); PTT covers the workflow.
