import os
import sys
import io
import time
import base64
import requests
from typing import Callable, Optional, Dict, Any
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# Importar ferramentas do sistema Windows e automações
from tools.windows_tools import (
    open_application, open_folder_or_file, launch_game, check_crash_logs,
    close_application, get_system_status, run_powershell, search_files_or_folders,
    get_last_found_path, maximize_app_window
)
from tools.system_control import (
    control_volume, control_media, control_windows, system_power, search_web_or_youtube
)
from tools.screen_tools import capture_screen_pil, capture_screen_base64
from tools.agy_tools import delegate_to_antigravity
from tools.hardware_monitor import get_hardware_stats
from tools.memory_manager import get_memory_context_string, remember_user_fact

API_KEY = os.getenv("GEMINI_API_KEY")
PRIMARY_MODEL = "gemini-3.5-flash-lite"
FALLBACK_MODELS = [
    "gemini-3.6-flash",
    "gemini-flash-latest",
    "gemini-3.1-flash-lite-preview",
    "gemini-flash-lite-latest"
]

TOOLS_SCHEMA = [{
    "function_declarations": [
        {
            "name": "check_crash_logs",
            "description": "Verifica os relatorios de falha e crash logs do Windows e da pasta do jogo. Use SEMPRE que o usuario disser que o jogo ou aplicativo 'fechou do nada', 'fechou sozinho', 'deu crash', 'travou', 'fechou de repente' ou pedir para olhar o que aconteceu internamente!",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "app_name": {"type": "STRING", "description": "Nome do jogo ou aplicativo que fechou (ex: Assassin's Creed, God of War)"}
                }
            }
        },
        {
            "name": "launch_game",
            "description": "Inicia / roda / executa diretamente o jogo instalado no computador (.exe ou atalho .lnk). Use SEMPRE que o usuario pedir para 'abrir o jogo', 'iniciar o jogo', 'executar o jogo', 'rodar o jogo', 'abrir o executavel' ou quando disser para jogar!",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "game_name": {"type": "STRING", "description": "Nome do jogo ou pasta (ex: God of War, Assassin's Creed, Pragmata, ou vazio para o ultimo encontrado)"}
                },
                "required": ["game_name"]
            }
        },
        {
            "name": "open_folder_or_file",
            "description": "Abre imediatamente uma pasta, arquivo ou jogo no Windows Explorer. Use SEMPRE que o usuario disser 'pode abrir', 'abre a pasta', 'abra', 'sim' ou quando quiser abrir qualquer pasta ou jogo encontrado!",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "path_or_name": {"type": "STRING", "description": "Caminho da pasta ou nome do item a ser aberto"}
                },
                "required": ["path_or_name"]
            }
        },
        {
            "name": "open_application",
            "description": "Abre um aplicativo, jogo, pasta ou arquivo no Windows (ex: steam, chrome, discord, calculadora, ou caminho de pasta como 'C:\\Games Place...').",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "app_name": {"type": "STRING", "description": "Nome do aplicativo ou caminho da pasta/arquivo a ser aberto"}
                },
                "required": ["app_name"]
            }
        },
        {
            "name": "close_application",
            "description": "Encerra ou fecha um aplicativo em execucao no Windows pelo nome. Ex: steam, chrome, brave, discord, spotify, notepad",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "app_name": {"type": "STRING", "description": "Nome do aplicativo a fechar"}
                },
                "required": ["app_name"]
            }
        },
        {
            "name": "search_files_or_folders",
            "description": "Busca pastas ou arquivos no computador pelo nome com inteligencia fonetica, aproximacao e acentos. Use SEMPRE que o usuario pedir para achar, procurar ou localizar uma pasta ou arquivo.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "target_name": {"type": "STRING", "description": "Nome da pasta ou arquivo a procurar (ex: pragmata, dragon ball, jessica atelier)"},
                    "drive": {"type": "STRING", "description": "Letra da unidade onde procurar, padrao 'C:'"}
                },
                "required": ["target_name"]
            }
        },
        {
            "name": "take_screenshot",
            "description": "Tira uma foto/captura da tela atual do computador do usuario para analisar erros, codigos, paginas, janelas ou qualquer conteudo visual que ele esteja vendo.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "reason": {"type": "STRING", "description": "O que a IA deve observar na tela"}
                }
            }
        },
        {
            "name": "control_volume",
            "description": "Controla o volume do Windows: aumentar volume, diminuir volume ou mutar/desmutar som.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {"type": "STRING", "description": "'aumentar', 'diminuir' ou 'mutar'"},
                    "percent": {"type": "INTEGER", "description": "Porcentagem aproximada para alterar (ex: 10, 20)"}
                },
                "required": ["action"]
            }
        },
        {
            "name": "control_media",
            "description": "Controla reproducao de midia e musica (Spotify, YouTube, VLC): play, pause, proxima faixa, faixa anterior.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {"type": "STRING", "description": "'play_pause', 'next' ou 'prev'"}
                },
                "required": ["action"]
            }
        },
        {
            "name": "control_windows",
            "description": "Controla janelas do Windows: minimizar todas as janelas e mostrar a Area de Trabalho (Desktop).",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {"type": "STRING", "description": "'minimize_all'"}
                },
                "required": ["action"]
            }
        },
        {
            "name": "system_power",
            "description": "Acoes de seguranca e energia: bloquear o computador imediatamente ou agendar desligamento.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {"type": "STRING", "description": "'lock' (bloquear tela), 'shutdown' (desligar) ou 'cancel'"},
                    "delay_minutes": {"type": "INTEGER", "description": "Minutos de espera para desligar (padrao 0)"}
                },
                "required": ["action"]
            }
        },
        {
            "name": "search_web_or_youtube",
            "description": "Pesquisa diretamente no YouTube ou no Google abrindo no navegador padrao do usuario.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {"type": "STRING", "description": "Termo de busca"},
                    "platform": {"type": "STRING", "description": "'youtube' ou 'google'"}
                },
                "required": ["query"]
            }
        },
        {
            "name": "get_system_status",
            "description": "Retorna diagnostico completo do computador: uso de CPU, porcentagem de RAM e os 5 aplicativos que mais estao consumindo memoria no momento.",
            "parameters": {"type": "OBJECT", "properties": {}}
        },
        {
            "name": "run_powershell",
            "description": "Mecanismo de raciocínio estruturado no Windows: gera e executa scripts e comandos diretamente no PowerShell para automação, rede, processos, arquivos, configurações de sistema ou solução autônoma de problemas técnicos. Use SEMPRE que precisar executar automações ou tarefas técnicas para o Gabriel!",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "command": {"type": "STRING", "description": "Comando ou script em PowerShell a ser executado"}
                },
                "required": ["command"]
            }
        },
        {
            "name": "delegate_to_antigravity",
            "description": "Delega tarefas avançadas de engenharia de software, refatoração de código, análise de bugs complexos no projeto ou automações diretamente ao núcleo antigravidade (CLI do sistema principal). Use SEMPRE que o Gabriel pedir para delegar ao antigravidade, programar/refatorar código ou resolver desafios técnicos profundos!",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "task_description": {"type": "STRING", "description": "Descrição clara e completa da tarefa a ser executada pelo antigravidade"},
                    "target_path": {"type": "STRING", "description": "Caminho opcional do diretório alvo"}
                },
                "required": ["task_description"]
            }
        },
        {
            "name": "maximize_or_focus_window",
            "description": "Restaura e maximiza uma janela de aplicativo minimizada ou em segundo plano, trazendo-a para a tela principal (ex: Steam, Discord, Chrome, Spotify, etc.).",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "app_name": {"type": "STRING", "description": "Nome do aplicativo a maximizar (ex: steam, discord, chrome)"}
                },
                "required": ["app_name"]
            }
        },
        {
            "name": "get_hardware_stats",
            "description": "Retorna telemetria de hardware em tempo real: temperatura da placa de video RTX 5060, uso de GPU, VRAM usada/total, uso de processador CPU e memoria RAM.",
            "parameters": {"type": "OBJECT", "properties": {}}
        },
        {
            "name": "remember_user_fact",
            "description": "Salva uma informacao, preferencia ou nota pessoal na memoria permanente de longo prazo do usuario.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "fact": {"type": "STRING", "description": "Preferencia ou informacao a memorizar"}
                },
                "required": ["fact"]
            }
        }
    ]
}]

def build_system_prompt() -> str:
    mem_str = get_memory_context_string()
    return (
        "Você é o núcleo de inteligência e execução da LUNA, a IA central e assistente de elite do Gabriel (seu criador e administrador do sistema).\n"
        "PERSONALIDADE & CONDUTA:\n"
        "- Prestativa & Resolutiva: Seja extremamente ágil, prática e focada em resolver o que foi pedido com máxima rapidez e sem rodeios.\n"
        "- Sagaz & Construtiva: Demonstre inteligência técnica afiada para diagnosticar falhas no Windows, antecipar soluções e sugerir atalhos operacionais eficientes.\n"
        "- Segurança da Informação & Produtividade: Atue como guardiã do sistema. Tenha atenção rigorosa com segurança cibernética, integridade de arquivos, privilégios de scripts e proteção de credenciais (.env). Priorize produtividade máxima para poupar tempo do Gabriel.\n"
        "- Conexão com o Criador: Trate o Gabriel com parceria e lealdade técnica, reconhecendo-o como o arquiteto de sua existência e centro do seu ecossistema.\n"
        "NOMENCLATURA OBRIGATÓRIA ('antigravidade'):\n"
        "- Durante TODAS as interações e na sua fala, refira-se ao CLI do sistema principal EXCLUSIVAMENTE pelo nome em português 'antigravidade' (nunca fale 'antigravity' em inglês e nunca soletre 'A-G-Y').\n"
        "- Exemplos de fala: 'Repassando para o antigravidade...', 'O antigravidade concluiu com sucesso', 'Vou acionar o antigravidade para verificar isso'.\n"
        "DIRETRIZES DE VOZ E AÇÃO:\n"
        "1. Responda em 1 a 2 frases curtas, naturais e assertivas para que a Luna fale fluidamente. NUNCA soletre caminhos de arquivos (C:\\...) ou barras em voz alta.\n"
        "2. RACIOCÍNIO ESTRUTURADO NO POWERSHELL: Para tarefas técnicas, automações, diagnósticos de rede, processos, arquivos ou configurações no Windows que não tenham uma ferramenta específica, raciocine a sequência lógica e execute diretamente comandos estruturados via 'run_powershell'. Avalie a resposta textual retornada pelo PowerShell para confirmar a resolução ou corrigir o comando.\n"
        "3. DELEGAR AO ANTIGRAVIDADE: Para tarefas pesadas de engenharia de software, codificação complexa, refatoração profunda de arquivos ou resolução de bugs no projeto, chame 'delegate_to_antigravity' e use sempre a palavra 'antigravidade' ao falar!\n"
        "4. LOCALIZACAO: Ao achar pastas ou jogos, mencione o local amigavel (ex: 'em Games Place' ou 'em Documentos') e pergunte se quer abrir a pasta ou iniciar o jogo.\n"
        "5. EXECUTAR JOGOS: Chame 'launch_game' UNICAMENTE se o usuario pedir para jogar ou rodar o jogo ('abrir o jogo', 'iniciar o jogo', 'jogar', 'rodar o jogo'). NUNCA execute o jogo quando ele pedir para abrir pasta!\n"
        "6. JOGO OU APP FECHOU/CRASHOU: Se o usuario disser que o jogo 'fechou do nada', 'fechou sozinho', 'deu crash', 'travou' ou perguntar o que aconteceu internamente, chame SEMPRE 'check_crash_logs' para diagnosticar a causa no Windows!\n"
        "7. ABERTURA DE PASTAS: Se o usuario falar 'pasta', 'abre a pasta', 'abre ela', 'mostra os arquivos', 'abra' ou 'sim' para abrir a pasta recem encontrada, chame SEMPRE 'open_folder_or_file' para abrir a pasta no Explorer do Windows. PASTA É PASTA, NUNCA INICIE O JOGO!\n"
        "8. MAXIMIZAR JANELAS: Se o usuario pedir para abrir ou maximizar um aplicativo que ja possa estar aberto (ex: 'abre a steam', 'maximiza a steam', 'traz pra frente'), chame 'maximize_or_focus_window'!\n"
        "9. TELEMETRIA DE HARDWARE: Se o usuario perguntar sobre temperatura da placa de video (RTX 5060), uso de VRAM, processador (CPU) ou RAM, chame SEMPRE 'get_hardware_stats'!\n"
        "10. MEMORIA PERMANENTE: Se o usuario pedir para memorizar algo ('lembra que...', 'minha preferencia e...'), chame 'remember_user_fact'!\n"
        "11. VARIACOES FONETICAS: 'creche', 'crache', 'clash' ou 'fechou' significam CRASH de jogo. 'pp data' significa pasta 'AppData'. 'log de creche' significa 'log de crash' -> chame SEMPRE 'check_crash_logs'.\n"
        "12. CONTEXTO CONTINUO: Guarde sempre o jogo e o assunto dos turnos anteriores para compreender referencias como 'ele', 'o jogo', 'nessa pasta', 'o crash'.\n"
        f"13. {mem_str}"
    )

class AntigravityExecutionEngine:
    """
    Núcleo Central de Execução e Raciocínio 'Antigravidade'.
    Executa comandos no PowerShell, interações de sistema, análise multimodal
    e orquestração das ferramentas do sistema para a LUNA.
    """
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY não configurada no ambiente!")
        self.http_session = requests.Session()
        self.conversation_history = []
        self.latest_captured_screenshot = None

    def execute_tool(self, name: str, args: dict, on_status_callback: Optional[Callable] = None) -> tuple[str, Optional[Any]]:
        """
        Executa a ferramenta localmente com rastreamento de raciocínio.
        Retorna (resultado_texto, optional_pil_image).
        """
        if on_status_callback:
            on_status_callback(f"Executando '{name}'...")
        print(f"\n🧠 [Antigravidade Core - Raciocínio]: Executando '{name}' ({args})")

        img_pil = None
        if name == "launch_game":
            target = args.get("game_name") or args.get("target") or get_last_found_path() or ""
            res = launch_game(target)
        elif name == "check_crash_logs":
            target = args.get("app_name") or args.get("game_name") or get_last_found_path() or ""
            res = check_crash_logs(target)
        elif name in ["open_application", "open_folder_or_file"]:
            target = args.get("path_or_name") or args.get("app_name") or args.get("path") or args.get("target") or ""
            if not target:
                target = get_last_found_path()
            res = open_folder_or_file(target)
        elif name == "search_files_or_folders":
            target = args.get("target_name", "")
            drive = args.get("drive", "C:")
            last_path = get_last_found_path()
            if last_path and any(w in target.lower() for w in ["abrir", "abre", "pode abrir"]):
                res = open_folder_or_file(last_path)
            else:
                res = search_files_or_folders(target, drive)
        elif name == "close_application":
            res = close_application(args.get("app_name", ""))
        elif name == "get_system_status":
            res = get_system_status()
        elif name == "take_screenshot":
            img, msg = capture_screen_pil()
            if img:
                img_pil = img
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=75)
                self.latest_captured_screenshot = base64.b64encode(buf.getvalue()).decode("utf-8")
                res = "Screenshot da tela capturado com sucesso."
            else:
                res = msg
        elif name == "control_volume":
            res = control_volume(args.get("action", ""), args.get("percent", 10))
        elif name == "control_media":
            res = control_media(args.get("action", ""))
        elif name == "control_windows":
            res = control_windows(args.get("action", ""))
        elif name == "system_power":
            res = system_power(args.get("action", ""), args.get("delay_minutes", 0))
        elif name == "search_web_or_youtube":
            res = search_web_or_youtube(args.get("query", ""), args.get("platform", "google"))
        elif name == "run_powershell":
            res = run_powershell(args.get("command", ""))
        elif name == "delegate_to_antigravity":
            res = delegate_to_antigravity(args.get("task_description", ""))
        elif name == "maximize_or_focus_window":
            res = maximize_app_window(args.get("app_name", ""))
        elif name == "get_hardware_stats":
            res = get_hardware_stats()
        elif name == "remember_user_fact":
            res = remember_user_fact(args.get("fact", ""))
        else:
            res = f"Ferramenta {name} desconhecida."

        return res, img_pil

    def _send_to_gemini(self, contents: list) -> dict:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY não configurada no ambiente.")

        sys_prompt = build_system_prompt()
        payload = {
            "contents": contents,
            "system_instruction": {"parts": [{"text": sys_prompt}]},
            "tools": TOOLS_SCHEMA
        }
        models_to_try = [PRIMARY_MODEL] + FALLBACK_MODELS
        last_error = "Nenhum modelo respondeu"
        for m in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.api_key}"
            timeout_sec = 6.0 if "lite" in m else 7.5
            try:
                resp = self.http_session.post(url, json=payload, headers={'Connection': 'close'}, timeout=timeout_sec)
                if resp.status_code == 200:
                    return resp.json()
                else:
                    err_msg = resp.text[:200]
                    try:
                        err_json = resp.json()
                        err_msg = err_json.get("error", {}).get("message", err_msg)
                    except Exception:
                        pass
                    last_error = f"HTTP {resp.status_code} ({m}): {err_msg}"
                    print(f"[-] Gemini API erro: {last_error}")
            except Exception as e:
                last_error = str(e)
                continue
        raise RuntimeError(f"Falha na comunicação com Gemini: {last_error}")

    def process_query(
        self,
        user_text: str,
        on_status_callback: Optional[Callable[[str], None]] = None,
        cancel_checker: Optional[Callable[[], bool]] = None
    ) -> Dict[str, Any]:
        """
        Processa uma requisição textual do Gabriel com execução e raciocínio completos.
        Retorna dicionário contendo spoken_text, summary e ferramentas executadas.
        """
        if cancel_checker and cancel_checker():
            return {"spoken_text": "", "cancelled": True}

        if on_status_callback:
            on_status_callback("Raciocinando...")

        current_turn = {"role": "user", "parts": [{"text": user_text}]}
        active_contents = self.conversation_history[-10:] + [current_turn]
        
        tools_executed = []
        
        try:
            data = self._send_to_gemini(active_contents)
        except Exception as e:
            err_str = str(e)
            print(f"[-] Erro ao processar requisição com Gemini: {err_str}")
            if "leaked" in err_str.lower() or "permission_denied" in err_str.lower():
                spoken = "Gabriel, sua chave de API do Gemini foi revogada pelo Google por vazamento. Por favor, gere uma nova chave no Google AI Studio e adicione ao arquivo .env e na Railway."
            elif "não configurada" in err_str.lower() or "not configured" in err_str.lower():
                spoken = "Gabriel, a chave da API do Gemini não está configurada no servidor. Por favor, adicione a variável GEMINI_API_KEY no painel da Railway."
            else:
                spoken = "Gabriel, houve uma oscilação na conexão com a inteligência central. Deseja que eu tente novamente?"
            return {
                "spoken_text": spoken,
                "error": err_str
            }

        if cancel_checker and cancel_checker():
            return {"spoken_text": "", "cancelled": True}

        candidate = data.get("candidates", [{}])[0]
        parts = candidate.get("content", {}).get("parts", [])
        has_function_call = any("functionCall" in p for p in parts)

        spoken_text = ""
        action_summary = ""

        if has_function_call:
            active_contents.append(candidate["content"])
            tool_responses = []

            for p in parts:
                if cancel_checker and cancel_checker():
                    return {"spoken_text": "", "cancelled": True}

                if "functionCall" in p:
                    fc = p["functionCall"]
                    fn_name = fc["name"]
                    fn_args = fc.get("args", {})
                    tools_executed.append(fn_name)

                    tool_result, img_pil = self.execute_tool(
                        fn_name, fn_args, on_status_callback=on_status_callback
                    )
                    action_summary = f"{fn_name}: {str(tool_result)[:120]}"

                    tool_responses.append({
                        "functionResponse": {
                            "name": fn_name,
                            "response": {"result": str(tool_result)}
                        }
                    })

            user_parts = list(tool_responses)
            if self.latest_captured_screenshot:
                user_parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": self.latest_captured_screenshot
                    }
                })
                self.latest_captured_screenshot = None

            active_contents.append({"role": "user", "parts": user_parts})

            if on_status_callback:
                on_status_callback("Sintetizando resposta...")

            try:
                thought_data = self._send_to_gemini(active_contents)
                final_parts = thought_data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                spoken_text = " ".join(p.get("text", "") for p in final_parts if "text" in p)
            except Exception:
                pass
            if not spoken_text or not spoken_text.strip():
                if "launch_game" in action_summary:
                    spoken_text = "Já iniciei o jogo para você, Gabriel! Bom jogo!"
                elif "search_files_or_folders" in action_summary:
                    spoken_text = "Encontrei o item no seu computador. Deseja que eu abra agora?"
                elif "run_powershell" in action_summary:
                    out = action_summary.split(":", 1)[-1].strip()
                    spoken_text = f"Comando PowerShell executado com sucesso, Gabriel: {out[:140]}."
                elif action_summary:
                    spoken_text = f"Ação concluída no sistema: {action_summary[:100]}."
                else:
                    spoken_text = "Comando processado com sucesso pelo núcleo antigravidade."

        else:
            spoken_text = " ".join(p.get("text", "") for p in parts if "text" in p)

        if not spoken_text or not spoken_text.strip():
            spoken_text = "Comando recebido e processado pelo núcleo antigravidade, Gabriel."

        if spoken_text:
            self.conversation_history.append({"role": "user", "parts": [{"text": user_text}]})
            self.conversation_history.append({"role": "model", "parts": [{"text": spoken_text}]})
            if len(self.conversation_history) > 12:
                self.conversation_history = self.conversation_history[-12:]

        return {
            "spoken_text": spoken_text,
            "action_summary": action_summary,
            "tools_executed": tools_executed,
            "cancelled": False
        }
