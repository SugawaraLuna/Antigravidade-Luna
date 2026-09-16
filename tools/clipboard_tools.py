import os
import re
import ctypes
from ctypes import wintypes

user32 = getattr(ctypes, "windll", None)
if user32:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.CloseClipboard.restype = wintypes.BOOL

def copy_to_clipboard(text: str) -> bool:
    """Copia texto diretamente para a Área de Transferência do Windows sem dependências externas."""
    if not user32 or not text:
        return False
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        data = (text + "\0").encode("utf-16le")
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h_mem:
            return False
        p_mem = kernel32.GlobalLock(h_mem)
        if not p_mem:
            return False
        ctypes.memmove(p_mem, data, len(data))
        kernel32.GlobalUnlock(h_mem)
        user32.SetClipboardData(CF_UNICODETEXT, h_mem)
        return True
    except Exception as e:
        print(f"[-] Erro ao copiar para clipboard: {e}")
        return False
    finally:
        user32.CloseClipboard()

def extract_code_blocks(text: str) -> list[tuple[str, str]]:
    """Extrai blocos de código em markdown do tipo ```linguagem ... ```."""
    pattern = r"```([a-zA-Z0-9_\-\+]*)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    results = []
    for lang, code in matches:
        cleaned_code = code.strip()
        if cleaned_code:
            results.append((lang.strip().lower() or "text", cleaned_code))
    return results

def handle_code_delivery(raw_output: str, task_hint: str = "script") -> str:
    """
    Detecta códigos gerados no output do antigravidade, copia para a Área de Transferência,
    imprime no terminal de forma legível e salva na pasta Downloads.
    Retorna uma mensagem de status para ser informada ao Gabriel.
    """
    blocks = extract_code_blocks(raw_output)
    if not blocks:
        return ""

    main_lang, main_code = blocks[0]
    copied = copy_to_clipboard(main_code)

    print("\n" + "=" * 68)
    print(f"📋 [CÓDIGO GERADO PELA LUNA / ANTIGRAVIDADE - LINGUAGEM: {main_lang.upper()}]:")
    print("=" * 68)
    print(main_code)
    print("=" * 68)
    if copied:
        print("[✓] Código copiado automaticamente para a sua Área de Transferência (Ctrl+V)!")
    print("=" * 68 + "\n")

    saved_path = None
    try:
        downloads_dir = os.path.expanduser("~/Downloads")
        if os.path.exists(downloads_dir):
            ext_map = {
                "javascript": ".js", "js": ".js",
                "google-apps-script": ".gs", "appsscript": ".gs",
                "python": ".py", "py": ".py",
                "powershell": ".ps1", "ps1": ".ps1",
                "html": ".html", "css": ".css", "sql": ".sql"
            }
            ext = ext_map.get(main_lang, ".txt")
            safe_hint = re.sub(r'[^a-zA-Z0-9_]', '_', task_hint[:20])
            filename = f"luna_{safe_hint}{ext}"
            file_full = os.path.join(downloads_dir, filename)
            with open(file_full, "w", encoding="utf-8") as f:
                f.write(main_code)
            saved_path = file_full
            print(f"[✓] Arquivo salvo em: {file_full}\n")
    except Exception as e:
        print(f"[-] Aviso ao salvar em Downloads: {e}")

    delivery_msg = "Já printei o código completo no terminal e copiei para sua Área de Transferência (Ctrl+V)!"
    if saved_path:
        delivery_msg += f" Também salvei uma cópia na sua pasta Downloads."
    return delivery_msg
