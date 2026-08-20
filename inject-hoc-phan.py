import os
import sys
import time
import json
import shutil
import subprocess
import requests
import websocket
from datetime import datetime
from colorama import init, Fore, Style

init(autoreset=True)

TARGET_URL = "https://dkhp.uit.edu.vn/app/reg"
DEFAULT_FILES = ["mon_hoc.txt", "mon-hoc.txt"]
CHROME_DEBUG_PORT = 9222
CONFIG_FILE = "config.json"
DEFAULT_AUTH_USER = ""
DEFAULT_AUTH_PASS = ""

class UITTurboBot:
    def __init__(self):
        self.ws = None
        self.ws_url = None
        self.target_classes = []
        self.msg_id = 0
        self.auth_user = DEFAULT_AUTH_USER
        self.auth_pass = DEFAULT_AUTH_PASS
        self.load_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    self.auth_user = cfg.get("auth_user", DEFAULT_AUTH_USER)
                    self.auth_pass = cfg.get("auth_pass", DEFAULT_AUTH_PASS)
            except Exception:
                pass

    def log(self, tag, msg, color=Fore.WHITE):
        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"{Fore.CYAN}[{now}]{Style.RESET_ALL} {color}[{tag:<12}]{Style.RESET_ALL} {msg}")

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
            self.log("INFO", "Chrome Debug đã chạy sẵn sàng.", Fore.GREEN)
            return True

        chrome_path = self.find_chrome_path()
        if not chrome_path:
            self.log("ERROR", "Không tìm thấy file chrome.exe trên máy!", Fore.RED)
            return False

        self.log("LAUNCH", f"Đang mở Chrome: {chrome_path}", Fore.YELLOW)
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
                self.log("SUCCESS", "Chrome đã mở và kết nối thành công!", Fore.GREEN)
                return True

        self.log("ERROR", "Không thể kết nối tới Chrome sau khi khởi chạy.", Fore.RED)
        return False

    def get_or_create_target_tab(self):
        try:
            res = requests.get(f"http://localhost:{CHROME_DEBUG_PORT}/json", timeout=2)
            tabs = res.json()
        except Exception as e:
            self.log("ERROR", f"Lỗi lấy danh sách tab: {e}", Fore.RED)
            return None

        for tab in tabs:
            url = tab.get("url", "")
            if "dkhp.uit.edu.vn" in url or "cas.uit.edu.vn" in url:
                return tab

        self.log("INFO", f"Đang mở trang {TARGET_URL}...", Fore.CYAN)
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
            self.log("ERROR", "Tab không có WebSocket Debug URL.", Fore.RED)
            return False

        try:
            if self.ws:
                try:
                    self.ws.close()
                except Exception:
                    pass
            self.ws = websocket.create_connection(self.ws_url, suppress_origin=True, timeout=5)
            return True
        except Exception as e:
            self.log("ERROR", f"Lỗi kết nối WebSocket: {e}", Fore.RED)
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

    def load_target_classes(self):
        for filename in DEFAULT_FILES:
            if os.path.exists(filename):
                with open(filename, "r", encoding="utf-8") as f:
                    classes = []
                    for line in f:
                        cleaned = line.strip().upper()
                        if (
                            cleaned
                            and not cleaned.startswith("#")
                            and not cleaned.startswith("LEARN MORE")
                            and "HTTP" not in cleaned
                        ):
                            classes.append(cleaned)
                if classes:
                    self.target_classes = classes
                    return self.target_classes
        self.target_classes = []
        return self.target_classes

    def auto_fill_login(self):
        if not self.auth_user or not self.auth_pass:
            self.log("AUTH", "Chưa cấu hình tài khoản/mật khẩu trong config.json.", Fore.YELLOW)
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
                self.log("AUTH", "Đã ở trong trang ĐKHP (đã đăng nhập).", Fore.GREEN)
            elif status == "filled":
                has_captcha = res.get("hasCaptcha", False)
                self.log("AUTH", f"Đã điền sẵn tài khoản '{self.auth_user}' và mật khẩu.", Fore.GREEN)
                if has_captcha:
                    self.log("CAPTCHA", "👉 Phát hiện có Captcha! Bạn hãy nhập mã Captcha trên Chrome và đăng nhập.", Fore.YELLOW)
                else:
                    self.log("NOTICE", "👉 Bạn hãy kiểm tra trên Chrome và bấm Đăng nhập nếu cần.", Fore.YELLOW)

    def build_turbo_payload(self):
        return f"""
        (() => {{
          const t0 = performance.now();
          const targets = new Set({json.dumps(self.target_classes)}.map(c => c.trim().toUpperCase()));
          const found = [];
          const newlyTicked = [];
          const alreadyTicked = [];

          const rows = document.querySelectorAll("table tbody tr");
          if (rows.length === 0) return {{ status: "error", message: "Chưa thấy bảng học phần! Hãy đảm bảo bạn đã đăng nhập và vào đúng trang ĐKHP." }};

          const setCheckbox = (cb) => {{
            if (!cb) return false;
            if (!cb.checked) {{
              try {{
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'checked')?.set;
                if (setter) setter.call(cb, true);
                else cb.checked = true;
              }} catch(e) {{
                cb.checked = true;
              }}
              cb.dispatchEvent(new Event('input', {{ bubbles: true }}));
              cb.dispatchEvent(new Event('change', {{ bubbles: true }}));
              cb.dispatchEvent(new MouseEvent('click', {{ bubbles: true, cancelable: true }}));
              return true;
            }}
            return false;
          }};

          for (let i = 0; i < rows.length; i++) {{
            const row = rows[i];
            const cells = row.querySelectorAll("td");
            if (cells.length < 2) continue;
            const code = (cells[1].textContent || "").trim().toUpperCase();

            if (targets.has(code)) {{
              found.push(code);
              const cb = row.querySelector("input[type='checkbox']") || cells[0].querySelector("input");
              if (cb) {{
                if (setCheckbox(cb)) {{
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

          const findBtn = () => {{
            const direct = document.querySelector("div.detailBar button, div.detailBar button.chakra-button, button.chakra-button.css-kyhdse, button[type='submit']");
            if (direct) return direct;
            const allButtons = document.querySelectorAll("button, input[type='submit'], div[role='button']");
            for (let i = 0; i < allButtons.length; i++) {{
              const txt = (allButtons[i].textContent || allButtons[i].value || "").trim().toLowerCase();
              if (txt.includes("đăng ký") || txt.includes("dang ky") || txt.includes("lưu") || txt.includes("xác nhận")) {{
                return allButtons[i];
              }}
            }}
            return null;
          }};

          const doClick = (btn) => {{
            if (!btn) return false;
            btn.removeAttribute('disabled');
            btn.disabled = false;
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

          // Micro-burst background trigger
          [5, 15, 30, 60, 100].forEach(delay => {{
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
        t_start = time.time()
        result = self.eval_js(self.build_turbo_payload())
        total_time_ms = round((time.time() - t_start) * 1000, 2)

        if not isinstance(result, dict) or result.get("status") == "error":
            msg = result.get("message") if isinstance(result, dict) else "Không nhận được phản hồi"
            self.log("ERROR", f"Lỗi: {msg} ({total_time_ms}ms)", Fore.RED)
            return False

        newly = result.get("newlyTicked", [])
        already = result.get("alreadyTicked", [])
        not_found = result.get("notFound", [])
        clicked = result.get("clickedRegister", False)
        js_time = result.get("elapsedMs", "0")

        self.log("FIRE", f"Đã thực thi trong {js_time}ms (Tổng: {total_time_ms}ms)", Fore.GREEN)

        if newly:
            self.log("TICK MỚI", f"({len(newly)} môn) {', '.join(newly)}", Fore.GREEN)
        if already:
            self.log("CÓ SẴN", f"({len(already)} môn) {', '.join(already)}", Fore.BLUE)
        if not_found:
            self.log("CHƯA THẤY", f"({len(not_found)} môn) {', '.join(not_found)}", Fore.YELLOW)

        if clicked:
            print(f"\n{Fore.GREEN}{'='*60}")
            print(f"  🎉 ĐÃ TICK TOÀN BỘ MÔN VÀ BẤM NÚT ĐĂNG KÝ THÀNH CÔNG!")
            print(f"{'='*60}{Style.RESET_ALL}\n")
            return True
        else:
            self.log("WARNING", "Đã tick môn nhưng chưa thấy nút Đăng ký!", Fore.YELLOW)
            return False

    def auto_fire_loop(self, interval_sec=0.05, max_seconds=30):
        self.log("AUTO-LOOP", f"Đang kích hoạt chế độ bắn liên tục (mỗi {int(interval_sec*1000)}ms)...", Fore.CYAN)
        start = time.time()
        attempts = 0
        while time.time() - start < max_seconds:
            attempts += 1
            res = self.eval_js(self.build_turbo_payload())
            if isinstance(res, dict) and res.get("status") == "ok":
                if res.get("clickedRegister"):
                    self.log("SUCCESS", f"Đã đăng ký thành công sau {attempts} lần bắn!", Fore.GREEN)
                    return True
                elif res.get("newlyTicked") or res.get("alreadyTicked"):
                    self.log("INFO", f"Đã tick được môn sau {attempts} lần bắn!", Fore.CYAN)
            time.sleep(interval_sec)
        self.log("TIMEOUT", "Hết thời gian chờ auto-fire.", Fore.RED)
        return False

    def start(self):
        print(f"\n{Fore.MAGENTA}{'='*65}")
        print(f"       UIT ĐKHP - TURBO ENGINE (MỞ SẴN CHROME & ĐỢI LỆNH)")
        print(f"{'='*65}{Style.RESET_ALL}")

        classes = self.load_target_classes()
        self.log("INIT", f"Nạp {len(classes)} mã môn: {', '.join(classes)}", Fore.CYAN)

        if not self.ensure_chrome():
            return

        if not self.connect_ws():
            self.log("ERROR", "Không thể kết nối tới tab Chrome!", Fore.RED)
            return

        self.auto_fill_login()

        print(f"\n{Fore.GREEN}┌─────────────────────────────────────────────────────────────┐")
        print(f"│  ⚡ TRẠNG THÁI SẴN SÀNG - GIỮ KẾT NỐI 0MS                    │")
        print(f"│  💡 Nếu có Captcha: Hãy nhập Captcha và đăng nhập trên Chrome│")
        print(f"├─────────────────────────────────────────────────────────────┤")
        print(f"│  👉 Nhấn [ENTER]        : BẮN LỆNH TICK & ĐĂNG KÝ TỨC THÌ  │")
        print(f"│  👉 Gõ 'f' + [ENTER]    : F5 Tải lại trang & Bắn ngay       │")
        print(f"│  👉 Gõ 'auto' + [ENTER] : Bắn liên tục (Loop 50ms)          │")
        print(f"│  👉 Gõ 'r' + [ENTER]    : Nạp lại file môn học (mon-hoc.txt)│")
        print(f"│  👉 Gõ 'q' + [ENTER]    : Thoát                             │")
        print(f"└─────────────────────────────────────────────────────────────┘{Style.RESET_ALL}\n")

        while True:
            try:
                cmd = input(f"{Fore.CYAN}UIT-Turbo > {Style.RESET_ALL}").strip().lower()
                if cmd == "":
                    self.fire()
                elif cmd == "f":
                    self.log("ACTION", "Đang F5 tải lại trang...", Fore.YELLOW)
                    self.reload_tab()
                    time.sleep(0.8)
                    self.auto_fire_loop(interval_sec=0.05, max_seconds=10)
                elif cmd == "auto":
                    self.auto_fire_loop(interval_sec=0.05, max_seconds=20)
                elif cmd == "r":
                    classes = self.load_target_classes()
                    self.log("RELOAD", f"Đã nạp lại {len(classes)} mã môn: {', '.join(classes)}", Fore.GREEN)
                elif cmd == "q":
                    print("Đã thoát.")
                    break
                else:
                    print("Lệnh: [ENTER] để bắn ngay, 'f' để F5, 'auto' để loop, 'r' để nạp lại môn, 'q' để thoát.")
            except (KeyboardInterrupt, EOFError):
                break

if __name__ == "__main__":
    bot = UITTurboBot()
    bot.start()