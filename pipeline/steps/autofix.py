"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


def fix(ds, issues, cfg):
    changes = []
    by_image = defaultdict(list)
    for issue in issues:
        if issue.severity == ERROR:
            by_image[issue.image].append(issue)

    drop_codes = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
    for stem in sorted(by_image):
        image_issues = by_image[stem]
        codes = {issue.code for issue in image_issues}
        remove_image = any(code.startswith("DUP_IMAGE_") for code in codes) or bool(
            codes & {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
        )
        path = ds.label_path(stem)
        if remove_image:
            # Xoá ảnh trước, bỏ qua mọi sửa dòng của ảnh đã bị loại.
            image_paths = [p for p in ds.image_files() if p.stem == stem]
            existing = image_paths + ([path] if path.exists() else [])
            if existing:
                before = "; ".join(p.relative_to(ds.root).as_posix() for p in existing)
                for p in existing:
                    p.unlink()
                changes.append({"image": stem, "line": None, "action": "remove_image", "before": before, "after": ""})
            continue

        if "BAD_CLASS_NAME" in codes and ds.yaml_path.exists():
            before = ds.yaml_path.read_text(encoding="utf-8")
            data = yaml.safe_load(before) or {}
            desired_names = list(cfg["classes"])
            if ds.yaml_names() != dict(enumerate(desired_names)):
                data["names"] = desired_names
                after = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
                ds.yaml_path.write_text(after, encoding="utf-8")
                changes.append({"image": stem, "line": None, "action": "rename_classes", "before": before, "after": after})

        if "MISSING_LABEL_FILE" in codes and not path.exists() and ds.image_path(stem) is not None:
            changes.append({"image": stem, "line": None, "action": "needs_label", "before": "(không có file)", "after": "chuyển người gán"})
        if not path.exists():
            continue
        row_codes = defaultdict(set)
        for issue in by_image[stem]:
            if issue.line is not None:
                row_codes[issue.line].add(issue.code)

        original = path.read_text(encoding="utf-8").splitlines()
        remaining = []
        changed = False
        for line_no, before in enumerate(original, 1):
            codes = row_codes[line_no]
            if codes & drop_codes:
                changes.append({"image": stem, "line": line_no, "action": "drop_line", "before": before, "after": ""})
                changed = True
                continue
            if "BOX_OUT_OF_IMAGE" in codes:
                c, x, y, w, h = parse_yolo_line(before)
                left, right = max(0.0, x - w / 2), min(1.0, x + w / 2)
                top, bottom = max(0.0, y - h / 2), min(1.0, y + h / 2)
                if right <= left or bottom <= top:
                    changes.append({"image": stem, "line": line_no, "action": "drop_line", "before": before, "after": ""})
                    changed = True
                    continue
                clipped = ((left + right) / 2, (top + bottom) / 2, right - left, bottom - top)
                if clipped != (x, y, w, h):
                    after = str(c) + " " + " ".join(f"{v:.10g}" for v in clipped)
                    remaining.append(after)
                    changes.append({"image": stem, "line": line_no, "action": "clip_box", "before": before, "after": after})
                    changed = True
                    continue
            remaining.append(before)
        if changed:
            path.write_text("\n".join(remaining) + ("\n" if remaining else ""), encoding="utf-8")

    return changes
