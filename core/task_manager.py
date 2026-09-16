import time
from typing import Optional, Dict, Any

class TaskManager:
    """
    Gerenciador singleton para a tarefa ativa da LUNA.
    Mantém o foco contínuo e absoluto da LUNA na tarefa até sua conclusão ou cancelamento explícito.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TaskManager, cls).__new__(cls)
            cls._instance.active_task = None
        return cls._instance

    def get_active_task(self) -> Optional[Dict[str, Any]]:
        return self.active_task

    def has_active_task(self) -> bool:
        return self.active_task is not None and self.active_task.get("status") == "in_progress"

    def start_active_task(self, title: str, details: str = "", action_label: str = "") -> Dict[str, Any]:
        self.active_task = {
            "title": title.strip(),
            "details": details.strip() or title.strip(),
            "action_label": action_label.strip() or title.strip(),
            "status": "in_progress",
            "started_at": time.time(),
            "updated_at": time.time(),
            "result": None,
            "last_action": action_label.strip() or "Iniciando tarefa..."
        }
        return self.active_task

    def update_task_progress(self, action_label: str = None, result: str = None, status: str = "in_progress"):
        if not self.active_task:
            return
        self.active_task["updated_at"] = time.time()
        self.active_task["status"] = status
        if action_label:
            self.active_task["action_label"] = action_label
            self.active_task["last_action"] = action_label
        if result:
            self.active_task["result"] = result

    def complete_active_task(self, result_summary: str = "") -> Optional[Dict[str, Any]]:
        if not self.active_task:
            return None
        self.active_task["status"] = "completed"
        self.active_task["updated_at"] = time.time()
        if result_summary:
            self.active_task["result"] = result_summary
        task = dict(self.active_task)
        # Manter como referência recente concluída
        return task

    def cancel_active_task(self, reason: str = "Cancelado pelo usuário") -> Optional[Dict[str, Any]]:
        if not self.active_task:
            return None
        self.active_task["status"] = "cancelled"
        self.active_task["updated_at"] = time.time()
        self.active_task["result"] = f"Cancelada: {reason}"
        task = dict(self.active_task)
        self.active_task = None
        return task

    def clear_active_task(self):
        self.active_task = None

    def get_task_context_string(self) -> str:
        if not self.active_task:
            return ""
        
        status = self.active_task.get("status", "in_progress")
        title = self.active_task.get("title", "")
        details = self.active_task.get("details", "")
        result = self.active_task.get("result")
        last_action = self.active_task.get("last_action", "")

        if status == "in_progress":
            ctx = (
                f"\n--- TAREFA ATIVA EM ANDAMENTO (FOCO ABSOLUTO) ---\n"
                f"Objetivo: {title}\n"
                f"Detalhes: {details}\n"
                f"Última Ação Realizada: {last_action}\n"
                f"Progresso/Retorno Atual: {result or 'Em execução contínua'}\n"
                f"DIRETRIZ DE FOCO: Você DEVE manter o foco absoluto nesta tarefa até concluí-la ou o Gabriel pedir expressamente para parar/deixar para lá. Não se esqueça dessa tarefa nos próximos turnos!\n"
                f"--------------------------------------------------\n"
            )
            return ctx
        elif status == "completed" and result:
            ctx = (
                f"\n--- TAREFA RECÉM-CONCLUÍDA ---\n"
                f"Tarefa: {title}\n"
                f"Resultado Obtido: {result}\n"
                f"-----------------------------\n"
            )
            return ctx
        return ""

task_manager = TaskManager()
