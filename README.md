# The Grind RPG — v1.1

App quản lý task kiểu RPG (Streamlit + Supabase), dùng cho một người chơi duy nhất.

## Chạy app
1. `pip install -r requirements.txt`
2. Tạo `.streamlit/secrets.toml` (KHÔNG commit file này lên GitHub):
   ```toml
   SUPABASE_URL = "https://xxxx.supabase.co"
   SUPABASE_KEY = "khoá-của-bạn"
   # Tuỳ chọn: đổi UserID cố định (đừng đổi sau khi đã chơi)
   # PLAYER_ID = "7b1f3c9e-5a42-4d6e-9c1a-2f8d0e6b4a37"
   ```
3. `streamlit run 3linhtinh.py`

Khi deploy trên Streamlit Cloud, dán nội dung secrets ở trên vào mục *Secrets* của app.

## Bảng Supabase
Chạy trong SQL Editor (bỏ qua nếu bảng `players` đã có cột `id` và `data`):
```sql
create table if not exists players (
  id uuid primary key,
  data jsonb not null
);
```
Nếu bật Row Level Security, cần policy cho phép khoá bạn dùng đọc/ghi bảng này.

## Lưu tiến trình
- Chỉ có một UserID cố định nên mở lại app lúc nào cũng ra đúng nhân vật cũ.
- Dữ liệu chỉ được ghi khi có thay đổi thật, mỗi lần lưu thử lại tối đa 3 lần.
- Nếu không đọc/ghi được Supabase, app báo lỗi và dừng thay vì tạo nhân vật mới hoặc ghi đè dữ liệu.
- Tự sao lưu tối đa 1 lần/ngày vào một dòng riêng, và sao lưu thêm trước mỗi lần Reset.
  Khôi phục: copy cột `data` của dòng sao lưu về dòng chính trong Supabase.
  Tìm id của dòng sao lưu bằng cách xem các dòng trong bảng `players` ngoài dòng chính.

## Dashboard Task
- Chọn tháng/năm ở đầu tab Task (◀ ▶ hoặc hộp chọn) để xem lại các tháng.
- Biểu đồ vòng "Task status" hiển thị số task Hoàn thành / Chờ làm / Quá hạn; bên cạnh là số task
  đặt ra, đã hoàn thành, tỉ lệ của tháng, cộng thêm tổng của cả năm và của tất cả các tháng.
- Bảng to-do: thêm dòng mới, sửa trực tiếp, chọn dòng rồi nhấn Delete để xóa.
  Tick ✅ rồi bấm **Lưu thay đổi** để hoàn thành task và nhận thưởng.
  Mỗi task chỉ nhận thưởng một lần dù bỏ tick rồi tick lại.

## Kiểm thử
`pip install pytest` rồi chạy `pytest -q`.
