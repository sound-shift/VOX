from __future__ import annotations

from pathlib import Path

from app.export.audio import AudioExporter, ExportError


def test_export_wav(tmp_path):
    exporter = AudioExporter()
    signal = [0.0 for _ in range(48000)]
    out = tmp_path / "test.wav"
    result = exporter.export(signal, 48000, out, "wav")
    assert out.exists()
    assert result.path == out


def test_export_mp3_without_ffmpeg(tmp_path):
    exporter = AudioExporter(ffmpeg_dir=tmp_path)
    signal = [0.0 for _ in range(48000)]
    out = tmp_path / "test.mp3"
    try:
        exporter.export(signal, 48000, out, "mp3")
    except ExportError as exc:
        assert "FFmpeg binary not found" in str(exc)
    else:
        raise AssertionError("Expected ExportError when ffmpeg is missing")
