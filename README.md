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

**Requirements:** Python 3.10+, **FFmpeg** on PATH (or in `third_party/ffmpeg/`) for MP3/FLAC export, video import, and some audio formats.

---

## Interface at a glance

```
┌─────────────────────────────────────────────────────────────┐
│  PICTURE LOCK  (ADR) — video preview + Import Video         │
├─────────────────────────────────────────────────────────────┤
│  Workflow hint bar (context tips for Podcast / ADR / …)     │
├──────────────────────────────┬──────────────────────────────┤
│  Arrange view                │  Channel Strip               │
│  • track lanes + waveforms   │  • Match EQ                  │
│  • playhead, markers         │  • Noise print               │
│  • arm (R) on track header   │  • Voice isolation           │
│                              │  • Deverb / gate             │
├──────────────────────────────┴──────────────────────────────┤
│  Transport: Stop ■  Play ▶  Record ●  Arm  Blade  Marker   │
└─────────────────────────────────────────────────────────────┘
```

| Area | What it does |
|------|----------------|
| **Start screen** | Pick workflow (Podcast / Audiobook / **ADR**) and voice preset |
| **Arrange view** | Timeline with waveforms; click to move playhead; Ctrl+wheel = zoom |
| **Channel Strip** | Processing: EQ match, noise print, isolation, dynamics |
| **Transport bar** | Play, record, arm, blade, marker — mirrors hotkeys |
| **Picture Lock** | Video preview (ADR); syncs with playhead; muted (audio on timeline track) |

---

## Workflows

### Podcast
1. Select **Voice** track → **R** (arm) → **Record** (`*`) — ~5 s takes with preroll beeps  
2. **Monitor Processed** to hear FX → **Export** (WAV/FLAC/MP3, −23 LUFS)

### Audiobook
- Longer takes (~8 s), noise gate and deverb enabled by default  
- **Blade (B)** to split clips · **L** to cycle take lanes

### ADR (dub to picture)
1. Start screen → **ADR — dub to picture** (preset **ADR / Dialog**)  
2. **File → Import Video** (or button in Picture Lock panel)  
3. Audio from video lands on **Picture Lock** track; video shows above timeline  
4. Move playhead to a **noise-only** moment → **Capture @ Playhead** (Channel Strip)  
5. Select **Dialog** track → arm → record while watching the picture  
6. **Options → Set Reference** for Match EQ (optional) · **Export**

---

## Audio I/O

| Action | Formats |
|--------|---------|
| **Import audio** | WAV, FLAC, MP3, OGG, M4A, AAC (soundfile + FFmpeg fallback) |
| **Import video** | MP4, MOV, MKV, AVI, WebM → extracts audio + preview |
| **Export** | WAV, FLAC, MP3 (128–320 kbps CBR) |

All exports: loudness **−23 LUFS**, true peak **≤ −1 dBTP**.

---

## Processing (Channel Strip)

| Control | Purpose |
|---------|---------|
| **Match** | Spectral EQ toward reference file (*Options → Set Reference*) |
| **Capture @ Playhead** | Grab ~0.5 s noise sample for profile denoise |
| **Reduce / Floor / Sens** | Noise print strength, floor, sensitivity |
| **Isolate** | Pull voice out of music/foley beds (heuristic, not AI) |
| **Tilt / Deverb** | Timbre and late-reflection cleanup |
| **Bypass FX** | Raw signal for comparison |

Presets: Male/Female Low/High + **ADR / Dialog**.

Settings persist in `~/.vox/settings.json` (hotkeys, noise profile, window geometry).

---

## Projects & autosave

- Projects: `*.voxproj` (SQLite timeline + takes)  
- **File → Save / Save As / Open**  
- Autosave ring (default 5 slots, 300 s) — restore offered on launch  
- Configure: **Options → Preferences**

---

## Hotkeys (defaults)

| Action | Key |
|--------|-----|
| Play / Pause | Space |
| Record | `*` |
| Arm track | R |
| Record all armed | Shift+R |
| Blade | B |
| Marker | M |
| Cycle takes | L |
| Zoom in / out | Z / X (also Ctrl+wheel) |
| Save / Save As | Ctrl+S / Shift+S |
| Open / New | Ctrl+O / Ctrl+N |
| Import / Export | Ctrl+I / Ctrl+E |
| Bypass / Monitor FX | Ctrl+B / Ctrl+T |

Remap in **Options → Preferences → Hotkeys**.

---

## FFmpeg

Place binaries in `third_party/ffmpeg/` or set `FFMPEG_PATH` / PATH.

Windows: `ffmpeg.exe`, `ffprobe.exe`  
Linux/macOS: `ffmpeg`, `ffprobe`

---

## Development

```bash
pytest          # 16 tests
```

Key modules:

| Path | Role |
|------|------|
| `app/ui/` | Logic-style shell, arrange view, transport |
| `app/dsp/pipeline.py` | Unify DSP + match EQ + noise print |
| `app/dsp/separation.py` | Voice isolation |
| `app/audio/` | Record, playback, media import |
| `app/legacy/unify/` | Original UnifyAudio core |
| `app/project/` | `.voxproj` database, autosave |

---

## Roadmap (ideas for next iterations)

Not all implemented yet — candidates for future work:

| Idea | Why |
|------|-----|
| **Waveform scrubbing in video panel** | Click video to set playhead |
| **Loop between markers** | ADR line rehearsal |
| **Punch-in record** | Overwrite a time range only |
| **Take comp lanes in UI** | Visual A/B/C lanes instead of L-cycle only |
| **Reference from Picture Lock** | One-click “match dialog on screen” |
| **ML voice separation** (e.g. Demucs) | Stronger isolation than HPSS heuristic |
| **Undo stack** | Blade / record mistakes |
| **In-app quick tour** | First-run tooltips |

If something feels unintuitive — feedback welcome; the hint bar and ADR video placeholder are first UX steps.

---

## Credits

- **Unify Audio** — `app/legacy/unify/` (used with permission)  
- **FFmpeg** — [ffmpeg.org](https://ffmpeg.org/) (GPL/LGPL, not bundled)  
- **PySide6**, **numpy**, **scipy**, **soundfile**, **pyloudnorm**
