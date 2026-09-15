import os
import json

MEMORY_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "user_memory.json")

def load_memory() -> dict:
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"user_name": "Gabriel", "favorite_games": [], "game_aliases": {}, "notes": []}

def save_memory(data: dict) -> bool:
    try:
        os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception:
        return False

def get_memory_context_string() -> str:
    """Gera uma string concisa para alimentar o contexto da LUNA."""
    mem = load_memory()
    favs = ", ".join(mem.get("favorite_games", []))
    aliases = mem.get("game_aliases", {})
    alias_str = ", ".join([f"'{k}' = {v}" for k, v in aliases.items()])
    notes = "; ".join(mem.get("notes", []))
    role = mem.get("user_role", "Criador e Administrador Geral do Sistema")
    
    ctx = f"MEMÓRIA DE LONGO PRAZO DA LUNA: Usuário: Gabriel ({role}). Jogos frequentes: [{favs}]."
    if alias_str:
        ctx += f" Apelidos: [{alias_str}]."
    if notes:
        ctx += f" Notas lembradas: [{notes}]."
    return ctx

def remember_user_fact(fact: str) -> str:
    """Salva uma informação ou preferência pessoal solicitada pelo usuário."""
    mem = load_memory()
    notes = mem.get("notes", [])
    clean_fact = fact.strip()
    if clean_fact not in notes:
        notes.append(clean_fact)
        mem["notes"] = notes
        save_memory(mem)
        print(f"\n[Memória Permanente]: Gravado -> '{clean_fact}'")
        return f"Entendido, memorizei para você: '{clean_fact}'."
    return f"Já tenho memorizado: '{clean_fact}'."
