# Development — vibe-dictate

## Commands
```bash
python3 dictate_daemon.py          # run daemon
python3 dictate_ctl.py ptt|live|stop|status|quit
./install-shortcuts.sh             # GNOME F9/F10 bindings
```

## Conventions
See `AGENTS.md` and `CLAUDE.md` at the repo root — they carry the shared
biofool rules (no secrets in git, never fail silently, fix scripts under
`scripts/fix/` with `--dry-run`, audit output to `data/audit/`).
