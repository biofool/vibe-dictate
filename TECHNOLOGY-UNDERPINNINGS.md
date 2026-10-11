# Technology Underpinnings — vibe-dictate

Two-file Python project. A daemon holds the speech model in memory. A thin
client sends it commands over a Unix socket.

## Speech recognition

- **RealtimeSTT** (`requirements.txt`) wraps **faster-whisper** and provides
  the recorder, VAD, and realtime preview pipeline.
- `dictate_daemon.py` creates one `AudioToTextRecorder` with two models:
  - `VIBE_MODEL` (default `small.en`) transcribes completed utterances.
  - `VIBE_REALTIME_MODEL` (default `tiny.en`) produces stabilized live
    previews via `on_realtime_transcription_stabilized`.
- CPU-safe defaults: `VIBE_DEVICE=cpu`, `VIBE_COMPUTE=int8`. GPU use is
  opt-in through the same env vars (`cuda`, `float16`).

## Control plane

- The daemon listens on a Unix stream socket at
  `$XDG_STATE_HOME/vibe-dictate/ctl.sock` using
  `socketserver.ThreadingMixIn` + `UnixStreamServer`
  (`dictate_daemon.py`, `Server`/`CtlHandler`).
- `dictate_ctl.py` connects, sends one line (`ptt`, `live`, `stop`,
  `status`, `quit`), and prints the reply.
- Wayland cannot grab global keys from userland without root, so the
  desktop environment delivers hotkeys: `install-shortcuts.sh` registers
  GNOME custom keybindings (F9 → `ptt`, F10 → `live`) through `gsettings`.
  Other DEs can bind the same `dictate_ctl.py` commands.

## Modes

- **Push-to-talk** (`cmd_ptt`, `_finish_ptt`): a lock-guarded state machine
  (`IDLE`/`PTT`/`LIVE`) toggles recording. On stop, the full model returns
  the transcript. Raw PCM chunks captured by `on_recorded_chunk` are
  drained from a `queue.Queue` and written as a 16 kHz mono `.wav` next to
  a `.txt` transcript (`save_pair`), timestamped into `~/dictation`.
- **Live dictation** (`cmd_live`, `_run_live`, `_on_live_text`): stabilized
  realtime segments are typed into the focused field as they arrive. On
  stop, utterances are joined and saved as a `-live` wav/txt pair.

## Output delivery — graceful degradation

Helpers probe `shutil.which` and fall back in order:

- Clipboard: `wl-copy` → `xclip` → fail (`clipboard_set`).
- Typing: `wtype` → `ydotool` → `xdotool` → notify-only (`type_text`).
- Paste chord: same tool chain sends Ctrl+V (`paste_chord`).

If no typing tool exists, the transcript stays on the clipboard and
`notify-send` tells the user to paste manually (`notify`).

## Supporting pieces

- `install-shortcuts.sh` — idempotent `gsettings` writer; preserves
  existing GNOME custom keybindings.
- `requirements.txt` — single direct dep (`RealtimeSTT`); system packages
  `portaudio19-dev` and `python3-dev` are required for the audio stack.
- `CLAUDE.md`, `wiki/` — project conventions and per-area notes.
- `.claude/hooks/post_edit_lint.py` — post-edit lint hook for local dev.
