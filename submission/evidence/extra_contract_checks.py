"""Synthetic contract checks, separate from protected tests and raw findings.
Run from repo root: python -m pytest work/test_extra_checks.py -q
"""
from pathlib import Path

from PIL import Image

from pipeline.common import Dataset, Issue, load_config, parse_yolo_line
from pipeline.checks import label_format, second_opinion
from pipeline.steps import autofix


def dataset(tmp_path, text):
    root = tmp_path / "synthetic"
    (root / "images").mkdir(parents=True)
    (root / "labels").mkdir()
    Image.new("RGB", (640, 480)).save(root / "images" / "sample.JPG")
    (root / "labels" / "sample.txt").write_text(text, encoding="utf-8")
    return Dataset(root, load_config()["classes"])


def error(code, line=None):
    return Issue("synthetic", "error", code, "sample", "synthetic test", line)


def test_combined_errors_blank_rows_and_repeated_issue(tmp_path):
    ds = dataset(tmp_path, "1 .5 .5 .2 .2\n\n1 .95 .5 .2 .2\n93 .5 .5 .2 .2\n")
    fixes = autofix.fix(ds, [error("BOX_OUT_OF_IMAGE", 3), error("DUP_BOX", 3),
                            error("DUP_BOX", 3), error("BAD_CLASS_ID", 4)], load_config())
    assert [(f["line"], f["action"]) for f in fixes] == [(3, "drop_line"), (4, "drop_line")]
    assert fixes[0]["before"] == "1 .95 .5 .2 .2" and fixes[0]["after"] == ""
    assert ds.label_path("sample").read_text().splitlines() == ["1 .5 .5 .2 .2", ""]
    assert autofix.fix(ds, label_format.run(ds, load_config()), load_config()) == []


def test_warning_preserves_exact_bytes(tmp_path):
    ds = dataset(tmp_path, "1 .5 .5 .001 .001\n\n")
    before = ds.label_path("sample").read_bytes()
    warn = Issue("synthetic", "warn", "BOX_TINY", "sample", "test", 1)
    assert autofix.fix(ds, [warn], load_config()) == []
    assert ds.label_path("sample").read_bytes() == before


def test_clip_two_edges_and_repeat_after_rechecking(tmp_path):
    ds = dataset(tmp_path, "1 .95 .95 .2 .2\n")
    fixes = autofix.fix(ds, [error("BOX_OUT_OF_IMAGE", 1)], load_config())
    assert len(fixes) == 1 and fixes[0]["action"] == "clip_box"
    _, x, y, w, h = parse_yolo_line(ds.label_path("sample").read_text())
    assert x + w / 2 <= 1.0 and y + h / 2 <= 1.0
    assert autofix.fix(ds, label_format.run(ds, load_config()), load_config()) == []


def test_missing_label_remains_missing_each_run(tmp_path):
    ds = dataset(tmp_path, "")
    ds.label_path("sample").unlink()
    for _ in range(2):
        fixes = autofix.fix(ds, [error("MISSING_LABEL_FILE")], load_config())
        assert [f["action"] for f in fixes] == ["needs_label"]
        assert not ds.label_path("sample").exists()


def test_multiple_prediction_codes_then_false_pos_original_row(tmp_path):
    ds = dataset(tmp_path, "2 .5 .5 .3 .4\n\n1 .1 .1 .1 .1\n")
    preds = {"sample": [[0, .95, .5, .5, .3, .4], [1, .96, .85, .7, .12, .3]]}
    issues = second_opinion.run(ds, load_config(), preds=preds)
    assert [(i.code, i.line) for i in issues] == [
        ("POSSIBLE_WRONG_CLASS", None), ("POSSIBLE_MISSING", None),
        ("POSSIBLE_FALSE_POS", 3),
    ]
    assert all(i.severity == "warn" for i in issues)
    assert [i.extra["conf"] for i in issues[:2]] == [.95, .96]


def test_supplied_empty_predictions_do_not_trigger_model(tmp_path):
    ds = dataset(tmp_path, "0 .5 .5 .3 .4\n")
    assert second_opinion.run(ds, load_config(), preds={}) == []
    issues = second_opinion.run(ds, load_config(), preds={"sample": []})
    assert [(i.code, i.line) for i in issues] == [("POSSIBLE_FALSE_POS", 1)]
