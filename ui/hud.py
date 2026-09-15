import tkinter as tk
import threading
import time

class LunaHUD:
    def __init__(self):
        self.root = None
        self.state = "idle" # idle, listening, thinking, speaking
        self.running = True
        self._drag_data = {"x": 0, "y": 0}
        
        # Dimensões e estados
        self.min_w = 52
        self.max_w = 290
        self.cur_w = self.min_w
        self.h = 52
        self.margin_x = 24
        self.margin_y = 70
        self.is_expanded = False
        self._anim_id = None

    def start(self):
        t = threading.Thread(target=self._run_tk, daemon=True)
        t.start()

    def set_state(self, new_state: str, text: str = None):
        self.state = new_state
        if self.root:
            try:
                self.root.after(0, self._apply_state, new_state, text)
            except Exception:
                pass

    def _keep_on_top(self):
        """Garante que o HUD permaneça sempre visível sobre jogos, navegadores e janelas."""
        if self.root:
            try:
                self.root.lift()
                self.root.wm_attributes("-topmost", True)
            except Exception:
                pass
            try:
                self.root.after(1000, self._keep_on_top)
            except Exception:
                pass

    def _run_tk(self):
        self.root = tk.Tk()
        self.root.title("Luna HUD")
        self.root.overrideredirect(True)
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-alpha", 0.85)
        self.root.configure(bg="#0B0F19")

        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()

        # Iniciar no canto inferior direito
        x = self.sw - self.min_w - self.margin_x
        y = self.sh - self.h - self.margin_y
        self.root.geometry(f"{self.min_w}x{self.h}+{x}+{y}")

        self._keep_on_top()

        # Container principal com borda neon vibrante
        self.container = tk.Frame(
            self.root, 
            bg="#0B0F19", 
            highlightbackground="#BE185D", 
            highlightthickness=1.5
        )
        self.container.pack(fill=tk.BOTH, expand=True)
        self.container.pack_propagate(False)

        # Canvas para o orbe circular
        self.canvas = tk.Canvas(self.container, width=48, height=48, bg="#0B0F19", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, padx=(1, 0))

        # Frame de textos
        self.text_frame = tk.Frame(self.container, bg="#0B0F19")
        self.title_label = tk.Label(
            self.text_frame, 
            text="LUNA AI", 
            font=("Segoe UI", 9, "bold"), 
            fg="#FF2E93", 
            bg="#0B0F19",
            anchor="w"
        )
        self.title_label.pack(fill=tk.X, anchor="w")

        self.status_label = tk.Label(
            self.text_frame, 
            text="Standby", 
            font=("Segoe UI", 8), 
            fg="#FCE7F3", 
            bg="#0B0F19",
            anchor="w",
            justify="left",
            wraplength=210
        )
        self.status_label.pack(fill=tk.X, anchor="w")

        # Desenhar orbe inicial em standby
        self._draw_orb(standby=True)

        # Permitir arrastar a janela livremente
        for w in [self.container, self.canvas, self.text_frame, self.title_label, self.status_label]:
            w.bind("<Button-1>", self._start_drag)
            w.bind("<B1-Motion>", self._do_drag)

        self.root.mainloop()

    def _start_drag(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _do_drag(self, event):
        deltax = event.x - self._drag_data["x"]
        deltay = event.y - self._drag_data["y"]
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")
        self.margin_x = max(10, self.sw - (x + self.cur_w))
        self.margin_y = max(10, self.sh - (y + self.h))

    def _draw_orb(self, border_color="#FF007F", fill_color="#FF2E93", standby=False):
        self.canvas.delete("all")
        cx, cy = 24, 24
        if standby:
            # Standby: perfeitamente visível com orbe neon lunar brilhante
            self.canvas.create_oval(cx - 17, cy - 17, cx + 17, cy + 17, outline="#BE185D", width=1.5)
            self.canvas.create_oval(cx - 12, cy - 12, cx + 12, cy + 12, outline="#FF2E93", width=2.0)
            self.canvas.create_oval(cx - 6, cy - 6, cx + 6, cy + 6, fill="#FF007F", outline="#FF69B4")
        else:
            # Ativo: rosa/magenta neon vibrante e pulsante perfeitamente centralizado
            self.canvas.create_oval(cx - 18, cy - 18, cx + 18, cy + 18, outline=border_color, width=2.5)
            self.canvas.create_oval(cx - 10, cy - 10, cx + 10, cy + 10, fill=fill_color, outline=fill_color)

    def _cancel_animation(self):
        if self._anim_id and self.root:
            try:
                self.root.after_cancel(self._anim_id)
            except Exception:
                pass
            self._anim_id = None

    def _animate_to(self, target_w, step):
        if not self.root:
            return

        reached = (step > 0 and self.cur_w >= target_w) or (step < 0 and self.cur_w <= target_w)
        if reached:
            self.cur_w = target_w
            x = self.sw - self.cur_w - self.margin_x
            y = self.sh - self.h - self.margin_y
            self.root.geometry(f"{self.cur_w}x{self.h}+{x}+{y}")
            self._anim_id = None
            if not self.is_expanded:
                # Ocultar o frame de texto ao finalizar colapso total
                try:
                    self.text_frame.pack_forget()
                except Exception:
                    pass
                self.root.wm_attributes("-alpha", 0.85)
                self._draw_orb(standby=True)
                self.container.config(highlightbackground="#BE185D")
            return

        self.cur_w += step
        if step > 0 and self.cur_w > target_w:
            self.cur_w = target_w
        elif step < 0 and self.cur_w < target_w:
            self.cur_w = target_w

        x = self.sw - self.cur_w - self.margin_x
        y = self.sh - self.h - self.margin_y
        self.root.geometry(f"{self.cur_w}x{self.h}+{x}+{y}")
        self._anim_id = self.root.after(10, self._animate_to, target_w, step)

    def _apply_state(self, state, text):
        if not self.root:
            return

        self._cancel_animation()

        if state in ["listening", "thinking", "speaking"]:
            self.is_expanded = True
            self.root.wm_attributes("-alpha", 0.97)

            # GARANTIA ABSOLUTA: text_frame SEMPRE montado quando ativo!
            self.text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4, 10), pady=4)

            if state == "listening":
                self.container.config(highlightbackground="#FF007F")
                self._draw_orb("#FF007F", "#FF2E93", standby=False)
                self.title_label.config(text="LUNA • Ouvindo", fg="#FF2E93")
                self.status_label.config(text=text or "Estou ouvindo você...", fg="#FCE7F3")
            elif state == "thinking":
                self.container.config(highlightbackground="#A855F7")
                self._draw_orb("#A855F7", "#EC4899", standby=False)
                self.title_label.config(text="LUNA • Pensando", fg="#F472B6")
                self.status_label.config(text=text or "Processando resposta...", fg="#FCE7F3")
            elif state == "speaking":
                self.container.config(highlightbackground="#FF1493")
                self._draw_orb("#FF1493", "#FF69B4", standby=False)
                self.title_label.config(text="LUNA • Falando", fg="#FF69B4")
                self.status_label.config(text=text or "Falando em tempo real...", fg="#FCE7F3")

            if self.cur_w < self.max_w:
                self._animate_to(self.max_w, step=32)
        else:
            # Estado idle / standby -> volta suavemente para a bolinha
            self.is_expanded = False
            self.title_label.config(text="LUNA AI", fg="#FF2E93")
            self.status_label.config(text="Standby", fg="#FCE7F3")
            if self.cur_w > self.min_w:
                self._animate_to(self.min_w, step=-32)
            else:
                try:
                    self.text_frame.pack_forget()
                except Exception:
                    pass
                self.root.wm_attributes("-alpha", 0.85)
                self._draw_orb(standby=True)
                self.container.config(highlightbackground="#BE185D")

JarvisHUD = LunaHUD

