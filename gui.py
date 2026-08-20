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
ACCOUNT_FILES = ["tai-khoan.txt", "tai_khoan.txt", "account.txt"]
CONFIG_FILE = "config.json"
DEFAULT_AUTH_USER = ""
DEFAULT_AUTH_PASS = ""

GWL_STYLE = -16
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_BORDER = 0x00800000

class UITTurboEngine:
    def __init__(self, log_callback=None, status_callback=None):
        self.ws = None
        self.ws_url = None
        self.target_classes = []
        self.msg_id = 0
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.is_looping = False
        self.chrome_process = None
        self.chrome_hwnd = None
        self.auth_user = DEFAULT_AUTH_USER
        self.auth_pass = DEFAULT_AUTH_PASS
        self.load_config()

    def parse_account_text(self, text):
        user = ""
        passw = ""
        lines = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#") and not l.strip().startswith("//")]
        for line in lines:
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip().upper()
                v = v.strip()
                if k in ("USER", "USERNAME", "MSSV", "TAI_KHOAN", "TAIKHOAN", "ID", "ACCOUNT"):
                    user = v
                elif k in ("PASS", "PASSWORD", "MAT_KHAU", "MATKHAU", "PASSW", "MK"):
                    passw = v
            elif "|" in line:
                parts = line.split("|", 1)
                user = parts[0].strip()
                passw = parts[1].strip()
            elif ":" in line and not line.startswith("http"):
                parts = line.split(":", 1)
                user = parts[0].strip()
                passw = parts[1].strip()

        if not user and len(lines) >= 1:
            user = lines[0]
        if not passw and len(lines) >= 2:
            passw = lines[1]
        return user, passw

    def load_config(self):
        self.auth_user = DEFAULT_AUTH_USER
        self.auth_pass = DEFAULT_AUTH_PASS

        # 1. Đọc từ tai-khoan.txt trước
        for fn in ACCOUNT_FILES:
            if os.path.exists(fn):
                try:
                    with open(fn, "r", encoding="utf-8") as f:
                        content = f.read()
                    u, p = self.parse_account_text(content)
                    if u or p:
                        self.auth_user = u
                        self.auth_pass = p
                        return
                except Exception:
                    pass

        # 2. Nếu chưa có, đọc từ config.json
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.auth_user = cfg.get("auth_user", DEFAULT_AUTH_USER)
                    self.auth_pass = cfg.get("auth_pass", DEFAULT_AUTH_PASS)
            except Exception:
                pass

    def save_config(self, user, password):
        self.auth_user = user
        self.auth_pass = password
        success = True
        try:
            with open("tai-khoan.txt", "w", encoding="utf-8") as f:
                f.write(f"# Thông tin tài khoản ĐKHP UIT\nUSER={user}\nPASS={password}\n")
        except Exception:
            success = False
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"auth_user": user, "auth_pass": password}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        return success

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

    def launch_chrome_embedded(self, container_hwnd, width=800, height=700):
        chrome_path = self.find_chrome_path()
        if not chrome_path:
            self.log("ERROR", "Không tìm thấy file chrome.exe!", "error")
            if self.status_callback:
                self.status_callback("Chrome: Không tìm thấy", False)
            return False

        if not self.is_chrome_running():
            self.log("LAUNCH", "Khởi động Chrome & nhúng trực tiếp...", "warning")
            cmd = [
                chrome_path,
                f"--app={TARGET_URL}",
                "--window-position=-10000,-10000",
                f"--window-size={max(width, 800)},{max(height, 700)}",
                f"--remote-debugging-port={CHROME_DEBUG_PORT}",
                "--remote-allow-origins=*",
                f"--user-data-dir={USER_DATA_DIR}",
                "--no-first-run",
                "--no-default-browser-check"
            ]
            self.chrome_process = subprocess.Popen(cmd)

        connected = False
        embedded = False
        for _ in range(40):
            if not embedded:
                embedded = self.embed_chrome_window(container_hwnd, width, height, max_attempts=1, delay=0.0)
            if not connected and self.is_chrome_running():
                connected = True
            if embedded and connected:
                break
            time.sleep(0.06)

        if not embedded:
            self.embed_chrome_window(container_hwnd, width, height, max_attempts=12, delay=0.08)

        if not self.is_chrome_running():
            self.log("ERROR", "Không thể kết nối tới Chrome Debug port.", "error")
            return False

        self.log("SUCCESS", "Chrome đã sẵn sàng.", "success")
        if self.status_callback:
            self.status_callback("Chrome: Đã kết nối", True)

        self.connect_ws()
        self.auto_fill_login()
        return True

    def _get_process_image_path(self, pid):
        if not ctypes or not pid:
            return ""
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h_proc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h_proc:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
                return buf.value
        except Exception:
            pass
        finally:
            kernel32.CloseHandle(h_proc)
        return ""

    def find_target_chrome_hwnd(self, container_hwnd):
        if not ctypes:
            return None

        user32 = ctypes.windll.user32
        my_pid = os.getpid()
        target_pid = self.chrome_process.pid if self.chrome_process else None
        candidates = []

        def enum_windows_callback(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True

            parent = user32.GetParent(hwnd)
            if parent != 0 and parent != container_hwnd:
                return True

            class_buff = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, class_buff, 256)
            cls_name = class_buff.value

            if cls_name != "Chrome_WidgetWin_1":
                return True

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == my_pid:
                return True

            exe_path = self._get_process_image_path(pid.value)
            exe_name = os.path.basename(exe_path).lower()

            # BẮT BUỘC: Chỉ nhận tiến trình chrome.exe thực sự (loại bỏ VS Code, Antigravity IDE, Electron...)
            if exe_name != "chrome.exe":
                return True

            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            if w < 100 or h < 100:
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.lower()

            score = 0
            if target_pid and pid.value == target_pid:
                score += 1000

            if parent == container_hwnd:
                score += 500

            title_keywords = ["dkhp", "đkhp", "uit", "đăng ký", "học phần", "cổng thông tin", "cas", "chrome"]
            for kw in title_keywords:
                if kw in title:
                    score += 100

            unrelated = ["youtube", "facebook", "google search", "gmail", "chatgpt"]
            for kw in unrelated:
                if kw in title:
                    score -= 500

            candidates.append((score, hwnd, title))
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_windows_callback), 0)

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def embed_chrome_window(self, container_hwnd, width=800, height=700, max_attempts=20, delay=0.08):
        if not ctypes or not container_hwnd:
            return False

        user32 = ctypes.windll.user32
        found_hwnd = None

        for _ in range(max_attempts):
            found_hwnd = self.find_target_chrome_hwnd(container_hwnd)
            if found_hwnd:
                break
            if delay > 0:
                time.sleep(delay)

        if found_hwnd:
            self.chrome_hwnd = found_hwnd
            # Khôi phục và nhúng vào container
            user32.ShowWindow(found_hwnd, 9)  # SW_RESTORE
            user32.SetParent(found_hwnd, container_hwnd)
            
            style = user32.GetWindowLongW(found_hwnd, GWL_STYLE)
            style &= ~WS_CAPTION
            style &= ~WS_THICKFRAME
            style &= ~WS_BORDER
            style &= ~0x00020000  # WS_MINIMIZEBOX
            style &= ~0x00010000  # WS_MAXIMIZEBOX
            style &= ~0x00080000  # WS_SYSMENU
            style |= WS_CHILD | WS_VISIBLE
            user32.SetWindowLongW(found_hwnd, GWL_STYLE, style)
            
            # SWP_FRAMECHANGED (0x0020) | SWP_SHOWWINDOW (0x0040) | SWP_NOZORDER (0x0004)
            user32.SetWindowPos(found_hwnd, 0, 0, 0, width, height, 0x0020 | 0x0040 | 0x0004)
            user32.MoveWindow(found_hwnd, 0, 0, width, height, True)
            user32.UpdateWindow(found_hwnd)
            self.log("EMBED", "Đã nhúng Chrome trực tiếp vào giao diện.", "success")
            return True
        else:
            return False

    def resize_embedded_chrome(self, width, height):
        if ctypes and self.chrome_hwnd and width > 0 and height > 0:
            user32 = ctypes.windll.user32
            user32.MoveWindow(self.chrome_hwnd, 0, 0, width, height, True)
            user32.UpdateWindow(self.chrome_hwnd)

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
            self.log("WS", "Đã kết nối WebSocket trực tiếp tới tab ĐKHP.", "success")
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

    def navigate_home(self):
        self.send_cdp("Page.navigate", {"url": TARGET_URL})

    def auto_fill_login(self):
        if not self.auth_user or not self.auth_pass:
            self.log("AUTH", "Chưa cấu hình tài khoản/mật khẩu. Bạn có thể vào tab '👤 TÀI KHOẢN' để lưu.", "info")
            return

        fill_js = f"""
        (() => {{
          const user = {json.dumps(self.auth_user)};
          const pass = {json.dumps(self.auth_pass)};

          if (document.querySelector("table tbody tr")) return {{ status: "logged_in" }};

          const userInputs = Array.from(document.querySelectorAll("input[name*='user' i], input[id*='user' i], input[type='text'], input[placeholder*='mã' i], input[placeholder*='MSSV' i], input[placeholder*='tên' i]"));
          const passInputs = Array.from(document.querySelectorAll("input[type='password'], input[name*='pass' i], input[id*='pass' i]"));

          const userInput = userInputs.find(i => i.offsetParent !== null) || userInputs[0];
          const passInput = passInputs.find(i => i.offsetParent !== null) || passInputs[0];

          if (userInput && passInput) {{
            const setVal = (el, val) => {{
              el.focus();
              try {{
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                if (setter) setter.call(el, val);
                else el.value = val;
              }} catch(e) {{
                el.value = val;
              }}
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
                self.log("AUTH", "Đã ở trong trang ĐKHP.", "success")
            elif status == "filled":
                has_captcha = res.get("hasCaptcha", False)
                self.log("AUTH", f"Đã tự điền tài khoản '{self.auth_user}'.", "success")
                if has_captcha:
                    self.log("CAPTCHA", "Có Captcha! Bạn hãy nhập Captcha trong khung Chrome và Đăng nhập.", "warning")
                else:
                    self.log("NOTICE", "Hãy bấm Đăng nhập trong khung Chrome nếu chưa vào trang.", "warning")

    def build_turbo_payload(self):
        return f"""
        (() => {{
          const t0 = performance.now();
          const targets = new Set({json.dumps(self.target_classes)}.map(c => c.trim().toUpperCase()));
          const found = [];
          const newlyTicked = [];
          const alreadyTicked = [];

          const rows = document.querySelectorAll("table tbody tr");
          if (rows.length === 0) return {{ status: "error", message: "Chưa thấy bảng học phần trong khung Chrome!" }};

          for (let i = 0; i < rows.length; i++) {{
            const row = rows[i];
            const cells = row.querySelectorAll("td");
            if (cells.length < 2) continue;

            let matchCode = null;
            for (let c = 1; c < Math.min(cells.length, 5); c++) {{
              const fullText = (cells[c].innerText || cells[c].textContent || "").trim().toUpperCase();
              const firstWord = fullText.split(/[\\s\\n\\r\\t\\-]+/)[0];
              if (targets.has(fullText)) {{ matchCode = fullText; break; }}
              if (targets.has(firstWord)) {{ matchCode = firstWord; break; }}
            }}

            if (matchCode) {{
              found.push(matchCode);
              const cb = row.querySelector("input[type='checkbox']") || (cells[0] ? cells[0].querySelector("input") : null);
              const chakraLabel = row.querySelector("label.chakra-checkbox, span.chakra-checkbox__control") || (cells[0] ? cells[0].querySelector("label, span") : null);

              if (cb) {{
                if (!cb.checked) {{
                  cb.click();
                  if (!cb.checked && chakraLabel) {{
                    chakraLabel.click();
                  }}
                  if (!cb.checked && cells[0]) {{
                    cells[0].click();
                  }}
                  if (!cb.checked) {{
                    cb.checked = true;
                    cb.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    cb.dispatchEvent(new Event('change', {{ bubbles: true }}));
                  }}
                  newlyTicked.push(matchCode);
                }} else {{
                  alreadyTicked.push(matchCode);
                }}
              }} else if (chakraLabel) {{
                chakraLabel.click();
                newlyTicked.push(matchCode);
              }} else if (cells[0]) {{
                cells[0].click();
                newlyTicked.push(matchCode);
              }}
            }}
          }}

          const notFound = Array.from(targets).filter(c => !found.includes(c));

          const findBtn = () => {{
            const direct = [
              "div.detailBar button.chakra-button.css-kyhdse",
              "div.detailBar button.chakra-button",
              "div.detailBar button",
              "div[class*='detailBar'] button",
              "button.chakra-button.css-kyhdse",
              "button[type='submit']",
              "form button[type='submit']"
            ];
            for (const s of direct) {{
              const el = document.querySelector(s);
              if (el) return el;
            }}

            const allButtons = Array.from(document.querySelectorAll("button, input[type='submit'], div[role='button'], a[role='button']"));
            for (const b of allButtons) {{
              const txt = (b.innerText || b.textContent || b.value || "").trim().toLowerCase();
              if (txt.includes("đăng ký") || txt.includes("dang ky") || txt.includes("lưu") || txt.includes("xác nhận")) {{
                return b;
              }}
            }}
            return null;
          }};

          const doClick = (btn) => {{
            if (!btn) return false;
            btn.removeAttribute('disabled');
            btn.disabled = false;
            try {{
              btn.scrollIntoView({{ behavior: "instant", block: "center" }});
            }} catch(e) {{}}

            ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(evt => {{
              btn.dispatchEvent(new MouseEvent(evt, {{ bubbles: true, cancelable: true, view: window }}));
            }});
            if (typeof btn.click === 'function') btn.click();
            const form = btn.closest('form') || document.querySelector('form');
            if (form) {{
              try {{
                if (typeof form.requestSubmit === 'function') form.requestSubmit(btn);
                else form.dispatchEvent(new Event('submit', {{ bubbles: true }}));
              }} catch(e) {{}}
            }}
            return true;
          }};

          let btn = findBtn();
          let clicked = false;
          if (btn) {{
            clicked = doClick(btn);
          }}

          [10, 30, 60, 100, 200].forEach(delay => {{
            setTimeout(() => {{
              const b = findBtn();
              if (b) doClick(b);
            }}, delay);
          }});

          const elapsedMs = (performance.now() - t0).toFixed(2);

          return {{
            status: "ok",
            newlyTicked: newlyTicked,
            alreadyTicked: alreadyTicked,
            notFound: notFound,
            clickedRegister: clicked || !!btn,
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

        # Thử lại nếu React render nút chậm sau khi tick
        if not clicked and (newly or already):
            for _ in range(6):
                time.sleep(0.04)
                res_btn = self.eval_js("""
                (() => {
                  const direct = [
                    "div.detailBar button.chakra-button.css-kyhdse",
                    "div.detailBar button.chakra-button",
                    "div.detailBar button",
                    "div[class*='detailBar'] button",
                    "button.chakra-button.css-kyhdse",
                    "button[type='submit']"
                  ];
                  for (const s of direct) {
                    const el = document.querySelector(s);
                    if (el) {
                      el.removeAttribute('disabled');
                      el.disabled = false;
                      ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(evt => {
                        el.dispatchEvent(new MouseEvent(evt, { bubbles: true, cancelable: true, view: window }));
                      });
                      if (typeof el.click === 'function') el.click();
                      return true;
                    }
                  }
                  const allButtons = Array.from(document.querySelectorAll("button, input[type='submit'], div[role='button']"));
                  for (const b of allButtons) {
                    const txt = (b.innerText || b.textContent || b.value || "").trim().toLowerCase();
                    if (txt.includes("đăng ký") || txt.includes("dang ky") || txt.includes("lưu") || txt.includes("xác nhận")) {
                      b.removeAttribute('disabled');
                      b.disabled = false;
                      ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(evt => {
                        b.dispatchEvent(new MouseEvent(evt, { bubbles: true, cancelable: true, view: window }));
                      });
                      if (typeof b.click === 'function') b.click();
                      return true;
                    }
                  }
                  return false;
                })();
                """)
                if res_btn:
                    clicked = True
                    break

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
        self.title("UIT ĐKHP - TẤT CẢ TRONG MỘT (EMBEDDED CHROME & TURBO CONTROL)")
        self.geometry("1420x860")
        self.minsize(1100, 700)

        # Mở GUI ở chế độ phóng to toàn màn hình (Maximized / Max screen)
        self.maximize_window()
        self.after(50, self.maximize_window)
        self.after(200, self.maximize_window)

        self.engine = UITTurboEngine(
            log_callback=self.append_log_threadsafe,
            status_callback=self.update_status_threadsafe
        )

        self.is_fullscreen = False
        self.timer_running = False
        self.timer_target_str = ""

        self.setup_ui()
        self.load_initial_subjects()
        self.bind_shortcuts()
        self.start_clock_thread()

        self.after(200, self.auto_start_embedded_chrome)

    def maximize_window(self):
        try:
            self.state("zoomed")
        except Exception:
            try:
                self.attributes("-zoomed", True)
            except Exception:
                pass

    def toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)

    def setup_ui(self):
        self.grid_columnconfigure(0, weight=78)
        self.grid_columnconfigure(1, weight=22)
        self.grid_rowconfigure(0, weight=1)

        self.left_pane = ctk.CTkFrame(self, corner_radius=10, fg_color=("#1e293b", "#0f172a"))
        self.left_pane.grid(row=0, column=0, padx=(8, 4), pady=8, sticky="nsew")
        self.left_pane.grid_columnconfigure(0, weight=1)
        self.left_pane.grid_rowconfigure(1, weight=1)

        browser_bar = ctk.CTkFrame(self.left_pane, height=44, fg_color=("#334155", "#1e293b"), corner_radius=8)
        browser_bar.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        browser_bar.grid_columnconfigure(4, weight=1)

        btn_nav_reload = ctk.CTkButton(
            browser_bar, text="🔄 Tải lại (F5)", width=85, height=28,
            command=self.reload_browser, fg_color="#475569", hover_color="#334155", font=ctk.CTkFont(size=12)
        )
        btn_nav_reload.grid(row=0, column=0, padx=(8, 3), pady=6)

        btn_nav_home = ctk.CTkButton(
            browser_bar, text="🏠 Trang ĐKHP", width=95, height=28,
            command=self.navigate_home, fg_color="#475569", hover_color="#334155", font=ctk.CTkFont(size=12)
        )
        btn_nav_home.grid(row=0, column=1, padx=3, pady=6)

        btn_reembed = ctk.CTkButton(
            browser_bar, text="🪟 Căn chỉnh", width=85, height=28,
            command=self.realign_chrome, fg_color="#0284c7", hover_color="#0369a1", font=ctk.CTkFont(size=12)
        )
        btn_reembed.grid(row=0, column=2, padx=3, pady=6)

        btn_acc = ctk.CTkButton(
            browser_bar, text="👤 Tài khoản", width=90, height=28,
            command=self.switch_to_account_tab, fg_color="#6366f1", hover_color="#4f46e5", font=ctk.CTkFont(size=12)
        )
        btn_acc.grid(row=0, column=3, padx=3, pady=6)

        lbl_url = ctk.CTkLabel(browser_bar, text=TARGET_URL, text_color="#94a3b8", font=ctk.CTkFont(size=11))
        lbl_url.grid(row=0, column=4, padx=10, sticky="e")

        self.chrome_container = tk.Frame(self.left_pane, bg="#000000")
        self.chrome_container.grid(row=1, column=0, padx=8, pady=(4, 8), sticky="nsew")
        self.chrome_container.bind("<Configure>", self.on_chrome_container_resize)

        self.right_pane = ctk.CTkFrame(self, corner_radius=10, fg_color=("#1f2937", "#111827"))
        self.right_pane.grid(row=0, column=1, padx=(4, 8), pady=8, sticky="nsew")
        self.right_pane.grid_columnconfigure(0, weight=1)
        self.right_pane.grid_rowconfigure(2, weight=1)

        self.header_frame = ctk.CTkFrame(self.right_pane, corner_radius=8, fg_color=("#374151", "#1f2937"))
        self.header_frame.grid(row=0, column=0, padx=8, pady=(8, 4), sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            self.header_frame, 
            text="⚡ ĐIỀU KHIỂN TURBO", 
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#38bdf8"
        )
        title_label.grid(row=0, column=0, padx=8, pady=(6, 2), sticky="w")

        self.status_badge = ctk.CTkLabel(
            self.header_frame,
            text="Chrome: Đang kết nối...",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#374151",
            text_color="#facc15",
            corner_radius=6,
            padx=6,
            pady=2
        )
        self.status_badge.grid(row=0, column=1, padx=8, pady=6, sticky="e")

        self.buttons_frame = ctk.CTkFrame(self.right_pane, corner_radius=8)
        self.buttons_frame.grid(row=1, column=0, padx=8, pady=4, sticky="ew")
        self.buttons_frame.grid_columnconfigure((0, 1), weight=1)

        self.btn_fire_now = ctk.CTkButton(
            self.buttons_frame,
            text="🚀 ĐĂNG KÝ TỨC THÌ (SPACE/ENTER)",
            command=self.trigger_fire_now,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#16a34a",
            hover_color="#15803d",
            height=46
        )
        self.btn_fire_now.grid(row=0, column=0, columnspan=2, padx=8, pady=(8, 4), sticky="ew")

        self.btn_f5_loop = ctk.CTkButton(
            self.buttons_frame,
            text="🔄 F5 & BẮN LIÊN TỤC (50ms)",
            command=self.trigger_f5_loop,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#d97706",
            hover_color="#b45309",
            height=34
        )
        self.btn_f5_loop.grid(row=1, column=0, columnspan=2, padx=8, pady=4, sticky="ew")

        btn_import_excel = ctk.CTkButton(
            self.buttons_frame, 
            text="📁 Import Excel / TXT", 
            command=self.import_file,
            fg_color="#0284c7",
            hover_color="#0369a1",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=28
        )
        btn_import_excel.grid(row=2, column=0, padx=(8, 3), pady=3, sticky="ew")

        btn_save = ctk.CTkButton(
            self.buttons_frame, 
            text="💾 Lưu danh sách môn", 
            command=self.save_subjects_to_file,
            fg_color="#059669",
            hover_color="#047857",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=28
        )
        btn_save.grid(row=2, column=1, padx=(3, 8), pady=3, sticky="ew")

        btn_clear = ctk.CTkButton(
            self.buttons_frame, 
            text="🗑️ Xóa trắng danh sách môn", 
            command=lambda: self.txt_subjects.delete("1.0", tk.END),
            fg_color="#475569",
            hover_color="#334155",
            font=ctk.CTkFont(size=11),
            height=26
        )
        btn_clear.grid(row=3, column=0, columnspan=2, padx=8, pady=3, sticky="ew")

        timer_subframe = ctk.CTkFrame(self.buttons_frame, fg_color="transparent")
        timer_subframe.grid(row=4, column=0, columnspan=2, padx=8, pady=(4, 8), sticky="ew")
        timer_subframe.grid_columnconfigure(1, weight=1)

        lbl_timer = ctk.CTkLabel(timer_subframe, text="⏱️", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_timer.grid(row=0, column=0, padx=(0, 2), sticky="w")

        self.entry_timer = ctk.CTkEntry(timer_subframe, placeholder_text="09:00:00.000", font=ctk.CTkFont(family="Consolas", size=12), height=28)
        self.entry_timer.grid(row=0, column=1, padx=2, sticky="ew")

        self.btn_timer = ctk.CTkButton(
            timer_subframe,
            text="Hẹn",
            command=self.toggle_timer,
            width=50,
            height=28,
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.btn_timer.grid(row=0, column=2, padx=2, sticky="e")

        self.lbl_clock = ctk.CTkLabel(
            timer_subframe,
            text="00:00:00.000",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color="#38bdf8"
        )
        self.lbl_clock.grid(row=0, column=3, padx=(4, 0), sticky="e")

        self.tabview_bottom = ctk.CTkTabview(self.right_pane, corner_radius=8)
        self.tabview_bottom.grid(row=2, column=0, padx=8, pady=(4, 8), sticky="nsew")

        self.tab_subjects = self.tabview_bottom.add("📝 DÁN MÃ MÔN")
        self.tab_log = self.tabview_bottom.add("📜 LIVE LOG")
        self.tab_account = self.tabview_bottom.add("👤 TÀI KHOẢN")

        self.tab_subjects.grid_columnconfigure(0, weight=1)
        self.tab_subjects.grid_rowconfigure(0, weight=1)

        self.txt_subjects = ctk.CTkTextbox(
            self.tab_subjects, 
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color="#0f172a",
            text_color="#f8fafc"
        )
        self.txt_subjects.grid(row=0, column=0, padx=4, pady=4, sticky="nsew")

        self.tab_log.grid_columnconfigure(0, weight=1)
        self.tab_log.grid_rowconfigure(1, weight=1)

        log_top_bar = ctk.CTkFrame(self.tab_log, fg_color="transparent")
        log_top_bar.grid(row=0, column=0, padx=4, pady=2, sticky="ew")
        log_top_bar.grid_columnconfigure(0, weight=1)

        btn_clear_log = ctk.CTkButton(
            log_top_bar, 
            text="Xóa log", 
            width=60, 
            height=22, 
            command=self.clear_log,
            fg_color="#374151",
            hover_color="#1f2937",
            font=ctk.CTkFont(size=11)
        )
        btn_clear_log.grid(row=0, column=1, sticky="e")

        self.txt_log = ctk.CTkTextbox(
            self.tab_log, 
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#0f172a",
            text_color="#f8fafc"
        )
        self.txt_log.grid(row=1, column=0, padx=4, pady=(2, 4), sticky="nsew")

        # Setup Tab Tài khoản
        self.tab_account.grid_columnconfigure(0, weight=1)
        self.tab_account.grid_rowconfigure(0, weight=1)

        acc_box = ctk.CTkFrame(self.tab_account, fg_color="#0f172a", corner_radius=8)
        acc_box.grid(row=0, column=0, padx=4, pady=4, sticky="nsew")
        acc_box.grid_columnconfigure(1, weight=1)

        lbl_acc_title = ctk.CTkLabel(
            acc_box, 
            text="🔐 CẤU HÌNH TÀI KHOẢN ĐKHP", 
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38bdf8"
        )
        lbl_acc_title.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 6), sticky="w")

        lbl_u = ctk.CTkLabel(acc_box, text="MSSV / User:", font=ctk.CTkFont(size=12))
        lbl_u.grid(row=1, column=0, padx=10, pady=4, sticky="w")
        self.entry_auth_user = ctk.CTkEntry(acc_box, font=ctk.CTkFont(size=12), height=28)
        self.entry_auth_user.grid(row=1, column=1, padx=(4, 10), pady=4, sticky="ew")
        self.entry_auth_user.insert(0, self.engine.auth_user)

        lbl_p = ctk.CTkLabel(acc_box, text="Mật khẩu:", font=ctk.CTkFont(size=12))
        lbl_p.grid(row=2, column=0, padx=10, pady=4, sticky="w")

        pass_frame = ctk.CTkFrame(acc_box, fg_color="transparent")
        pass_frame.grid(row=2, column=1, padx=(4, 10), pady=4, sticky="ew")
        pass_frame.grid_columnconfigure(0, weight=1)

        self.entry_auth_pass = ctk.CTkEntry(pass_frame, show="*", font=ctk.CTkFont(size=12), height=28)
        self.entry_auth_pass.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        self.entry_auth_pass.insert(0, self.engine.auth_pass)

        self.btn_show_pass = ctk.CTkButton(
            pass_frame, 
            text="👁️", 
            width=30, 
            height=28,
            command=self.toggle_password_visibility,
            fg_color="#334155",
            hover_color="#475569"
        )
        self.btn_show_pass.grid(row=0, column=1, sticky="e")

        btn_box = ctk.CTkFrame(acc_box, fg_color="transparent")
        btn_box.grid(row=3, column=0, columnspan=2, padx=10, pady=(10, 4), sticky="ew")
        btn_box.grid_columnconfigure((0, 1), weight=1)

        btn_save_acc = ctk.CTkButton(
            btn_box,
            text="💾 Lưu tài khoản",
            command=self.save_account_settings,
            fg_color="#059669",
            hover_color="#047857",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=30
        )
        btn_save_acc.grid(row=0, column=0, padx=(0, 3), sticky="ew")

        btn_fill_now = ctk.CTkButton(
            btn_box,
            text="⚡ Tự điền vào Chrome",
            command=self.auto_fill_login_now,
            fg_color="#6366f1",
            hover_color="#4f46e5",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=30
        )
        btn_fill_now.grid(row=0, column=1, padx=(3, 0), sticky="ew")

        lbl_note = ctk.CTkLabel(
            acc_box,
            text="ℹ️ Lưu vào config.json và tự điền khi mở ĐKHP.",
            font=ctk.CTkFont(size=10),
            text_color="#94a3b8",
            justify="left"
        )
        lbl_note.grid(row=4, column=0, columnspan=2, padx=10, pady=(6, 8), sticky="w")

    def switch_to_account_tab(self):
        self.tabview_bottom.set("👤 TÀI KHOẢN")

    def toggle_password_visibility(self):
        if self.entry_auth_pass.cget("show") == "*":
            self.entry_auth_pass.configure(show="")
            self.btn_show_pass.configure(text="🔒")
        else:
            self.entry_auth_pass.configure(show="*")
            self.btn_show_pass.configure(text="👁️")

    def save_account_settings(self):
        u = self.entry_auth_user.get().strip()
        p = self.entry_auth_pass.get().strip()
        if not u or not p:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập đầy đủ tài khoản và mật khẩu!")
            return
        if self.engine.save_config(u, p):
            self.append_log_threadsafe(f"Đã lưu tài khoản: {u}", "success")
            messagebox.showinfo("Thành công", f"Đã lưu tài khoản '{u}' vào config.json!")
            threading.Thread(target=self.engine.auto_fill_login, daemon=True).start()
        else:
            messagebox.showerror("Lỗi", "Không thể lưu vào file config.json!")

    def auto_fill_login_now(self):
        u = self.entry_auth_user.get().strip()
        p = self.entry_auth_pass.get().strip()
        if u and p:
            self.engine.auth_user = u
            self.engine.auth_pass = p
            self.engine.save_config(u, p)
        self.append_log_threadsafe("Đang tự điền tài khoản vào Chrome...", "info")
        threading.Thread(target=self.engine.auto_fill_login, daemon=True).start()

    def bind_shortcuts(self):
        self.bind("<Return>", lambda e: self.trigger_fire_now() if e.widget != self.txt_subjects else None)
        self.bind("<space>", lambda e: self.trigger_fire_now() if e.widget != self.txt_subjects and e.widget != self.entry_timer else None)
        self.bind("<F5>", lambda e: self.trigger_f5_loop())
        self.bind("<F11>", lambda e: self.toggle_fullscreen())

    def on_chrome_container_resize(self, event):
        if event.width > 50 and event.height > 50:
            self.engine.resize_embedded_chrome(event.width, event.height)

    def auto_start_embedded_chrome(self):
        hwnd = self.chrome_container.winfo_id()
        w = self.chrome_container.winfo_width() or 800
        h = self.chrome_container.winfo_height() or 700
        def _run():
            self.engine.launch_chrome_embedded(hwnd, w, h)
        threading.Thread(target=_run, daemon=True).start()

    def realign_chrome(self):
        hwnd = self.chrome_container.winfo_id()
        w = self.chrome_container.winfo_width() or 800
        h = self.chrome_container.winfo_height() or 700
        def _run():
            self.engine.embed_chrome_window(hwnd, w, h)
        threading.Thread(target=_run, daemon=True).start()

    def reload_browser(self):
        threading.Thread(target=self.engine.reload_tab, daemon=True).start()

    def navigate_home(self):
        threading.Thread(target=self.engine.navigate_home, daemon=True).start()

    def append_log_threadsafe(self, text, level="info"):
        self.after(0, self._append_log_ui, text, level)

    def _append_log_ui(self, text, level):
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
        self.txt_subjects.delete("1.0", tk.END)
        self.engine.target_classes = []

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
                self.append_log_threadsafe(f"Đã import {len(subs)} mã môn từ {os.path.basename(path)}", "success")
            else:
                messagebox.showwarning("Không tìm thấy", "Không tìm thấy mã môn học hợp lệ nào trong file!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi đọc file: {e}")

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
        self.append_log_threadsafe(f"Đã hẹn giờ tự động bắn lúc: {target}", "warning")

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
