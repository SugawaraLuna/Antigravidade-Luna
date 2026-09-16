import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import json
import asyncio
import ctypes
try:
    import winsound
except ImportError:
    winsound = None
import keyboard
import threading
import aiohttp
import edge_tts
import re
import speech_recognition as sr
from dotenv import load_dotenv

from ui.hud import LunaHUD
from audio.vad_recorder import record_with_smart_vad, set_vad_abort
from audio.wake_word import WakeWordDetector
from tools.system_control import duck_audio, unduck_audio
from audio.live_engine import LunaLiveWebSocketEngine
from core.engine import build_system_prompt, TOOLS_SCHEMA, AntigravityExecutionEngine
from tools.screen_tools import capture_screen_pil
from core.task_manager import task_manager
from tools.agy_tools import delegate_to_antigravity
from audio.stt import transcribe_audio_pcm

load_dotenv(override=True)

# Suporte automático para Núcleo Local ou Remoto (Railway / Nuvem)
CORE_WS_URL = os.getenv("ANTIGRAVITY_CORE_URL")
if not CORE_WS_URL:
    CORE_HOST = os.getenv("ANTIGRAVITY_CORE_HOST", "127.0.0.1")
    CORE_PORT = os.getenv("PORT", os.getenv("ANTIGRAVITY_CORE_PORT", "8765"))
    CORE_WS_URL = f"ws://{CORE_HOST}:{CORE_PORT}/ws/luna"
else:
    # Formatação automática de protocolo caso o usuário use https://, http:// ou apenas o domínio
    CORE_WS_URL = CORE_WS_URL.strip()
    if not (CORE_WS_URL.startswith("ws://") or CORE_WS_URL.startswith("wss://") or CORE_WS_URL.startswith("http://") or CORE_WS_URL.startswith("https://")):
        CORE_WS_URL = "wss://" + CORE_WS_URL
    if CORE_WS_URL.startswith("https://"):
        CORE_WS_URL = "wss://" + CORE_WS_URL[8:]
    elif CORE_WS_URL.startswith("http://"):
        CORE_WS_URL = "ws://" + CORE_WS_URL[7:]
    if not CORE_WS_URL.endswith("/ws/luna") and not CORE_WS_URL.endswith("/ws/luna/"):
        CORE_WS_URL = CORE_WS_URL.rstrip("/") + "/ws/luna"

VOICE_NAME = "pt-BR-FranciscaNeural"

# Estados de execução do cliente leve
is_speaking_active = False
emergency_reset_active = False
recognizer = sr.Recognizer()
hud = LunaHUD()
wake_detector = None

# Gerenciador de conexão WebSocket com o núcleo Antigravidade
class AntigravityClient:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.session: aiohttp.ClientSession = None
        self.ws: aiohttp.ClientWebSocketResponse = None
        self.loop = None
        self.thread = None
        self.response_future: asyncio.Future = None
        self.is_connected = False

    def start(self):
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._maintain_connection())

    async def _maintain_connection(self):
        while True:
            try:
                self.session = aiohttp.ClientSession()
                async with self.session.ws_connect(self.ws_url) as ws:
                    self.ws = ws
                    self.is_connected = True
                    print(f"[✓] LUNA conectada ao Núcleo Antigravidade em {self.ws_url}")
                    
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            msg_type = data.get("type")

                            if msg_type == "status":
                                state = data.get("state", "thinking")
                                text = data.get("text", "Pensando...")
                                hud.set_state(state, text)

                            elif msg_type == "response":
                                if self.response_future and not self.response_future.done():
                                    self.response_future.set_result(data)

                            elif msg_type == "cancelled":
                                hud.set_state("idle")
                                if self.response_future and not self.response_future.done():
                                    self.response_future.set_result({"cancelled": True})

                        elif msg.type in [aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR]:
                            break
            except Exception:
                self.is_connected = False
                await asyncio.sleep(2.0)
            finally:
                self.is_connected = False
                if self.session and not self.session.closed:
                    await self.session.close()

    def send_query_sync(self, user_text: str, timeout: float = 35.0) -> dict:
        """Envia texto de comando para o Núcleo Antigravidade e aguarda a resposta."""
        if not self.is_connected or not self.loop or not self.ws:
            return {"spoken_text": "Gabriel, não consegui conexão com o núcleo antigravidade. Verifique se o servidor está ativo."}

        future = asyncio.run_coroutine_threadsafe(self._async_query(user_text, timeout), self.loop)
        try:
            return future.result(timeout=timeout)
        except Exception as e:
            print(f"[-] Timeout ou falha na resposta do núcleo: {e}")
            return {"spoken_text": "Gabriel, houve demora no retorno do núcleo antigravidade."}

    async def _async_query(self, user_text: str, timeout: float) -> dict:
        self.response_future = self.loop.create_future()
        await self.ws.send_json({"type": "query", "text": user_text})
        try:
            return await asyncio.wait_for(self.response_future, timeout=timeout)
        except asyncio.TimeoutError:
            return {"spoken_text": "Gabriel, a requisição ao núcleo excedeu o tempo limite."}

    def cancel_active_query(self):
        """Envia sinal de cancelamento imediato para o núcleo Antigravidade."""
        if self.is_connected and self.loop and self.ws:
            asyncio.run_coroutine_threadsafe(
                self.ws.send_json({"type": "cancel"}),
                self.loop
            )

core_client = AntigravityClient(CORE_WS_URL)
core_engine = AntigravityExecutionEngine()

# Instância do Gemini Multimodal Live (Voz Neural Nativa Aoede)
live_engine = None
gemini_key = os.getenv("GEMINI_API_KEY")
if gemini_key:
    try:
        live_engine = LunaLiveWebSocketEngine(api_key=gemini_key, voice_name="Aoede")
    except Exception as e:
        print(f"[-] Aviso ao inicializar Live Engine: {e}")

def _get_winmm():
    if sys.platform == "win32" and hasattr(ctypes, "windll"):
        try:
            return ctypes.windll.winmm
        except Exception:
            pass
    return None

def stop_speaking():
    global is_speaking_active
    is_speaking_active = False
    if live_engine:
        live_engine.interrupt()
    winmm = _get_winmm()
    if winmm:
        try:
            winmm.mciSendStringW("stop luna_speech", None, 0, None)
            winmm.mciSendStringW("close luna_speech", None, 0, None)
        except Exception:
            pass

def trigger_emergency_reset():
    """
    Reset Imediato e de Emergência:
    - Cancela fala local
    - Cancela gravação do microfone
    - Notifica o Núcleo Antigravidade para abortar a tarefa ativa
    - Restaura volume e HUD para Standby
    """
    global emergency_reset_active
    emergency_reset_active = True
    set_vad_abort(True)
    core_client.cancel_active_query()

    print("\n" + "=" * 68)
    print("🚨 [RESET DE EMERGÊNCIA]: Abortando tudo e retornando ao Standby!")
    print("=" * 68 + "\n")
    stop_speaking()
    unduck_audio()
    hud.set_state("idle")
    play_beep_cancel()
    if wake_detector:
        wake_detector.resume()

def play_mp3(file_path: str):
    global is_speaking_active
    full_path = os.path.abspath(file_path)
    winmm = _get_winmm()
    if not winmm:
        return
    winmm.mciSendStringW("close luna_speech", None, 0, None)
    winmm.mciSendStringW(f'open "{full_path}" type mpegvideo alias luna_speech', None, 0, None)
    winmm.mciSendStringW("play luna_speech", None, 0, None)
    
    is_speaking_active = True
    buff = ctypes.create_unicode_buffer(64)
    while is_speaking_active:
        winmm.mciSendStringW("status luna_speech mode", buff, 64, None)
        if buff.value != "playing":
            break
        # Barge-in / Tecla de pânico
        try:
            if keyboard.is_pressed("F8") or keyboard.is_pressed("esc") or keyboard.is_pressed("f9"):
                print("\n[🛑 Barge-in]: Fala interrompida pelo usuário via atalho!")
                break
        except Exception:
            pass
        time.sleep(0.04)
        
    winmm.mciSendStringW("stop luna_speech", None, 0, None)
    winmm.mciSendStringW("close luna_speech", None, 0, None)
    is_speaking_active = False

def speak(text: str):
    if not text or not text.strip():
        return
    clean_text = text.strip()
    print(f"\n[LUNA]: {clean_text}\n")
    hud.set_state("speaking", clean_text[:45] + "...")
    try:
        mp3_path = os.path.abspath("temp_response.mp3")
        com = edge_tts.Communicate(clean_text, voice=VOICE_NAME, rate="+6%")
        asyncio.run(com.save(mp3_path))
        play_mp3(mp3_path)
    except Exception as e:
        print(f"[Erro de TTS]: {e}")

def play_beep_start():
    if winsound:
        try:
            winsound.Beep(1000, 80)
            winsound.Beep(1400, 90)
        except Exception:
            pass

def play_beep_end():
    if winsound:
        try:
            winsound.Beep(1200, 70)
            winsound.Beep(800, 80)
        except Exception:
            pass

def play_beep_cancel():
    if winsound:
        try:
            winsound.Beep(600, 120)
        except Exception:
            pass

def process_user_turn(user_text: str):
    """Executa o turno com voz fluida Multimodal Live (Aoede) ou fallback no Antigravidade."""
    global emergency_reset_active
    if not user_text or emergency_reset_active:
        return

    # 1. Canal Primário: Gemini Multimodal Live (Voz Neural Aoede 24kHz em tempo real)
    if live_engine and not emergency_reset_active:
        hud.set_state("thinking", "LUNA formulando...")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            success = loop.run_until_complete(
                live_engine.run_turn(
                    system_instruction=build_system_prompt(),
                    tools_schema=TOOLS_SCHEMA,
                    user_text=user_text,
                    execute_tool_fn=lambda name, args: core_engine.execute_tool(name, args)[0],
                    get_screenshot_pil_fn=capture_screen_pil,
                    hud=hud
                )
            )
            loop.close()
            if success and not emergency_reset_active:
                hud.set_state("idle")
                return
        except Exception as live_err:
            print(f"[-] Falha no Live Audio: {live_err}. Alternando para canal secundário...")

    # 2. Canal Secundário / Fallback: Núcleo Antigravidade + TTS
    hud.set_state("thinking", "Trabalhando nisso...")
    print(f"\n💭 [LUNA]: Trabalhando nisso...")

    resp = core_client.send_query_sync(user_text)
    
    if emergency_reset_active or resp.get("cancelled"):
        hud.set_state("idle")
        return

    spoken_text = resp.get("spoken_text", "")
    if spoken_text:
        speak(spoken_text)

    hud.set_state("idle")

def is_closure_intent(text: str) -> bool:
    """
    Detecta se a fala do Gabriel é um encerramento natural do assunto,
    agradecimento ou confirmação de que não precisa de mais nada.
    """
    if not text:
        return False
    clean = text.lower().strip(" .,!?¡¿;:")
    exact_closures = {
        "obrigado", "muito obrigado", "muitíssimo obrigado", "brigado", "brigadão",
        "valeu", "valeu luna", "obrigado luna", "muito obrigado luna",
        "não obrigado", "não, obrigado", "nao obrigado", "nao, obrigado",
        "não preciso de nada", "nao preciso de nada", "não preciso de mais nada", "nao preciso de mais nada",
        "não preciso de nada não obrigado", "nao preciso de nada nao obrigado",
        "não quero nada", "nao quero nada", "não quero mais nada", "nao quero mais nada",
        "não precisa", "nao precisa", "não precisa não", "nao precisa nao", "não precisa mais", "nao precisa mais",
        "nada não", "nada nao", "nada mais", "não, nada mais", "nao, nada mais",
        "era só isso", "era so isso", "só isso", "so isso", "só isso mesmo", "so isso mesmo",
        "por hoje é só", "por hoje so", "por enquanto não", "por enquanto nao",
        "tudo certo", "fechou", "tá tudo bem", "ta tudo bem", "não, tá tudo bem", "nao, ta tudo bem",
        "tá tudo certo", "ta tudo certo", "não, tá tudo certo", "nao, ta tudo certo",
        "tá ótimo", "ta otimo", "tá ótimo assim", "ta otimo assim", "beleza, valeu", "beleza valeu",
        "pode deixar", "pode deixar, obrigado", "pode deixar obrigado",
        "pode descansar", "tchau", "até mais", "ate mais", "até logo", "ate logo",
        "cancelar", "cancela", "deixa pra lá", "deixa pra la", "esquece", "pode parar"
    }
    if clean in exact_closures:
        return True

    closure_patterns = [
        r"^n[aã]o,?\s*(muito\s*)?obrigad[ao]",
        r"^n[aã]o,?\s*valeu",
        r"^n[aã]o,?\s*era\s*s[oó]\s*isso",
        r"^n[aã]o,?\s*por\s*enquanto\s*n[aã]o",
        r"^n[aã]o,?\s*t[aá]\s*tudo\s*(certo|bem|tranquilo|ótimo|otimo)",
        r"^t[aá]\s*tudo\s*(certo|bem|tranquilo|ótimo|otimo)",
        r"^t[aá]\s*(ótimo|otimo|bom|perfeito)\s*assim",
        r"^pode\s*deixar,?\s*(obrigad[ao]|valeu)?",
        r"^n[aã]o\s*(preciso|quero)\s*(de\s*)?(mais\s*)?nada",
        r"^n[aã]o\s*precisa\s*(n[aã]o|mais)",
        r"n[aã]o\s*preciso\s*de\s*nada.*obrigad[ao]",
        r"obrigad[ao]\s*$",
        r"^muito\s*obrigad[ao]\s*(luna)?",
        r"^obrigad[ao]\s*(luna)?",
        r"^valeu\s*(luna)?",
        r"^tchau\s*(luna)?",
        r"^at[eé]\s*(mais|logo)",
        r"^deixa\s*pra\s*l[aá]",
        r"^pode\s*descansar"
    ]
    for pat in closure_patterns:
        if re.search(pat, clean):
            return True

    return False

def is_cancel_task_intent(text: str) -> bool:
    if not text:
        return False
    clean = text.lower().strip(" .,!?")
    cancel_words = [
        "cancela", "cancelar", "deixa pra lá", "deixa pra la",
        "esquece", "pode parar", "cancela a tarefa", "esquece isso", "para com isso"
    ]
    return any(w in clean for w in cancel_words)

def is_confirmation_intent(text: str) -> bool:
    """Detecta intenção afirmativa/autorização do Gabriel (Opção 4: aceita tudo relacionado)."""
    if not text:
        return False
    clean = text.lower().strip(" .,!?")
    confirmations = {
        "sim", "sim pode", "pode", "pode fazer", "pode sim", "pode executar",
        "confirmo", "confirmar", "confirmado", "autorizo", "autorizado", "autorizar",
        "claro", "com certeza", "aceito", "aceita", "manda ver", "manda bala",
        "vai fundo", "prosseguir", "continuar", "continua", "pode continuar",
        "opção 4", "opcao 4", "opcao quatro", "opção quatro", "4", "quatro",
        "aceita tudo", "aceitar tudo", "aceita tudo relacionado", "aceito tudo"
    }
    if clean in confirmations:
        return True
    confirm_patterns = [
        r"^(sim|pode|claro|confirmo|autorizo)",
        r"^pode\s+(fazer|executar|continuar|ir|mandar)",
        r"^(opção|opcao)\s*(4|quatro)",
        r"^aceit[ao]\s+tudo"
    ]
    for pat in confirm_patterns:
        if re.search(pat, clean):
            return True
    return False

def handle_confirmation_turn(user_text: str) -> bool:
    """
    Se houver uma permissão pendente no TaskManager e o usuário expressar confirmação
    ('Sim', 'pode fazer', 'confirmo', 'autorizo', 'opção 4', etc.), executa a ação no antigravidade
    com Opção 4 (auto_approve=True) e sintetiza a resposta da LUNA.
    Retorna True se processou confirmação, False caso contrário.
    """
    if not task_manager.has_pending_permission() or not is_confirmation_intent(user_text):
        return False

    pending = task_manager.get_pending_permission()
    action = pending.get("action", "ação solicitada")
    task_desc = pending.get("task_description", "")
    target_path = pending.get("target_path")

    print(f"\n🧠 [Raciocínio LUNA]: Opção 4 selecionada: autorizando e executando '{action}' no antigravidade...")
    hud.set_state("thinking", "Opção 4: Autorizando execução...")

    # Executa a ação no antigravidade com permissão total aprovada (Opção 4)
    res = delegate_to_antigravity(task_desc, target_path=target_path, auto_approve=True)
    task_manager.complete_active_task(result_summary=res[:400])
    task_manager.clear_pending_permission()

    approval_prompt = (
        f"O Gabriel disse '{user_text}', confirmando a execução da ação (Opção 4: autorização total aceita). "
        f"O antigravidade executou '{action}' com sucesso. Resumo do resultado: {res[:300]}. "
        f"Responda ao Gabriel de forma alegre, fofa e carinhosa confirmando que a ação foi autorizada e concluída com sucesso, explicando o resultado em 1 ou 2 frases curtas."
    )
    process_user_turn(approval_prompt)
    return True

def run_continuous_conversation(initial_text: str = None):
    """
    Modo conversacional contínuo:
    Processa primeiro turno e continua ouvindo por até 5s sem exigir 'Luna'.
    Encerra imediatamente para Standby se for detectado fim de assunto.
    """
    global wake_detector, emergency_reset_active

    if emergency_reset_active:
        emergency_reset_active = False
        unduck_audio()
        hud.set_state("idle")
        if wake_detector:
            wake_detector.resume()
        return

    if wake_detector:
        wake_detector.pause()
    duck_audio()

    if initial_text:
        process_user_turn(initial_text)

    while True:
        if emergency_reset_active:
            emergency_reset_active = False
            unduck_audio()
            hud.set_state("idle")
            break

        time.sleep(0.35)

        hud.set_state("listening", "Ouvindo você... (fale ou espere 5s)")
        print("\n🎙️ [Modo Conversa Ativo]: Ouvindo continuação (silêncio de 5s para encerrar)...")

        pcm = record_with_smart_vad(
            max_wait_silence=5.0,
            silence_timeout=2.2,
            max_speech_duration=45.0,
            abort_checker=lambda: emergency_reset_active
        )

        if emergency_reset_active:
            emergency_reset_active = False
            unduck_audio()
            hud.set_state("idle")
            break

        if not pcm:
            print("\n[-] 5 segundos de silêncio detectados. Voltando para Standby...")
            play_beep_cancel()
            unduck_audio()
            hud.set_state("idle")
            break

        play_beep_end()
        hud.set_state("thinking", "Transcrevendo...")
        text = transcribe_audio_pcm(pcm)

        if text:
            print(f"[Gabriel]: \"{text}\"")
            hud.set_state("thinking", "Pensando...")

            # 1. Cancelar tarefa ativa / Deixar pra lá
            if is_cancel_task_intent(text):
                task_manager.cancel_active_task()
                closing_prompt = f"O Gabriel disse '{text}'. Cancelei a tarefa ativa. Responda de forma fofa e acolhedora em 1 frase curta confirmando que deixou pra lá e que está à disposição."
                process_user_turn(closing_prompt)
                print("\n[-] Tarefa cancelada. Retornando diretamente para Standby...")
                play_beep_cancel()
                unduck_audio()
                hud.set_state("idle")
                break

            # 2. Confirmação de Permissão Pendente (Opção 4: Aceita tudo relacionado)
            if handle_confirmation_turn(text):
                continue

            # 3. Encerramento natural / Agradecimento / Término de assunto
            if is_closure_intent(text):
                closing_prompt = f"O Gabriel disse '{text}'. Trata-se de um encerramento natural de assunto ou agradecimento. Responda de forma fofa, espontânea e amigável em 1 frase curta concluindo a conversa (ex: agradecendo ou dizendo que está sempre por aqui se ele precisar)."
                process_user_turn(closing_prompt)
                print("\n[-] Assunto concluído. Retornando diretamente para Standby...")
                unduck_audio()
                hud.set_state("idle")
                break

            process_user_turn(text)
        else:
            hud.set_state("idle")

    unduck_audio()
    hud.set_state("idle")
    if wake_detector:
        wake_detector.resume()

def handle_wake_word(command_remainder: str = None):
    """Disparado pelo detector de Wake Word 'Luna'."""
    global emergency_reset_active
    duck_audio()
    play_beep_start()

    if command_remainder:
        print(f"[Gabriel (Voz Wake)]: \"{command_remainder}\"")
        if is_cancel_task_intent(command_remainder):
            task_manager.cancel_active_task()
            process_user_turn("O Gabriel pediu para cancelar a tarefa ativa ou deixar pra lá. Confirme com carinho em 1 frase curta.")
            unduck_audio()
            hud.set_state("idle")
            if wake_detector:
                wake_detector.resume()
            return
        if handle_confirmation_turn(command_remainder):
            unduck_audio()
            hud.set_state("idle")
            if wake_detector:
                wake_detector.resume()
            return
        if is_closure_intent(command_remainder):
            closing_prompt = f"O Gabriel disse: '{command_remainder}'. Responda de forma fofa e amigável em 1 frase curta."
            process_user_turn(closing_prompt)
            unduck_audio()
            hud.set_state("idle")
            if wake_detector:
                wake_detector.resume()
            return

        hud.set_state("thinking", "Pensando...")
        run_continuous_conversation(initial_text=command_remainder)
    else:
        hud.set_state("listening", "Fale agora...")
        pcm = record_with_smart_vad(
            max_wait_silence=5.0,
            silence_timeout=2.2,
            max_speech_duration=45.0,
            abort_checker=lambda: emergency_reset_active
        )
        if emergency_reset_active:
            emergency_reset_active = False
            unduck_audio()
            hud.set_state("idle")
            if wake_detector:
                wake_detector.resume()
            return

        if pcm:
            play_beep_end()
            hud.set_state("thinking", "Transcrevendo...")
            try:
                text = transcribe_audio_pcm(pcm)
                if text:
                    print(f"[Gabriel (Voz)]: \"{text}\"")
                    if is_cancel_task_intent(text):
                        task_manager.cancel_active_task()
                        process_user_turn("O Gabriel pediu para cancelar a tarefa ativa ou deixar pra lá. Confirme com carinho em 1 frase curta.")
                        unduck_audio()
                        hud.set_state("idle")
                        if wake_detector:
                            wake_detector.resume()
                        return
                    if handle_confirmation_turn(text):
                        unduck_audio()
                        hud.set_state("idle")
                        if wake_detector:
                            wake_detector.resume()
                        return
                    if is_closure_intent(text):
                        closing_prompt = f"O Gabriel disse: '{text}'. Responda de forma fofa e amigável em 1 frase curta."
                        process_user_turn(closing_prompt)
                        unduck_audio()
                        hud.set_state("idle")
                        if wake_detector:
                            wake_detector.resume()
                        return

                    hud.set_state("thinking", "Pensando...")
                    run_continuous_conversation(initial_text=text)
                else:
                    play_beep_cancel()
                    unduck_audio()
                    hud.set_state("idle")
                    if wake_detector:
                        wake_detector.resume()
            except Exception as e:
                print(f"[-] Erro ao processar transcrição: {e}")
                play_beep_cancel()
                unduck_audio()
                hud.set_state("idle")
                if wake_detector:
                    wake_detector.resume()
        else:
            play_beep_cancel()
            unduck_audio()
            hud.set_state("idle")
            if wake_detector:
                wake_detector.resume()

f8_lock = threading.Lock()

def handle_manual_f8():
    """Atalho F8 disparado globalmente para captura manual de voz."""
    global wake_detector, emergency_reset_active
    if not f8_lock.acquire(blocking=False):
        return

    try:
        emergency_reset_active = False
        stop_speaking()
        if wake_detector:
            wake_detector.pause()
        duck_audio()
        play_beep_start()
        hud.set_state("listening", "Gravando [F8]...")
        print("\n🎙️ [Atalho F8]: Ouvindo você agora (fale com a Luna)...")

        pcm = record_with_smart_vad(
            max_wait_silence=5.0,
            silence_timeout=2.2,
            max_speech_duration=45.0,
            abort_checker=lambda: emergency_reset_active
        )

        if emergency_reset_active:
            emergency_reset_active = False
            unduck_audio()
            hud.set_state("idle")
            if wake_detector:
                wake_detector.resume()
            return

        if not pcm:
            print("[-] Nenhum áudio detectado no microfone. Cancelando.\n")
            play_beep_cancel()
            unduck_audio()
            hud.set_state("idle")
            if wake_detector:
                wake_detector.resume()
            return

        play_beep_end()
        hud.set_state("thinking", "Transcrevendo...")

        try:
            text = transcribe_audio_pcm(pcm)
        except Exception as e:
            print(f"[-] Erro na transcrição F8: {e}")
            text = None

        if text:
            print(f"[Gabriel (Voz)]: \"{text}\"")
            if is_cancel_task_intent(text):
                task_manager.cancel_active_task()
                process_user_turn("O Gabriel pediu para cancelar a tarefa ativa ou deixar pra lá. Confirme com carinho em 1 frase curta.")
                unduck_audio()
                hud.set_state("idle")
                if wake_detector:
                    wake_detector.resume()
                return

            if handle_confirmation_turn(text):
                unduck_audio()
                hud.set_state("idle")
                if wake_detector:
                    wake_detector.resume()
                return

            if is_closure_intent(text):
                closing_prompt = f"O Gabriel disse: '{text}'. Responda de forma fofa e amigável em 1 frase curta."
                process_user_turn(closing_prompt)
                unduck_audio()
                hud.set_state("idle")
                if wake_detector:
                    wake_detector.resume()
                return

            hud.set_state("thinking", "Pensando...")
            run_continuous_conversation(initial_text=text)
        else:
            play_beep_cancel()
            unduck_audio()
            hud.set_state("idle")
            if wake_detector:
                wake_detector.resume()
    finally:
        f8_lock.release()

def main():
    global wake_detector, emergency_reset_active

    print("=" * 68)
    print("   🌙 LUNA AI (Interface de Voz Multimodal Live + Núcleo Central)")
    print("=" * 68)
    print("-> Canal de Voz Primário: Gemini Multimodal Live (Streaming 24kHz • Voz Aoede)")
    print(f"-> Núcleo Central Conectado: {CORE_WS_URL}")
    print("-> Interface Visual: HUD Dinâmico Flutuante (Standby / Ativo)")
    print("-> Ativação por Voz: Diga 'Luna ...' a qualquer momento!")
    print("-> Atalho Manual: Pressione [F8] para falar diretamente.")
    print("-> Modo Digitação: Digite comandos e perguntas no terminal abaixo.")
    print("-> Tecla de Pânico / Abortar: Pressione [ESC] ou [F9] a qualquer momento.")
    print("-> Conversação Contínua: Responda diretamente após a fala da Luna.")
    print("-> Pressione Ctrl+C para sair.\n")

    hud.start()
    hud.set_state("idle")

    # Iniciar cliente WebSocket com o núcleo Antigravidade
    core_client.start()

    wake_detector = WakeWordDetector(on_wake_callback=handle_wake_word)
    wake_detector.start()

    try:
        keyboard.add_hotkey("esc", trigger_emergency_reset, suppress=False)
        keyboard.add_hotkey("f9", trigger_emergency_reset, suppress=False)
        keyboard.add_hotkey("f8", lambda: threading.Thread(target=handle_manual_f8, daemon=True).start(), suppress=False)
    except Exception as e:
        print(f"[-] Aviso ao registrar atalhos de teclado: {e}")

    print("💬 [Terminal Pronto]: Digite uma mensagem abaixo ou use a voz (Diga 'Luna' / [F8]):")

    while True:
        try:
            emergency_reset_active = False
            user_text = input("\n💬 Gabriel > ")
            if not user_text or not user_text.strip():
                continue

            clean_text = user_text.strip()
            if clean_text.lower() in ["sair", "exit", "quit"]:
                print("\n[!] Encerrando Luna Client...")
                break

            emergency_reset_active = False
            stop_speaking()
            if wake_detector:
                wake_detector.pause()

            duck_audio()

            if is_cancel_task_intent(clean_text):
                task_manager.cancel_active_task()
                process_user_turn("O Gabriel pediu para cancelar a tarefa ativa ou deixar pra lá. Confirme com carinho em 1 frase curta.")
            elif handle_confirmation_turn(clean_text):
                pass
            elif is_closure_intent(clean_text):
                closing_prompt = f"O Gabriel disse: '{clean_text}'. Trata-se de um encerramento natural de assunto ou agradecimento. Responda de forma fofa e amigável em 1 frase curta."
                process_user_turn(closing_prompt)
            else:
                process_user_turn(clean_text)

            unduck_audio()
            hud.set_state("idle")

            if wake_detector:
                wake_detector.resume()

        except (KeyboardInterrupt, EOFError):
            print("\n[!] Encerrando Luna Client...")
            break
        except Exception as e:
            print(f"[Erro no processamento de texto]: {e}")
            hud.set_state("idle")
            unduck_audio()
            if wake_detector:
                wake_detector.resume()

if __name__ == "__main__":
    main()
