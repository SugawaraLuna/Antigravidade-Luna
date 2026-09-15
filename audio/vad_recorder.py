import time
import numpy as np
import sounddevice as sd
from collections import deque
import keyboard

SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_MS = 25
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_MS / 1000)

_emergency_abort_requested = False

def set_vad_abort(flag: bool = True):
    global _emergency_abort_requested
    _emergency_abort_requested = flag

def record_with_smart_vad(
    max_wait_silence=4.5, 
    silence_timeout=1.3, 
    max_speech_duration=15.0, 
    abort_checker=None
):
    """
    Grava áudio do microfone garantindo que não corte nem o início nem o fim da fala:
    - Grava imediatamente com histórico pre-roll generoso (350ms).
    - Calibração dinâmica de ruído ambiente para evitar falso positivo por ventoinha/eco.
    - Monitora o silêncio: encerra após 1.3 segundos de silêncio contínuo após falar.
    - Protegido contra travamento infinito com timeout absoluto e suporte a tecla de emergência [ESC]/[F9].
    """
    global _emergency_abort_requested
    _emergency_abort_requested = False

    print("🎙️ Ouvindo... (fale agora)")
    
    frames = []
    pre_roll = deque(maxlen=14)  # 14 chunks de 25ms = 350ms de histórico antes da fala
    is_speaking = False
    silence_start = None
    speech_start_time = None
    start_time = time.time()

    # Calibração adaptativa inicial rápida (100ms)
    calib_rms_list = []
    default_threshold = 290.0
    speech_threshold = default_threshold
    
    try:
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16") as stream:
            # Descartar os primeiros 75ms para limpar qualquer resquício de som residual nos alto-falantes
            for _ in range(3):
                stream.read(CHUNK_SIZE)

            while True:
                # Verificação de interrupção de emergência (Hotkeys ESC, F9 ou flag global)
                if _emergency_abort_requested or (abort_checker and abort_checker()):
                    print("\n[🛑 Abort VAD]: Gravação interrompida por sinal de emergência.")
                    return None
                try:
                    if keyboard.is_pressed("esc") or keyboard.is_pressed("f9"):
                        print("\n[🛑 Abort VAD]: Gravação cancelada via tecla de emergência!")
                        return None
                except Exception:
                    pass

                data, _ = stream.read(CHUNK_SIZE)
                audio_block = np.frombuffer(data, dtype=np.int16)
                block_rms = float(np.sqrt(np.mean(audio_block.astype(np.float32)**2)))
                
                # Coleta primeiros 100ms para ajustar threshold dinâmico se houver ruído de fundo
                if len(calib_rms_list) < 4:
                    calib_rms_list.append(block_rms)
                    if len(calib_rms_list) == 4:
                        ambient_avg = float(np.mean(calib_rms_list))
                        # Se houver ruído de ventoinha ou GPU, sobe o limiar automaticamente
                        speech_threshold = max(default_threshold, ambient_avg * 2.2)

                elapsed = time.time() - start_time
                
                if not is_speaking:
                    pre_roll.append(data)
                    # Se detectou voz (volume acima do limiar adaptativo)
                    if block_rms > speech_threshold:
                        is_speaking = True
                        speech_start_time = time.time()
                        frames.extend(pre_roll)
                        frames.append(data)
                    elif elapsed > max_wait_silence:
                        # Nenhuma fala detectada após o tempo máximo de espera
                        return None
                else:
                    frames.append(data)
                    
                    # Se o volume caiu abaixo do limiar, inicia a contagem de silêncio
                    if block_rms < (speech_threshold * 0.85):
                        if silence_start is None:
                            silence_start = time.time()
                        elif time.time() - silence_start >= silence_timeout:
                            # Silêncio contínuo detectado após fala -> envia o áudio completo!
                            break
                    else:
                        # Gabriel continuou a falar -> zera o cronômetro de silêncio
                        silence_start = None
                        
                    # Proteção contra falas excessivamente longas ou travamento de ruído
                    if speech_start_time and (time.time() - speech_start_time > max_speech_duration):
                        break

    except Exception as e:
        print(f"[-] Erro na captura de áudio VAD: {e}")
        return None
                        
    if frames:
        return b"".join(frames)
    return None

