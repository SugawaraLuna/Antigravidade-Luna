import os
import sys
import time
import asyncio
import threading
from typing import Callable, Optional
import sounddevice as sd
from google import genai
from google.genai import types

class LunaLiveWebSocketEngine:
    """
    Motor de comunicação bidirecional por WebSockets em tempo real da LUNA.
    Utiliza a Gemini Multimodal Live API com streaming nativo de áudio (24kHz PCM),
    suporte a chamadas de ferramentas locais no Windows e interrupção imediata (Barge-in).
    """

    def __init__(self, api_key: str, voice_name: str = "Aoede"):
        self.api_key = api_key
        self.voice_name = voice_name
        self.model_name = "gemini-2.5-flash-native-audio-latest"
        self.client = genai.Client(api_key=self.api_key, http_options={'api_version': 'v1alpha'})
        
        self.audio_stream: Optional[sd.RawOutputStream] = None
        self.is_playing = False
        self.is_interrupted = False

    def _ensure_audio_stream(self):
        try:
            if self.audio_stream is None or self.audio_stream.closed:
                self.audio_stream = sd.RawOutputStream(
                    samplerate=24000,
                    channels=1,
                    dtype='int16',
                    blocksize=1024
                )
                self.audio_stream.start()
            elif self.audio_stream.stopped:
                self.audio_stream.start()
        except Exception as e:
            print(f"[-] Aviso ao inicializar stream de áudio Live: {e}")

    def stop_audio(self):
        """Para e libera o dispositivo de áudio para que o microfone/VAD possa gravar livremente."""
        try:
            if self.audio_stream and not self.audio_stream.closed:
                self.audio_stream.stop()
        except Exception:
            pass

    def interrupt(self):
        """Interrompe imediatamente a fala atual (Barge-in / Reset de Emergência)."""
        self.is_interrupted = True
        self.is_playing = False
        self.stop_audio()

    def _build_tools_list(self, tools_schema: list) -> list:
        try:
            raw_decls = tools_schema[0]["function_declarations"]
            f_decls = [types.FunctionDeclaration(**d) for d in raw_decls]
            return [types.Tool(function_declarations=f_decls)]
        except Exception as e:
            print(f"[-] Aviso ao converter ferramentas para WebSocket: {e}")
            return []

    async def run_turn(
        self,
        system_instruction: str,
        tools_schema: list,
        user_text: Optional[str] = None,
        pcm_bytes: Optional[bytes] = None,
        execute_tool_fn: Optional[Callable] = None,
        get_screenshot_pil_fn: Optional[Callable] = None,
        hud = None
    ) -> bool:
        """
        Executa um turno completo via WebSocket com streaming de áudio em tempo real.
        Retorna True se concluído com sucesso, ou False para acionar fallback HTTP.
        """
        self.is_interrupted = False
        self._ensure_audio_stream()

        tools = self._build_tools_list(tools_schema)
        
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.voice_name)
                )
            ),
            tools=tools,
            system_instruction=types.Content(
                parts=[types.Part.from_text(text=system_instruction)]
            )
        )

        try:
            if hud:
                hud.set_state("thinking", "Conectando WebSocket Live...")

            async with self.client.aio.live.connect(model=self.model_name, config=config) as session:
                if hud:
                    hud.set_state("thinking", "LUNA formulando...")

                # Enviar entrada do usuário
                if user_text:
                    content = types.Content(parts=[types.Part.from_text(text=user_text)])
                    await session.send_client_content(turns=[content], turn_complete=True)
                elif pcm_bytes:
                    await session.send_realtime_input(
                        audio=types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")
                    )
                else:
                    return False

                first_chunk = True
                chunk_count = 0
                t_start = time.time()

                async for response in session.receive():
                    if self.is_interrupted:
                        print("\n[🛑 Barge-in WebSocket]: Reprodução interrompida pelo usuário.")
                        break

                    # 1. Tratar chamada de ferramentas (Function Calling)
                    if response.tool_call is not None and execute_tool_fn is not None:
                        tool_responses = []
                        for fc in response.tool_call.function_calls:
                            fn_name = fc.name
                            fn_args = fc.args if hasattr(fc, "args") and fc.args else {}
                            if hud:
                                hud.set_state("thinking", f"Executando: {fn_name}")
                            print(f"\n🧠 [Raciocínio WebSocket]: Ferramenta '{fn_name}' acionada ({fn_args})")
                            
                            # Executar localmente
                            tool_result = execute_tool_fn(fn_name, fn_args)
                            print(f"[*] Resposta local: {str(tool_result)[:120]}...")

                            # Se a ferramenta executada foi captura de tela, enviar imagem em tempo real
                            if fn_name == "take_screenshot" and get_screenshot_pil_fn:
                                pil_img = get_screenshot_pil_fn()
                                if pil_img:
                                    try:
                                        print("[📷 Visão WebSocket]: Transmitindo captura de tela para a LUNA...")
                                        await session.send_realtime_input(media=pil_img)
                                    except Exception as img_err:
                                        print(f"[-] Aviso ao transmitir imagem via WebSocket: {img_err}")

                            tool_responses.append(
                                types.FunctionResponse(
                                    name=fn_name,
                                    id=fc.id,
                                    response={"result": str(tool_result)}
                                )
                            )

                        # Enviar de volta pela WebSocket para que a Luna fale o resultado
                        await session.send_tool_response(function_responses=tool_responses)
                        if hud:
                            hud.set_state("thinking", "Sintetizando resposta...")

                    # 2. Receber chunks de áudio PCM em tempo real (24kHz)
                    sc = response.server_content
                    if sc is not None:
                        if sc.model_turn is not None:
                            for part in sc.model_turn.parts:
                                if part.inline_data and not self.is_interrupted:
                                    if first_chunk:
                                        latency = time.time() - t_start
                                        print(f"[⚡ Streaming WebSocket]: Primeiro áudio em {latency:.2f}s!")
                                        if hud:
                                            hud.set_state("speaking", "Falando em tempo real...")
                                        self.is_playing = True
                                        first_chunk = False

                                    chunk_count += 1
                                    self._ensure_audio_stream()
                                    self.audio_stream.write(part.inline_data.data)

                        if sc.turn_complete:
                            break

                # Dar tempo mínimo para os últimos milissegundos do buffer de áudio tocarem
                await asyncio.sleep(0.4)
                self.stop_audio()
                self.is_playing = False
                return True

        except Exception as e:
            print(f"[-] Oscilação na Live API WebSocket: {e}. Alternando para fallback HTTP...")
            self.stop_audio()
            self.is_playing = False
            return False

    def close(self):
        try:
            if self.audio_stream:
                self.audio_stream.stop()
                self.audio_stream.close()
        except Exception:
            pass
