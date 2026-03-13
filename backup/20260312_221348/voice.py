# -*- coding: utf-8 -*-
"""
HZL AI Voice — Whisper STT + ElevenLabs TTS (Piper fallback)
"""
import subprocess
import os
import re
import time

# ── Configuration ─────────────────────────────────────────────────────────────
VOICE_MODEL        = os.path.expanduser("~/jarvis/voices/en_US-lessac-medium.onnx")
PIPER_BIN          = "/home/ryannlynnmurphy/.local/bin/piper"
SPEAKER_CARD       = os.environ.get("JARVIS_SPEAKER_CARD", "plughw:1,0")
MIC_CARD           = os.environ.get("JARVIS_MIC_CARD", "plughw:2,0")
RECORD_SECONDS     = int(os.environ.get("JARVIS_RECORD_SECONDS", "6"))
WHISPER_MODEL_SIZE = os.environ.get("JARVIS_WHISPER_MODEL", "base")

ELEVENLABS_API_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "Uc7anshoV8mdBhDnEZEX")
ELEVENLABS_MODEL    = "eleven_turbo_v2"

# Set HAZEL_TTS=piper in .env to force Piper for debugging
TTS_ENGINE = os.environ.get("HAZEL_TTS", "elevenlabs").lower()

# Timeouts
ELEVENLABS_TIMEOUT = 15   # seconds to wait for API response
MPG123_TIMEOUT     = 30   # seconds max for playback before giving up

_faster_whisper_model = None


# ── Whisper STT ───────────────────────────────────────────────────────────────

def _get_whisper():
    global _faster_whisper_model
    if _faster_whisper_model is None:
        print("[Voice] Loading faster-whisper tiny model...")
        from faster_whisper import WhisperModel
        _faster_whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        print("[Voice] Whisper ready.")
    return _faster_whisper_model


def listen(seconds=None):
    """Record audio and return transcribed text. Returns '' if nothing heard."""
    duration = seconds or RECORD_SECONDS
    result = subprocess.run(
        ["arecord", "-D", MIC_CARD, "-f", "cd", "-t", "wav", "-d", str(duration),
         "/tmp/jarvis_input.wav"],
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"[Voice] Recording error: {result.stderr.decode()}")
        return ""
    try:
        model = _get_whisper()
        segments, _ = model.transcribe("/tmp/jarvis_input.wav", language="en")
        text = " ".join(s.text for s in segments).strip()
        noise = ["you", "thank you", "thanks", ".", "..", "...", " "]
        if text.lower() in noise or len(text) < 3:
            return ""
        return text
    except Exception as e:
        print(f"[Voice] Transcription error: {e}")
        return ""


# ── Text Cleaning ─────────────────────────────────────────────────────────────

def _clean(text):
    """Strip markdown, action tags, and asterisks before speaking."""
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    return text.strip()


# ── Mic mute helpers ──────────────────────────────────────────────────────────

def _mic_mute():
    subprocess.run(["amixer", "-c", "2", "set", "Mic Capture Switch", "off"],
                   capture_output=True)

def _mic_unmute():
    subprocess.run(["amixer", "-c", "2", "set", "Mic Capture Switch", "on"],
                   capture_output=True)


# ── TTS Engines ───────────────────────────────────────────────────────────────

def _play_wav(path):
    subprocess.run(["amixer", "-c", "2", "set", "Speaker Playback Switch", "on"],
                   capture_output=True)
    subprocess.run(["aplay", "-q", "-D", SPEAKER_CARD, path], capture_output=True,
                   timeout=MPG123_TIMEOUT)
    time.sleep(0.3)


def _speak_elevenlabs(text):
    """Speak via ElevenLabs API. Returns True on success."""
    if not ELEVENLABS_API_KEY:
        print("[Voice] No ElevenLabs API key set.")
        return False
    try:
        import urllib.request
        import json

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        payload = json.dumps({
            "text": text,
            "model_id": ELEVENLABS_MODEL,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        })

        _mic_mute()

        with urllib.request.urlopen(req, timeout=ELEVENLABS_TIMEOUT) as resp:
            audio_data = resp.read()

        # Validate we actually got audio before writing
        if len(audio_data) < 1000:
            print(f"[Voice] ElevenLabs returned suspiciously small response ({len(audio_data)} bytes), falling back.")
            _mic_unmute()
            return False

        with open("/tmp/hazel_output.mp3", "wb") as f:
            f.write(audio_data)

        # Run mpg123 with a timeout so it can't hang forever
        result = subprocess.run(
            ["mpg123", "-a", SPEAKER_CARD, "/tmp/hazel_output.mp3"],
            timeout=MPG123_TIMEOUT,
            capture_output=True,
        )
        time.sleep(0.3)

        if result.returncode != 0:
            print(f"[Voice] mpg123 error: {result.stderr.decode()}")
            _mic_unmute()
            return False

        _mic_unmute()
        return True

    except subprocess.TimeoutExpired:
        print("[Voice] mpg123 timed out — killing and falling back.")
        subprocess.run(["pkill", "-f", "mpg123"], capture_output=True)
        _mic_unmute()
        return False
    except Exception as e:
        print(f"[Voice] ElevenLabs error: {e}")
        _mic_unmute()
        return False


def _speak_piper(text):
    """Speak via local Piper TTS. Returns True on success."""
    try:
        pr = subprocess.run(
            [PIPER_BIN, "--model", VOICE_MODEL, "--output_file", "/tmp/jarvis_output.wav"],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=20,
        )
        if pr.returncode == 0:
            _play_wav("/tmp/jarvis_output.wav")
            return True
        else:
            print(f"[Voice] Piper error: {pr.stderr.decode()}")
            return False
    except subprocess.TimeoutExpired:
        print("[Voice] Piper timed out.")
        return False
    except FileNotFoundError:
        print("[Voice] Piper not found.")
        return False
    except Exception as e:
        print(f"[Voice] Piper error: {e}")
        return False


# ── Main speak() ──────────────────────────────────────────────────────────────

def speak(text):
    """Speak text using configured TTS engine with fallback."""
    if not text or not text.strip():
        return
    clean = _clean(text)
    if not clean:
        return

    if TTS_ENGINE == "piper":
        print("[Voice] TTS: Piper (forced)")
        _speak_piper(clean)
    else:
        # ElevenLabs primary, Piper fallback
        if not _speak_elevenlabs(clean):
            print("[Voice] Falling back to Piper...")
            _speak_piper(clean)


# ── Sounds & Utils ────────────────────────────────────────────────────────────

def play_sound(sound_name):
    sounds = {
        "startup": "Hazel online.",
        "listening": "",
        "thinking": "",
        "error": "Sorry, I ran into an error.",
    }
    msg = sounds.get(sound_name, "")
    if msg:
        speak(msg)


def detect_mic():
    """Auto-detect the first available USB microphone."""
    result = subprocess.run(["arecord", "-l"], capture_output=True, text=True)
    for line in result.stdout.split("\n"):
        if "card" in line.lower() and "device" in line.lower():
            import re as _re
            match = _re.search(r'card (\d+).*device (\d+)', line, re.IGNORECASE)
            if match:
                return f"plughw:{match.group(1)},{match.group(2)}"
    return None
