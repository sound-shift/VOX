# VoiceOverXeaven (VOX) — MVP

VoiceOverXeaven (VOX) is a desktop application for recording and processing voice-over sessions. The MVP included in this repository focuses on the core ADR workflow: timeline management, simulated recording with take lanes, preset-based processing, loudness normalisation, export, autosave rotation, and a dark UI derived from the original Unify project.

## Getting started

```bash
pip install -r requirements.txt
python -m app.main
```

### Launch flow
1. Choose **Podcast** or **Audiobook** mode and a voice preset on the start screen.
2. The main window provides a two-track timeline, transport and processing controls.
3. Arm a track and record takes; takes appear as lanes and can be comped with the blade tool.
4. Use the process panel to switch between *Monitor processed* and *Bypass* or to reset to the chosen preset.
5. Markers (`M`) are stored inside the project database and restored on load.

## Key features

- **Magic vs. Advanced**: `app/dsp/magic.py` implements preset-based processing (Magic) and parameterised chains (Advanced) with loudness normalisation to −23 LUFS and true-peak limiting to −1 dBTP.
- **Timeline and takes**: `app/timeline/model.py` maintains multitrack audio clips, markers, and take lanes that can be split with the blade tool.
- **Recording**: `app/audio/engine.py` simulates takes, applies preroll beeps (3× beep + GO) and stores temporary WAV files for each take.
- **Autosave**: `app/project/database.py` exposes `AutosaveManager`, creating a ring of at least five rolling autosaves.
- **Export**: `app/export/audio.py` exports WAV/FLAC directly and MP3 through FFmpeg (CBR 128–320 kbps). Missing FFmpeg binaries raise a clear error instructing to drop them into `third_party/ffmpeg/` or add the executable to `PATH`.
- **Hotkeys**: configurable via `app/settings/storage.py` with import/export using JSON files.

## Exporting audio

1. Select **File → Export…**.
2. Choose WAV, FLAC or MP3. Loudness is normalised to −23 LUFS with true-peak constraint ≤ −1 dBTP.
3. For MP3 export, ensure FFmpeg is available. Either add it to `PATH` or place the Windows binaries under `third_party/ffmpeg/` (`ffmpeg.exe`, `ffprobe.exe`).
4. Export summaries include LUFS and true-peak readings from the loudness report.

## Autosave configuration

Options → Autosave lets you define interval (seconds) and number of slots (default 5). Autosaves are stored alongside the project in `autosaves/VOX-Autosave-*.voxproj`, and the last good autosave is offered on restart.

## Hotkeys

| Action                | Default |
|-----------------------|---------|
| Play / Pause          | Space   |
| Record on selected    | *       |
| Arm track             | R       |
| Record armed tracks   | Shift+R |
| Blade                 | B       |
| Marker                | M       |
| Toggle take-lanes     | L       |
| Zoom in / out         | Z / X   |
| Save / Save As        | Ctrl+S / Shift+S |
| Open / New            | Ctrl+O / Ctrl+N |
| Export / Import       | Ctrl+E / Ctrl+I |
| Bypass processing     | Ctrl+B |
| Monitor processed     | Ctrl+T |

Hotkeys can be remapped in Options → Hotkeys. Use the import/export buttons to manage JSON profiles.

## FFmpeg location

Place FFmpeg binaries in `third_party/ffmpeg/` or set the `FFMPEG_PATH` environment variable. On Windows the application expects `ffmpeg.exe`. On other systems executable names without extension are accepted.

## Testing

```
pytest
```

## Licenses & credits

- **Unify project components** reused under permission: see `app/legacy/unify/`.
- **FFmpeg** — GPL/LGPL, binaries not bundled; download from [ffmpeg.org](https://ffmpeg.org/).
- **PyAV** placeholder modules included for future expansion.
- **PySide6** — see licence; DSP routines in this MVP are implemented in pure Python for portability.
