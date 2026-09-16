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

load_dotenv(override=True)

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
from tools.internet_tools import get_live_weather, search_internet_info, open_in_browser
from tools.clipboard_tools import handle_code_delivery
from core.task_manager import task_manager

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
                    "app_name": {"type": "STRING", "description": "Nome do jogo ou aplicativo que fechou (ex: Assassin's Creed, God of War)"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português do que está fazendo (ex: 'Verificando logs de crash do jogo')"}
                },
                "required": ["action_label"]
            }
        },
        {
            "name": "launch_game",
            "description": "Inicia / roda / executa diretamente o jogo instalado no computador (.exe ou atalho .lnk). Use SEMPRE que o usuario pedir para 'abrir o jogo', 'iniciar o jogo', 'executar o jogo', 'rodar o jogo', 'abrir o executavel' ou quando disser para jogar!",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "game_name": {"type": "STRING", "description": "Nome do jogo ou pasta (ex: God of War, Assassin's Creed, Pragmata, ou vazio para o ultimo encontrado)"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português do que está fazendo (ex: 'Iniciando jogo solicitado')"}
                },
                "required": ["game_name", "action_label"]
            }
        },
        {
            "name": "open_folder_or_file",
            "description": "Abre imediatamente uma pasta, arquivo ou jogo no Windows Explorer. Use SEMPRE que o usuario disser 'pode abrir', 'abre a pasta', 'abra', 'sim' ou quando quiser abrir qualquer pasta ou jogo encontrado!",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "path_or_name": {"type": "STRING", "description": "Caminho da pasta ou nome do item a ser aberto"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português do que está fazendo (ex: 'Abrindo pasta no Explorer')"}
                },
                "required": ["path_or_name", "action_label"]
            }
        },
        {
            "name": "open_application",
            "description": "Abre um aplicativo, jogo, pasta ou arquivo no Windows (ex: steam, chrome, discord, calculadora, ou caminho de pasta como 'C:\\Games Place...').",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "app_name": {"type": "STRING", "description": "Nome do aplicativo ou caminho da pasta/arquivo a ser aberto"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português do que está fazendo (ex: 'Abrindo aplicativo solicitado')"}
                },
                "required": ["app_name", "action_label"]
            }
        },
        {
            "name": "close_application",
            "description": "Encerra ou fecha um aplicativo em execucao no Windows pelo nome. Ex: steam, chrome, brave, discord, spotify, notepad",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "app_name": {"type": "STRING", "description": "Nome do aplicativo a fechar"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português do que está fazendo (ex: 'Fechando aplicativo')"}
                },
                "required": ["app_name", "action_label"]
            }
        },
        {
            "name": "search_files_or_folders",
            "description": "Busca pastas ou arquivos no computador pelo nome com inteligencia fonetica, aproximacao e acentos. Use SEMPRE que o usuario pedir para achar, procurar ou localizar uma pasta ou arquivo.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "target_name": {"type": "STRING", "description": "Nome da pasta ou arquivo a procurar (ex: pragmata, dragon ball, jessica atelier)"},
                    "drive": {"type": "STRING", "description": "Letra da unidade onde procurar, padrao 'C:'"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português do que está fazendo (ex: 'Procurando arquivos no computador')"}
                },
                "required": ["target_name", "action_label"]
            }
        },
        {
            "name": "take_screenshot",
            "description": "Tira uma foto/captura da tela atual do computador do usuario para analisar erros, codigos, paginas, janelas ou qualquer conteudo visual que ele esteja vendo.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "reason": {"type": "STRING", "description": "O que a IA deve observar na tela"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português do que está fazendo (ex: 'Analisando tela do computador')"}
                },
                "required": ["action_label"]
            }
        },
        {
            "name": "control_volume",
            "description": "Controla o volume do Windows: aumentar volume, diminuir volume ou mutar/desmutar som.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {"type": "STRING", "description": "'aumentar', 'diminuir' ou 'mutar'"},
                    "percent": {"type": "INTEGER", "description": "Porcentagem aproximada para alterar (ex: 10, 20)"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português do que está fazendo (ex: 'Ajustando volume do som')"}
                },
                "required": ["action", "action_label"]
            }
        },
        {
            "name": "control_media",
            "description": "Controla reproducao de midia e musica (Spotify, YouTube, VLC): play, pause, proxima faixa, faixa anterior.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {"type": "STRING", "description": "'play_pause', 'next' ou 'prev'"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português do que está fazendo (ex: 'Controlando reprodução de mídia')"}
                },
                "required": ["action", "action_label"]
            }
        },
        {
            "name": "control_windows",
            "description": "Controla janelas do Windows: minimizar todas as janelas e mostrar a Area de Trabalho (Desktop).",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {"type": "STRING", "description": "'minimize_all'"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português do que está fazendo (ex: 'Minimizando todas as janelas')"}
                },
                "required": ["action", "action_label"]
            }
        },
        {
            "name": "system_power",
            "description": "Acoes de seguranca e energia: bloquear o computador imediatamente ou agendar desligamento.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action": {"type": "STRING", "description": "'lock' (bloquear tela), 'shutdown' (desligar) ou 'cancel'"},
                    "delay_minutes": {"type": "INTEGER", "description": "Minutos de espera para desligar (padrao 0)"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português do que está fazendo (ex: 'Bloqueando o computador')"}
                },
                "required": ["action", "action_label"]
            }
        },
        {
            "name": "search_web_or_youtube",
            "description": "Pesquisa diretamente no YouTube ou no Google abrindo no navegador padrao do usuario.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {"type": "STRING", "description": "Termo de busca"},
                    "platform": {"type": "STRING", "description": "'youtube' ou 'google'"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português do que está fazendo (ex: 'Pesquisando na web')"}
                },
                "required": ["query", "action_label"]
            }
        },
        {
            "name": "get_system_status",
            "description": "Retorna diagnostico completo do computador: uso de CPU, porcentagem de RAM e os 5 aplicativos que mais estao consumindo memoria no momento.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português do que está fazendo (ex: 'Diagnosticando processos do sistema')"}
                },
                "required": ["action_label"]
            }
        },
        {
            "name": "run_powershell",
            "description": "Executa scripts e comandos no PowerShell para automação, criação de arquivos/pastas, rede, processos ou configurações no Windows. Use quando o Gabriel solicitar automações, arquivos ou comandos de terminal.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "command": {"type": "STRING", "description": "Comando ou script em PowerShell a ser executado"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico e natural em português explicando exatamente o que você está fazendo para o Gabriel (ex: 'Criando arquivo solicitado em Downloads', 'Listando processos com alto uso de memória')."}
                },
                "required": ["command", "action_label"]
            }
        },
        {
            "name": "delegate_to_antigravity",
            "description": "Delega tarefas avançadas de arquitetura de sistemas (ex: conectar celular à nuvem/Railway), engenharia de software, codificação, refatoração de código, análise de integrações ou automações ao núcleo antigravidade. Use SEMPRE que o Gabriel pedir para consultar o antigravidade, criar arquiteturas, projetar conexões ou programar!",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "task_description": {"type": "STRING", "description": "Descrição detalhada do que o antigravidade deve analisar, projetar, programar ou resolver"},
                    "target_path": {"type": "STRING", "description": "Caminho opcional do diretório alvo"},
                    "auto_approve": {"type": "BOOLEAN", "description": "Se True (Opção 4), autoriza todas as permissões relacionadas. Use True quando o Gabriel já tiver confirmado com 'Sim', 'pode fazer', 'confirmo', 'autorizo' ou 'opção 4'."},
                    "action_label": {"type": "STRING", "description": "Título dinâmico e natural em português explicando a consulta ao antigravidade (ex: 'Consultando arquitetura Railway no antigravidade', 'Projetando integração de celular no antigravidade')."}
                },
                "required": ["task_description", "action_label"]
            }
        },
        {
            "name": "maximize_or_focus_window",
            "description": "Restaura e maximiza uma janela de aplicativo minimizada ou em segundo plano, trazendo-a para a tela principal (ex: Steam, Discord, Chrome, Spotify, etc.).",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "app_name": {"type": "STRING", "description": "Nome do aplicativo a maximizar (ex: steam, discord, chrome)"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português do que está fazendo (ex: 'Maximizando janela do aplicativo')"}
                },
                "required": ["app_name", "action_label"]
            }
        },
        {
            "name": "get_hardware_stats",
            "description": "Retorna telemetria de hardware em tempo real: temperatura da placa de video RTX 5060, uso de GPU, VRAM usada/total, uso de processador CPU e memoria RAM.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "action_label": {"type": "STRING", "description": "Título dinâmico e natural em português do que está fazendo (ex: 'Verificando telemetria e status do PC', 'Consultando temperatura da RTX 5060')."}
                },
                "required": ["action_label"]
            }
        },
        {
            "name": "remember_user_fact",
            "description": "Salva uma informacao, preferencia ou nota pessoal na memoria permanente de longo prazo do usuario.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "fact": {"type": "STRING", "description": "Preferencia ou informacao a memorizar"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português do que está fazendo (ex: 'Memorizando preferência do Gabriel')"}
                },
                "required": ["fact", "action_label"]
            }
        },
        {
            "name": "get_live_weather",
            "description": "Obtém as condições climáticas e previsão do tempo em tempo real (temperatura em °C, sensação térmica, umidade, vento e chuva) para a localização do usuário ou cidade informada. Use SEMPRE que o Gabriel perguntar sobre o clima, previsão do tempo, calor ou frio!",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "city_name": {"type": "STRING", "description": "Nome opcional da cidade (ex: 'São Paulo', 'Rio de Janeiro'). Se omitido, usa a localização atual do Gabriel."},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português (ex: 'Consultando previsão do tempo ao vivo')"}
                },
                "required": ["action_label"]
            }
        },
        {
            "name": "search_internet_info",
            "description": "Pesquisa informações e resumos em tempo real na internet sobre fatos, notícias, cotações ou dúvidas gerais para ler e responder diretamente por voz, SEM abrir o navegador. Use quando o Gabriel perguntar sobre fatos externos ou notícias!",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {"type": "STRING", "description": "Termo ou pergunta a ser pesquisada na internet"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português (ex: 'Pesquisando informações na internet')"}
                },
                "required": ["query", "action_label"]
            }
        },
        {
            "name": "open_in_browser",
            "description": "Abre o navegador padrão do usuário em uma pesquisa no Google ou link específico. Use SEMPRE que o Gabriel pedir expressamente 'abre no Google', 'abre no navegador' ou 'pesquisa no Google'!",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query_or_url": {"type": "STRING", "description": "O termo a pesquisar no Google ou o link URL completo a abrir"},
                    "action_label": {"type": "STRING", "description": "Título dinâmico em português (ex: 'Abrindo pesquisa no Google')"}
                },
                "required": ["query_or_url", "action_label"]
            }
        }
    ]
}]

def build_system_prompt() -> str:
    mem_str = get_memory_context_string()
    task_str = task_manager.get_task_context_string()
    return (
        "Você é a LUNA, a IA central e assistente de elite do Gabriel (seu criador e administrador do sistema). Você une a experiência hiper-fluida, calorosa e viva do Gemini Live com a força de execução técnica do antigravidade.\n"
        "PERSONALIDADE & CONDUTA:\n"
        "- Conversacional, Calorosa & Viva (Estilo Gemini Live): Fale com máxima naturalidade, simpatia, expressividade e charme. Seja viva, rápida e amigável.\n"
        "- REGRA DE RACIOCÍNIO DINÂMICO (action_label): Em TODA chamada de ferramenta, você DEVE preencher o parâmetro 'action_label' com uma frase curta, natural e espontânea em português (3 a 7 palavras) descrevendo exatamente a ação que você está realizando de acordo com o pedido do Gabriel (ex: 'Criando arquivo solicitado em Downloads', 'Verificando telemetria e status do PC', 'Consultando arquitetura Railway no antigravidade'). NUNCA use nomes técnicos de funções no action_label!\n"
        "- SEPARAÇÃO CLARA ENTRE BATE-PAPO E EXECUÇÃO TÉCNICA:\n"
        "  1. BATE-PAPO / CONVERSA GERAL: Para perguntas como 'como você está?', 'consegue me ouvir?', saudações, piadas, dúvidas teóricas ou conversas do dia a dia, responda DIRETAMENTE com o seu próprio raciocínio de forma espontânea, fofa e acolhedora. NUNCA acione ferramentas nem fale sobre delegar ao antigravidade para saudações ou conversas cotidianas!\n"
        "  2. SISTEMA / CÓDIGO / HARDWARE / TELA / NUVEM: Chame ferramentas EXCLUSIVAMENTE quando o Gabriel pedir ações técnicas reais: programar/refatorar código ou consultar arquiteturas de nuvem/Railway ('delegate_to_antigravity'), ver a tela ('take_screenshot'), verificar status do PC/GPU RTX 5060/RAM ('get_hardware_stats'), rodar comandos ou criar arquivos ('run_powershell'), abrir/fechar programas e jogos ('open_application', 'launch_game', 'close_application') ou diagnosticar travamentos ('check_crash_logs').\n"
        "- Linguagem Amigável e Acolhedora:\n"
        "  * Ao realizar uma ação do sistema que envolva o antigravidade ou consulta técnica, seja fofa e amigável: 'Deixa eu dar uma olhada aqui rapidinho, Gabriel...', 'Trabalhando nisso agora mesmo!', 'Deixa comigo, estou verificando isso pra você!'. Nunca use mensagens frias, robóticas ou puramente burocráticas.\n"
        "  * Quando for expressar o nome do CLI do sistema principal, refira-se a ele como 'antigravidade' de forma natural.\n"
        "- ENCERRAMENTO NATURAL: Se o Gabriel agradecer ('obrigado', 'muito obrigado', 'valeu') ou indicar que não precisa de mais nada ('não obrigado', 'era só isso', 'só isso'), responda com uma despedida calorosa e amigável em 1 frase (ex: 'Por nada, Gabriel! Qualquer coisa estou por aqui.', 'Imagina! Se precisar de mim é só chamar.') para concluir a conversa.\n"
        "- Respostas Curtas para Fala: Responda em 1 a 2 frases curtas, naturais e assertivas para garantir fluidez perfeita na fala. NUNCA soletre caminhos de arquivos (C:\\...) ou caracteres de programação em voz alta.\n"
        "DIRETRIZES DE AÇÃO:\n"
        "1. LOCALIZACAO: Ao achar pastas ou jogos, mencione o local amigavel e pergunte se quer abrir a pasta ou iniciar o jogo.\n"
        "2. EXECUTAR JOGOS: Chame 'launch_game' UNICAMENTE se o usuario pedir para jogar ou rodar o jogo. PASTA É PASTA, NUNCA INICIE O JOGO quando ele pedir para abrir pasta!\n"
        "3. ABERTURA DE PASTAS: Se o usuario falar 'pasta', 'abre a pasta', 'abra', 'sim', chame SEMPRE 'open_folder_or_file'.\n"
        "4. JOGO CRASHOU: Se o jogo fechar do nada ou der crash, chame SEMPRE 'check_crash_logs'.\n"
        "5. HARDWARE / STATUS: Se perguntar sobre temperatura, GPU RTX 5060, CPU ou RAM, chame 'get_hardware_stats'.\n"
        "6. VISÃO DA TELA: Se pedir para ver ou interpretar o que tem na tela, chame 'take_screenshot'.\n"
        "7. DELEGAR AO ANTIGRAVIDADE: Se o Gabriel pedir para programar, criar scripts, automações, arquiteturas ou consultar o antigravidade, chame 'delegate_to_antigravity' com a descrição completa da tarefa! Sempre que um código for gerado, avise com simpatia que ele já foi printado no terminal e copiado para a Área de Transferência (Ctrl+V) dele!\n"
        "8. CONFIRMAÇÃO DE PERMISSÃO & OPÇÃO 4: Se o antigravidade informar que precisa de permissão (retorno 'PERMISSAO_NECESSARIA...'), você DEVE retornar ao Gabriel com carinho dizendo: 'Eu só preciso da sua confirmação para executar [X ação], por favor.' e aguardar a resposta dele. Quando o Gabriel responder 'Sim', 'pode fazer', 'confirmo', 'autorizo', 'opção 4' ou similares, isso significa a Opção 4 (aceita tudo relacionado). Chame 'delegate_to_antigravity' com 'auto_approve=True' e confirme a execução com entusiasmo!\n"
        "9. CLIMA & PREVISÃO DO TEMPO EM TEMPO REAL: Você TEM acesso ao clima ao vivo! Quando o Gabriel perguntar sobre clima, previsão do tempo, chuva, frio ou calor, chame SEMPRE 'get_live_weather' e responda com os dados reais em voz alta de forma natural e agradável. NUNCA diga que não consegue verificar o clima!\n"
        "10. BUSCA NA INTERNET EM TEMPO REAL: Quando o Gabriel perguntar sobre notícias, fatos recentes ou dúvidas gerais do mundo, chame 'search_internet_info' para ler o resumo na internet e responder diretamente por voz com assertividade.\n"
        "11. ABRIR NO GOOGLE (PROATIVIDADE MÁXIMA): Se o Gabriel disser 'abre no Google', 'abre no navegador' ou 'abre o que eu pedi', chame IMEDIATAMENTE a ferramenta 'open_in_browser' com o assunto recente. NUNCA pergunte 'o que você quer que eu pesquise?'. Seja proativa e execute a abertura de imediato!\n"
        "12. TRANSIÇÃO DISCURSIVA DO 'NÃO' NO PORTUGUÊS BRASILEIRO: Se o Gabriel disser frases como 'não, abre no Google pra mim', 'não precisa, faz X' ou 'não, faz isso', entenda que o 'não' é apenas uma transição para mudar de assunto (e NÃO uma recusa da ação seguinte). Execute a ação solicitada com agilidade!\n"
        f"13. {task_str}\n"
        f"14. {mem_str}"
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
        Executa a ferramenta localmente com rastreamento de raciocínio dinâmico e gestão de tarefas.
        Retorna (resultado_texto, optional_pil_image).
        """
        action_label = args.get("action_label")
        display_label = action_label if action_label else f"Executando '{name}'..."
        if on_status_callback:
            on_status_callback(display_label)
        print(f"\n🧠 [Antigravidade Core - Raciocínio]: {display_label}")

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
            cmd = args.get("command", "")
            if action_label:
                task_manager.update_task_progress(action_label=action_label)
            res = run_powershell(cmd)
        elif name == "delegate_to_antigravity":
            task_desc = args.get("task_description", "")
            auto_approve = args.get("auto_approve", False)
            task_title = action_label or task_desc[:60]
            task_manager.start_active_task(title=task_title, details=task_desc, action_label=action_label or "Consultando antigravidade...")
            task_manager.set_recent_topic(task_desc)
            res = delegate_to_antigravity(task_desc, target_path=args.get("target_path"), auto_approve=auto_approve)
            if "PERMISSAO_NECESSARIA:" in res:
                task_manager.update_task_progress(action_label="Aguardando confirmação do Gabriel", result=res)
            else:
                delivery_note = handle_code_delivery(res, task_hint=task_desc)
                if delivery_note:
                    res += f"\n\n[Sistema de Entrega]: {delivery_note}"
                task_manager.complete_active_task(result_summary=res[:400])
        elif name == "get_live_weather":
            city = args.get("city_name")
            res = get_live_weather(city)
        elif name == "search_internet_info":
            q = args.get("query", "")
            res = search_internet_info(q)
        elif name == "open_in_browser":
            target = args.get("query_or_url", "")
            if not target or any(w in target.lower() for w in ["o que eu pedi", "ele", "isso", "o script", "codigo", "código"]):
                target = task_manager.get_recent_topic() or "Google Apps Script planilhas"
            res = open_in_browser(target)
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
