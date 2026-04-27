#!/usr/bin/env python3
"""
Scatter · Voice stack (voice.py)
Platform-aware: auto-detects Windows vs Linux and uses the right audio backend.
  - Windows: sounddevice + soundfile (laptop mic/speakers)
  - Linux:   arecord / aplay (ALSA, Pi cluster)

Patched for Scatter OS (ui/scatter.html):
  - Voice ID locked to Uc7anshoV8mdBhDnEZEX (Scatter)
  - start_listening() / stop_listening() hooks for WS mic control
  - Strips action tags and markdown before speaking
"""

import os
import io
import re
import platform
import subprocess
import tempfile
import logging
import threading

import whisper
import requests

log = logging.getLogger(__name__)

PLATFORM = platform.system()  # "Windows" or "Linux"

# ── PLATFORM-SPECIFIC IMPORTS ─────────────────────────────────────────────
if PLATFORM == "Windows":
    import sounddevice as sd
    import soundfile as sf
    import numpy as np

# ── CONFIG ─────────────────────────────────────────────────────────────────
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = "Uc7anshoV8mdBhDnEZEX"          # Scatter — DO NOT CHANGE
ELEVENLABS_MODEL    = "eleven_turbo_v2"
ELEVENLABS_FORMAT   = "mp3_44100_128"

WHISPER_MODEL_SIZE  = os.environ.get("JARVIS_WHISPER_MODEL", "base")
MIC_CARD            = os.environ.get("JARVIS_MIC_CARD", "")        # Linux only
SPEAKER_CARD        = os.environ.get("JARVIS_SPEAKER_CARD", "plughw:2,0")  # Linux only
RECORD_SECONDS      = int(os.environ.get("JARVIS_RECORD_SECONDS", "6"))
SAMPLE_RATE         = 16000  # Whisper expects 16kHz

# Noise / junk filter — phrases too short or meaningless to process
NOISE_PHRASES = {"you", "thank you", "thanks", "okay", "ok", "uh", "um", "hmm", ""}

# ── WHISPER MODEL (loaded once) ────────────────────────────────────────────
_whisper_model = None
_whisper_lock  = threading.Lock()

def get_whisper():
    global _whisper_model
    with _whisper_lock:
        if _whisper_model is None:
            log.info(f"Loading Whisper model: {WHISPER_MODEL_SIZE}")
            _whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
    return _whisper_model

# ── MIC DETECTION ──────────────────────────────────────────────────────────
def detect_mic() -> str:
    """Return mic identifier for the current platform."""
    if PLATFORM == "Windows":
        # sounddevice uses the system default — return a label, not an ALSA card
        try:
            device = sd.query_devices(kind='input')
            name = device.get('name', 'default')
            log.info(f"Detected Windows mic: {name}")
            return name
        except Exception as e:
            log.warning(f"Windows mic detection failed: {e}")
            return "default"

    # Linux / Pi — ALSA detection
    if MIC_CARD:
        return MIC_CARD
    try:
        result = subprocess.run(["arecord", "-l"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if "card" in line.lower():
                parts = line.split()
                for i, p in enumerate(parts):
                    if p.lower() == "card":
                        card_num = parts[i+1].strip(":")
                        dev_num = "0"
                        for j, pp in enumerate(parts):
                            if pp.lower() == "device":
                                dev_num = parts[j+1].strip(",")
                        return f"plughw:{card_num},{dev_num}"
    except Exception as e:
        log.warning(f"Mic detection failed: {e}")
    return "plughw:1,0"

# ── TEXT CLEANING ──────────────────────────────────────────────────────────
_ACTION_TAG = re.compile(r'\[[A-Z_]+:[^\]]*\]', re.IGNORECASE)
_MARKDOWN   = re.compile(r'[*_`#>~]')
_MULTI_SP   = re.compile(r' {2,}')

def clean_for_speech(text: str) -> str:
    """Strip action tags, markdown, and excess whitespace before TTS."""
    text = _ACTION_TAG.sub('', text)
    text = _MARKDOWN.sub('', text)
    text = _MULTI_SP.sub(' ', text)
    return text.strip()

# ── STT (WHISPER) ──────────────────────────────────────────────────────────
_listening = False

def start_listening():
    global _listening
    _listening = True
    log.info("Mic listening started")

def stop_listening():
    global _listening
    _listening = False
    log.info("Mic listening stopped")

def _record_windows() -> str | None:
    """Record from the laptop mic using sounddevice, return path to wav or None."""
    wav_path = tempfile.mktemp(suffix=".wav")
    try:
        log.info(f"Recording {RECORD_SECONDS}s from laptop mic...")
        audio = sd.rec(
            int(RECORD_SECONDS * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype='float32',
        )
        sd.wait()  # block until recording finishes
        sf.write(wav_path, audio, SAMPLE_RATE)
        return wav_path
    except Exception as e:
        log.error(f"Windows recording failed: {e}")
        try:
            os.remove(wav_path)
        except OSError:
            pass
        return None

def _record_linux() -> str | None:
    """Record from ALSA mic using arecord, return path to wav or None."""
    mic = detect_mic()
    wav_path = tempfile.mktemp(suffix=".wav")
    try:
        subprocess.run([
            "arecord",
            "-D", mic,
            "-f", "cd",
            "-t", "wav",
            "-d", str(RECORD_SECONDS),
            "-q",
            wav_path
        ], check=True, capture_output=True)
        return wav_path
    except subprocess.CalledProcessError as e:
        log.error(f"arecord failed: {e}")
        try:
            os.remove(wav_path)
        except OSError:
            pass
        return None

def transcribe_once() -> str | None:
    """
    Record a single utterance and return transcribed text, or None if noise/empty.
    Called by main.py's listen loop.
    """
    if PLATFORM == "Windows":
        wav = _record_windows()
    else:
        wav = _record_linux()

    if wav is None:
        return None

    try:
        model  = get_whisper()
        result = model.transcribe(wav, language="en", fp16=False)
        text   = result.get("text", "").strip()
    except Exception as e:
        log.error(f"Whisper transcribe error: {e}")
        return None
    finally:
        try:
            os.remove(wav)
        except OSError:
            pass

    if not text or len(text) < 3 or text.lower() in NOISE_PHRASES:
        return None

    log.info(f"STT: {text!r}")
    return text

# ── PLAYBACK HELPERS ──────────────────────────────────────────────────────
def _play_wav_file(wav_path: str):
    """Play a wav file using the right backend for this platform."""
    if PLATFORM == "Windows":
        data, samplerate = sf.read(wav_path, dtype='float32')
        sd.play(data, samplerate)
        sd.wait()
    else:
        subprocess.run(
            ["aplay", "-D", SPEAKER_CARD, "-q", wav_path],
            check=True, capture_output=True
        )

def _mp3_to_wav(mp3_path: str, wav_path: str):
    """Convert mp3 to wav. Uses ffmpeg if available, falls back to soundfile."""
    # Try ffmpeg first (works on both platforms if installed)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, "-ar", "44100", "-ac", "2", wav_path],
            check=True, capture_output=True
        )
        return
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Fallback: use soundfile (reads mp3 via libsndfile if supported,
    # otherwise use the io approach with the raw bytes)
    try:
        data, samplerate = sf.read(mp3_path)
        sf.write(wav_path, data, samplerate)
        return
    except Exception:
        pass

    # Last resort on Windows: use the mp3 directly with sounddevice
    # by reading raw bytes through io — this won't work, so log the error
    log.error("Cannot convert mp3 to wav — install ffmpeg for best results")

# ── TTS (ELEVENLABS + PIPER FALLBACK) ──────────────────────────────────────
def speak(text: str):
    """Speak text via ElevenLabs, falling back to Piper if unavailable."""
    clean = clean_for_speech(text)
    if not clean:
        return

    # Read key at call time (not import time) so .env loading in main.py works
    api_key = os.environ.get("ELEVENLABS_API_KEY", "") or ELEVENLABS_API_KEY
    if api_key:
        try:
            _speak_elevenlabs(clean, api_key)
            return
        except Exception as e:
            log.warning(f"ElevenLabs failed ({e}), falling back to Piper")

    _speak_piper(clean)


def _speak_elevenlabs(text: str, api_key: str = None):
    key = api_key or os.environ.get("ELEVENLABS_API_KEY", "") or ELEVENLABS_API_KEY
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream"
    headers = {
        "Accept":       "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key":   key,
    }
    payload = {
        "text":       text,
        "model_id":   ELEVENLABS_MODEL,
        "voice_settings": {
            "stability":        0.45,
            "similarity_boost": 0.82,
            "style":            0.20,
            "use_speaker_boost": True,
        },
    }
    response = requests.post(url, headers=headers, json=payload, stream=True, timeout=15)
    response.raise_for_status()
    mp3 = tempfile.mktemp(suffix=".mp3")
    wav = tempfile.mktemp(suffix=".wav")
    try:
        with open(mp3, "wb") as f:
            for chunk in response.iter_content(chunk_size=4096):
                if chunk:
                    f.write(chunk)

        if PLATFORM == "Windows":
            # On Windows, use the start command to play mp3 natively,
            # or convert to wav and play via sounddevice
            _mp3_to_wav(mp3, wav)
            if os.path.exists(wav) and os.path.getsize(wav) > 0:
                _play_wav_file(wav)
            else:
                # Direct mp3 playback via Windows Media Player (blocking)
                log.info("Playing mp3 via Windows native player")
                subprocess.run(
                    ["powershell", "-c",
                     f"Add-Type -AssemblyName presentationCore; "
                     f"$p = New-Object System.Windows.Media.MediaPlayer; "
                     f"$p.Open('{mp3.replace(chr(92), '/')}'); "
                     f"$p.Play(); Start-Sleep -Milliseconds 100; "
                     f"while($p.NaturalDuration.HasTimeSpan -eq $false){{Start-Sleep -Milliseconds 100}}; "
                     f"Start-Sleep -Seconds $p.NaturalDuration.TimeSpan.TotalSeconds; "
                     f"$p.Close()"],
                    capture_output=True, timeout=30
                )
        else:
            _mp3_to_wav(mp3, wav)
            if os.path.exists(wav):
                _play_wav_file(wav)
            else:
                log.error("TTS playback failed — no wav file produced")
    finally:
        for f in (mp3, wav):
            try:
                os.remove(f)
            except OSError:
                pass


def _speak_piper(text: str):
    """Local Piper TTS fallback."""
    voice_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voices")
    model     = os.path.join(voice_dir, "en_US-lessac-medium.onnx")

    if not os.path.exists(model):
        log.error("Piper model not found — cannot speak")
        return

    wav = tempfile.mktemp(suffix=".wav")
    try:
        subprocess.run(
            ["piper", "--model", model, "--output_file", wav],
            input=text.encode(), capture_output=True, check=True
        )
        _play_wav_file(wav)
    except Exception as e:
        log.error(f"Piper TTS error: {e}")
    finally:
        try:
            os.remove(wav)
        except OSError:
            pass

listen = transcribe_once
