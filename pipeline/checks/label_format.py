"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    issues = []

    for label_file in ds.label_files():
        stem = label_file.stem
        previous_boxes = []

        for line_no, text in ds.read_label_lines(stem) or []:
            try:
                class_id, cx, cy, w, h = parse_yolo_line(text)
            except ValueError as exc:
                issues.append(
                    Issue(
                        check="label_format",
                        severity=ERROR,
                        code="BAD_FORMAT",
                        image=stem,
                        message=str(exc),
                        line=line_no,
                    )
                )
                continue

            if not 0 <= class_id < len(ds.classes):
                issues.append(
                    Issue(
                        check="label_format",
                        severity=ERROR,
                        code="BAD_CLASS_ID",
                        image=stem,
                        message=f"ID lớp không hợp lệ: {class_id}",
                        line=line_no,
                    )
                )
                continue

            if w <= 0 or h <= 0:
                issues.append(
                    Issue(
                        check="label_format",
                        severity=ERROR,
                        code="BOX_ZERO",
                        image=stem,
                        message=f"Kích thước box không hợp lệ: w={w}, h={h}",
                        line=line_no,
                    )
                )
                continue
            left = cx - w / 2
            right = cx + w / 2
            top = cy - h / 2
            bottom = cy + h / 2

            overflow = max(
                0.0,
                -left,
                right - 1.0,
                -top,
                bottom - 1.0,
            )

            if overflow > cfg["label_format"]["overflow_tol"]:
                issues.append(
                    Issue(
                        check="label_format",
                        severity=ERROR,
                        code="BOX_OUT_OF_IMAGE",
                        image=stem,
                        message=f"Box tràn khỏi ảnh: {overflow:.6f}",
                        line=line_no,
                        extra={"overflow": overflow},
                    )
                )
            box = (cx, cy, w, h)

            for previous_class, previous_box in previous_boxes:
                if (
                    class_id == previous_class
                    and iou_xywh(box, previous_box)
                    > cfg["label_format"]["dup_box_iou"]
                ):
                    issues.append(
                        Issue(
                            check="label_format",
                            severity=ERROR,
                            code="DUP_BOX",
                            image=stem,
                            message="Box trùng với một dòng nhãn trước đó",
                            line=line_no,
                        )
                    )
                    break

            previous_boxes.append((class_id, box))
            image_size = ds.image_size(stem)

            if image_size is not None:
                image_width, image_height = image_size
                short_side_px = min(
                    w * image_width,
                    h * image_height,
                )

                if short_side_px < cfg["label_format"]["min_box_px"]:
                    issues.append(
                        Issue(
                            check="label_format",
                            severity=WARN,
                            code="BOX_TINY",
                            image=stem,
                            message=f"Cạnh ngắn của box: {short_side_px:.2f}px",
                            line=line_no,
                        )
                    )

            if w * h > cfg["label_format"]["max_box_frac"]:
                issues.append(
                    Issue(
                        check="label_format",
                        severity=WARN,
                        code="BOX_HUGE",
                        image=stem,
                        message=f"Diện tích box chuẩn hóa quá lớn: {w * h:.6f}",
                        line=line_no,
                    )
                )

    return issues
