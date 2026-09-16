import os
import shutil
import subprocess
import re
from core.task_manager import task_manager

def summarize_action_name(task_description: str) -> str:
    """Extrai uma descrição concisa e natural da ação que necessita de permissão."""
    desc = task_description.strip()
    lower = desc.lower()
    for prefix in [
        "execute o comando powershell:", "execute o comando:", "execute:",
        "rode o comando powershell:", "rode o comando:", "rode:",
        "crie o arquivo:", "crie um arquivo:", "crie:",
        "modifique o arquivo:", "delete:", "remova:"
    ]:
        if lower.startswith(prefix):
            desc = desc[len(prefix):].strip()
            break
    if len(desc) > 60:
        desc = desc[:57] + "..."
    return desc

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

def delegate_to_antigravity(task_description: str, target_path: str = None, auto_approve: bool = False) -> str:
    """
    Delega tarefas complexas de desenvolvimento, refatoração, análise profunda ou automação
    ao núcleo Antigravity CLI do Google.

    Se auto_approve for True (Opção 4 do Gabriel):
        Passa '--dangerously-skip-permissions' para aceitar todas as ferramentas e permissões relacionadas.
    Se auto_approve for False:
        Executa sem auto-aprovar. Se o antigravidade exigir permissão (ex: command, file modification),
        detecta a exigência, registra no TaskManager e retorna mensagem estruturada de permissão:
        'PERMISSAO_NECESSARIA: Eu só preciso da sua confirmação para executar [X ação], por favor.'
    """
    agy_bin = get_agy_executable()

    if auto_approve:
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
            task_manager.clear_pending_permission()
            if result.returncode == 0:
                output_summary = result.stdout.strip()[:600] if result.stdout else 'Tarefa concluída com sucesso pelo antigravidade.'
                return f'O antigravidade executou a tarefa com sucesso (Opção 4: autorização total): {output_summary}'
            else:
                err_msg = result.stderr.strip()[:300] if result.stderr else result.stdout.strip()[:300]
                return f'O antigravidade retornou aviso/erro: {err_msg}'
        except subprocess.TimeoutExpired:
            return 'A tarefa enviada ao antigravidade demorou mais de 2 minutos e continua em segundo plano.'
        except Exception as e:
            return f'Não foi possível contactar o CLI antigravidade: {str(e)}'

    # Tentativa padrão sem auto-aprovação
    cmd = [agy_bin, '--print', task_description]
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
        combined_text = (result.stdout + " " + result.stderr).lower()

        # Verifica se o agy exigiu permissão
        permission_patterns = [
            "tool required the",
            "permission that headless mode cannot prompt for",
            "dangerously-skip-permissions",
            "permission denied",
            "requires confirmation"
        ]

        if any(pat in combined_text for pat in permission_patterns):
            action_summary = summarize_action_name(task_description)
            if "command" in combined_text:
                action_display = f"comandos no sistema para {action_summary}"
            elif "file" in combined_text or "edit" in combined_text:
                action_display = f"modificações de arquivos para {action_summary}"
            else:
                action_display = f"a ação '{action_summary}'"

            task_manager.set_pending_permission(
                action=action_display,
                task_description=task_description,
                target_path=target_path
            )
            return f"PERMISSAO_NECESSARIA: Eu só preciso da sua confirmação para executar {action_display}, por favor."

        if result.returncode == 0:
            task_manager.clear_pending_permission()
            output_summary = result.stdout.strip()[:600] if result.stdout else 'Tarefa concluída com sucesso pelo antigravidade.'
            return f'O antigravidade executou a tarefa com sucesso: {output_summary}'
        else:
            err_msg = result.stderr.strip()[:300] if result.stderr else result.stdout.strip()[:300]
            return f'O antigravidade retornou aviso/erro: {err_msg}'

    except subprocess.TimeoutExpired:
        return 'A tarefa enviada ao antigravidade demorou mais de 2 minutos e continua em segundo plano.'
    except Exception as e:
        return f'Não foi possível contactar o CLI antigravidade: {str(e)}'
