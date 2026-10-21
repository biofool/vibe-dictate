#!/usr/bin/env python3
"""vibe-dictate daemon — local system-wide dictation (Wispr Flow replacement).

Runs a RealtimeSTT/faster-whisper recorder and listens for commands on a Unix
socket. Bind desktop shortcuts to `dictate_ctl.py ptt` / `dictate_ctl.py live`
(see install-shortcuts.sh) — this is what replaces global hotkeys on Wayland,
where userland daemons cannot grab keys without root.

Commands (socket):
    ptt     — toggle push-to-talk: record -> transcribe -> save wav+txt ->
              clipboard -> type/paste into focused field
    live    — toggle live dictation: streams stabilized text into the
              focused field in real time
    stop    — stop whatever is running
    status  — print daemon state
    quit    — exit the daemon
"""

import fcntl
import json
import logging
import os
import queue
import shutil
import socketserver
import subprocess
import sys
import threading
import wave
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s dictate %(levelname)s %(message)s")
log = logging.getLogger("vibe-dictate")

STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "vibe-dictate"
SOCK = STATE_DIR / "ctl.sock"
OUT_DIR = Path(os.environ.get("VIBE_DICTATE_DIR", Path.home() / "dictation"))

# CPU-safe defaults — this machine has no GPU. Override via env:
#   VIBE_MODEL=medium.en VIBE_DEVICE=cuda VIBE_COMPUTE=float16
MODEL = os.environ.get("VIBE_MODEL", "small.en")
REALTIME_MODEL = os.environ.get("VIBE_REALTIME_MODEL", "tiny.en")
DEVICE = os.environ.get("VIBE_DEVICE", "cpu")
COMPUTE = os.environ.get("VIBE_COMPUTE", "int8")

SAMPLE_RATE = 16000

IDLE, PTT, LIVE, FINISHING = "idle", "ptt", "live", "finishing"

# ~25 chunks/sec at realtime_processing_pause=0.04 → 45k caps the queue near
# 30 min of audio instead of growing ~115MB/h on a forgotten PTT session.
PCM_QUEUE_MAX = 45_000


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def notify(msg: str) -> None:
    log.info(msg)
    if have("notify-send"):
        subprocess.Popen(["notify-send", "vibe-dictate", msg],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def clipboard_set(text: str) -> bool:
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard", "-in"]):
        if have(cmd[0]) and subprocess.run(
                cmd, input=text.encode(), check=False).returncode == 0:
            return True
    return False


def type_text(text: str) -> bool:
    """Type text into the focused field. wtype = Wayland, ydotool = universal."""
    for cmd in (["wtype", "--", text],
                ["ydotool", "type", "--", text],
                ["xdotool", "type", "--clearmodifiers", "--", text]):
        if have(cmd[0]) and subprocess.run(cmd, check=False).returncode == 0:
            return True
    return False


def paste_chord() -> bool:
    """Simulate Ctrl+V into the focused field."""
    for cmd in (["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"],
                ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
                ["xdotool", "key", "--clearmodifiers", "ctrl+v"]):
        if have(cmd[0]) and subprocess.run(cmd, check=False).returncode == 0:
            return True
    return False


def save_pair(wav_path: Path, text: str, pcm: bytes) -> None:
    # Transcripts can hold health/personal notes — keep them owner-only.
    if pcm:
        with wave.open(str(wav_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SAMPLE_RATE)
            w.writeframes(pcm)
        wav_path.chmod(0o600)
    txt_path = wav_path.with_suffix(".txt")
    txt_path.write_text(text + "\n", encoding="utf-8")
    txt_path.chmod(0o600)


class DictateDaemon:
    def __init__(self) -> None:
        self.state = IDLE
        self.lock = threading.Lock()
        self.live_stop = threading.Event()
        self.pcm_chunks: "queue.Queue[bytes | None]" = queue.Queue(maxsize=PCM_QUEUE_MAX)
        self.live_typed = 0  # chars already emitted for the live session

        from RealtimeSTT import AudioToTextRecorder  # heavy import, deferred

        self.recorder = AudioToTextRecorder(
            model=MODEL,
            realtime_model_type=REALTIME_MODEL,
            device=DEVICE,
            compute_type=COMPUTE,
            enable_realtime_transcription=True,
            realtime_processing_pause=0.04,
            on_recorded_chunk=self._on_chunk,
            on_realtime_transcription_stabilized=self._on_live_text,
            spinner=False,
            level=logging.WARNING,
        )
        log.info("recorder ready (model=%s device=%s compute=%s)", MODEL, DEVICE, COMPUTE)

    # -- recorder callbacks -------------------------------------------------

    def _on_chunk(self, chunk: bytes) -> None:
        try:
            self.pcm_chunks.put_nowait(chunk)
        except queue.Full:
            pass  # forgotten long session — drop audio rather than grow or block

    def _on_live_text(self, text: str) -> None:
        # Fires with stabilized realtime segments; type only in live mode.
        with self.lock:
            if self.state != LIVE or not text.strip():
                return
            self.live_typed += len(text) + 1
        type_text(text + " ")

    def _drain_pcm(self) -> bytes:
        parts = []
        while True:
            try:
                parts.append(self.pcm_chunks.get_nowait())
            except queue.Empty:
                return b"".join(parts)

    # -- commands ------------------------------------------------------------

    def cmd_ptt(self) -> str:
        with self.lock:
            if self.state == PTT:
                # FINISHING (not IDLE) until _finish_ptt returns — a fast
                # re-press must not start a new session mid-finish.
                self.state = FINISHING
                threading.Thread(target=self._finish_ptt, daemon=True).start()
                return "ptt stopping"
            if self.state != IDLE:
                return f"busy ({self.state})"
            self.state = PTT
            self._drain_pcm()
            self.recorder.start()
            notify("recording… press shortcut again to stop")
            return "ptt recording"

    def _finish_ptt(self) -> None:
        try:
            self.recorder.stop()
            text = (self.recorder.text() or "").strip()
            pcm = self._drain_pcm()
            if not text:
                notify("nothing transcribed")
                return
            stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            OUT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
            save_pair(OUT_DIR / f"{stamp}.wav", text, pcm)
            log.info("ptt transcript (%d chars) -> %s.*", len(text), stamp)
            clipboard_set(text)
            if not (type_text(text) or paste_chord()):
                notify("transcript on clipboard — paste manually")
        except Exception as e:
            log.exception("finish_ptt failed")
            notify(f"transcription failed: {e}")
        finally:
            with self.lock:
                self.state = IDLE

    def cmd_live(self) -> str:
        with self.lock:
            if self.state == LIVE:
                self.state = IDLE
                self.live_stop.set()
            elif self.state != IDLE:
                return f"busy ({self.state})"
            else:
                self.state = LIVE
                self.live_stop.clear()
                self.live_typed = 0
                self._drain_pcm()
                threading.Thread(target=self._run_live, daemon=True).start()
                return "live dictation on"
        self.recorder.stop()  # outside the lock — stop() can block
        return "live stopped"

    def _run_live(self) -> None:
        try:
            notify("live dictation — speak")
            utterances = []
            while not self.live_stop.is_set():
                t = self.recorder.text()  # keep recorder fed; field text goes via callback
                if t and t.strip():
                    utterances.append(t.strip())
            pcm = self._drain_pcm()
            text = " ".join(utterances)
            if text:
                stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                OUT_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
                save_pair(OUT_DIR / f"{stamp}-live.wav", text, pcm)
                clipboard_set(text)
                log.info("live transcript (%d chars) -> %s-live.*", len(text), stamp)
            log.info("live session ended")
        except Exception as e:
            log.exception("live session failed")
            notify(f"live dictation failed: {e}")

    def cmd_stop(self) -> str:
        with self.lock:
            prev = self.state
            # FINISHING means _finish_ptt owns the recorder — leave state
            # alone and let it return to IDLE when done.
            if prev != FINISHING:
                self.state = IDLE
        if prev == LIVE:
            self.live_stop.set()
        if prev in (PTT, LIVE):
            self.recorder.stop()
        return f"stopped (was {prev})"

    def cmd_status(self) -> str:
        return json.dumps({
            "state": self.state, "model": MODEL, "device": DEVICE,
            "compute": COMPUTE, "out_dir": str(OUT_DIR),
            "clipboard": "wl-copy" if have("wl-copy") else "xclip" if have("xclip") else "none",
            "type": "wtype" if have("wtype") else "ydotool" if have("ydotool") else "xdotool" if have("xdotool") else "none",
        })


class CtlHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        cmd = self.rfile.readline(4096).decode("utf-8", "replace").strip()
        d = self.server.daemon  # type: ignore[attr-defined]
        fn = {"ptt": d.cmd_ptt, "live": d.cmd_live, "stop": d.cmd_stop,
              "status": d.cmd_status}.get(cmd)
        if cmd == "quit":
            self.wfile.write(b"bye\n")
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        elif fn:
            try:
                reply = fn()
            except Exception as e:
                log.exception("command %s failed", cmd)
                reply = f"error: {e}"
            self.wfile.write((reply + "\n").encode())
        else:
            self.wfile.write(f"unknown command: {cmd}\n".encode())


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATE_DIR, 0o700)
    # Single-instance guard — a second daemon must not unlink the live socket.
    lock_fd = open(STATE_DIR / "daemon.lock", "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log.error("another vibe-dictate daemon is already running — exiting")
        return 1
    SOCK.unlink(missing_ok=True)
    srv = Server(str(SOCK), CtlHandler)
    SOCK.chmod(0o600)  # socket is a command channel — owner only
    srv.daemon = DictateDaemon()  # type: ignore[attr-defined]
    log.info("listening on %s", SOCK)
    try:
        srv.serve_forever()
    finally:
        srv.daemon.cmd_stop()  # type: ignore[attr-defined]
        SOCK.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
