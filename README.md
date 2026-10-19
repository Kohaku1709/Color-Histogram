# HỆ THỐNG TRUY XUẤT ẢNH DỰA TRÊN COLOR HISTOGRAM (CBIR)

Ứng dụng web chạy cục bộ (Localhost, không Docker, không Deploy cloud) cho phép người dùng nạp tập dữ liệu ảnh từ máy tính, trích xuất đặc trưng phân bố màu sắc (Color Histogram), lưu bộ nhớ đệm (Cache) và thực hiện truy xuất Top-K ảnh tương tự với ảnh truy vấn.

---

> [!WARNING]
> ### TUYÊN BỐ PHẠM VI THUẬT TOÁN (SCIENTIFIC DISCLAIMER)
> Đây là **hệ thống truy xuất dựa trên phân bố màu sắc (Color Histogram)** ở mức đặc trưng thấp (Low-level features), **KHÔNG PHẢI** hệ thống nhận diện vật thể hay hiểu nội dung ngữ nghĩa (AI / Deep Learning Object Detection):
> - **Nguyên lý:** Hệ thống đo lường tỷ lệ các dải màu xuất hiện trong toàn bộ ảnh.
> - **Hiện tượng điển hình:** 
>   - Một bức ảnh *quả bóng rổ màu cam* và ảnh *hoàng hôn rực cam* sẽ có điểm tương đồng rất cao vì cùng chung phân bố sắc cam ấm, dù nội dung đối tượng hoàn toàn khác nhau.
>   - Một con *chó lông trắng* và một con *chó lông đen* sẽ bị xếp cách xa nhau vì biểu đồ tần suất sắc độ trắng/đen đối lập nhau.
>   - Hệ thống không phân biệt được vị trí không gian của vật thể (ví dụ ảnh nửa trên xanh nửa dưới vàng sẽ giống ảnh nửa trên vàng nửa dưới xanh nếu dùng global histogram).

---

## 🌟 TÍNH NĂNG ĐÁP ỨNG TOÀN BỘ 12 YÊU CẦU

1. **Nạp dữ liệu từ máy tính:** Quét và nạp ảnh từ bất kỳ thư mục nào trên máy tính (hỗ trợ cả đường dẫn tương đối và tuyệt đối, hỗ trợ tiếng Việt Unicode trên Windows).
2. **Kiểm tra và tiền xử lý ảnh:** Kiểm tra tính toàn vẹn (integrity check), tự động bỏ qua file 0 byte, file hỏng, chuyển đổi ảnh xám/PNG 4 kênh về 3 kênh chuẩn.
3. **Trích xuất Color Histogram:**
   - Hỗ trợ 3 không gian màu: **HSV** (tách riêng sắc độ, bão hòa, ánh sáng - khuyên dùng), **RGB**, **CIELAB** (chuẩn cảm nhận mắt người).
   - Hỗ trợ **3D Joint Histogram** ($N \times N \times N$ bins) và **1D Concatenated Histogram** ($3 \times N$ bins).
   - Chuẩn hóa L1 (tổng bằng 1.0) biểu thị phân bố xác suất độc lập với kích thước ảnh.
4. **Lưu trữ đặc trưng tái sử dụng (Cache):**
   - Tự động nén và lưu ma trận đặc trưng vào thư mục `index_cache/` dưới định dạng NumPy `.npz`.
   - Nạp lại chỉ mục tức thì (< 50ms) trong những lần chạy sau mà không cần quét lại từ đầu.
5. **Nhận ảnh truy vấn đa dạng:** Kéo & thả file ảnh, duyệt file từ máy tính hoặc chọn trực tiếp từ thư viện ảnh dataset có sẵn.
6. **Trích xuất histogram truy vấn:** Đồng nhất tham số với chỉ mục đang nạp.
7. **So sánh với 7 độ đo khoảng cách:**
   - **Chi-Square ($\chi^2$):** Phù hợp và chính xác nhất cho histogram.
   - **Histogram Intersection:** Đo diện tích giao thoa phân bố màu.
   - **Euclidean (L2 Distance):** Khoảng cách hình học Euclid chuẩn.
   - **Manhattan (L1 Distance):** Tổng độ lệch tuyệt đối giữa các bins.
   - **Cosine Distance:** Đo góc hướng của vector đặc trưng.
   - **Bhattacharyya Distance:** Đo độ chồng chập phân bố xác suất.
   - **Correlation:** Hệ số tương quan Pearson chuẩn hóa.
8. **Sắp xếp vector hóa:** Tính toán song song bằng ma trận NumPy, xử lý hàng nghìn ảnh chỉ trong vài miligiây.
9. **Trả về Top-K:** Tùy chỉnh linh hoạt số lượng kết quả (từ 3 đến 50 ảnh).
10. **Giao diện trực quan & so sánh chi tiết:**
    - Hiển thị thẻ kết quả với ảnh xem trước, tên file, độ phân giải, dung lượng, điểm khoảng cách và thanh phần trăm tương đồng.
    - Bảng màu chủ đạo (Dominant Color Swatches) với mã HEX và tỷ lệ phần trăm.
    - Cửa sổ Modal đối chiếu biểu đồ Histogram 3 kênh (Query vs Candidate) chồng đè bằng Chart.js.
    - Nút *"Dùng làm Query mới"* để lặp lại tìm kiếm theo chu trình phản hồi.
11. **Tùy biến cấu hình:** Dễ dàng thay đổi hệ màu (HSV/RGB/Lab), số bins (4, 8, 16, 32), khoảng cách đo, buộc quét lại chỉ mục (Force Rebuild).
12. **Module Kiểm thử & Đánh giá (Evaluation & Benchmark):**
    - Đo tốc độ truy vấn: Độ trễ trung bình (ms), Min/Max, Percentile 95, Thông lượng (QPS).
    - Đo độ chính xác **Precision@K** và bảng thống kê chi tiết theo từng danh mục thư mục con.
    - Ma trận đối chiếu đồng thời cả 7 độ đo khoảng cách cho cùng một ảnh truy vấn.
    - Tab tài liệu khoa học và hướng dẫn sử dụng tích hợp sẵn trong giao diện web.

---

## 🚀 HƯỚNG DẪN CÀI ĐẶT VÀ KHỞI CHẠY CỤC BỘ

### Cách 1: Khởi chạy bằng 1 click (Windows)
Chỉ cần nhấp đúp chuột vào file:
```
run.bat
```
Script sẽ tự động kiểm tra thư viện, tạo 50 ảnh mẫu (nếu chưa có) và mở trình duyệt web tại địa chỉ `http://127.0.0.1:5000`.

---

### Cách 2: Khởi chạy thủ công bằng dòng lệnh

1. **Cài đặt các thư viện cần thiết:**
   ```bash
   pip install flask opencv-python pillow numpy scipy
   ```

2. **Khởi chạy ứng dụng Web Flask:**
   ```bash
   python app.py
   ```

3. **Mở trình duyệt truy cập:**
   ```
   http://127.0.0.1:5000
   ```

---

## 📁 CẤU TRÚC THƯ MỤC DỰ ÁN

```
color histogram/
├── app.py                   # Server Flask quản lý API và giao diện Web
├── run.bat                  # Script khởi động tự động 1-click cho Windows
├── README.md                # Tài liệu hướng dẫn kỹ thuật chi tiết
│
├── cbir/                    # Gói lõi thuật toán CBIR Color Histogram
│   ├── __init__.py
│   ├── extractor.py         # Trích xuất Color Histogram (RGB/HSV/Lab, 1D/3D)
│   ├── metrics.py           # 7 công thức tính khoảng cách & độ tương đồng
│   ├── indexer.py           # Quét dataset, tiền xử lý, kiểm tra lỗi và cache
│   └── evaluator.py         # Benchmark độ trễ, Precision@K, so sánh đa metric
│
├── dataset/                 # Thư mục bộ ảnh mẫu (phân theo nhóm màu)
│   ├── bien_xanh_duong/
│   ├── rung_cay_xanh_la/
│   ├── hoang_hon_do_cam/
│   ├── hoa_vang_sa_mac/
│   └── dem_toi_huyen_bi/
│
├── index_cache/             # Nơi lưu trữ cache chỉ mục dạng file .npz
│
├── templates/
│   └── index.html           # Giao diện web 4 tab, modal và Chart.js
│
└── static/
    ├── css/
    │   └── style.css        # CSS phong cách hiện đại, responsive
    ├── js/
    │   └── main.js          # JavaScript xử lý tải ảnh, tìm kiếm, vẽ biểu đồ
    └── uploads/             # Thư mục tạm lưu ảnh truy vấn tải lên
```

---

## 📐 CÁC CÔNG THỨC TOÁN HỌC ÁP DỤNG

Cho hai vector histogram đã được chuẩn hóa $H_1, H_2$ có độ dài $D$:

1. **Chi-Square Distance ($\chi^2$):**
   $$D_{\chi^2}(H_1, H_2) = \frac{1}{2} \sum_{i=1}^{D} \frac{(H_{1,i} - H_{2,i})^2}{H_{1,i} + H_{2,i} + \epsilon}$$

2. **Histogram Intersection:**
   $$S_{inter}(H_1, H_2) = \sum_{i=1}^{D} \min(H_{1,i}, H_{2,i}), \quad D_{inter} = 1 - S_{inter}$$

3. **Euclidean Distance (L2):**
   $$D_{L2}(H_1, H_2) = \sqrt{\sum_{i=1}^{D} (H_{1,i} - H_{2,i})^2}$$

4. **Manhattan Distance (L1):**
   $$D_{L1}(H_1, H_2) = \sum_{i=1}^{D} |H_{1,i} - H_{2,i}|$$

5. **Cosine Distance:**
   $$D_{cos}(H_1, H_2) = 1 - \frac{H_1 \cdot H_2}{\|H_1\|_2 \|H_2\|_2}$$

6. **Bhattacharyya Distance:**
   $$D_{bhat}(H_1, H_2) = \sqrt{1 - \sum_{i=1}^{D} \sqrt{H_{1,i} \cdot H_{2,i}}}$$
