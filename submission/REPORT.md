# Báo cáo Day 09 — Cù Việt Đức, 2A202603042

## 1. Kết luận trước

**Hold, chưa phát hành.** Pipeline nhận 205/224 ảnh, loại 19/224 ảnh; xuất bản nháp `submission/export/clean_v1/` gồm 205 ảnh. Sau người duyệt **mô phỏng** theo đề, còn 0 lỗi bắt buộc nhưng 38/205 ảnh còn cảnh báo chưa duyệt (tỉ lệ trong summary: 0.1854), vượt ngưỡng Hold 0.10. Nguồn: `reports/01_intake.csv`, `reports/08_summary.json` và manifest của export.

## 2. Lỗi và phân việc

Nguồn: `reports/02_error_list_v1.csv`. Cột số lượng là **bản ghi / ảnh khác nhau**; mẫu số ảnh: intake **224**, QC **205**. Các mã cấp dataset không có mẫu số ảnh. Một ảnh/dòng có thể có nhiều mã, không cộng cột ảnh để suy ra số ảnh lỗi.

| Mã lỗi | Bản ghi / ảnh | Ai xử lý | Vì sao |
|---|---:|---|---|
| `CORRUPT_IMAGE` | 2 / 2 | Máy, intake | Ảnh không đọc được |
| `BAD_SIZE` | 3 / 3 | Máy, intake | Không đạt kích thước |
| `DUP_IMAGE_EXACT` | 8 / 8 | Máy, intake | Trùng byte |
| `DUP_IMAGE_NEAR` | 2 / 2 | Máy, intake | Trùng gần theo pHash |
| `LEAK_TEST` | 4 / 4 | Máy, intake | Trùng kho tham chiếu |
| `BAD_CLASS_NAME` | 2 / cấp dataset | Máy | Chuẩn hóa tên lớp |
| `BAD_FORMAT` | 3 / 3 | Máy | Xóa dòng không đọc được |
| `BAD_CLASS_ID` | 6 / 6 | Máy | Xóa dòng có lớp ngoài taxonomy |
| `BOX_ZERO` | 4 / 4 | Máy | Xóa box không có diện tích hợp lệ |
| `BOX_OUT_OF_IMAGE` | 8 / 8 | Máy | Cắt về biên ảnh |
| `DUP_BOX` | 7 / 7 | Máy | Xóa dòng box xuất hiện sau |
| `MISSING_LABEL_FILE` | 6 / 6 | Người mô phỏng | Máy không bịa nhãn |
| `EMPTY_LABEL` | 12 / 12 | Người mô phỏng | Xác minh ảnh nền hay thiếu nhãn |
| `BOX_TINY` | 6 / 4 | Người mô phỏng | Vật nhỏ chưa chắc sai |
| `BOX_HUGE` | 3 / 3 | Người mô phỏng | Box lớn cần xem ngữ cảnh |
| `CLASS_RARE` | 4 / cấp dataset | Người phân tích | Thống kê lớp ít box |
| `POSSIBLE_MISSING` | 53 / 52 | Người mô phỏng | Nghi thiếu box |
| `POSSIBLE_WRONG_CLASS` | 18 / 18 | Người mô phỏng | Nghi sai lớp hợp lệ |
| `POSSIBLE_LOOSE_BOX` | 28 / 24 | Người mô phỏng | Nghi box lỏng/lệch |
| `POSSIBLE_FALSE_POS` | 29 / 27 | Người mô phỏng | Nhãn không khớp model, chưa phải lỗi chắc chắn |

`03_fixes.csv` ghi 35 thao tác: 20 `drop_line`, 8 `clip_box`, 1 `rename_classes`, 6 `needs_label`; thao tác cuối chỉ chuyển người gán, không tạo file rỗng. Dữ liệu raw không bị sửa.

Hàng đợi có 125 ảnh, xếp theo tổng trọng số lỗi và độ tin cậy; ảnh từng bị xóa dòng/cắt box được cộng điểm. `img_0020` đứng đầu với 11.524 điểm do kết hợp `FIXED_DROP_LINE`, `POSSIBLE_MISSING`, `POSSIBLE_WRONG_CLASS`; ảnh thiếu nhãn có `NEEDS_LABEL` được cộng 10 điểm. Ngân sách xử lý 80/125 ảnh. Đối chiếu v2 với review log: 74/80 ảnh được chọn có tổng 94 bản ghi cảnh báo ngữ nghĩa (51 missing, 18 wrong-class, 13 false-pos, 12 loose-box); đây là **nghi vấn được đưa cho mô phỏng**, không phải 94 lỗi đã được người thật xác nhận.

## 3. Calibration (2 ngưỡng)

Nguồn: `calibration/calibration.json`; P/R là precision/recall trên calib 39 ảnh, không phải độ chính xác trên raw.

| Tham số | Khởi đầu → chọn | P/R trước → sau | Đánh đổi |
|---|---|---|---|
| `duplicates.phash_dist` | 2 → **4** | Near: 1.00/0.50 → 1.00/0.667 | Bắt 4/6 thay vì 3/6 ảnh gần trùng, không có FP trên calib; chọn ngưỡng nhỏ nhất trong dải 4–14 cùng kết quả, hạn chế gộp nhầm |
| `second_opinion.conf` | 0.25 → **0.6** | Missing: 0.50/1.00 → 0.571/1.00; wrong-class: 0.556/0.833 → 0.625/0.833 | Giảm báo động giả trong hai nhóm này, giữ recall; chấp nhận loose-box kém hơn: P/R 0.286/0.40 → 0.20/0.20 |

`FALSE_POS` không đổi vì dùng `fp_conf` riêng. Không chọn ngưỡng chỉ để được Release. So với lần đầu, cảnh báo QC v1 giảm 273 → 153, hàng đợi 145 → 125 ảnh; ảnh còn cảnh báo chưa duyệt giảm 60/205 → 38/205, nhưng vẫn Hold.

**Bẫy calibration:** recall gần trùng tăng trên calib, song danh sách 10 cặp trùng raw và tổng 19 ảnh bị loại không đổi khi tăng pHash 2 → 4. Calib nhỏ và khác raw; không thể suy ra recall raw từ recall calib. Hai cặp near raw đều có khoảng cách pHash 0.

**Nhận xét trực tiếp của học viên:** đồng ý loại `img_0076` khi so với `img_0042`: theo quan sát, khác một chút về góc độ nhưng cơ bản các vật thể giống nhau; đồng ý loại `img_0143` khi so với `img_0037`: hai ảnh và các vật thể xuất hiện giống nhau. Đây là hai quyết định học viên báo lại sau khi xem ảnh, không phải AI tự xác nhận toàn bộ dữ liệu.

## 4. Cửa chặn và điều pipeline không bắt được

Thí nghiệm không người duyệt, tách riêng để không ghi đè kết quả chính:

```bash
python -m pipeline.run --budget 0 --work work/no_review_run --reports submission/evidence/no_review --export-dir work/no_review_export
```

Kết quả thật: **Rework**, mã thoát **20**, còn 6 lỗi `MISSING_LABEL_FILE` trên 6/205 ảnh; `exported=null`, không có `work/no_review_export/clean_v1`. Bằng chứng: `evidence/no_review/08_summary.json`, `evidence/no_review/07_error_list_v3.csv`, `evidence/no_review_run.log`.

Hai điểm mù có số liệu calib tại ngưỡng đã chọn: (1) near-duplicate chỉ bắt 4/6, còn bỏ sót 2/6 ảnh; (2) loose-box chỉ bắt 1/5, bỏ sót 4/5 lỗi chèn. Test xanh không chứng minh mọi lỗi ngữ nghĩa được tìm thấy.

Ba quan sát ban đầu **do học viên cung cấp, chưa coi là ground truth**: `img_0002` dòng 2 nghi sai lớp person; `img_0006` dòng 1–2 nghi cùng khoanh một vật thể; `img_0030` dòng 11 khó xác định vị trí và nghi thiếu nhãn. Cần xem lại ảnh gốc để phân biệt sai lớp, lệch box và bỏ sót, không tự sửa raw theo nghi vấn.

## 5. Train: raw vs clean

**Chưa chạy.** Hiện hoàn thành phần lõi trước; chưa có kết quả huấn luyện để so sánh. Không có số liệu mAP, precision/recall của model sau train hoặc kết luận clean tốt hơn raw. Phần train tùy chọn 15 điểm chưa thực hiện.

## 6. Quyết định và ghi chú AI

Giữ **Hold**, chỉ dùng export làm bản nháp thử nghiệm. Để Release cần giữ 0 lỗi bắt buộc và đưa tỉ lệ ảnh còn cảnh báo chưa duyệt xuống dưới 10% theo đúng quy trình/ngân sách; nếu không xử lý được thì giữ Hold, không đổi luật gate hoặc nâng conf chỉ để che cảnh báo. Học viên chọn ngưỡng và xác nhận hai cặp ảnh; 80 ảnh trong review log do chương trình mô phỏng xử lý, không phải học viên duyệt thủ công.

Kiểm tra phần lõi bằng checker nguyên bản trên bản sao cô lập trong Linux/Python 3.12.16: **85 passed, 0 lỗi, 1 cảnh báo** (chỉ bỏ qua train). Log: `evidence/check_core_container.log`; cách kiểm chứng và lỗi đường dẫn của checker khi chạy trực tiếp trên Windows được ghi ở `evidence/VERIFICATION.md`. Không sửa checker hoặc danh sách hash bảo vệ để đạt kết quả này.

- **Prompt chính:** yêu cầu hướng dẫn rồi hỗ trợ triển khai 4 module theo docstring/test, giữ nguyên dữ liệu và file đề, giải thích từng bước; sau đó chạy calibration với hai ngưỡng học viên đồng ý.
- **Cách kiểm AI:** học viên tự chạy các test đầu; Hermes trực tiếp chạy 79 test của đề và 6 ca tổng hợp bổ sung, kiểm gate không export khi Rework, đối chiếu báo cáo/manifest và hash raw. AI hỗ trợ code, tổng hợp số liệu và diễn đạt báo cáo; quan sát ảnh được ghi theo lời học viên.
- **Một lần AI sai:** lần đầu dọn định dạng cuối `label_format.py` chưa hết dòng trống thừa; `git diff --check` vẫn báo `new blank line at EOF`. Đã sửa lại và kiểm tra không còn lỗi định dạng; không trình bày lỗi định dạng này như một lỗi thuật toán.
