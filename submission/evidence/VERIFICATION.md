# Kiểm chứng phần lõi và ghi chú Windows

## Kết quả cần dùng

- Log thành công: `check_core_container.log` — checker nguyên bản, mã thoát 0; 85 test passed, 0 lỗi, 1 cảnh báo bỏ qua phần train tùy chọn.
- 85 = 79 test đề + 6 ca tổng hợp. Sáu ca được lưu nguyên nội dung tại `extra_contract_checks.py`; không sửa `tests/` được bảo vệ.
- Quyết định dữ liệu vẫn là **Hold**: 0 lỗi bắt buộc, 38/205 ảnh còn cảnh báo chưa duyệt. Checker qua không có nghĩa dataset được Release.
- Bằng chứng gate không xuất khi Rework: `no_review/08_summary.json`, `no_review/07_error_list_v3.csv`, `no_review_run.log`.
- Các log `check_core_linux*.log` là các lượt thử WSL trực tiếp chưa thành công, giữ làm dấu vết chẩn đoán, không dùng để tuyên bố đã qua kiểm tra.

## Vì sao chạy trực tiếp trên Windows báo hai lỗi ở calibrate.py?

Checker dùng `str(p.relative_to(ROOT))` để đối chiếu tên file với danh sách bảo vệ. Trên Windows tên này là `pipeline\\calibrate.py`, còn khóa được ghim là `pipeline/calibrate.py`. Vì vậy checker quét nhầm file calibration do giảng viên cung cấp, rồi báo các từ `MANIFEST` và `data/calib`.

Đã kiểm tra hash SHA-1 chuẩn hóa CRLF: file calibration vẫn khớp bản đề. Không sửa checker, file calibration, test hoặc hash kỳ vọng để bỏ qua lỗi. Trên Linux dấu phân cách khớp nên checker nguyên bản hoạt động đúng.

WSL chạy trực tiếp trên ổ Windows còn gặp lỗi file tạm khi pytest thu output ở mức file descriptor. `--capture=sys` tránh cơ chế đó nhưng I/O qua filesystem dùng chung quá chậm. Lượt thành công dùng bản sao trong filesystem Linux của container; tất cả file sao chép được đối chiếu SHA-256 với nguồn trước khi kiểm tra.

## Chạy lại từ PowerShell tại thư mục gốc repo

Cần Docker Desktop đang chạy. Repo được gắn **chỉ đọc**; runner sao chép các thư mục cần thiết vào filesystem container, không sao chép `.venv/` hay `.git/`, không sửa checker hoặc dữ liệu nguồn.

```powershell
$repo = (Get-Location).Path

docker run --rm --mount "type=bind,source=$repo,target=/source,readonly" python:3.12-slim sh -c "python -m pip install --disable-pip-version-check --no-cache-dir -q -r /source/requirements.txt && python /source/submission/evidence/run_linux_check.py --source /source"
```

Runner chép thêm 6 ca tổng hợp vào `work/test_extra_checks.py` của bản sao để checker chạy đủ 85 test. Không có test nào bị bỏ chọn hoặc thay đổi. Mã thoát cuối là mã của checker. Lần đầu cần tải image/thư viện; các phiên bản thư viện được in trong output để truy vết.

Trên Linux đã có môi trường phù hợp, lệnh đề vẫn là:

```bash
python scripts/check_submission.py --no-train
```

Nếu clone mới chưa tạo `work/test_extra_checks.py`, lệnh trên chạy 79 test đề. Có thể kiểm riêng cả 85 ca bằng:

```bash
python -m pytest tests submission/evidence/extra_contract_checks.py -q
```

Phần train chưa chạy; không có kết quả mAP được tạo hoặc suy đoán. Lịch sử commit/push là một yêu cầu nộp bài riêng, chưa được thực hiện bởi các lệnh kiểm chứng này.
