import json
import os
import threading
import time
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

import cv2
from PIL import Image, ImageTk

from detector import ColorDetector, ColorRange
from logger import DetectionLogger


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Color Detection Dashboard")
        self.root.geometry("1200x700")
        self.root.configure(bg="#1f1f1f")

        self.config_path = "config.json"
        self.config = self.load_config()
        self.detector = ColorDetector(min_area=self.config.get("min_area", 800))
        self.logger = DetectionLogger("detections.csv")

        self.cap = None
        self.running = False
        self.frame = None
        self.frame_lock = threading.Lock()
        self.last_log = 0.0
        self.fps = 0.0
        self.last_frame_time = time.time()

        self.stats_vars = {}
        self.hsv_vars = {k: tk.IntVar() for k in ["h_min", "h_max", "s_min", "s_max", "v_min", "v_max"]}
        self.active_color_var = tk.StringVar(value=self.config.get("active_color", "red"))

        self.build_ui()
        self.apply_color_to_sliders()
        self.start_camera()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_config(self):
        if os.path.exists(self.config_path):
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"active_color": "red", "min_area": 800, "colors": {}}

    def save_config(self):
        self.save_sliders_to_config()
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)
        self.status_var.set("Config saved")

    def build_ui(self):
        container = tk.Frame(self.root, bg="#1f1f1f")
        container.pack(fill="both", expand=True)

        self.video_label = tk.Label(container, bg="#111")
        self.video_label.place(relx=0.0, rely=0.0, relwidth=0.7, relheight=0.95)

        right_panel = tk.Frame(container, bg="#2a2a2a")
        right_panel.place(relx=0.7, rely=0.0, relwidth=0.3, relheight=0.95)

        notebook = ttk.Notebook(right_panel)
        notebook.pack(fill="both", expand=True, padx=8, pady=8)

        self.settings_tab = tk.Frame(notebook, bg="#2a2a2a")
        self.stats_tab = tk.Frame(notebook, bg="#2a2a2a")
        self.history_tab = tk.Frame(notebook, bg="#2a2a2a")
        notebook.add(self.settings_tab, text="Settings")
        notebook.add(self.stats_tab, text="Stats")
        notebook.add(self.history_tab, text="History")

        self.build_settings_tab()
        self.build_stats_tab()
        self.build_history_tab()

        status = tk.Frame(self.root, bg="#151515")
        status.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="Camera: Disconnected")
        tk.Label(status, textvariable=self.status_var, fg="#39ff14", bg="#151515").pack(side="left", padx=10, pady=4)

    def build_settings_tab(self):
        tk.Label(self.settings_tab, text="Active Color", bg="#2a2a2a", fg="white").pack(anchor="w", padx=8, pady=4)
        colors = list(self.config["colors"].keys())
        color_box = ttk.Combobox(self.settings_tab, textvariable=self.active_color_var, values=colors, state="readonly")
        color_box.pack(fill="x", padx=8)
        color_box.bind("<<ComboboxSelected>>", lambda _: self.apply_color_to_sliders())

        for key, label, frm, to in [
            ("h_min", "H min", 0, 179), ("h_max", "H max", 0, 179),
            ("s_min", "S min", 0, 255), ("s_max", "S max", 0, 255),
            ("v_min", "V min", 0, 255), ("v_max", "V max", 0, 255),
        ]:
            tk.Label(self.settings_tab, text=label, bg="#2a2a2a", fg="white").pack(anchor="w", padx=8, pady=(8, 0))
            tk.Scale(self.settings_tab, from_=frm, to=to, orient="horizontal", variable=self.hsv_vars[key], bg="#2a2a2a", fg="white", highlightthickness=0).pack(fill="x", padx=8)

        ttk.Button(self.settings_tab, text="Save Config", command=self.save_config).pack(fill="x", padx=8, pady=8)
        ttk.Button(self.settings_tab, text="Snapshot", command=self.snapshot).pack(fill="x", padx=8, pady=2)

    def build_stats_tab(self):
        for color in self.config["colors"].keys():
            var = tk.StringVar(value="0")
            self.stats_vars[color] = var
            row = tk.Frame(self.stats_tab, bg="#2a2a2a")
            row.pack(fill="x", padx=10, pady=6)
            tk.Label(row, text=f"{color.title()}:", bg="#2a2a2a", fg="white").pack(side="left")
            tk.Label(row, textvariable=var, bg="#2a2a2a", fg="#39ff14").pack(side="right")

    def build_history_tab(self):
        self.history_text = tk.Text(self.history_tab, bg="#121212", fg="#e6e6e6", height=20)
        self.history_text.pack(fill="both", expand=True, padx=8, pady=8)

    def apply_color_to_sliders(self):
        color = self.active_color_var.get()
        data = self.config["colors"][color]
        low, high = data["lower"], data["upper"]
        self.hsv_vars["h_min"].set(low[0]); self.hsv_vars["s_min"].set(low[1]); self.hsv_vars["v_min"].set(low[2])
        self.hsv_vars["h_max"].set(high[0]); self.hsv_vars["s_max"].set(high[1]); self.hsv_vars["v_max"].set(high[2])

    def save_sliders_to_config(self):
        color = self.active_color_var.get()
        self.config["active_color"] = color
        self.config["colors"][color]["lower"] = [self.hsv_vars["h_min"].get(), self.hsv_vars["s_min"].get(), self.hsv_vars["v_min"].get()]
        self.config["colors"][color]["upper"] = [self.hsv_vars["h_max"].get(), self.hsv_vars["s_max"].get(), self.hsv_vars["v_max"].get()]

    def get_color_ranges(self):
        self.save_sliders_to_config()
        ranges = []
        for name, cfg in self.config["colors"].items():
            ranges.append(ColorRange(name=name, lower=tuple(cfg["lower"]), upper=tuple(cfg["upper"]), box_color=tuple(cfg["box_color"])))
        return ranges

    def start_camera(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            messagebox.showerror("Camera Error", "Cannot open camera")
            return
        self.running = True
        self.status_var.set("Camera: Connected")
        threading.Thread(target=self.camera_loop, daemon=True).start()
        self.update_ui()

    def camera_loop(self):
        while self.running:
            ok, frame = self.cap.read()
            if not ok:
                self.status_var.set("Camera Lost")
                time.sleep(0.2)
                continue
            with self.frame_lock:
                self.frame = frame

    def update_ui(self):
        if not self.running:
            return
        frame = None
        with self.frame_lock:
            if self.frame is not None:
                frame = self.frame.copy()
        if frame is not None:
            out, counts, events = self.detector.detect(frame, self.get_color_ranges())
            now = time.time()
            dt = now - self.last_frame_time
            self.last_frame_time = now
            if dt > 0:
                self.fps = 1.0 / dt
            cv2.putText(out, f"FPS: {self.fps:.1f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (57, 255, 20), 2)

            rgb = cv2.cvtColor(out, cv2.COLOR_BGR2RGB)
            image = ImageTk.PhotoImage(Image.fromarray(rgb))
            self.video_label.configure(image=image)
            self.video_label.image = image

            for color, count in counts.items():
                self.stats_vars[color].set(str(count))

            if now - self.last_log > 1.0 and any(v > 0 for v in counts.values()):
                details = ", ".join([f"{e['color']} area={e['area']}" for e in events[:5]])
                self.logger.log_counts(counts, details)
                self.add_history(f"{datetime.now().strftime('%H:%M:%S')} - {details}")
                self.last_log = now

            self.status_var.set(f"Camera: Connected | FPS: {self.fps:.1f} | Log: detections.csv")

        self.root.after(15, self.update_ui)

    def add_history(self, msg: str):
        self.history_text.insert("end", msg + "\n")
        self.history_text.see("end")

    def snapshot(self):
        os.makedirs("captures", exist_ok=True)
        with self.frame_lock:
            if self.frame is None:
                return
            frame = self.frame.copy()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join("captures", f"snapshot_{ts}.png")
        cv2.imwrite(path, frame)
        self.add_history(f"Saved snapshot: {path}")

    def on_close(self):
        self.running = False
        if self.cap is not None:
            self.cap.release()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
