# VoiceOverXeaven (VOX)

Desktop app for recording and polishing voice-over: podcasts, audiobooks, and **ADR** (dubbing to picture). Built on PySide6 with a Logic Pro–inspired dark UI and the **Unify** DSP engine (scipy/numpy).

---

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate

pip install -r requirements.txt
python -m app.main
```

**Optional ML isolation (Demucs):** heavier install (~2 GB with PyTorch):

```bash
pip install -r requirements-ml.txt
```

Then enable **ML separation (Demucs)** in the Channel Strip. Without it, HPSS heuristic isolation still works.

**Requirements:** Python 3.10+, **FFmpeg** on PATH (or in `third_party/ffmpeg/`) for MP3/FLAC export, video import, and some audio formats.

---

## Interface at a glance

```
┌─────────────────────────────────────────────────────────────┐
│  PICTURE LOCK  (ADR) — video preview, click to scrub        │
├─────────────────────────────────────────────────────────────┤
│  Workflow hint bar                                          │
├──────────────────────────────┬──────────────────────────────┤
│  Arrange view                │  Channel Strip               │
│  • waveforms + take lanes    │  • Match EQ + Picture Lock   │
│  • loop region (orange)      │  • Noise print / Demucs ML   │
│  • playhead, markers         │  • Deverb / gate             │
├──────────────────────────────┴──────────────────────────────┤
│  Transport: ■ ▶ ● R  Blade Marker  [ ] ↻ P                  │
└─────────────────────────────────────────────────────────────┘
```

| Area | What it does |
|------|----------------|
| **Start screen** | Pick workflow (Podcast / Audiobook / **ADR**) and voice preset |
| **Arrange view** | Timeline; click take lanes **A/B/C** to comp; loop region highlighted |
| **Channel Strip** | Processing; **Use Picture Lock as Reference** for ADR Match EQ |
| **Transport bar** | `[` loop in, `]` loop out, `\` toggle loop, **P** punch-in |
| **Picture Lock** | Video preview; **click video** to move playhead |

First launch shows a **Quick tour** (View → Quick Tour to replay).

---

## Workflows

### Podcast
1. Select **Voice** track → **R** (arm) → **Record** (`*`)
2. **Monitor Processed** → **Export** (WAV/FLAC/MP3, −23 LUFS)

### Audiobook
- Longer takes, gate/deverb defaults
- **Blade (B)** · click take lanes or **L** to cycle

### ADR (dub to picture)
1. Start → **ADR — dub to picture**
2. **Import Video** → click picture to scrub playhead
3. Set loop **`[` / `]`**, toggle **`\\`**, rehearse line
4. **Capture @ Playhead** on noise-only moment
5. Arm **Dialog** → **P** punch-in (overwrites loop only) or **`*`** full take
6. **Use Picture Lock as Reference** → Match EQ
7. **Export**

---

## Hotkeys (defaults)

| Action | Key |
|--------|-----|
| Play / Pause | Space |
| Record | `*` |
| Punch-in (loop region) | P |
| Arm track | R |
| Blade | B |
| Marker | M |
| Loop in / out | `[` / `]` |
| Toggle loop | `\` |
| Cycle takes | L |
| Undo / Redo | Ctrl+Z / Ctrl+Shift+Z |
| Save / Export | Ctrl+S / Ctrl+E |

Remap in **Options → Preferences → Hotkeys**.

---

## Processing (Channel Strip)

| Control | Purpose |
|---------|---------|
| **Match** | Spectral EQ toward reference (*Options → Set Reference* or Picture Lock button) |
| **Capture @ Playhead** | ~0.5 s noise sample for profile denoise |
| **Isolate** | HPSS heuristic, or **Demucs ML** if `requirements-ml.txt` installed |
| **Bypass FX** | Raw signal for comparison |

Presets: Male/Female Low/High + **ADR / Dialog**.

Settings: `~/.vox/settings.json`

---

## Audio I/O

| Action | Formats |
|--------|---------|
| **Import audio** | WAV, FLAC, MP3, OGG, M4A |
| **Import video** | MP4, MOV, MKV, AVI, WebM |
| **Export** | WAV, FLAC, MP3 (−23 LUFS, ≤ −1 dBTP) |

---

## Development

```bash
pytest          # unit tests
```

Key modules:

| Path | Role |
|------|------|
| `app/ui/` | Shell, arrange view, transport, quick tour |
| `app/timeline/undo.py` | Undo/redo stack |
| `app/dsp/pipeline.py` | Unify DSP + match EQ + isolation |
| `app/dsp/ml_separation.py` | Optional Demucs vocals |
| `app/audio/` | Record, punch-in, playback |
| `app/legacy/unify/` | Original UnifyAudio core |

---

## Credits

- **Unify Audio** — `app/legacy/unify/`
- **Demucs** (optional) — Meta AI, vocal separation
- **FFmpeg** — [ffmpeg.org](https://ffmpeg.org/)
- **PySide6**, **numpy**, **scipy**, **soundfile**, **pyloudnorm**
