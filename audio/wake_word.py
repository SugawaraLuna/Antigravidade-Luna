import time
import threading
import numpy as np
import sounddevice as sd
import speech_recognition as sr
from collections import deque

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_MS = 30
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_MS / 1000)
SPEECH_THRESHOLD = 280.0

import re
import difflib

WAKE_KEYWORDS = [
    # Formas com Luna
    "hey luna", "oi luna", "olá luna", "ola luna", "ok luna", "ei luna", "fala luna",
    "chama a luna", "chama luna", "luna", "lúna", "lunna", "lunas",
    # Formas com prefixo (Gemini como fallback)
    "hey geminai", "hey geminy", "hey gemini", "hey geminais",
    "oi geminai", "oi geminy", "oi gemini", "oi geminais",
    "ok geminai", "ok geminy", "ok gemini", "ok geminais",
    "olá geminai", "olá geminy", "olá gemini", "olá geminais",
    "ola geminai", "ola geminy", "ola gemini", "ola geminais",
    "ei geminai", "ei geminy", "ei gemini", "ei geminais",
    "fala geminai", "fala geminy", "fala gemini",
    # Formas diretas com sotaque (Geminy, Gêminai, Geminais, etc.)
    "geminai", "gêminai", "geminais", "gêminais",
    "geminy", "gêminy", "jeminy", "jeminai", "jeminais",
    "djeminai", "djemini", "djeminy", "djeminais",
    "gemenai", "gêmenai", "gemeni", "gemeny",
    "gemine", "gemini", "gêmini", "gemi", "gêmeos"
]

WAKE_ROOTS = [
    "luna", "lúna", "lunna",
    "gemini", "geminai", "geminy", "geminais", "gêminai", "gêminy",
    "jeminai", "jeminy", "djeminai", "djemini", "gemenai", "gemine"
]

class WakeWordDetector:
    def __init__(self, on_wake_callback):
        self.on_wake_callback = on_wake_callback
        self.recognizer = sr.Recognizer()
        self.is_active = True
        self.is_listening_wake = True
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def pause(self):
        self.is_listening_wake = False

    def resume(self):
        self.is_listening_wake = True

    def _listen_loop(self):
        pre_roll = deque(maxlen=10) # 300ms de pre-roll
        
        while self.is_active:
            if not self.is_listening_wake:
                time.sleep(0.2)
                continue

            try:
                with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16") as stream:
                    while self.is_active and self.is_listening_wake:
                        data, _ = stream.read(CHUNK_SIZE)
                        audio_block = np.frombuffer(data, dtype=np.int16)
                        block_rms = np.sqrt(np.mean(audio_block.astype(np.float32)**2))
                        
                        pre_roll.append(data)
                        
                        # Se detectou voz acima do limiar
                        if block_rms > SPEECH_THRESHOLD:
                            # Capturar fala (até 3.5 segundos ou 0.8s de silêncio)
                            frames = list(pre_roll)
                            silence_start = None
                            capture_start = time.time()
                            
                            while (time.time() - capture_start) < 3.5:
                                d, _ = stream.read(CHUNK_SIZE)
                                frames.append(d)
                                b = np.frombuffer(d, dtype=np.int16)
                                rms = np.sqrt(np.mean(b.astype(np.float32)**2))
                                
                                if rms < SPEECH_THRESHOLD:
                                    if silence_start is None:
                                        silence_start = time.time()
                                    elif time.time() - silence_start >= 0.7:
                                        break
                                else:
                                    silence_start = None
                                    
                            if not self.is_listening_wake:
                                break

                            # Processar transcrição rápida
                            pcm_bytes = b"".join(frames)
                            try:
                                audio_data = sr.AudioData(pcm_bytes, SAMPLE_RATE, 2)
                                text = self.recognizer.recognize_google(audio_data, language="pt-BR").lower().strip()
                                
                                wake_found = False
                                command_remainder = ""
                                
                                # 1. Busca por padrões exatos (ordenados pelo tamanho)
                                for kw in sorted(WAKE_KEYWORDS, key=len, reverse=True):
                                    if kw in text:
                                        wake_found = True
                                        idx = text.find(kw) + len(kw)
                                        command_remainder = text[idx:].strip(" ,.?!")
                                        break
                                        
                                # 2. Reconhecimento fonético tolerante a sotaque (Geminy, Gêminai, etc.)
                                if not wake_found:
                                    words = re.findall(r'\b\w+\b', text)
                                    for i, w in enumerate(words):
                                        for root in WAKE_ROOTS:
                                            if w == root or difflib.SequenceMatcher(None, w, root).ratio() >= 0.74:
                                                wake_found = True
                                                command_remainder = " ".join(words[i+1:]).strip(" ,.?!")
                                                break
                                        if wake_found:
                                            break
                                        
                                if wake_found and self.is_listening_wake:
                                    print(f"\n[⚡ Wake Word Detectada]: '{text}'")
                                    self.pause()
                                    self.on_wake_callback(command_remainder if command_remainder else None)
                                    break
                            except Exception:
                                pass
            except Exception as e:
                time.sleep(0.5)
