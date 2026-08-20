import os
import sys
import re
import time
import json
import shutil
import threading
import subprocess
import requests
import websocket
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import openpyxl

try:
    import ctypes
    from ctypes import wintypes
except ImportError:
    ctypes = None

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

TARGET_URL = "https://dkhp.uit.edu.vn/app/reg"
DEFAULT_FILES = ["mon_hoc.txt", "mon-hoc.txt"]
CHROME_DEBUG_PORT = 9222
USER_DATA_DIR = r"C:\chrome_debug"
AUTH_USER = "25520412"
AUTH_PASS = "QawJcz975zuBs$8"

class UITTurboEngine:
    def __init__(self, log_callback=None, status_callback=None):
        self.ws = None
        self.ws_url = None
        self.target_classes = []
        self.msg_id = 0
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.is_looping = False

    def log(self, tag, msg, level="info"):
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted = f"[{now}] [{tag:<10}] {msg}"
        if self.log_callback:
            self.log_callback(formatted, level)
        else:
            print(formatted)

    def find_chrome_path(self):
        potential_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
            shutil.which("chrome"),
            shutil.which("chrome.exe"),
        ]
        for path in potential_paths:
            if path and os.path.exists(path):
                return path
        return None

    def is_chrome_running(self):
        try:
            res = requests.get(f"http://localhost:{CHROME_DEBUG_PORT}/json/version", timeout=0.8)
            return res.status_code == 200
        except Exception:
            return False

    def ensure_chrome(self):
        if self.is_chrome_running():
            self.log("CHROME", "Chrome Debug port 9222 đã sẵn sàng.", "success")
            if self.status_callback:
                self.status_callback("Chrome: Đã kết nối", True)
            return True

        chrome_path = self.find_chrome_path()
        if not chrome_path:
            self.log("ERROR", "Không tìm thấy đường dẫn chrome.exe!", "error")
            if self.status_callback:
                self.status_callback("Chrome: Không tìm thấy", False)
            return False

        self.log("LAUNCH", f"Đang khởi chạy Chrome: {chrome_path}", "warning")
        cmd = [
            chrome_path,
            f"--remote-debugging-port={CHROME_DEBUG_PORT}",
            "--remote-allow-origins=*",
            f"--user-data-dir={USER_DATA_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            TARGET_URL
        ]
        
        subprocess.Popen(cmd)
        
        for _ in range(25):
            time.sleep(0.3)
            if self.is_chrome_running():
                self.log("SUCCESS", "Chrome đã mở và kết nối thành công!", "success")
                if self.status_callback:
                    self.status_callback("Chrome: Đã kết nối", True)
                return True

        self.log("ERROR", "Không thể kết nối tới Chrome sau khi khởi động.", "error")
        if self.status_callback:
            self.status_callback("Chrome: Lỗi kết nối", False)
        return False

    def get_or_create_target_tab(self):
        try:
            res = requests.get(f"http://localhost:{CHROME_DEBUG_PORT}/json", timeout=2)
            tabs = res.json()
        except Exception as e:
            self.log("ERROR", f"Lỗi lấy danh sách tab: {e}", "error")
            return None

        for tab in tabs:
            url = tab.get("url", "")
            if "dkhp.uit.edu.vn" in url or "cas.uit.edu.vn" in url:
                return tab

        try:
            new_tab = requests.put(f"http://localhost:{CHROME_DEBUG_PORT}/json/new?{TARGET_URL}", timeout=2).json()
            time.sleep(0.5)
            return new_tab
        except Exception:
            if tabs:
                return tabs[0]
        return None

    def connect_ws(self):
        tab = self.get_or_create_target_tab()
        if not tab:
            return False

        self.ws_url = tab.get("webSocketDebuggerUrl")
        if not self.ws_url:
            self.log("ERROR", "Tab không có WebSocket URL.", "error")
            return False

        try:
            if self.ws:
                try:
                    self.ws.close()
                except Exception:
                    pass
            self.ws = websocket.create_connection(self.ws_url, suppress_origin=True, timeout=5)
            self.log("WS", "Đã duy trì kết nối WebSocket trực tiếp (0ms delay).", "success")
            return True
        except Exception as e:
            self.log("ERROR", f"Lỗi kết nối WebSocket: {e}", "error")
            return False

    def send_cdp(self, method, params=None):
        if not self.ws:
            if not self.connect_ws():
                return None
        self.msg_id += 1
        payload = {
            "id": self.msg_id,
            "method": method,
            "params": params or {}
        }
        try:
            self.ws.send(json.dumps(payload))
            raw = self.ws.recv()
            return json.loads(raw)
        except Exception:
            if self.connect_ws():
                try:
                    self.ws.send(json.dumps(payload))
                    raw = self.ws.recv()
                    return json.loads(raw)
                except Exception:
                    pass
            return None

    def eval_js(self, expression, await_promise=False):
        res = self.send_cdp("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": await_promise
        })
        if res and "result" in res and "result" in res["result"]:
            return res["result"]["result"].get("value")
        return None

    def reload_tab(self):
        self.send_cdp("Page.reload", {"ignoreCache": True})

    def auto_fill_login(self):
        fill_js = f"""
        (() => {{
          const user = "{AUTH_USER}";
          const pass = "{AUTH_PASS}";

          if (document.querySelector("table tbody tr")) return {{ status: "logged_in" }};

          const userInputs = Array.from(document.querySelectorAll("input[name*='user' i], input[id*='user' i], input[type='text'], input[placeholder*='mã' i], input[placeholder*='MSSV' i], input[placeholder*='tên' i]"));
          const passInputs = Array.from(document.querySelectorAll("input[type='password'], input[name*='pass' i], input[id*='pass' i]"));

          const userInput = userInputs.find(i => i.offsetParent !== null) || userInputs[0];
          const passInput = passInputs.find(i => i.offsetParent !== null) || passInputs[0];

          if (userInput && passInput) {{
            const setVal = (el, val) => {{
              el.focus();
              el.value = val;
              el.dispatchEvent(new Event('input', {{ bubbles: true }}));
              el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }};

            setVal(userInput, user);
            setVal(passInput, pass);

            const captchaEl = document.querySelector("img[src*='captcha' i], div[class*='captcha' i], iframe[src*='recaptcha' i], input[name*='captcha' i]");
            
            return {{
              status: "filled",
              hasCaptcha: !!captchaEl
            }};
          }}

          return {{ status: "no_form", url: window.location.href }};
        }})();
        """

        res = self.eval_js(fill_js)
        if isinstance(res, dict):
            status = res.get("status")
            if status == "logged_in":
                self.log("AUTH", "Đã đăng nhập và đang ở trang ĐKHP.", "success")
            elif status == "filled":
                has_captcha = res.get("hasCaptcha", False)
                self.log("AUTH", f"Đã tự điền tài khoản '{AUTH_USER}'.", "success")
                if has_captcha:
                    self.log("CAPTCHA", "Phát hiện Captcha! Bạn hãy nhập Captcha trên Chrome và Đăng nhập.", "warning")
                else:
                    self.log("NOTICE", "Hãy kiểm tra Chrome và bấm Đăng nhập nếu cần.", "warning")

    def build_turbo_payload(self):
        return f"""
        (() => {{
          const t0 = performance.now();
          const targets = new Set({json.dumps(self.target_classes)}.map(c => c.trim().toUpperCase()));
          const found = [];
          const newlyTicked = [];
          const alreadyTicked = [];

          const rows = document.querySelectorAll("table tbody tr");
          if (rows.length === 0) return {{ status: "error", message: "Chưa thấy bảng học phần trên trang!" }};

          for (let i = 0; i < rows.length; i++) {{
            const row = rows[i];
            const cells = row.querySelectorAll("td");
            if (cells.length < 2) continue;
            const code = (cells[1].innerText || cells[1].textContent || "").trim().toUpperCase();

            if (targets.has(code)) {{
              found.push(code);
              const cb = row.querySelector("input[type='checkbox']") || cells[0].querySelector("input");
              if (cb) {{
                if (!cb.checked) {{
                  cb.click();
                  cb.dispatchEvent(new Event('change', {{ bubbles: true }}));
                  newlyTicked.push(code);
                }} else {{
                  alreadyTicked.push(code);
                }}
              }} else {{
                cells[0].click();
                newlyTicked.push(code);
              }}
            }}
          }}

          const notFound = Array.from(targets).filter(c => !found.includes(c));

          const btn = 
            document.querySelector("div.detailBar button.chakra-button.css-kyhdse") ||
            document.querySelector("div.detailBar button") ||
            document.querySelector("html body.chakra-ui-light div.css-7t4500 div.css-7t4500 div.css-b95f0i div.css-15u5c5a div.css-1n8vwuv div.css-1luud69 div.chakra-stack.css-1ozbvuw div.css-16b2evc form div.p-2 div.detailBar.fixed.w-full.left-0.bottom-0.bg-gray-100.z-10.border-t.border-solid.border-gray-300.text-center.py-2 div.w-full.justify-center.items-center div.chakra-stack.css-1rafi8n button.chakra-button.css-kyhdse") ||
            Array.from(document.querySelectorAll("button")).find(b => (b.innerText || "").includes("Đăng ký"));

          let clicked = false;
          if (btn) {{
            btn.scrollIntoView({{ behavior: "instant", block: "center" }});
            btn.click();
            clicked = true;
          }}

          const elapsedMs = (performance.now() - t0).toFixed(2);

          return {{
            status: "ok",
            newlyTicked: newlyTicked,
            alreadyTicked: alreadyTicked,
            notFound: notFound,
            clickedRegister: clicked,
            elapsedMs: elapsedMs
          }};
        }})();
        """

    def fire(self):
        if not self.target_classes:
            self.log("WARN", "Chưa có mã môn học nào được nạp!", "warning")
            return False

        t_start = time.time()
        result = self.eval_js(self.build_turbo_payload())
        total_time_ms = round((time.time() - t_start) * 1000, 2)

        if not isinstance(result, dict) or result.get("status") == "error":
            msg = result.get("message") if isinstance(result, dict) else "Không nhận được phản hồi"
            self.log("ERROR", f"Lỗi: {msg} ({total_time_ms}ms)", "error")
            return False

        newly = result.get("newlyTicked", [])
        already = result.get("alreadyTicked", [])
        not_found = result.get("notFound", [])
        clicked = result.get("clickedRegister", False)
        js_time = result.get("elapsedMs", "0")

        self.log("FIRE", f"Thực thi trong {js_time}ms (Tổng: {total_time_ms}ms)", "success")

        if newly:
            self.log("TICK MỚI", f"({len(newly)} môn) {', '.join(newly)}", "success")
        if already:
            self.log("CÓ SẴN", f"({len(already)} môn) {', '.join(already)}", "info")
        if not_found:
            self.log("CHƯA THẤY", f"({len(not_found)} môn) {', '.join(not_found)}", "warning")

        if clicked:
            self.log("SUCCESS", "🎉 ĐÃ TICK TOÀN BỘ MÔN VÀ BẤM NÚT ĐĂNG KÝ THÀNH CÔNG!", "success")
            return True
        else:
            self.log("WARN", "Đã tick môn nhưng chưa thấy nút Đăng ký!", "warning")
            return False

    def auto_fire_loop(self, interval_sec=0.05, max_seconds=30):
        self.is_looping = True
        self.log("LOOP", f"Kích hoạt bắn liên tục mỗi {int(interval_sec*1000)}ms...", "warning")
        start = time.time()
        attempts = 0
        while self.is_looping and (time.time() - start < max_seconds):
            attempts += 1
            res = self.eval_js(self.build_turbo_payload())
            if isinstance(res, dict) and res.get("status") == "ok":
                if res.get("clickedRegister"):
                    self.log("SUCCESS", f"Đã đăng ký thành công sau {attempts} lần bắn!", "success")
                    self.is_looping = False
                    return True
                elif res.get("newlyTicked") or res.get("alreadyTicked"):
                    self.log("INFO", f"Đã tick được môn sau {attempts} lần bắn!", "info")
            time.sleep(interval_sec)
        self.is_looping = False
        self.log("STOP", "Đã dừng chế độ auto-fire.", "info")
        return False

class UITGuiApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("UIT ĐKHP - TURBO CONTROL PANEL")
        self.geometry("640x820")
        self.minsize(580, 720)

        self.engine = UITTurboEngine(
            log_callback=self.append_log_threadsafe,
            status_callback=self.update_status_threadsafe
        )

        self.timer_running = False
        self.timer_target_str = ""

        self.setup_ui()
        self.load_initial_subjects()
        self.bind_shortcuts()
        self.start_clock_thread()

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.header_frame = ctk.CTkFrame(self, corner_radius=10, fg_color=("#1f2937", "#111827"))
        self.header_frame.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            self.header_frame, 
            text="⚡ UIT ĐKHP TURBO PANEL", 
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#38bdf8"
        )
        title_label.grid(row=0, column=0, padx=12, pady=(10, 2), sticky="w")

        subtitle_label = ctk.CTkLabel(
            self.header_frame, 
            text="Độ trễ < 2ms | Chrome Debug CDP | Hỗ trợ Excel & Hotkey", 
            font=ctk.CTkFont(size=12),
            text_color="#9ca3af"
        )
        subtitle_label.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="w")

        self.status_badge = ctk.CTkLabel(
            self.header_frame,
            text="Chrome: Chưa kết nối",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#374151",
            text_color="#f87171",
            corner_radius=6,
            padx=10,
            pady=4
        )
        self.status_badge.grid(row=0, column=1, rowspan=2, padx=12, pady=10, sticky="e")

        self.input_frame = ctk.CTkFrame(self, corner_radius=10)
        self.input_frame.grid(row=1, column=0, padx=12, pady=6, sticky="ew")
        self.input_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        input_title = ctk.CTkLabel(
            self.input_frame, 
            text="📋 Danh sách mã môn học (Mỗi mã 1 dòng hoặc cách nhau bằng dấu phẩy):", 
            font=ctk.CTkFont(size=13, weight="bold")
        )
        input_title.grid(row=0, column=0, columnspan=4, padx=12, pady=(8, 4), sticky="w")

        self.txt_subjects = ctk.CTkTextbox(self.input_frame, height=140, font=ctk.CTkFont(family="Consolas", size=13))
        self.txt_subjects.grid(row=1, column=0, columnspan=4, padx=12, pady=4, sticky="ew")

        btn_import_excel = ctk.CTkButton(
            self.input_frame, 
            text="📁 Import Excel / File", 
            command=self.import_file,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(weight="bold")
        )
        btn_import_excel.grid(row=2, column=0, padx=(12, 4), pady=8, sticky="ew")

        btn_save = ctk.CTkButton(
            self.input_frame, 
            text="💾 Lưu danh sách", 
            command=self.save_subjects_to_file,
            fg_color="#059669",
            hover_color="#047857",
            font=ctk.CTkFont(weight="bold")
        )
        btn_save.grid(row=2, column=1, padx=4, pady=8, sticky="ew")

        btn_sample = ctk.CTkButton(
            self.input_frame, 
            text="🔄 Nạp mẫu", 
            command=self.load_sample_subjects,
            fg_color="#4b5563",
            hover_color="#374151"
        )
        btn_sample.grid(row=2, column=2, padx=4, pady=8, sticky="ew")

        btn_clear = ctk.CTkButton(
            self.input_frame, 
            text="🗑️ Xóa trắng", 
            command=lambda: self.txt_subjects.delete("1.0", tk.END),
            fg_color="#dc2626",
            hover_color="#b91c1c"
        )
        btn_clear.grid(row=2, column=3, padx=(4, 12), pady=8, sticky="ew")

        self.control_frame = ctk.CTkFrame(self, corner_radius=10)
        self.control_frame.grid(row=2, column=0, padx=12, pady=6, sticky="ew")
        self.control_frame.grid_columnconfigure((0, 1), weight=1)

        self.btn_open_chrome = ctk.CTkButton(
            self.control_frame,
            text="🌐 MỞ CHROME & SNAP 1 BÊN",
            command=self.open_and_snap_chrome,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            height=42
        )
        self.btn_open_chrome.grid(row=0, column=0, padx=(12, 6), pady=(10, 6), sticky="ew")

        self.btn_f5_loop = ctk.CTkButton(
            self.control_frame,
            text="🔄 F5 & BẮN LIÊN TỤC (50ms)",
            command=self.trigger_f5_loop,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#d97706",
            hover_color="#b45309",
            height=42
        )
        self.btn_f5_loop.grid(row=0, column=1, padx=(6, 12), pady=(10, 6), sticky="ew")

        self.btn_fire_now = ctk.CTkButton(
            self.control_frame,
            text="🚀 ĐĂNG KÝ TỨC THÌ (SPACE / ENTER)",
            command=self.trigger_fire_now,
            font=ctk.CTkFont(size=17, weight="bold"),
            fg_color="#16a34a",
            hover_color="#15803d",
            height=54
        )
        self.btn_fire_now.grid(row=1, column=0, columnspan=2, padx=12, pady=6, sticky="ew")

        timer_subframe = ctk.CTkFrame(self.control_frame, fg_color="transparent")
        timer_subframe.grid(row=2, column=0, columnspan=2, padx=12, pady=(4, 10), sticky="ew")
        timer_subframe.grid_columnconfigure(1, weight=1)

        lbl_timer = ctk.CTkLabel(timer_subframe, text="⏱️ Hẹn giờ tự bắn:", font=ctk.CTkFont(weight="bold"))
        lbl_timer.grid(row=0, column=0, padx=(0, 6), sticky="w")

        self.entry_timer = ctk.CTkEntry(timer_subframe, placeholder_text="09:00:00.000", font=ctk.CTkFont(family="Consolas"))
        self.entry_timer.grid(row=0, column=1, padx=6, sticky="ew")

        self.btn_timer = ctk.CTkButton(
            timer_subframe,
            text="Đặt giờ",
            command=self.toggle_timer,
            width=90,
            fg_color="#8b5cf6",
            hover_color="#7c3aed"
        )
        self.btn_timer.grid(row=0, column=2, padx=(6, 0), sticky="e")

        self.lbl_clock = ctk.CTkLabel(
            timer_subframe,
            text="00:00:00.000",
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_clock.grid(row=0, column=3, padx=(10, 0), sticky="e")

        self.log_frame = ctk.CTkFrame(self, corner_radius=10)
        self.log_frame.grid(row=3, column=0, padx=12, pady=(6, 12), sticky="nsew")
        self.log_frame.grid_columnconfigure(0, weight=1)
        self.log_frame.grid_rowconfigure(1, weight=1)

        log_header = ctk.CTkFrame(self.log_frame, fg_color="transparent")
        log_header.grid(row=0, column=0, padx=10, pady=(6, 2), sticky="ew")
        log_header.grid_columnconfigure(0, weight=1)

        lbl_log = ctk.CTkLabel(log_header, text="📜 Live Terminal Log:", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_log.grid(row=0, column=0, sticky="w")

        btn_clear_log = ctk.CTkButton(
            log_header, 
            text="Xóa log", 
            width=60, 
            height=24, 
            command=self.clear_log,
            fg_color="#374151",
            hover_color="#1f2937"
        )
        btn_clear_log.grid(row=0, column=1, sticky="e")

        self.txt_log = ctk.CTkTextbox(
            self.log_frame, 
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#0f172a",
            text_color="#f8fafc"
        )
        self.txt_log.grid(row=1, column=0, padx=10, pady=(2, 10), sticky="nsew")

    def bind_shortcuts(self):
        self.bind("<Return>", lambda e: self.trigger_fire_now() if e.widget != self.txt_subjects else None)
        self.bind("<space>", lambda e: self.trigger_fire_now() if e.widget != self.txt_subjects and e.widget != self.entry_timer else None)
        self.bind("<F5>", lambda e: self.trigger_f5_loop())

    def append_log_threadsafe(self, text, level="info"):
        self.after(0, self._append_log_ui, text, level)

    def _append_log_ui(self, text, level):
        tag_color = "#38bdf8"
        if level == "success":
            tag_color = "#4ade80"
        elif level == "warning":
            tag_color = "#facc15"
        elif level == "error":
            tag_color = "#f87171"

        self.txt_log.insert(tk.END, text + "\n")
        self.txt_log.see(tk.END)

    def update_status_threadsafe(self, text, connected):
        self.after(0, self._update_status_ui, text, connected)

    def _update_status_ui(self, text, connected):
        self.status_badge.configure(
            text=text,
            text_color="#4ade80" if connected else "#f87171",
            fg_color="#14532d" if connected else "#450a0a"
        )

    def clear_log(self):
        self.txt_log.delete("1.0", tk.END)

    def parse_subjects_from_text(self, raw_text):
        pattern = r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)+"
        matches = re.findall(pattern, raw_text)
        if not matches:
            lines = [l.strip().upper() for l in raw_text.splitlines() if l.strip() and not l.startswith("#")]
            return lines
        clean = []
        for m in matches:
            up = m.strip().upper()
            if not up.startswith("HTTP") and not up.startswith("WWW") and up not in clean:
                clean.append(up)
        return clean

    def get_current_subjects(self):
        raw = self.txt_subjects.get("1.0", tk.END)
        return self.parse_subjects_from_text(raw)

    def load_initial_subjects(self):
        for fn in DEFAULT_FILES:
            if os.path.exists(fn):
                with open(fn, "r", encoding="utf-8") as f:
                    content = f.read()
                subs = self.parse_subjects_from_text(content)
                if subs:
                    self.txt_subjects.delete("1.0", tk.END)
                    self.txt_subjects.insert(tk.END, "\n".join(subs))
                    self.engine.target_classes = subs
                    self.append_log_threadsafe(f"Đã nạp {len(subs)} môn từ {fn}", "info")
                    return
        self.load_sample_subjects()

    def load_sample_subjects(self):
        samples = [
            "IT012.R11", "IT012.R11.1", "SS007.R15", "SS003.R14",
            "IT005.R18", "IT005.R18.2", "IT007.R111.1", "IT007.R111",
            "IT004.R117", "IT004.R117.1"
        ]
        self.txt_subjects.delete("1.0", tk.END)
        self.txt_subjects.insert(tk.END, "\n".join(samples))
        self.engine.target_classes = samples
        self.append_log_threadsafe(f"Đã nạp {len(samples)} môn mẫu.", "info")

    def save_subjects_to_file(self):
        subs = self.get_current_subjects()
        if not subs:
            messagebox.showwarning("Cảnh báo", "Chưa có mã môn học nào trong ô văn bản!")
            return
        with open("mon-hoc.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(subs))
        self.engine.target_classes = subs
        self.append_log_threadsafe(f"Đã lưu {len(subs)} môn vào mon-hoc.txt", "success")
        messagebox.showinfo("Thành công", f"Đã lưu {len(subs)} mã môn học vào mon-hoc.txt!")

    def import_file(self):
        path = filedialog.askopenfilename(
            title="Chọn file môn học",
            filetypes=[
                ("Tất cả file hỗ trợ", "*.xlsx;*.xls;*.csv;*.txt"),
                ("Excel Files", "*.xlsx;*.xls"),
                ("Text / CSV", "*.txt;*.csv")
            ]
        )
        if not path:
            return

        subs = []
        ext = os.path.splitext(path)[1].lower()

        try:
            if ext in [".xlsx", ".xls"]:
                wb = openpyxl.load_workbook(path, data_only=True)
                for sheet in wb.worksheets:
                    for row in sheet.iter_rows(values_only=True):
                        for val in row:
                            if val:
                                sval = str(val).strip()
                                found = self.parse_subjects_from_text(sval)
                                for f in found:
                                    if f not in subs:
                                        subs.append(f)
            else:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                subs = self.parse_subjects_from_text(content)

            if subs:
                self.txt_subjects.delete("1.0", tk.END)
                self.txt_subjects.insert(tk.END, "\n".join(subs))
                self.engine.target_classes = subs
                self.append_log_threadsafe(f"Đã import thành công {len(subs)} mã môn từ {os.path.basename(path)}", "success")
            else:
                messagebox.showwarning("Không tìm thấy", "Không tìm thấy mã môn học hợp lệ nào trong file!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi đọc file: {e}")

    def snap_windows(self):
        if not ctypes:
            return
        user32 = ctypes.windll.user32
        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)

        gui_w = int(sw * 0.40)
        gui_h = sh - 40
        gui_x = sw - gui_w
        gui_y = 0

        self.geometry(f"{gui_w}x{gui_h}+{gui_x}+{gui_y}")

        chrome_w = sw - gui_w
        chrome_h = sh - 40

        def enum_cb(hwnd, lparam):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if "Chrome" in title or "ĐKHP" in title or "localhost:9222" in title:
                        user32.ShowWindow(hwnd, 9)
                        user32.MoveWindow(hwnd, 0, 0, chrome_w, chrome_h, True)
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

    def open_and_snap_chrome(self):
        def _run():
            self.engine.ensure_chrome()
            time.sleep(0.8)
            self.engine.connect_ws()
            self.engine.auto_fill_login()
            self.after(500, self.snap_windows)
        threading.Thread(target=_run, daemon=True).start()

    def trigger_fire_now(self):
        self.engine.target_classes = self.get_current_subjects()
        def _run():
            self.engine.fire()
        threading.Thread(target=_run, daemon=True).start()

    def trigger_f5_loop(self):
        self.engine.target_classes = self.get_current_subjects()
        def _run():
            self.append_log_threadsafe("F5 tải lại trang...", "warning")
            self.engine.reload_tab()
            time.sleep(0.8)
            self.engine.auto_fire_loop(interval_sec=0.05, max_seconds=15)
        threading.Thread(target=_run, daemon=True).start()

    def toggle_timer(self):
        if self.timer_running:
            self.timer_running = False
            self.btn_timer.configure(text="Đặt giờ", fg_color="#8b5cf6")
            self.append_log_threadsafe("Đã hủy hẹn giờ.", "info")
            return

        target = self.entry_timer.get().strip()
        if not target:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập giờ hẹn dạng HH:MM:SS hoặc HH:MM:SS.mmm")
            return

        self.timer_target_str = target
        self.timer_running = True
        self.btn_timer.configure(text="Hủy hẹn", fg_color="#dc2626")
        self.append_log_threadsafe(f"Đã đặt lịch hẹn tự động bắn lúc: {target}", "warning")

    def start_clock_thread(self):
        def _clock_loop():
            while True:
                now = datetime.now()
                now_str = now.strftime("%H:%M:%S.%f")[:-3]
                self.after(0, lambda s=now_str: self.lbl_clock.configure(text=s))

                if self.timer_running and self.timer_target_str:
                    cur_hms = now.strftime("%H:%M:%S")
                    if self.timer_target_str.startswith(cur_hms):
                        self.timer_running = False
                        self.after(0, lambda: self.btn_timer.configure(text="Đặt giờ", fg_color="#8b5cf6"))
                        self.append_log_threadsafe(f"⏰ ĐẾN GIỜ {now_str}! TỰ ĐỘNG BẮN LỆNH!", "success")
                        self.trigger_fire_now()

                time.sleep(0.02)
        threading.Thread(target=_clock_loop, daemon=True).start()

if __name__ == "__main__":
    app = UITGuiApp()
    app.mainloop()
