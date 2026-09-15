import ctypes
import time
import subprocess
import webbrowser
import urllib.parse

user32 = ctypes.windll.user32

# Códigos de Teclas Virtuais do Windows
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_LWIN = 0x5B

def _press_key(vk_code):
    user32.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.04)
    user32.keybd_event(vk_code, 0, 2, 0)

is_ducked = False

def duck_audio(steps: int = 6):
    """Abaixa o volume do Windows temporariamente enquanto o usuario fala."""
    global is_ducked
    if not is_ducked:
        for _ in range(steps):
            _press_key(VK_VOLUME_DOWN)
            time.sleep(0.015)
        is_ducked = True

def unduck_audio(steps: int = 6):
    """Restaura o volume do Windows apos a interacao."""
    global is_ducked
    if is_ducked:
        for _ in range(steps):
            _press_key(VK_VOLUME_UP)
            time.sleep(0.015)
        is_ducked = False

def control_volume(action: str, percent: int = 10) -> str:
    """Controla o volume do Windows: aumentar, diminuir ou mutar."""
    act = action.lower().strip()
    steps = max(1, min(25, int(percent / 2))) # Cada passo no Windows é ~2%
    
    if "aument" in act or "up" in act or "mais" in act:
        for _ in range(steps):
            _press_key(VK_VOLUME_UP)
            time.sleep(0.02)
        return f"Volume aumentado em aproximadamente {percent}%."
    elif "diminu" in act or "down" in act or "menos" in act or "abaix" in act:
        for _ in range(steps):
            _press_key(VK_VOLUME_DOWN)
            time.sleep(0.02)
        return f"Volume reduzido em aproximadamente {percent}%."
    elif "mut" in act or "desmut" in act or "silenci" in act:
        _press_key(VK_VOLUME_MUTE)
        return "Estado de mudo alternado com sucesso."
    return "Ação de volume desconhecida."

def control_media(action: str) -> str:
    """Controla reprodução de mídia (Spotify, YouTube, VLC, etc.): play, pause, proxima, anterior."""
    act = action.lower().strip()
    if any(w in act for w in ["play", "pause", "pausar", "tocar", "continuar"]):
        _press_key(VK_MEDIA_PLAY_PAUSE)
        return "Mídia pausada ou iniciada."
    elif any(w in act for w in ["prox", "next", "avanc", "pular"]):
        _press_key(VK_MEDIA_NEXT_TRACK)
        return "Avançado para a próxima faixa."
    elif any(w in act for w in ["anter", "prev", "voltar"]):
        _press_key(VK_MEDIA_PREV_TRACK)
        return "Retornado para a faixa anterior."
    return "Ação de mídia desconhecida."

def control_windows(action: str) -> str:
    """Controla janelas e o desktop: minimizar tudo, mostrar area de trabalho."""
    act = action.lower().strip()
    if any(w in act for w in ["minimizar", "desktop", "area de trabalho", "limpar tela"]):
        # Win + D
        user32.keybd_event(VK_LWIN, 0, 0, 0)
        user32.keybd_event(0x44, 0, 0, 0) # 'D'
        time.sleep(0.05)
        user32.keybd_event(0x44, 0, 2, 0)
        user32.keybd_event(VK_LWIN, 0, 2, 0)
        return "Todas as janelas foram minimizadas, mostrando a Área de Trabalho."
    return "Ação de janela desconhecida."

def system_power(action: str, delay_minutes: int = 0) -> str:
    """Ações de energia e segurança: bloquear computador ou agendar desligamento."""
    act = action.lower().strip()
    if "bloque" in act or "lock" in act or "tranc" in act:
        user32.LockWorkStation()
        return "Computador bloqueado com sucesso."
    elif "deslig" in act or "shutdown" in act:
        seconds = max(0, delay_minutes * 60)
        subprocess.Popen(f"shutdown /s /t {seconds}", shell=True)
        if seconds > 0:
            return f"Desligamento agendado para daqui a {delay_minutes} minutos."
        return "Desligamento iniciado."
    elif "cancel" in act:
        subprocess.Popen("shutdown /a", shell=True)
        return "Agendamento de desligamento cancelado."
    return "Ação de energia não reconhecida."

def search_web_or_youtube(query: str, platform: str = "google") -> str:
    """Abre pesquisa no YouTube ou Google no navegador padrão."""
    clean_q = query.strip()
    # Proteção contra termos incompletos causados por pausas na fala
    incomplete_fillers = ["porque que", "por que que", "por que", "porque", "como que", "o que", "quem que", "qual que", "onde que"]
    if clean_q.lower() in incomplete_fillers or len(clean_q) < 3:
        return f"A busca '{clean_q}' parece incompleta. Pergunte ao usuário o que exatamente ele gostaria de pesquisar."

    encoded = urllib.parse.quote(clean_q)
    if "youtube" in platform.lower():
        url = f"https://www.youtube.com/results?search_query={encoded}"
        webbrowser.open(url)
        return f"Pesquisa aberta no YouTube para: '{clean_q}'."
    else:
        url = f"https://www.google.com/search?q={encoded}"
        webbrowser.open(url)
        return f"Pesquisa aberta no Google para: '{clean_q}'."
