# Executive Summary — vibe-dictate

vibe-dictate is an offline, system-wide speech-to-text tool for Linux.
It replaces a paid dictation subscription (Wispr Flow) with local Whisper
models. No audio or text leaves the machine.

## Benefits for somatic studios and practitioners

- **Hands-free notes.** A teacher can dictate observations while watching a
  student move. No need to stop, sit down, or type.
- **Works in any app.** Press one key, speak, and the text is typed into
  whichever field has focus — a notes app, a booking system, an email.
- **Client privacy.** All transcription runs locally. Session notes about
  bodies, injuries, and health never pass through a cloud service.
- **No recurring cost.** Open-source models and code. No subscription and
  no per-minute fees.
- **Automatic records.** Each session is saved as a timestamped `.wav` +
  `.txt` pair. Practitioners keep a searchable history of notes.
- **Two working modes.** Push-to-talk for short notes between cues. Live
  dictation for continuous narration during a session.

## Trade-offs

- Linux only (tested on GNOME/Wayland; other desktops need manual key binds).
- CPU-only machines have noticeable latency on live dictation. A modest GPU
  removes most of it.
- Accuracy matches the underlying Whisper model. Technical vocabulary may
  need correction.
