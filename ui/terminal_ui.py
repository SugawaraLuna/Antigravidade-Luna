import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import ctypes
import re

# Habilitar suporte a ANSI Escape Codes no Windows
if sys.platform == "win32":
    try:
        kernel32 = ctypes.windll.kernel32
        h_out = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(h_out, ctypes.byref(mode))
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        kernel32.SetConsoleMode(h_out, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
    except Exception:
        pass

# Paleta de Cores ANSI (Luna Theme: Preto e Roxo Profundo)
PURPLE_MAIN = "\033[38;2;168;85;247m"     # #A855F7 (Roxo Luna)
PURPLE_BRIGHT = "\033[38;2;216;180;254m"  # #D8B4FE (Roxo Neon / Título)
PURPLE_DARK = "\033[38;2;126;34;206m"     # #7E22CE (Roxo Escuro / Bordas)
PURPLE_BG = "\033[48;2;30;15;48m"        # Fundo Roxo Escuro
TEXT_WHITE = "\033[38;2;248;250;252m"     # Texto Branco
TEXT_MUTED = "\033[38;2;148;163;184m"     # Texto Cinza / Dim
GREEN_DIFF = "\033[38;2;74;222;128m"      # #4ADE80 (Verde Adição)
RED_DIFF = "\033[38;2;248;113;113m"       # #F87171 (Vermelho Exclusão)
YELLOW_WARN = "\033[38;2;251;191;36m"     # #FBBF24 (Amarelo Alerta)
CYAN_ACCENT = "\033[38;2;56;189;248m"     # #38BDF8 (Ciano Hunk / @@)
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"

def render_luna_banner():
    """Renderiza o banner futurista da Luna em Preto e Roxo estilo Gemini CLI / Claude Code."""
    banner_art = f"""{PURPLE_MAIN}{BOLD}
    ██╗     ██╗   ██╗███╗   ██╗ █████╗     █████╗ ██╗
    ██║     ██║   ██║████╗  ██║██╔══██╗   ██╔══██╗██║
    ██║     ██║   ██║██╔██╗ ██║███████║   ███████║██║
    ██║     ██║   ██║██║╚██╗██║██╔══██║   ██╔══██║██║
    ███████╗╚██████╔╝██║ ╚████║██║  ██║██╗██║  ██║██║
    ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝╚═╝  ╚═╝╚═╝{RESET}"""
    print(banner_art)
    print(f"{PURPLE_DARK}──────────────────────────────────────────────────────────────────────{RESET}")
    print(f" {PURPLE_BRIGHT}{BOLD}🌙 LUNA v3.0{RESET}")
    print(f" {TEXT_MUTED}Status:{RESET} {GREEN_DIFF}[● SUPERUSUÁRIO ATIVO]{RESET} {PURPLE_MAIN}[● NÚCLEO ONLINE]{RESET} {CYAN_ACCENT}[● VOZ LIVE 24kHz]{RESET}")
    print(f"{PURPLE_DARK}──────────────────────────────────────────────────────────────────────{RESET}")
    print(f" {PURPLE_BRIGHT}Atalhos:{RESET} {TEXT_WHITE}[F8]{RESET} {TEXT_MUTED}Voz Manual{RESET} │ {TEXT_WHITE}[ESC/F9]{RESET} {TEXT_MUTED}Pânico{RESET} │ {TEXT_WHITE}/sair{RESET} {TEXT_MUTED}Fechar{RESET} │ {TEXT_WHITE}/rollback{RESET} {TEXT_MUTED}Desfazer{RESET} │ {TEXT_WHITE}/reiniciar{RESET}")
    print(f" {PURPLE_BRIGHT}Terminal:{RESET} {TEXT_WHITE}Digite abaixo ou fale com a Luna.{RESET}")
    print(f"{PURPLE_DARK}──────────────────────────────────────────────────────────────────────{RESET}\n")

def render_codes_card(title: str, codes: list, subtitle: str = ""):
    """Desenha um card de códigos e itens para seleção fácil com o mouse no terminal."""
    if not codes:
        return
    print(f"\n{PURPLE_MAIN}┌─── 🎮 [{title.upper()}]{RESET}{PURPLE_MAIN} ──────────────────────────────────────{RESET}")
    if subtitle:
        print(f"{PURPLE_MAIN}│{RESET}  {TEXT_WHITE}{subtitle}{RESET}")
        print(f"{PURPLE_MAIN}│{RESET}")
    for item in codes:
        code_str = item.strip(" ,.;:")
        if code_str:
            print(f"{PURPLE_MAIN}│{RESET}    {CYAN_ACCENT}• {BOLD}{code_str}{RESET}")
    print(f"{PURPLE_MAIN}├──────────────────────────────────────────────────────────────────{RESET}")
    print(f"{PURPLE_MAIN}│{RESET}  {GREEN_DIFF}💡 Selecione com o mouse no terminal para copiar direto!{RESET}")
    print(f"{PURPLE_MAIN}└──────────────────────────────────────────────────────────────────{RESET}\n")

    # Copiar automaticamente todos os códigos para a Área de Transferência
    try:
        from tools.clipboard_tools import copy_to_clipboard
        copy_to_clipboard("\n".join(codes))
    except Exception:
        pass

def detect_and_render_codes_from_text(text: str, user_query: str = "") -> bool:
    """Detecta automaticamente se a resposta contém códigos promocionais/de jogos e os desenha em um card."""
    if not text:
        return False
    
    query_hint = any(w in (user_query or "").lower() for w in ["codigo", "código", "codes", "cupom", "cupons", "promo"])
    text_hint = any(w in text.lower() for w in ["código", "codigo", "codes", "ativo", "resgatar"])
    
    if not (query_hint or text_hint):
        return False

    # Regex para capturar sequências em MAIÚSCULAS típicas de códigos (ex: REACTOR, FREEDOM, 2026_CODE, NEBULA)
    matches = re.findall(r'\b[A-Z0-9_\-]{4,25}\b', text)
    stopwords = {
        "LUNA", "ROBLOX", "DISCORD", "TWITTER", "YOUTUBE", "GOOGLE",
        "WINDOWS", "POWER", "STATUS", "ENTER", "CLIQUE", "JOGO", "GAMES",
        "ONLINE", "STREAMING", "MAIS", "PARA", "ESTE", "ESSES", "ALGUNS", "TODOS",
        "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO", "JANEIRO", "FEVEREIRO", "MARCO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO"
    }
    codes = [m for m in matches if m not in stopwords]
    # Remover duplicatas mantendo a ordem
    unique_codes = list(dict.fromkeys(codes))
    if unique_codes:
        render_codes_card("Códigos Encontrados", unique_codes, "Selecione e copie os códigos abaixo:")
        return True
    return False

def render_activity_box(action_title: str, details: str = ""):
    """Exibe um card roxo indicando ação do Antigravidade em tempo real."""
    print(f"\n{PURPLE_MAIN}┌─── ⚡ {BOLD}[ANTIGRAVIDADE: {action_title.upper()}]{RESET}{PURPLE_MAIN} ─────────────────────────────{RESET}")
    if details:
        for line in details.strip().split("\n"):
            print(f"{PURPLE_MAIN}│{RESET}  {TEXT_WHITE}{line}{RESET}")
    print(f"{PURPLE_MAIN}└──────────────────────────────────────────────────────────────────{RESET}\n")

def render_diff_log(diff_text: str, title: str = "LOG DE ALTERAÇÕES (DIFF UNIFICADO)"):
    """
    Renderiza um bloco de diff idêntico à interface visual do Antigravidade:
    - Linhas adicionadas (+) em verde
    - Linhas excluídas (-) em vermelho
    - Cabeçalhos de hunk (@@ ... @@) em ciano
    - Arquivos afetados em roxo neon
    """
    if not diff_text or not diff_text.strip():
        print(f"{TEXT_MUTED}[Nenhuma alteração de linhas registrada]{RESET}")
        return

    lines = diff_text.strip().split("\n")
    added_count = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
    removed_count = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))

    print(f"\n{PURPLE_DARK}┌─── {PURPLE_BRIGHT}{BOLD}📝 {title}{RESET} {GREEN_DIFF}+{added_count}{RESET} {RED_DIFF}-{removed_count}{RESET} {PURPLE_DARK}──────────────────────────────{RESET}")
    
    for line in lines:
        if line.startswith("diff --git") or line.startswith("index "):
            print(f"{PURPLE_DARK}│{RESET}  {TEXT_MUTED}{line}{RESET}")
        elif line.startswith("--- ") or line.startswith("+++ "):
            print(f"{PURPLE_DARK}│{RESET}  {PURPLE_BRIGHT}{BOLD}{line}{RESET}")
        elif line.startswith("@@"):
            print(f"{PURPLE_DARK}│{RESET}  {CYAN_ACCENT}{line}{RESET}")
        elif line.startswith("+"):
            print(f"{PURPLE_DARK}│{RESET}  {GREEN_DIFF}{line}{RESET}")
        elif line.startswith("-"):
            print(f"{PURPLE_DARK}│{RESET}  {RED_DIFF}{line}{RESET}")
        else:
            print(f"{PURPLE_DARK}│{RESET}  {TEXT_MUTED}{line}{RESET}")

    print(f"{PURPLE_DARK}└──────────────────────────────────────────────────────────────────{RESET}\n")

def render_proposal_report(proposal: dict):
    """Renderiza o relatório de entendimento da Luna antes de aplicar alterações."""
    target = proposal.get("target_agent", "Luna").upper()
    understanding = proposal.get("understanding", "")
    files = proposal.get("affected_files", [])
    action = proposal.get("action_summary", "")

    print(f"\n{PURPLE_MAIN}╔══════════════════════════════════════════════════════════════════════╗{RESET}")
    print(f"{PURPLE_MAIN}║{RESET}  {PURPLE_BRIGHT}{BOLD}📋 RELATÓRIO DE ALTERAÇÃO DE CÓDIGO - ALVO: [{target}]{RESET}")
    print(f"{PURPLE_MAIN}╠══════════════════════════════════════════════════════════════════════╣{RESET}")
    print(f"{PURPLE_MAIN}║{RESET}  {BOLD}{TEXT_WHITE}O que a Luna entendeu:{RESET}")
    print(f"{PURPLE_MAIN}║{RESET}    {TEXT_WHITE}{understanding}{RESET}")
    print(f"{PURPLE_MAIN}║{RESET}")
    print(f"{PURPLE_MAIN}║{RESET}  {BOLD}{TEXT_WHITE}Arquivos previstos para alteração:{RESET}")
    for f in files:
        print(f"{PURPLE_MAIN}║{RESET}    {CYAN_ACCENT}• {f}{RESET}")
    if not files:
        print(f"{PURPLE_MAIN}║{RESET}    {TEXT_MUTED}• Módulos identificados dinamicamente pelo Antigravidade{RESET}")
    print(f"{PURPLE_MAIN}║{RESET}")
    print(f"{PURPLE_MAIN}║{RESET}  {BOLD}{TEXT_WHITE}Ação a ser executada no Antigravidade:{RESET}")
    print(f"{PURPLE_MAIN}║{RESET}    {TEXT_WHITE}{action}{RESET}")
    print(f"{PURPLE_MAIN}║{RESET}")
    print(f"{PURPLE_MAIN}║{RESET}  {YELLOW_WARN}{BOLD}⚠️  Aguardando sua autorização explícita para prosseguir.{RESET}")
    print(f"{PURPLE_MAIN}║{RESET}  {TEXT_MUTED}Diga ou digite 'Sim' / 'Pode fazer' / 'Confirmo' para aplicar.{RESET}")
    print(f"{PURPLE_MAIN}╚══════════════════════════════════════════════════════════════════════╝{RESET}\n")

def render_code_card(lang: str, code: str, copied: bool = True, saved_path: str = None):
    """Exibe código formatado no terminal com realce em roxo."""
    print(f"\n{PURPLE_MAIN}┌─── 📋 [CÓDIGO GERADO - LINGUAGEM: {lang.upper()}]{RESET}{PURPLE_MAIN} ───────────────────────{RESET}")
    for line in code.split("\n"):
        print(f"{PURPLE_MAIN}│{RESET}  {TEXT_WHITE}{line}{RESET}")
    print(f"{PURPLE_MAIN}├──────────────────────────────────────────────────────────────────{RESET}")
    if copied:
        print(f"{PURPLE_MAIN}│{RESET}  {GREEN_DIFF}✓ Copiado para a Área de Transferência (Ctrl+V){RESET}")
    if saved_path:
        print(f"{PURPLE_MAIN}│{RESET}  {CYAN_ACCENT}✓ Arquivo salvo em: {saved_path}{RESET}")
    print(f"{PURPLE_MAIN}└──────────────────────────────────────────────────────────────────{RESET}\n")
