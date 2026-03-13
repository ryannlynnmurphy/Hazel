import pyaudio
import numpy as np
import threading
import time

CHUNK  = 1280
RATE   = 44100
DEVICE = 1
THRESHOLD = 0.5
MODEL_PATH = "/home/ryannlynnmurphy/.local/lib/python3.13/site-packages/openwakeword/resources/models/hey_jarvis_v0.1.onnx"

_model    = None
_running  = False
_callback = None
_thread   = None

def _load():
    global _model
    if _model is None:
        from openwakeword.model import Model
        print("[WakeWord] Loading model...")
        _model = Model(wakeword_model_paths=[MODEL_PATH])
        print("[WakeWord] Ready — say 'Hey Hazel'")

def _listen_loop():
    global _running
    pa = pyaudio.PyAudio()
    stream = pa.open(rate=RATE, channels=1, format=pyaudio.paInt16,
                     input=True, input_device_index=DEVICE, frames_per_buffer=CHUNK)
    while _running:
        try:
            audio = np.frombuffer(stream.read(CHUNK, exception_on_overflow=False), dtype=np.int16)
            preds = _model.predict(audio)
            for name, score in preds.items():
                if score > THRESHOLD:
                    print(f"[WakeWord] Detected! ({name}: {score:.2f})")
                    if _callback:
                        threading.Thread(target=_callback, daemon=True).start()
                    time.sleep(2)
        except Exception as e:
            print(f"[WakeWord] Error: {e}")
            time.sleep(0.1)
    stream.stop_stream()
    stream.close()
    pa.terminate()

def start(callback):
    global _running, _callback, _thread
    _load()
    _callback = callback
    _running  = True
    _thread   = threading.Thread(target=_listen_loop, daemon=True)
    _thread.start()

def stop():
    global _running
    _running = False
