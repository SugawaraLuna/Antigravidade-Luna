import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import argparse
import subprocess
import requests

CORE_HOST = os.getenv("ANTIGRAVITY_CORE_HOST", "127.0.0.1")
CORE_PORT = int(os.getenv("ANTIGRAVITY_CORE_PORT", "8765"))
HEALTH_URL = f"http://{CORE_HOST}:{CORE_PORT}/health"

def is_core_online() -> bool:
    try:
        r = requests.get(HEALTH_URL, timeout=1.5)
        return r.status_code == 200 and r.json().get("core") == "antigravidade"
    except Exception:
        return False

def start_core_background():
    print(f"[*] Inicializando o Núcleo Antigravidade em segundo plano (porta {CORE_PORT})...")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    proc = subprocess.Popen(
        [sys.executable, "-m", "core.server"],
        cwd=script_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    for _ in range(25):
        time.sleep(0.3)
        if is_core_online():
            print(f"[✓] Núcleo Antigravidade online e sincronizado!")
            return proc
    print("[!] Aviso: O núcleo pode estar demorando a inicializar. Continuando...")
    return proc

def main():
    parser = argparse.ArgumentParser(description="LUNA & Núcleo Antigravidade Launcher")
    parser.add_argument("--core", action="store_true", help="Inicia exclusivamente o Núcleo Antigravidade")
    parser.add_argument("--client", action="store_true", help="Inicia exclusivamente a interface LUNA")
    args = parser.parse_args()

    if args.core:
        from core.server import main as run_server
        run_server()
        return

    if args.client:
        from luna_client import main as run_client
        run_client()
        return

    # Modo padrão: Orquestração Unificada
    print("=" * 68)
    print("   🌙 SISTEMA LUNA + NÚCLEO ANTIGRAVIDADE (Inicializador Unificado)")
    print("=" * 68)

    core_proc = None
    if not is_core_online():
        core_proc = start_core_background()
    else:
        print(f"[✓] Núcleo Antigravidade já detectado ativo na porta {CORE_PORT}.")

    try:
        from luna_client import main as run_client
        run_client()
    finally:
        if core_proc:
            try:
                core_proc.terminate()
            except Exception:
                pass

if __name__ == "__main__":
    main()
