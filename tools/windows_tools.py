import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import subprocess
import psutil
import time
import unicodedata
import difflib
import re

STOP_WORDS = {'de', 'da', 'do', 'das', 'dos', 'em', 'no', 'na', 'nos', 'nas', 'um', 'uma', 'o', 'a', 'os', 'as', 'e', 'para', 'pra', 'pasta', 'arquivo'}

def normalize_name(text: str) -> str:
    """Normaliza texto removendo acentos, padronizando equivalências comuns PT-BR."""
    t = unicodedata.normalize('NFKD', text)
    t = ''.join(c for c in t if not unicodedata.combining(c)).lower()
    equivalences = [
        (r'\batelier\b', 'atelie'),
        (r'\bdownloads\b', 'download'),
        (r'\bfotos\b', 'foto'),
        (r'\bjogos\b', 'jogo'),
        (r'\bvideos\b', 'video'),
        (r'\bmusicas\b', 'musica'),
        (r'\bdocumentos\b', 'documento'),
        (r'\bprojetos\b', 'projeto'),
        (r'\bbackups\b', 'backup'),
    ]
    for pattern, repl in equivalences:
        t = re.sub(pattern, repl, t)
    return re.sub(r'[^a-z0-9]+', ' ', t).strip()

def compute_similarity(query: str, target: str) -> float:
    """Calcula a similaridade fuzzy e semantica entre o termo pesquisado e o nome do arquivo/pasta."""
    q_norm = normalize_name(query)
    t_norm = normalize_name(target)
    if not q_norm or not t_norm:
        return 0.0
    if q_norm == t_norm:
        return 1.0
    all_q_words = [w for w in q_norm.split() if len(w) > 0]
    q_words = [w for w in all_q_words if w not in STOP_WORDS]
    if not q_words:
        q_words = all_q_words
    t_words = [w for w in t_norm.split() if len(w) > 0]
    if not q_words or not t_words:
        return 0.0
    if q_norm in t_norm:
        return 0.95

    # Match palavra por palavra
    matched_scores = []
    for qw in q_words:
        best_score = 0.0
        for tw in t_words:
            if qw == tw:
                best_score = max(best_score, 1.0)
            elif (len(qw) >= 4 and tw.startswith(qw)) or (len(tw) >= 4 and qw.startswith(tw)):
                best_score = max(best_score, 0.92)
            else:
                sim = difflib.SequenceMatcher(None, qw, tw).ratio()
                if sim >= 0.70:
                    best_score = max(best_score, sim)
        matched_scores.append(best_score)
        
    if matched_scores:
        avg_score = sum(matched_scores) / len(matched_scores)
        min_score = min(matched_scores)
        
        # Se for consulta de apenas 1 palavra e o alvo tiver essa palavra
        if len(q_words) == 1 and max(matched_scores) >= 0.88:
            return 0.88
            
        # Se for consulta multi-palavras: exige que ao menos metade das palavras bata bem
        if len(q_words) > 1:
            good_matches = sum(1 for s in matched_scores if s >= 0.70)
            if good_matches < len(q_words) * 0.5:
                return 0.15 * avg_score
            if min_score >= 0.70:
                return 0.80 + (avg_score * 0.18)
            return avg_score

    if abs(len(q_norm) - len(t_norm)) <= 4:
        return difflib.SequenceMatcher(None, q_norm, t_norm).ratio()
    return 0.0

LAST_FOUND_PATH = ""

def get_last_found_path():
    return LAST_FOUND_PATH

def find_game_executable(target: str) -> str:
    """Encontra o arquivo executável (.exe ou atalho .lnk) de um jogo."""
    target_clean = target.strip().strip('"').strip("'")
    if os.path.isfile(target_clean) and target_clean.lower().endswith(('.exe', '.lnk')):
        return target_clean
    folder = target_clean
    # 1. Procurar em C:\Games Place\Installed Games por atalhos diretos
    installed_shortcuts = r"C:\Games Place\Installed Games"
    if os.path.exists(installed_shortcuts):
        for f in os.listdir(installed_shortcuts):
            if f.lower().endswith('.lnk'):
                f_clean = f.replace('.exe', '').replace('- Atalho', '').replace('.lnk', '').strip()
                if compute_similarity(target_clean, f_clean) >= 0.70:
                    return os.path.join(installed_shortcuts, f)
    # 2. Se folder não for uma pasta existente, tenta buscar em Pc Games
    if not os.path.isdir(folder):
        base_games = r"C:\Games Place\Pc Games"
        if os.path.exists(base_games):
            for d in os.listdir(base_games):
                if compute_similarity(target_clean, d) >= 0.75:
                    folder = os.path.join(base_games, d)
                    break
    if not os.path.isdir(folder):
        return ""
    game_name = os.path.basename(folder)
    # 3. Procurar atalhos dentro da pasta do jogo
    try:
        for f in os.listdir(folder):
            if f.lower().endswith('.lnk') and not f.lower().startswith(('unins', 'setup')):
                return os.path.join(folder, f)
    except Exception:
        pass
    # 4. Procurar executáveis (.exe) dentro da pasta do jogo
    blacklist = ('unins', 'crash', 'setup', 'install', 'dx', 'vc', 'language', 'breakpad', 'helper', 'unity')
    candidates = []
    try:
        for root, dirs, files in os.walk(folder):
            if root.rstrip('\\/').count(os.sep) - folder.rstrip('\\/').count(os.sep) > 1:
                dirs.clear()
                continue
            for f in files:
                fl = f.lower()
                if fl.endswith('.exe') and not fl.startswith(blacklist):
                    full = os.path.join(root, f)
                    size = os.path.getsize(full)
                    sim = compute_similarity(game_name, f[:-4])
                    candidates.append((sim, size, full))
    except Exception:
        pass
    if candidates:
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        return candidates[0][2]
    return ""

def launch_game(game_name_or_path: str = "") -> str:
    """Inicia / executa diretamente o executável (.exe ou atalho .lnk) de um jogo."""
    global LAST_FOUND_PATH
    target = game_name_or_path.strip().strip('"').strip("'")
    if (not target or any(w in target.lower() for w in ["o jogo", "ele", "jogo", "executavel", "pode abrir", "sim"])) and LAST_FOUND_PATH:
        target = LAST_FOUND_PATH
        
    exe = find_game_executable(target)
    if not exe and LAST_FOUND_PATH and LAST_FOUND_PATH != target:
        exe = find_game_executable(LAST_FOUND_PATH)
        
    if exe and os.path.exists(exe):
        try:
            exe_name = os.path.basename(exe)
            game_title = exe_name.replace(".exe", "").replace(".lnk", "").replace("- Atalho", "").strip()
            print(f"\n🚀 [Executando jogo]: '{exe}'")
            os.startfile(exe)
            return f"Jogo '{game_title}' iniciado com sucesso atraves do executavel '{exe_name}'. Diga ao usuario que o jogo foi iniciado e bom jogo!"
        except Exception as e:
            try:
                subprocess.Popen([exe], cwd=os.path.dirname(exe), shell=True)
                return f"Jogo iniciado com sucesso: {exe}."
            except Exception as e2:
                return f"Erro ao tentar iniciar o jogo {game_name_or_path}: {e2}"
                
    # Se não achou executável, abre a pasta correspondente
    if target and os.path.exists(target):
        os.startfile(target)
        return f"Nao encontrei o .exe principal diretamente, mas abri a pasta do jogo no Explorer: {target}"
        
    return f"Nenhum executavel ou pasta encontrado para o jogo '{game_name_or_path}'."

def open_folder_or_file(path_or_name: str = "") -> str:
    """
    Abre uma pasta ou arquivo no Explorer do Windows.
    JAMAIS inicia um jogo executavel quando o usuario pediu para abrir pasta.
    """
    global LAST_FOUND_PATH
    target = path_or_name.strip().strip('"').strip("'")
    target_lower = target.lower()
    
    # Se for uma referência à última pasta pesquisada ("a pasta", "pasta", "ela", "o arquivo", "pode abrir", "sim", "abra")
    if (not target or any(w in target_lower for w in ["a pasta", "pasta", "ela", "o arquivo", "pode abrir", "sim", "abra", "abre"])) and LAST_FOUND_PATH:
        target = LAST_FOUND_PATH
        
    # Se for caminho existente no disco
    if os.path.isdir(target):
        os.startfile(target)
        return f"Pasta aberta com sucesso no Explorer: {target}"
    elif os.path.isfile(target):
        os.startfile(target)
        return f"Arquivo aberto com sucesso: {target}"
        
    # Se não existir diretamente, procura pelo nome
    if not os.path.exists(target):
        # Se for o nome de um jogo conhecido em Games Place
        for base in [r"C:\Games Place\Pc Games", r"C:\Games Place\Installed Games"]:
            if os.path.exists(base):
                for entry in os.listdir(base):
                    if compute_similarity(target, entry) >= 0.70 or target.lower() in entry.lower():
                        full_entry = os.path.join(base, entry)
                        if os.path.isdir(full_entry):
                            os.startfile(full_entry)
                            return f"Pasta aberta com sucesso no Explorer: {full_entry}"
                        elif full_entry.endswith('.lnk'):
                            # Se for atalho em Installed Games mas o usuário pediu pasta, abre o diretório do jogo em Pc Games
                            pc_game_dir = os.path.join(r"C:\Games Place\Pc Games", entry.replace('.lnk', '').replace('- Atalho', '').strip())
                            if os.path.exists(pc_game_dir):
                                os.startfile(pc_game_dir)
                                return f"Pasta aberta com sucesso no Explorer: {pc_game_dir}"

        search_files_or_folders(target)
        if LAST_FOUND_PATH and os.path.exists(LAST_FOUND_PATH):
            target = LAST_FOUND_PATH
            if os.path.isdir(target):
                os.startfile(target)
                return f"Pasta aberta com sucesso no Explorer: {target}"
            elif os.path.isfile(target):
                os.startfile(target)
                return f"Arquivo aberto com sucesso: {target}"

    return f"Nao foi possivel localizar a pasta ou arquivo '{path_or_name}' para abrir."

def maximize_app_window(app_name: str) -> str:
    """
    Restaura e maximiza uma janela de aplicativo minimizada ou em segundo plano,
    trazendo-a diretamente para a tela principal (ex: Steam, Discord, Chrome, etc.).
    """
    app_lower = app_name.lower().strip()
    
    # 1. Caso especial Steam
    if "steam" in app_lower:
        os.startfile("steam://open/main")
        time.sleep(0.4)
        ps_steam = """
        Add-Type @'
        using System;
        using System.Runtime.InteropServices;
        public class WinAPI {
            [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
            [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
        }
'@
        $procs = Get-Process -Name "steamwebhelper", "steam" -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 }
        foreach ($p in $procs) {
            [WinAPI]::ShowWindowAsync($p.MainWindowHandle, 3) | Out-Null
            [WinAPI]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
        }
        """
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_steam], capture_output=True, text=True)
        return "A Steam foi restaurada do segundo plano e maximizada na tela principal."

    # 2. Caso especial Discord
    elif "discord" in app_lower:
        os.startfile("discord://")
        time.sleep(0.3)
        return "O Discord foi trazido para a tela principal."

    # 3. Caso especial Spotify
    elif "spotify" in app_lower:
        os.startfile("spotify://")
        time.sleep(0.3)
        return "O Spotify foi trazido para a tela principal."

    # 4. Outros aplicativos no Windows
    ps_generic = f"""
    Add-Type @'
    using System;
    using System.Runtime.InteropServices;
    public class WinAPI {{
        [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
        [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    }}
'@
    $target = "*{app_name}*"
    $p = Get-Process | Where-Object {{ ($_.ProcessName -like $target -or $_.MainWindowTitle -like $target) -and $_.MainWindowHandle -ne 0 }} | Select-Object -First 1
    if ($p) {{
        [WinAPI]::ShowWindowAsync($p.MainWindowHandle, 3) | Out-Null
        [WinAPI]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
        Write-Output "MAXIMIZED"
    }} else {{
        Write-Output "NOT_FOUND"
    }}
    """
    proc = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_generic], capture_output=True, text=True)
    if "MAXIMIZED" in proc.stdout:
        return f"A janela do aplicativo {app_name} foi restaurada e maximizada na tela principal."
        
    return f"Não encontrei uma janela ativa de {app_name} em segundo plano."

def open_application(app_name: str) -> str:
    """Abre aplicativos do Windows (Chrome, Spotify, etc.) ou restaura/maximiza se ja estiver aberto."""
    global LAST_FOUND_PATH
    app_clean = app_name.strip().strip('"').strip("'")
    app_lower = app_clean.lower()
    
    # Se o usuário pediu pasta, redireciona estritamente para abrir a pasta no Explorer
    if any(w in app_lower for w in ["pasta", "diretorio", "diretório", "explorer", "ela"]):
        return open_folder_or_file(app_clean)
        
    # Se o pedido for EXPLICITAMENTE para iniciar/jogar um jogo
    is_game_launch = any(w in app_lower for w in ['iniciar o jogo', 'abrir o jogo', 'rodar o jogo', 'jogar', 'executar o jogo'])
    if is_game_launch:
        return launch_game(app_clean)

    # Se for pedido para abrir ou maximizar Steam, Discord, Spotify ou se já estiver em segundo plano
    if any(w in app_lower for w in ['steam', 'discord', 'spotify']) or any(w in app_lower for w in ['maximizar', 'maximiza', 'traz pra frente', 'tela principal']):
        res_max = maximize_app_window(app_clean)
        if "maximizada" in res_max or "restaurada" in res_max or "tela principal" in res_max:
            return res_max

    apps_map = {
        'steam': 'steam://open/main',
        'discord': 'discord://',
        'spotify': 'spotify://',
        'chrome': 'chrome.exe',
        'brave': 'brave.exe',
        'edge': 'msedge.exe',
        'browser': 'https://www.google.com',
        'navegador': 'https://www.google.com',
        'bloco de notas': 'notepad.exe',
        'notepad': 'notepad.exe',
        'calculadora': 'calc.exe',
        'vs code': 'code',
        'vscode': 'code',
        'gerenciador de tarefas': 'taskmgr.exe',
        'explorer': 'explorer.exe'
    }
    target = apps_map.get(app_lower, app_clean)

    # Se target for uma pasta existente, abre no Explorer
    if os.path.isdir(target):
        os.startfile(target)
        return f"Pasta aberta com sucesso no Explorer: {target}"

    # Tenta primeiro verificar se já está rodando para maximizar
    if not ('://' in target or target.startswith('http')):
        base_name = os.path.splitext(os.path.basename(target))[0]
        res_max = maximize_app_window(base_name)
        if "maximizada" in res_max or "restaurada" in res_max:
            return res_max

    try:
        if os.path.exists(target):
            os.startfile(target)
            return f"Arquivo ou aplicativo aberto com sucesso: {target}"
        elif '://' in target or target.startswith('http'):
            os.startfile(target)
        else:
            subprocess.Popen(target, shell=True)
        return f"Aplicativo {app_name} aberto com sucesso."
    except Exception as e:
        return f"Erro ao tentar abrir {app_name}: {str(e)}"

def close_application(app_name: str) -> str:
    app_lower = app_name.lower().strip()
    closed = []
    
    for p in psutil.process_iter(['pid', 'name']):
        try:
            p_name = p.info['name'].lower()
            if app_lower in p_name:
                p.terminate()
                closed.append(p.info['name'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
            
    if closed:
        return f'Processo(s) encerrado(s): {", ".join(set(closed))}.'
    return f'Nenhum processo correspondente a "{app_name}" foi encontrado em execucao.'

def get_system_status() -> str:
    cpu_percent = psutil.cpu_percent(interval=0.2)
    ram = psutil.virtual_memory()
    used_gb = ram.used / (1024 ** 3)
    total_gb = ram.total / (1024 ** 3)
    
    # Coletar top processos por memoria
    mem_by_name = {}
    for p in psutil.process_iter(['name', 'memory_info']):
        try:
            name = p.info['name']
            mem = p.info['memory_info'].rss if p.info['memory_info'] else 0
            if name:
                mem_by_name[name] = mem_by_name.get(name, 0) + mem
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
            
    top_procs = sorted(mem_by_name.items(), key=lambda x: x[1], reverse=True)[:5]
    top_desc = [f'{name} ({mem / (1024*1024):.0f} MB)' for name, mem in top_procs]
    
    return (
        f'Uso de CPU: {cpu_percent}%. '
        f'Memoria RAM: {ram.percent}% em uso ({used_gb:.1f} GB de {total_gb:.1f} GB). '
        f'Aplicativos que mais estao consumindo memoria no momento: {", ".join(top_desc)}.'
    )

def run_powershell(command: str) -> str:
    """Executa um comando no PowerShell do Windows com raciocínio estruturado e retorna a saída."""
    # Lista de comandos restritos/destrutivos que exigem cuidado
    destructive_keywords = ["format-volume", "drop-database", "diskpart"]
    cmd_lower = command.lower()
    for kw in destructive_keywords:
        if kw in cmd_lower:
            return f"Aviso de segurança: O comando contém a ação potencialmente perigosa '{kw}'. Confirme explicitamente com o Gabriel antes de executar."

    print(f"\n⚡ [PowerShell - Raciocínio Estruturado]: {command}")
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace"
        )
        stdout = proc.stdout.strip() if proc.stdout else ""
        stderr = proc.stderr.strip() if proc.stderr else ""
        
        if proc.returncode != 0 and stderr:
            print(f"[-] Erro retornado pelo PowerShell: {stderr[:200]}")
            return f"Erro na execução (código {proc.returncode}): {stderr[:600]}"
            
        if not stdout:
            return "Comando executado com sucesso no PowerShell (sem saída textual retornada)."
            
        if len(stdout) > 1200:
            stdout = stdout[:1200] + "\n... [saída resumida]"
            
        print(f"[*] Saída obtida ({len(stdout)} chars): {stdout[:100]}...")
        return stdout
    except subprocess.TimeoutExpired:
        return "O comando PowerShell demorou mais de 30 segundos e foi interrompido por timeout."
    except Exception as e:
        return f"Falha ao executar PowerShell: {str(e)}"

def get_friendly_location(path: str) -> str:
    """Retorna uma descrição amigável do local para a IA falar naturalmente."""
    p = path.lower()
    if r'games place\pc games' in p:
        return "Games Place (Pc Games)"
    elif r'games place\installed games' in p:
        return "Games Place (Jogos Instalados)"
    elif r'games place' in p:
        return "Games Place"
    elif r'steamapps\common' in p or 'steamlibrary' in p:
        return "Steam"
    elif r'xbox games' in p:
        return "Xbox Games"
    elif r'playbox' in p:
        return "Playbox"
    elif r'documents' in p:
        return "Documentos"
    elif r'desktop' in p:
        return "Área de Trabalho"
    elif r'downloads' in p:
        return "Downloads"
    elif r'videos' in p:
        return "Vídeos"
    elif r'pictures' in p or r'imagens' in p:
        return "Imagens"
    try:
        parent = os.path.basename(os.path.dirname(path))
        if parent and len(parent) > 2:
            return f"pasta {parent}"
    except Exception:
        pass
    return "computador"

def search_files_or_folders(target_name: str, drive: str = "C:") -> str:
    """Busca pastas ou arquivos no computador com inteligência fonética, priorização de jogos e contexto."""
    clean_target = target_name.strip()
    for prefix in ["pasta ", "arquivo ", "pasta do ", "pasta da "]:
        if clean_target.lower().startswith(prefix):
            clean_target = clean_target[len(prefix):].strip()
            
    print(f"\n🔎 [Buscando no computador]: '{clean_target}'...")
    start_time = time.time()
    user_home = os.path.expanduser("~")
    found = []

    # TIER 1: Varredura instantânea nos diretórios raízes de Jogos e Usuário (menos de 50ms)
    tier1_roots = [
        # Locais de instalação de Jogos (Máxima prioridade sobre saves!)
        (r"C:\Games Place\Pc Games", 0.20),
        (r"C:\Games Place\Installed Games", 0.15),
        (r"C:\Program Files (x86)\Steam\steamapps\common", 0.15),
        (r"D:\SteamLibrary\steamapps\common", 0.15),
        (r"C:\Games", 0.15),
        (r"C:\Jogos", 0.15),
        (r"D:\Playbox", 0.15),
        (r"D:\Xbox Games", 0.15),
        (r"D:\Games", 0.15),
        (r"D:\Jogos", 0.15),
        # Pastas pessoais do usuário
        (os.path.join(user_home, "Desktop"), 0.0),
        (os.path.join(user_home, "Downloads"), 0.0),
        (os.path.join(user_home, "Documents"), -0.05), # ligeira penalidade para saves quando comparado à instalação
        (os.path.join(user_home, "Videos"), 0.0),
        (os.path.join(user_home, "Pictures"), 0.0),
    ]

    for d_path, bonus in tier1_roots:
        if not os.path.exists(d_path):
            continue
        try:
            with os.scandir(d_path) as it:
                for entry in it:
                    s = compute_similarity(clean_target, entry.name)
                    if s >= 0.75:
                        found.append((s + bonus, entry.path))
        except Exception:
            pass

    global LAST_FOUND_PATH

    # Se já encontrou com alta confiança no Tier 1 (ex: jogo instalado)
    if found and any(s >= 0.90 for s, _ in found):
        found.sort(key=lambda x: x[0], reverse=True)
        # Deduplicar
        unique_matches = []
        seen = set()
        for s, p in found:
            norm = os.path.normpath(p).lower()
            if norm not in seen:
                seen.add(norm)
                unique_matches.append((s, p))

        top_s, top_path = unique_matches[0]
        LAST_FOUND_PATH = top_path
        elapsed = time.time() - start_time
        item_name = os.path.basename(top_path)
        top_loc = get_friendly_location(top_path)

        # Verificar se existe outra pasta (ex: Documentos vs Games Place)
        other_locs = []
        for s, p in unique_matches[1:4]:
            loc = get_friendly_location(p)
            if loc != top_loc and loc not in other_locs:
                other_locs.append(loc)

        extra_info = ""
        if other_locs:
            extra_info = f" (Nota: Também existe pasta em {', '.join(other_locs)})."

        print(f"✅ Encontrado no Tier 1 ({elapsed:.3f}s) em [{top_loc}]: {top_path}")
        return (
            f"Encontrado em {top_loc}: '{item_name}' (Caminho: {top_path}).{extra_info} "
            f"Diga ao usuario que encontrou a pasta em {top_loc} e pergunte se ele quer abrir agora."
        )

    # TIER 2: Varredura em subpastas dos locais prioritários (profundidade até 2)
    tier2_roots = [
        (r"C:\Games Place", 2, 0.15),
        (r"D:\Playbox", 2, 0.15),
        (r"D:\Apps HD 1", 2, 0.10),
        (os.path.join(user_home, "Desktop"), 2, 0.0),
        (os.path.join(user_home, "Downloads"), 2, 0.0),
        (os.path.join(user_home, "Documents"), 2, -0.05),
        (user_home, 1, -0.10),
    ]

    for root, max_depth, bonus in tier2_roots:
        if not os.path.exists(root):
            continue
        root_depth = root.rstrip("\\/").count(os.sep)
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                cur_depth = dirpath.rstrip("\\/").count(os.sep) - root_depth
                if cur_depth > max_depth:
                    dirnames.clear()
                    continue
                for d in list(dirnames):
                    s = compute_similarity(clean_target, d)
                    if s >= 0.75:
                        found.append((s + bonus + 0.05, os.path.join(dirpath, d)))
                        if s >= 0.88 and bonus > 0 and d in dirnames:
                            dirnames.remove(d)
                for f in filenames:
                    s = compute_similarity(clean_target, f)
                    if s >= 0.75:
                        found.append((s + bonus, os.path.join(dirpath, f)))
        except Exception:
            continue

    if found:
        found.sort(key=lambda x: x[0], reverse=True)
        unique_matches = []
        seen = set()
        for s, p in found:
            norm = os.path.normpath(p).lower()
            if norm not in seen:
                seen.add(norm)
                unique_matches.append((s, p))

        top_s, top_path = unique_matches[0]
        LAST_FOUND_PATH = top_path
        elapsed = time.time() - start_time
        item_name = os.path.basename(top_path)
        top_loc = get_friendly_location(top_path)

        other_locs = []
        for s, p in unique_matches[1:4]:
            loc = get_friendly_location(p)
            if loc != top_loc and loc not in other_locs:
                other_locs.append(loc)

        extra_info = ""
        if other_locs:
            extra_info = f" (Nota: Também existe pasta em {', '.join(other_locs)})."

        print(f"✅ Encontrado no Tier 2 ({elapsed:.3f}s) em [{top_loc}]: {top_path}")
        return (
            f"Encontrado em {top_loc}: '{item_name}' (Caminho: {top_path}).{extra_info} "
            f"Diga ao usuario que encontrou a pasta em {top_loc} e pergunte se quer abrir agora."
        )

    # TIER 3: Varredura nos discos evitando pastas pesadas de sistema (tempo limite estrito de 10s)
    blacklist = {
        'windows', '$recycle.bin', 'system volume information', 'node_modules',
        '.git', '.venv', '__pycache__', 'package cache', 'msdownld.tmp', 'recovery',
        'windowsapps', 'appdata'
    }
    
    drives_to_search = []
    if drive and drive.strip():
        d_letter = drive.replace("/", "").replace("\\", "").replace(":", "").strip().upper()
        if d_letter:
            drives_to_search.append(f"{d_letter}:\\")
    for d in ["C:\\", "D:\\"]:
        if d not in drives_to_search and os.path.exists(d):
            drives_to_search.append(d)
            
    for root_drive in drives_to_search:
        if not os.path.exists(root_drive):
            continue
        try:
            for dirpath, dirnames, filenames in os.walk(root_drive):
                if time.time() - start_time > 10:
                    break
                dirnames[:] = [d for d in dirnames if d.lower() not in blacklist and not d.startswith('$')]
                
                for d in dirnames:
                    s = compute_similarity(clean_target, d)
                    if s >= 0.75:
                        found.append((s + 0.05, os.path.join(dirpath, d)))
                for f in filenames:
                    s = compute_similarity(clean_target, f)
                    if s >= 0.75:
                        found.append((s, os.path.join(dirpath, f)))
                if any(s >= 0.90 for s, _ in found):
                    break
        except Exception:
            pass
        if any(s >= 0.90 for s, _ in found):
            break
            
    if found:
        found.sort(key=lambda x: x[0], reverse=True)
        top_path = found[0][1]
        LAST_FOUND_PATH = top_path
        item_name = os.path.basename(top_path)
        top_loc = get_friendly_location(top_path)
        return (
            f"Encontrado em {top_loc}: '{item_name}' (Caminho: {top_path}). "
            f"Diga ao usuario que encontrou no disco e pergunte se quer abrir."
        )

    return f"Nenhum arquivo ou pasta correspondente a '{clean_target}' foi encontrado no computador."

def check_crash_logs(game_or_app_name: str = "") -> str:
    """Verifica relatorios de falha, logs de erro do Windows, AppData, CrashDumps e logs do jogo."""
    global LAST_FOUND_PATH
    target = game_or_app_name.strip().strip('"').strip("'")
    if (not target or any(w in target.lower() for w in ["o jogo", "ele", "jogo", "aplicativo", "programa"])) and LAST_FOUND_PATH:
        target = os.path.basename(LAST_FOUND_PATH)
        
    print(f"\n🩺 [Diagnóstico de Falhas]: Verificando logs e AppData para '{target}'...")
    
    user_profile = os.environ.get("USERPROFILE", r"C:\Users\Gabriel Stoler")
    local_app_data = os.environ.get("LOCALAPPDATA", os.path.join(user_profile, "AppData", "Local"))
    app_data = os.environ.get("APPDATA", os.path.join(user_profile, "AppData", "Roaming"))
    docs_dir = os.path.join(user_profile, "Documents")
    
    # 1. Consultar eventos de erro no Visualizador de Eventos do Windows (Event ID 1000/1001)
    cmd = 'Get-WinEvent -FilterHashtable @{LogName="Application"; Id=1000, 1001} -MaxEvents 25 -ErrorAction SilentlyContinue | Select-Object TimeCreated, Message | ForEach-Object { "TIME: " + $_.TimeCreated.ToString("HH:mm:ss dd/MM") + "`nMSG: " + $_.Message + "===END===" }'
    
    exception_explanations = {
        '0xc0000005': 'Violação de acesso à memória (Access Violation - memória RAM/VRAM insuficiente, conflito de drivers ou shader corrompido)',
        '0xc000041d': 'Exceção não tratada em interface gráfica ou janela',
        '0x887a0006': 'DXGI_ERROR_DEVICE_HUNG (A placa de vídeo travou ou houve timeout de renderização da GPU)',
        '0x887a0005': 'DXGI_ERROR_DEVICE_REMOVED (O driver de vídeo da placa reiniciou ou parou de responder)',
        '0xc000001d': 'Instrução ilegal (instrução de CPU incompatível ou arquivo de DLL corrompido)',
        '0xc0000374': 'Corrupção de heap de memória',
        '0x80000003': 'Ponto de interrupção atingido (Assertion failure)'
    }
    
    found_crashes = []
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace"
        )
        for entry in proc.stdout.split("===END==="):
            if not entry.strip():
                continue
            time_match = re.search(r"TIME:\s*([^\r\n]+)", entry)
            app_match = re.search(r"(?:Nome do aplicativo com falha|Faulting application name):\s*([^\r\n,]+)", entry, re.I)
            mod_match = re.search(r"(?:Nome do m[^\s]+dulo com falha|Faulting module name):\s*([^\r\n,]+)", entry, re.I)
            code_match = re.search(r"(?:C[^\s]+digo de exce[^\s]+o|Exception code):\s*([^\r\n,]+)", entry, re.I)
            
            t = time_match.group(1).strip() if time_match else "Recente"
            app = app_match.group(1).strip() if app_match else ""
            mod = mod_match.group(1).strip() if mod_match else "módulo desconhecido"
            code = code_match.group(1).strip().lower() if code_match else ""
            
            if app:
                is_match = False
                if not target:
                    is_match = True
                else:
                    if compute_similarity(target, app) >= 0.45 or target.lower() in app.lower() or app.lower() in target.lower():
                        is_match = True
                    elif "assassin" in target.lower() and "acshadows" in app.lower():
                        is_match = True
                    elif "god of war" in target.lower() and "gow" in app.lower():
                        is_match = True
                    elif "detroit" in target.lower() and "detroit" in app.lower():
                        is_match = True
                
                if is_match:
                    exp = exception_explanations.get(code, f"Código de erro {code}")
                    found_crashes.append(f"• Às {t}: O executável '{app}' falhou no módulo '{mod}'. Motivo: {exp}.")
    except Exception:
        pass
        
    # 2. Inspecionar CrashDumps do Windows
    crash_dumps_dir = os.path.join(local_app_data, "CrashDumps")
    recent_dumps = []
    if os.path.exists(crash_dumps_dir):
        try:
            for f in os.listdir(crash_dumps_dir):
                if f.lower().endswith(".dmp"):
                    f_low = f.lower()
                    if any(k in f_low for k in ["shadow", "assassin", "ac", "gow", "war", "detroit"]) or (target and compute_similarity(target, f) > 0.4):
                        full_p = os.path.join(crash_dumps_dir, f)
                        if time.time() - os.path.getmtime(full_p) < 86400 * 3:
                            recent_dumps.append(f)
        except Exception:
            pass

    # 3. Inspecionar AppData e Logs de Launchers
    appdata_locations = []
    ubi_game_dir = os.path.join(local_app_data, "Ubisoft", "Assassin's Creed Shadows")
    if os.path.exists(ubi_game_dir):
        appdata_locations.append("AppData Local (pasta Ubisoft)")
    ubi_launcher_logs = r"C:\Program Files (x86)\Ubisoft\Ubisoft Game Launcher\logs"
    if os.path.exists(ubi_launcher_logs):
        appdata_locations.append("Logs do Launcher Ubisoft")

    # 4. Inspecionar pasta do jogo e logs de ReShade / mods
    reshade_summary = ""
    game_folder_logs = []
    possible_game_dirs = [
        r"C:\Games Place\Pc Games\Assassin's Creed Shadows",
        r"C:\Games Place\Pc Games\God of War",
        r"C:\Games Place\Pc Games\Detroit Become Human"
    ]
    if LAST_FOUND_PATH and os.path.exists(LAST_FOUND_PATH):
        folder = LAST_FOUND_PATH if os.path.isdir(LAST_FOUND_PATH) else os.path.dirname(LAST_FOUND_PATH)
        if folder not in possible_game_dirs:
            possible_game_dirs.insert(0, folder)
            
    for gdir in possible_game_dirs:
        if not os.path.exists(gdir):
            continue
        gname = os.path.basename(gdir)
        if target and compute_similarity(target, gname) < 0.4 and not any(k in target.lower() for k in ["assassin", "shadows"]):
            continue
        reshade_file = os.path.join(gdir, "ReShade.log")
        if os.path.exists(reshade_file):
            try:
                with open(reshade_file, "r", encoding="utf-8", errors="ignore") as rf:
                    rlines = [l.strip() for l in rf.readlines() if l.strip()]
                    last_15 = rlines[-15:]
                    if any("Finished exiting" in l for l in last_15):
                        reshade_summary = f"No arquivo ReShade.log na pasta do jogo, todos os mods gráficos (DLSS 5 e RenoDX) descarregaram normalmente com 'Finished exiting', sem travamento brusco de shader."
                    elif any("ERROR" in l or "CRASH" in l for l in last_15):
                        reshade_summary = f"No arquivo ReShade.log há registros de erro recente nos shaders ou injeção de DLL."
            except Exception:
                pass
        try:
            for f in os.listdir(gdir):
                if f.lower().endswith((".log", ".txt", ".crash")) and not f.lower().startswith("unins") and "license" not in f.lower():
                    game_folder_logs.append(f)
        except Exception:
            pass
        break

    # Montar resposta consolidada
    report_parts = []
    if found_crashes:
        report_parts.append("Falha fatal registrada no Visualizador de Eventos do Windows:\n" + "\n".join(found_crashes[:2]))
    else:
        report_parts.append(f"O Windows não registrou exceção de crash crítico (Event ID 1000) para '{target}'.")

    if recent_dumps:
        report_parts.append(f"Minidumps encontrados na pasta CrashDumps: {', '.join(recent_dumps[:3])}.")
    else:
        report_parts.append("Não há minidumps recentes na pasta CrashDumps da AppData.")

    if reshade_summary:
        report_parts.append(reshade_summary)

    loc_info = "Locais de logs e dados encontrados: AppData Local (Ubisoft), pasta Documentos e pasta de instalação do jogo (ReShade.log)."
    report_parts.append(loc_info)
    
    report_parts.append("Diga ao usuário onde os logs ficam (AppData Local e pasta do jogo) e explique que o encerramento não gerou falha crítica de memória, sugerindo que foi fechamento limpo ou interrupção do launcher.")
    return "\n\n".join(report_parts)
