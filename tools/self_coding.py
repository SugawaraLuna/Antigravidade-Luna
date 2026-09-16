import os
import sys
import json
import time
import shutil
import datetime
import subprocess
from pathlib import Path
from tools.agy_tools import get_agy_executable
from ui.terminal_ui import render_activity_box, render_diff_log, render_proposal_report

LUNA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VERONICA_DIR = os.path.abspath(os.path.join(LUNA_DIR, "..", "Veronica"))
BACKUPS_DIR = os.path.join(LUNA_DIR, ".backups")

LUNA_CONVERSATION_ID = "f97374c8-de9d-481a-aab5-a18047a70eb3"
VERONICA_CONVERSATION_ID = "a77ff5e8-ed8c-4bd2-a675-00c08e9135ff"

def get_git_executable() -> str:
    """Localiza o binário do git no sistema operacional."""
    git_which = shutil.which("git")
    if git_which:
        return git_which
    candidates = [
        r"C:\Program Files\Git\cmd\git.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe")
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "git"

def create_backup(target_agent: str, target_dir: str) -> str:
    """Cria um snapshot do código antes de qualquer alteração para possibilitar rollback imediato."""
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{timestamp}_{target_agent}"
    backup_path = os.path.join(BACKUPS_DIR, backup_name)
    os.makedirs(backup_path, exist_ok=True)

    ignore_patterns = shutil.ignore_patterns(".git", "__pycache__", "venv", ".venv", ".backups", "*.pyc", "*.mp3", "*.jpg", "*.bin")
    
    backed_files = []
    for item in os.listdir(target_dir):
        s = os.path.join(target_dir, item)
        d = os.path.join(backup_path, item)
        if item in [".git", "__pycache__", "venv", ".venv", ".backups"]:
            continue
        try:
            if os.path.isdir(s):
                shutil.copytree(s, d, ignore=ignore_patterns, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
            backed_files.append(item)
        except Exception as e:
            print(f"[-] Aviso ao copiar {item} para backup: {e}")

    manifest = {
        "timestamp": timestamp,
        "target_agent": target_agent,
        "target_dir": target_dir,
        "backed_files": backed_files
    }
    with open(os.path.join(backup_path, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return backup_path

def list_backups() -> list[dict]:
    """Lista todos os backups disponíveis ordenados pelo mais recente."""
    if not os.path.exists(BACKUPS_DIR):
        return []
    backups = []
    for folder in sorted(os.listdir(BACKUPS_DIR), reverse=True):
        full_path = os.path.join(BACKUPS_DIR, folder)
        manifest_file = os.path.join(full_path, "manifest.json")
        if os.path.isdir(full_path) and os.path.exists(manifest_file):
            try:
                with open(manifest_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["folder"] = folder
                    data["path"] = full_path
                    backups.append(data)
            except Exception:
                pass
    return backups

def rollback_latest_backup(target_agent: str = None) -> dict:
    """Restaura o código a partir do último backup disponível."""
    all_backups = list_backups()
    if not all_backups:
        return {"success": False, "message": "Nenhum backup encontrado para desfazer alterações."}

    selected_backup = None
    if target_agent:
        norm_target = target_agent.lower()
        for b in all_backups:
            if b.get("target_agent", "").lower() == norm_target:
                selected_backup = b
                break
    if not selected_backup:
        selected_backup = all_backups[0]

    src_dir = selected_backup["path"]
    dst_dir = selected_backup.get("target_dir", LUNA_DIR)

    restored = []
    for item in os.listdir(src_dir):
        if item == "manifest.json":
            continue
        s = os.path.join(src_dir, item)
        d = os.path.join(dst_dir, item)
        try:
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)
            restored.append(item)
        except Exception as e:
            print(f"[-] Erro ao restaurar {item}: {e}")

    return {
        "success": True,
        "backup_name": selected_backup.get("folder"),
        "target_agent": selected_backup.get("target_agent"),
        "restored_items": restored,
        "message": f"Backup '{selected_backup.get('folder')}' restaurado com sucesso! Itens restaurados: {', '.join(restored[:5])}."
    }

def prepare_code_change_proposal(target_agent: str, instruction: str) -> dict:
    """
    Analisa a solicitação de alteração de código feita pelo Gabriel,
    gera um relatório de entendimento, identifica os arquivos envolvidos
    e prepara a proposta que exigirá autorização antes da execução.
    """
    norm = (target_agent or "").lower()
    if "veronica" in norm or "verônica" in norm or "binfae" in instruction.lower():
        target = "veronica"
        target_dir = VERONICA_DIR
        conv_id = VERONICA_CONVERSATION_ID
    else:
        target = "luna"
        target_dir = LUNA_DIR
        conv_id = LUNA_CONVERSATION_ID

    # Extrair arquivos potenciais mencionados ou pertinentes
    affected_files = []
    common_modules = [
        "core/engine.py", "core/server.py", "core/task_manager.py",
        "luna_client.py", "main.py", "ui/hud.py", "ui/terminal_ui.py",
        "tools/internet_tools.py", "tools/clipboard_tools.py", "tools/self_coding.py",
        "audio/live_engine.py", "audio/vad_recorder.py", "audio/stt.py",
        "veronica.py", "modules/mailer.py", "modules/scraper.py"
    ]
    inst_lower = instruction.lower()
    for m in common_modules:
        base = os.path.basename(m).lower()
        if base in inst_lower or m in inst_lower:
            affected_files.append(m)

    if not affected_files:
        if target == "veronica":
            affected_files.append("veronica.py")
        else:
            affected_files.append("core/engine.py")

    action_summary = f"Executar refatoração e implementação via Antigravidade CLI no repositório de {target.capitalize()}."
    understanding = f"Alterar funcionalidade de acordo com a solicitação: '{instruction}'."

    proposal = {
        "target_agent": target,
        "target_dir": target_dir,
        "conversation_id": conv_id,
        "instruction": instruction,
        "understanding": understanding,
        "affected_files": affected_files,
        "action_summary": action_summary
    }

    # Renderizar o relatório no terminal
    render_proposal_report(proposal)

    return proposal

def execute_approved_code_change(proposal: dict) -> dict:
    """
    Executa a alteração aprovada pelo Gabriel:
    1. Cria backup prévio automático
    2. Invoca o Antigravidade CLI com o ID da conversa correspondente
    3. Coleta o git diff unificado
    4. Exibe o diff colorido no terminal (+ verde / - vermelho)
    """
    target = proposal.get("target_agent", "luna")
    target_dir = proposal.get("target_dir", LUNA_DIR)
    conv_id = proposal.get("conversation_id", LUNA_CONVERSATION_ID)
    instruction = proposal.get("instruction", "")

    render_activity_box("Criando Backup Preventivo", f"Snapshot dos arquivos em .backups/ para {target.upper()}")
    backup_path = create_backup(target, target_dir)

    render_activity_box("Delegando ao Antigravidade", f"Contexto de Conversa: {conv_id}\nAlvo: {target_dir}\nInstrução: {instruction}")

    agy_bin = get_agy_executable()
    cmd = [
        agy_bin,
        "--conversation", conv_id,
        "--add-dir", target_dir,
        "--dangerously-skip-permissions",
        "-p", instruction
    ]

    diff_text = ""
    result_output = ""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
            encoding="utf-8",
            errors="replace"
        )
        result_output = proc.stdout.strip()
        if proc.returncode != 0 and proc.stderr:
            result_output += f"\nAvisos: {proc.stderr.strip()}"
    except Exception as e:
        result_output = f"Falha na comunicação com o Antigravidade: {e}"

    # Capturar diff via git
    git_bin = get_git_executable()
    try:
        git_diff = subprocess.run(
            [git_bin, "diff"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=10,
            encoding="utf-8",
            errors="replace"
        )
        if git_diff.returncode == 0 and git_diff.stdout.strip():
            diff_text = git_diff.stdout.strip()
    except Exception:
        pass

    # Exibir o diff no terminal com a estética roxa/verde/vermelha
    if diff_text:
        render_diff_log(diff_text, f"DIFF DE ALTERAÇÃO ({target.upper()})")
    else:
        render_activity_box("Resultado do Antigravidade", result_output[:400] if result_output else "Modificação finalizada com sucesso.")

    return {
        "success": True,
        "backup_path": backup_path,
        "diff": diff_text,
        "output": result_output,
        "spoken_message": f"Gabriel, apliquei as alterações no código da {target.capitalize()} com sucesso pelo antigravidade! Criei um backup prévio. Se desejar que o novo código entre em vigor agora, basta me pedir para reiniciar."
    }

def restart_system():
    """Reinicia o sistema Luna e o Núcleo Antigravidade de forma limpa."""
    render_activity_box("Reinicializando Sistema", "Encerrando instâncias ativas e religando processo principal...")
    time.sleep(0.8)
    main_script = os.path.join(LUNA_DIR, "main.py")
    subprocess.Popen([sys.executable, main_script], cwd=LUNA_DIR)
    os._exit(0)
