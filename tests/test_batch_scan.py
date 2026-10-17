"""Batch directory queue helpers."""

from axiom.core.batch_scan import normalize_batch_extension, scan_batch_files


def test_extension_normalisation():
    assert normalize_batch_extension("mp4") == ".mp4"
    assert normalize_batch_extension(".MKV") == ".mkv"
    assert normalize_batch_extension("extension") == ""
    assert normalize_batch_extension("") == ""


def test_scan_filters_and_sorts_files(tmp_path):
    for name in ("b.MP4", "a.mp4", "notes.txt"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    (tmp_path / "folder.mp4").mkdir()

    files = scan_batch_files(tmp_path, "mp4")
    assert [path.name for path in files] == ["a.mp4", "b.MP4"]
    assert len(scan_batch_files(tmp_path, "extension")) == 3
    assert scan_batch_files(tmp_path / "missing", "mp4") == []


def test_scan_accepts_a_file_and_uses_its_parent_folder(tmp_path):
    for name in ("one.mp4", "two.mp4"):
        (tmp_path / name).write_text("x", encoding="utf-8")

    files = scan_batch_files(tmp_path / "one.mp4", "mp4")

    assert [path.name for path in files] == ["one.mp4", "two.mp4"]
