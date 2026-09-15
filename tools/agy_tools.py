import os
import shutil
import subprocess

def get_agy_executable() -> str:
    """Retorna o caminho exato do executável agy no Windows."""
    agy_path = shutil.which("agy")
    if agy_path:
        return agy_path
    appdata_path = os.path.expandvars(r"%LOCALAPPDATA%\agy\bin\agy.exe")
    if os.path.exists(appdata_path):
        return appdata_path
    return "agy"

def ping_antigravity() -> bool:
    """Verifica se o núcleo Antigravity CLI está responsivo."""
    try:
        cmd = [get_agy_executable(), "--version"]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace")
        return res.returncode == 0
    except Exception:
        return False

def delegate_to_antigravity(task_description: str, target_path: str = None) -> str:
    """
    Delega tarefas complexas de desenvolvimento, refatoração, análise profunda ou automação
    ao núcleo Antigravity CLI do Google.
    """
    agy_bin = get_agy_executable()
    cmd = [agy_bin, '--print', task_description, '--dangerously-skip-permissions']
    if target_path and os.path.exists(target_path):
        cmd.extend(['--add-dir', target_path])
        
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            encoding="utf-8",
            errors="replace"
        )
        if result.returncode == 0:
            output_summary = result.stdout.strip()[:600] if result.stdout else 'Tarefa concluída com sucesso pelo antigravidade.'
            return f'O antigravidade executou a tarefa com sucesso: {output_summary}'
        else:
            err_msg = result.stderr.strip()[:300] if result.stderr else result.stdout.strip()[:300]
            return f'O antigravidade retornou aviso/erro: {err_msg}'
    except subprocess.TimeoutExpired:
        return 'A tarefa enviada ao antigravidade demorou mais de 2 minutos e continua em segundo plano.'
    except Exception as e:
        return f'Não foi possível contactar o CLI antigravidade: {str(e)}'
