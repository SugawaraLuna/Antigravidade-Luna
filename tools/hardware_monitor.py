import os
import subprocess
import psutil

def get_hardware_stats() -> str:
    """
    Obtém dados de telemetria de hardware em tempo real do computador:
    - GPU (NVIDIA RTX): Temperatura (°C), uso da GPU (%), VRAM usada/total (GB) e consumo (Watts).
    - CPU (Processador): Uso percentual de processamento e threads.
    - RAM (Memória): Uso em GB e porcentagem.
    """
    lines = []
    
    # 1. Telemetria de GPU via nvidia-smi
    gpu_found = False
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if proc.returncode == 0 and proc.stdout.strip():
            raw = proc.stdout.strip().split("\n")[0]
            parts = [p.strip() for p in raw.split(",")]
            if len(parts) >= 6:
                name, temp, util, mem_used, mem_total, power = parts[:6]
                vram_used_gb = float(mem_used) / 1024.0
                vram_total_gb = float(mem_total) / 1024.0
                lines.append(
                    f"Placa de Vídeo ({name}): Temperatura a {temp}°C, "
                    f"uso da GPU em {util}%, VRAM em {vram_used_gb:.1f} GB usados de {vram_total_gb:.1f} GB, "
                    f"consumindo cerca de {float(power):.1f}W."
                )
                gpu_found = True
    except Exception:
        pass
        
    if not gpu_found:
        lines.append("Telemetria da GPU indisponível no momento.")

    # 2. Telemetria de CPU e RAM
    try:
        cpu_percent = psutil.cpu_percent(interval=0.2)
        cpu_count = psutil.cpu_count(logical=True)
        ram = psutil.virtual_memory()
        ram_used_gb = ram.used / (1024 ** 3)
        ram_total_gb = ram.total / (1024 ** 3)
        
        lines.append(
            f"Processador: {cpu_percent}% de uso atual ({cpu_count} threads). "
            f"Memória RAM: {ram.percent}% em uso ({ram_used_gb:.1f} GB de {ram_total_gb:.1f} GB)."
        )
    except Exception as e:
        lines.append(f"Erro ao ler CPU/RAM: {e}")

    summary = " ".join(lines)
    print(f"\n[Telemetria de Hardware]: {summary}")
    return summary
