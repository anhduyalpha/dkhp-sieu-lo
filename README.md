# UIT ĐKHP - TURBO ENGINE ⚡

Công cụ hỗ trợ đăng ký học phần UIT siêu tốc độ (độ trễ < 2ms) qua Chrome DevTools Protocol (CDP) WebSocket.

## 🌟 Tính năng nổi bật

- **Tự động mở Chrome**: Tự tìm đường dẫn Chrome và khởi chạy ở chế độ Debugging Port.
- **Tự động điền tài khoản & mật khẩu**: Điền sẵn thông tin đăng nhập, hỗ trợ giải Captcha thủ công trên màn hình trình duyệt.
- **Persistent WebSocket (0ms delay)**: Giữ kết nối socket liên tục với tab ĐKHP để khi bấm nút có thể bắn lệnh tức thì mà không cần kết nối lại.
- **Thuật toán O(1) Turbo**: Tra cứu mã môn học bằng `Set`, tick toàn bộ lớp học phần và kích hoạt nút Đăng ký trong vòng chưa tới 1ms.
- **Bảng điều khiển tương tác nhanh**:
  - `[ENTER]`: Bắn lệnh tick và Đăng ký tức thì.
  - `f` + `[ENTER]`: F5 tải lại trang và tự động bắn liên tục (mỗi 50ms).
  - `auto` + `[ENTER]`: Bắn lặp liên tục mỗi 50ms cho tới khi đăng ký thành công.
  - `r` + `[ENTER]`: Nạp lại danh sách mã môn từ file `mon-hoc.txt`.
  - `q` + `[ENTER]`: Thoát chương trình.

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

## 🚀 Hướng dẫn sử dụng

### Bước 1: Cấu hình mã môn học
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

### Bước 2: Chạy công cụ

```powershell
.\.venv\Scripts\python.exe inject-hoc-phan.py
```

### Bước 3: Đăng nhập & Sẵn sàng

1. Tool sẽ tự mở Chrome và truy cập vào trang `https://dkhp.uit.edu.vn/app/reg`.
2. Tài khoản & Mật khẩu đã được điền sẵn. Nếu xuất hiện **Captcha**, bạn chỉ cần nhập Captcha trên màn hình Chrome và bấm Đăng nhập.
3. Khi đã vào trang ĐKHP, tool sẽ ở trạng thái chờ lệnh sẵn sàng.
4. **Đến đúng giây mở cổng ĐKHP**: Nhấn phím **`ENTER]`** trên terminal để hệ thống tự động tick chọn tất cả các môn và bấm Đăng ký.

---

## 📜 Sử dụng trực tiếp trên trình duyệt (Console / Bookmarklet)

Nếu không dùng Python, bạn có thể copy nội dung trong file `scripts.js` và dán trực tiếp vào **DevTools Console (F12)** trên tab ĐKHP để chạy tức thì.
