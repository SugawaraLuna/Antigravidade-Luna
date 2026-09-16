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
            cls._instance.pending_permission = None
            cls._instance.recent_topic = ""
            cls._instance.last_generated_code = ""
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
        self.clear_pending_permission()
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
        self.clear_pending_permission()

    def set_pending_permission(self, action: str, task_description: str, target_path: str = None) -> Dict[str, Any]:
        """Registra uma ação no antigravidade que está aguardando confirmação do Gabriel."""
        self.pending_permission = {
            "action": action.strip(),
            "task_description": task_description.strip(),
            "target_path": target_path,
            "requested_at": time.time(),
            "status": "waiting_approval"
        }
        return self.pending_permission

    def get_pending_permission(self) -> Optional[Dict[str, Any]]:
        return self.pending_permission

    def has_pending_permission(self) -> bool:
        return self.pending_permission is not None and self.pending_permission.get("status") == "waiting_approval"

    def clear_pending_permission(self):
        self.pending_permission = None

    def set_recent_topic(self, topic: str):
        """Atualiza o assunto ou artefato técnico mais recente da conversa."""
        self.recent_topic = topic.strip()

    def get_recent_topic(self) -> str:
        return self.recent_topic

    def set_last_generated_code(self, code: str, lang: str = ""):
        self.last_generated_code = code

    def get_last_generated_code(self) -> str:
        return self.last_generated_code

    def get_task_context_string(self) -> str:
        ctx_parts = []

        if self.recent_topic:
            ctx_parts.append(
                f"\n--- TÓPICO / ARTEFATO TÉCNICO RECENTE ---\n"
                f"Assunto Recente Tratado: {self.recent_topic}\n"
                f"DIRETRIZ DE PROATIVIDADE: Se o Gabriel pedir 'abre no Google', 'pesquisa sobre isso' ou 'abre ele', "
                f"abra IMEDIATAMENTE a pesquisa no navegador padrão usando a ferramenta 'open_in_browser' "
                f"pesquisando exatamente '{self.recent_topic}', SEM fazer perguntas de esclarecimento!\n"
                f"-----------------------------------------\n"
            )
        
        if self.has_pending_permission():
            perm = self.pending_permission
            ctx_parts.append(
                f"\n--- PEDIDO DE AUTORIZAÇÃO PENDENTE (OPÇÃO 4) ---\n"
                f"Ação que necessita de autorização: {perm.get('action')}\n"
                f"Tarefa no antigravidade: {perm.get('task_description')}\n"
                f"INSTRUÇÃO OBRIGATÓRIA: Se você acabou de delegar e precisa de confirmação, pergunte com carinho: "
                f"'Eu só preciso da sua confirmação para executar {perm.get('action')}, por favor.'\n"
                f"Quando o Gabriel responder 'Sim', 'pode fazer', 'confirmo', 'autorizo' ou 'opção 4', isso significa a OPÇÃO 4 (aceita tudo relacionado). "
                f"Chame 'delegate_to_antigravity' com auto_approve=True e confirme a conclusão com entusiasmo!\n"
                f"--------------------------------------------------\n"
            )

        if not self.active_task:
            return "".join(ctx_parts)
        
        status = self.active_task.get("status", "in_progress")
        title = self.active_task.get("title", "")
        details = self.active_task.get("details", "")
        result = self.active_task.get("result")
        last_action = self.active_task.get("last_action", "")

        if status == "in_progress":
            ctx_parts.append(
                f"\n--- TAREFA ATIVA EM ANDAMENTO (FOCO ABSOLUTO) ---\n"
                f"Objetivo: {title}\n"
                f"Detalhes: {details}\n"
                f"Última Ação Realizada: {last_action}\n"
                f"Progresso/Retorno Atual: {result or 'Em execução contínua'}\n"
                f"DIRETRIZ DE FOCO: Você DEVE manter o foco absoluto nesta tarefa até concluí-la ou o Gabriel pedir expressamente para parar/deixar para lá. Não se esqueça dessa tarefa nos próximos turnos!\n"
                f"--------------------------------------------------\n"
            )
        elif status == "completed" and result:
            ctx_parts.append(
                f"\n--- TAREFA RECÉM-CONCLUÍDA ---\n"
                f"Tarefa: {title}\n"
                f"Resultado Obtido: {result}\n"
                f"-----------------------------\n"
            )
        return "".join(ctx_parts)

task_manager = TaskManager()

