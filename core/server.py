import asyncio
import json
import os
import sys
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

# Assegurar codificação UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from core.engine import AntigravityExecutionEngine

HOST = os.getenv("HOST", os.getenv("ANTIGRAVITY_CORE_HOST", "0.0.0.0"))
PORT = int(os.getenv("PORT", os.getenv("ANTIGRAVITY_CORE_PORT", "8765")))

engine = AntigravityExecutionEngine()

async def handle_health(request: web.Request) -> web.Response:
    """Endpoint para checagem de saúde e descoberta do núcleo."""
    return web.json_response({
        "status": "online",
        "core": "antigravidade",
        "version": "2.0",
        "timestamp": asyncio.get_event_loop().time()
    })

async def handle_rest_query(request: web.Request) -> web.Response:
    """Endpoint REST para envio de comandos pontuais."""
    try:
        data = await request.json()
        query_text = data.get("text", "")
        if not query_text:
            return web.json_response({"error": "Texto da requisição vazio"}, status=400)
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, engine.process_query, query_text)
        return web.json_response(result)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

async def handle_ws_luna(request: web.Request) -> web.WebSocketResponse:
    """Canal WebSocket bidirecional para o cliente leve da LUNA."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    client_ip = request.remote
    print(f"\n[+] [Antigravidade Core]: Cliente LUNA conectado de {client_ip} via WebSocket.")

    current_cancel_flag = False
    current_task = None

    try:
        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    payload = json.loads(msg.data)
                except Exception:
                    continue

                msg_type = payload.get("type", "")

                if msg_type == "cancel":
                    print("\n[🛑 Antigravidade Core]: Sinal de cancelamento recebido da LUNA.")
                    current_cancel_flag = True
                    if current_task and not current_task.done():
                        current_task.cancel()
                    await ws.send_json({"type": "cancelled"})
                    await ws.send_json({"type": "status", "state": "idle"})
                    continue

                elif msg_type == "query":
                    user_text = payload.get("text", "")
                    if not user_text:
                        continue

                    current_cancel_flag = False
                    print(f"\n📨 [Antigravidade Core]: Comando recebido da LUNA: \"{user_text}\"")

                    # Avisar imediatamente que está raciocinando
                    await ws.send_json({"type": "status", "state": "thinking", "text": "LUNA pensando..."})

                    loop = asyncio.get_event_loop()

                    def on_status_update(status_text: str):
                        # Enviar evento de status para o HUD da Luna em tempo real
                        if not current_cancel_flag and not ws.closed:
                            asyncio.run_coroutine_threadsafe(
                                ws.send_json({
                                    "type": "status",
                                    "state": "thinking",
                                    "text": status_text
                                }),
                                loop
                            )

                    def cancel_checker():
                        return current_cancel_flag

                    # Executar o motor de raciocínio em thread pool assíncrona
                    current_task = loop.run_in_executor(
                        None,
                        engine.process_query,
                        user_text,
                        on_status_update,
                        cancel_checker
                    )

                    try:
                        result = await current_task
                    except asyncio.CancelledError:
                        print("[*] Tarefa cancelada com sucesso no núcleo.")
                        await ws.send_json({"type": "status", "state": "idle"})
                        continue
                    except Exception as err:
                        print(f"[-] Erro ao processar turno no núcleo: {err}")
                        result = {
                            "spoken_text": "Gabriel, encontrei uma falha momentânea no núcleo de execução.",
                            "error": str(err)
                        }

                    if current_cancel_flag or ws.closed:
                        continue

                    # Transmitir resposta final formulada para o cliente leve LUNA
                    spoken_text = result.get("spoken_text", "")
                    action_summary = result.get("action_summary", "")
                    print(f"🚀 [Antigravidade Core]: Enviando resposta para LUNA: \"{spoken_text[:60]}...\"")

                    await ws.send_json({
                        "type": "response",
                        "spoken_text": spoken_text,
                        "action_summary": action_summary,
                        "state": "speaking"
                    })

            elif msg.type == web.WSMsgType.ERROR:
                print(f"[-] Erro na conexão WebSocket: {ws.exception()}")

    finally:
        print(f"[-] [Antigravidade Core]: Cliente LUNA desconectado de {client_ip}.")

    return ws

def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", handle_health)
    app.router.add_post("/api/query", handle_rest_query)
    app.router.add_get("/ws/luna", handle_ws_luna)
    return app

def main():
    print("=" * 68)
    print("   🌌 NÚCLEO CENTRAL DE INTELIGÊNCIA & EXECUÇÃO: ANTIGRAVIDADE")
    print("=" * 68)
    print(f"-> Servidor Central: http://{HOST}:{PORT}")
    print(f"-> Canal WebSocket LUNA: ws://{HOST}:{PORT}/ws/luna")
    print(f"-> Rota de Diagnóstico: http://{HOST}:{PORT}/health")
    print("-> Motor: Gemini Multimodal + Raciocínio Estruturado PowerShell")
    print("-> Pressione Ctrl+C para encerrar o núcleo.\n")

    app = create_app()
    web.run_app(app, host=HOST, port=PORT, print=None)

if __name__ == "__main__":
    main()
