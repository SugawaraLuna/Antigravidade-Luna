import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import threading
import argparse
import subprocess
import requests

CORE_HOST = os.getenv("ANTIGRAVITY_CORE_HOST", "127.0.0.1")
CORE_PORT = int(os.getenv("ANTIGRAVITY_CORE_PORT", "8765"))
HEALTH_URL = f"http://{CORE_HOST}:{CORE_PORT}/health"

def is_core_online() -> bool:
    try:
        r = requests.get(HEALTH_URL, timeout=1.5)
        return r.status_code == 200 and r.json().get("status") == "online"
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

    is_cloud_env = (
        sys.platform != "win32"
        or os.getenv("RAILWAY_ENVIRONMENT") is not None
        or os.getenv("RAILWAY_STATIC_URL") is not None
        or os.getenv("DYNO") is not None
        or os.getenv("RENDER") is not None
        or (os.getenv("PORT") is not None and not sys.stdin.isatty())
    )

    if args.core or is_cloud_env:
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
    stop_watchdog = threading.Event()

    def watchdog_loop():
        nonlocal core_proc
        while not stop_watchdog.is_set():
            time.sleep(3.0)
            if not is_core_online() and not stop_watchdog.is_set():
                print("\n[⚠️ WATCHDOG]: Núcleo Antigravidade inacessível. Reiniciando processo...")
                if core_proc:
                    try:
                        core_proc.terminate()
                    except Exception:
                        pass
                core_proc = start_core_background()

    if not is_core_online():
        core_proc = start_core_background()
    else:
        print(f"[✓] Núcleo Antigravidade já detectado ativo na porta {CORE_PORT}.")

    watchdog_thread = threading.Thread(target=watchdog_loop, daemon=True)
    watchdog_thread.start()

    try:
        from luna_client import main as run_client
        run_client()
    finally:
        stop_watchdog.set()
        if core_proc:
            try:
                core_proc.terminate()
            except Exception:
                pass

if __name__ == "__main__":
    main()
