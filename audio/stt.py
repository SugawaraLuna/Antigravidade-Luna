import os
import io
import wave
import speech_recognition as sr
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(override=True)

_sr_recognizer = sr.Recognizer()
_gemini_client = None

def get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        key = os.getenv("GEMINI_API_KEY")
        if key:
            _gemini_client = genai.Client(api_key=key)
    return _gemini_client

def pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1, sampwidth: int = 2) -> bytes:
    """Empacota áudio PCM cru em formato WAV padrão em memória."""
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return wav_io.getvalue()

def restore_punctuation_fallback(text: str) -> str:
    """Aplica regras heurísticas de pontuação em português caso o fallback da Web Speech seja utilizado."""
    if not text:
        return ""
    t = text.strip()
    if not t:
        return ""
    # Primeira letra maiúscula
    t = t[0].upper() + t[1:] if len(t) > 1 else t.upper()

    question_starters = [
        "como", "o que", "onde", "quando", "quem", "por que", "porque",
        "qual", "quais", "quanto", "quantos", "quanta", "quantas",
        "consegue", "você consegue", "voce consegue", "pode", "você pode", "voce pode",
        "tá me ouvindo", "ta me ouvindo", "está me ouvindo", "esta me ouvindo",
        "será que", "sera que", "seria", "dá pra", "da pra", "tem como",
        "você sabe", "voce sabe", "sabe me dizer", "me diz"
    ]
    lower = t.lower()
    is_q = any(lower.startswith(q) for q in question_starters)
    if not t.endswith(("?", "!", ".")):
        t += "?" if is_q else "."
    return t

def transcribe_audio_pcm(pcm_bytes: bytes) -> str:
    """
    Transcreve áudio gravado do microfone com máxima fidelidade e pontuação completa:
    - Inclui vírgulas, pontos e PONTOS DE INTERROGAÇÃO (?) em perguntas.
    - Reconhece termos técnicos e nomes próprios com precisão ('Google Apps Script', 'PowerShell', 'Luna').
    - Motor Primário: Gemini 3.5 Flash Lite (alta fidelidade e sem cortes).
    - Motor Secundário: Google Web Speech com heurística de pontuação.
    """
    if not pcm_bytes:
        return ""

    client = get_gemini_client()
    if client:
        try:
            wav_data = pcm_to_wav(pcm_bytes)
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=[
                    types.Part.from_bytes(data=wav_data, mime_type="audio/wav"),
                    "Transcreva fielmente a fala do usuário em português do Brasil. "
                    "Coloque pontuação perfeita: vírgulas nos momentos adequados e PONTO DE INTERROGAÇÃO (?) no final se for uma pergunta ou dúvida. "
                    "Se o usuário fizer uma pausa natural e continuar, una toda a fala sem cortar. "
                    "Retorne EXCLUSIVAMENTE o texto transcrito, sem aspas, sem markdown e sem qualquer comentário."
                ]
            )
            if response and response.text:
                result = response.text.strip().strip('"`\'')
                if result and result.lower() not in ["none", "vazio", "null"]:
                    return result
        except Exception as e:
            print(f"[-] Transcrição Gemini falhou ({e}). Alternando para fallback local...")

    # Fallback: speech_recognition
    try:
        audio_data = sr.AudioData(pcm_bytes, 16000, 2)
        raw_text = _sr_recognizer.recognize_google(audio_data, language="pt-BR")
        return restore_punctuation_fallback(raw_text)
    except Exception:
        return ""
