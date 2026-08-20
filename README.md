# UIT ĐKHP

Công cụ hỗ trợ đăng ký học phần UIT siêu lỏ qua Chrome DevTools Protocol (CDP) WebSocket.

- **Bảng điều khiển tương tác nhanh**:
  - `[ENTER]`: Bắn lệnh tick và Đăng ký tức thì.
  - `f` + `[ENTER]`: F5 tải lại trang và tự động bắn liên tục (mỗi 50ms).
  - `auto` + `[ENTER]`: Bắn lặp liên tục mỗi 50ms cho tới khi đăng ký thành công.
  - `r` + `[ENTER]`: Nạp lại danh sách mã môn từ file `mon-hoc.txt`.
  - `q` + `[ENTER]`: Thoát chương trình.

---

## 🎥 Video hướng dẫn

https://github.com/anhduyalpha/dkhp-sieu-lo/raw/main/a.mp4

---

## 🛠️ Yêu cầu & Cài đặt

### 1. Yêu cầu

- Python 3.8+
- Google Chrome

### 2. Cài đặt môi trường ảo & Thư viện

Mở PowerShell tại thư mục dự án và chạy:

```powershell
# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt môi trường ảo
.\.venv\Scripts\Activate.ps1

# Cài đặt thư viện
pip install -r requirements.txt
```

---

## Hướng dũng sử dệnh

### Bước 1: Tự lực cánh sinh nhập tay =)))))

Mở file `mon-hoc.txt` và nhập danh sách mã lớp học phần cần đăng ký (mỗi mã 1 dòng), ví dụ:

```text
IT012.R11
IT012.R11.1
SS007.R15
SS003.R14
IT005.R18
IT005.R18.2
IT007.R111.1
IT007.R111
IT004.R117
IT004.R117.1
```

### Bước 2: Chạy tool ( biết python và env là được )

```powershell
.\.venv\Scripts\python.exe inject-hoc-phan.py
```

### Bước 3: Đăng nhập & Sẵn sàng

1. Tool sẽ tự mở Chrome và truy cập vào trang `https://dkhp.uit.edu.vn/app/reg`.
2. Tài khoản & Mật khẩu đã được điền sẵn. Nếu xuất hiện **Captcha**, bạn chỉ cần nhập Captcha trên màn hình Chrome và bấm Đăng nhập. ( còn không mua thì money talk có tool bypass capcha mà tỉ lệ ra capcha khá thấp nếu auto liên tục mới ra ).
3. Khi đã vào trang ĐKHP, tool sẽ ở trạng thái chờ lệnh sẵn sàng.
4. **Đến đúng giây mở cổng ĐKHP**: Nhấn phím **`ENTER]`** trên terminal để hệ thống tự động tick chọn tất cả các môn và bấm Đăng ký.

---

## 📜 Sử dụng trực tiếp trên trình duyệt (Console / Bookmarklet)

Nếu không dùng Python, bạn có thể copy nội dung trong file `scripts.js` và dán trực tiếp vào **DevTools Console (F12)** trên tab ĐKHP để chạy tức thì.
