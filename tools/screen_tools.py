import io
import os
import sys
import shutil
import base64
import subprocess
from PIL import Image

from typing import Optional

def capture_screen_pil() -> tuple[Optional[Image.Image], str]:
    """
    Captura a tela do computador do usuário e retorna:
    (PIL.Image, status_message)
    """
    if sys.platform != "win32" and not os.getenv("DISPLAY"):
        return None, "Captura de tela indisponível em servidor em nuvem (headless)."

    # Método 1: PIL ImageGrab (rápido quando em sessão desktop interativa)
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab()
        if img:
            img.thumbnail((1024, 576), Image.Resampling.LANCZOS)
            return img, "Tela capturada com sucesso."
    except Exception:
        pass

    # Método 2: Fallback via PowerShell .NET (apenas Windows)
    ps_bin = shutil.which("powershell") or shutil.which("pwsh")
    if not ps_bin:
        return None, "Captura de tela indisponível sem PowerShell ou interface gráfica."

    try:
        temp_file = os.path.abspath("temp_screen.jpg")
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "Add-Type -AssemblyName System.Drawing; "
            "$s = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
            "$b = New-Object System.Drawing.Bitmap $s.Width, $s.Height; "
            "$g = [System.Drawing.Graphics]::FromImage($b); "
            "$g.CopyFromScreen($s.Location, [System.Drawing.Point]::Empty, $s.Size); "
            f"$b.Save('{temp_file}', [System.Drawing.Imaging.ImageFormat]::Jpeg); "
            "$g.Dispose(); $b.Dispose();"
        )
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, timeout=5)
        if os.path.exists(temp_file):
            with open(temp_file, "rb") as f:
                img_data = f.read()
            os.remove(temp_file)
            img = Image.open(io.BytesIO(img_data))
            img.thumbnail((1024, 576), Image.Resampling.LANCZOS)
            return img, "Tela capturada com sucesso via sistema."
    except Exception as e:
        return None, f"Não foi possível capturar a tela: {str(e)}"

    return None, "Não foi possível capturar a tela no momento."

def capture_screen_base64() -> tuple[str, str]:
    """
    Captura a tela do computador do usuário e retorna:
    (base64_jpeg, status_message)
    """
    img, msg = capture_screen_pil()
    if img:
        try:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75)
            b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")
            return b64_str, msg
        except Exception as e:
            return "", f"Erro ao codificar imagem: {e}"
    return "", msg

