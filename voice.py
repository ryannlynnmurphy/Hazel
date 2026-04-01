#!/usr/bin/env python3
"""
HZL AI · Voice Stack  (voice.py)
Patched for hazel-v5:
  - Voice ID locked to Uc7anshoV8mdBhDnEZEX (Hazel)
  - start_listening() / stop_listening() hooks for WS mic control
  - Strips action tags and markdown before speaking
"""

import os
import re
import subprocess
import tempfile
import logging
import threading

import whisper
import requests

log = logging.getLogger(__name__)

# ── CONFIG ─────────────────────────────────────────────────────────────────
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = "Uc7anshoV8mdBhDnEZEX"          # Hazel — DO NOT CHANGE
ELEVENLABS_MODEL    = "eleven_turbo_v2"
ELEVENLABS_FORMAT   = "mp3_44100_128"

WHISPER_MODEL_SIZE  = os.environ.get("JARVIS_WHISPER_MODEL", "base")
MIC_CARD            = os.environ.get("JARVIS_MIC_CARD", "")        # auto-detect if empty
SPEAKER_CARD        = os.environ.get("JARVIS_SPEAKER_CARD", "plughw:2,0")
RECORD_SECONDS      = int(os.environ.get("JARVIS_RECORD_SECONDS", "6"))

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
    """Return the first USB mic card string, e.g. 'plughw:1,0'."""
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
                        # grab device
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

def transcribe_once() -> str | None:
    """
    Record a single utterance and return transcribed text, or None if noise/empty.
    Called by main.py's listen loop.
    """
    mic = detect_mic()
    wav = tempfile.mktemp(suffix=".wav")

    try:
        subprocess.run([
            "arecord",
            "-D", mic,
            "-f", "cd",
            "-t", "wav",
            "-d", str(RECORD_SECONDS),
            "-q",
            wav
        ], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        log.error(f"arecord failed: {e}")
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

# ── TTS (ELEVENLABS + PIPER FALLBACK) ──────────────────────────────────────
def speak(text: str):
    """Speak text via ElevenLabs, falling back to Piper if unavailable."""
    clean = clean_for_speech(text)
    if not clean:
        return

    if ELEVENLABS_API_KEY:
        try:
            _speak_elevenlabs(clean)
            return
        except Exception as e:
            log.warning(f"ElevenLabs failed ({e}), falling back to Piper")

    _speak_piper(clean)


def _speak_elevenlabs(text: str):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream"
    headers = {
        "Accept":       "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key":   ELEVENLABS_API_KEY,
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
    with open(mp3, "wb") as f:
        for chunk in response.iter_content(chunk_size=4096):
            if chunk:
                f.write(chunk)
    # Convert MP3 to WAV and play via aplay (Blue Yeti compatible)
    subprocess.run(["ffmpeg", "-y", "-i", mp3, "-ar", "44100", "-ac", "2", wav],
                   check=True, capture_output=True)
    subprocess.run(["aplay", "-D", SPEAKER_CARD, "-q", wav],
                   check=True, capture_output=True)
    os.remove(mp3)
    os.remove(wav)


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
        subprocess.run(
            ["aplay", "-D", SPEAKER_CARD, "-q", wav],
            check=True, capture_output=True
        )
    except Exception as e:
        log.error(f"Piper TTS error: {e}")
    finally:
        try:
            os.remove(wav)
        except OSError:
            pass
listen = transcribe_once
