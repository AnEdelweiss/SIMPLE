import shutil

import pytest

from simple.dry_run import dry_run
from simple.errors import DataImportError

DUMMY = "exp_database/dummy_experiment"


def test_dry_run_dummy_experiment_ok():
    lines, ok = dry_run(DUMMY)
    assert ok
    assert any("RGB1_tabular_data.xlsx: 20 row(s), OK" in line for line in lines)


def test_dry_run_reports_missing_files(tmp_path):
    folder = tmp_path / "exp"
    shutil.copytree(DUMMY, folder, ignore=shutil.ignore_patterns("*.png", "*.zip"))
    lines, ok = dry_run(str(folder))
    assert not ok
    assert any("missing:" in line for line in lines)


def test_dry_run_errors(tmp_path):
    with pytest.raises(DataImportError):
        dry_run(str(tmp_path / "nope"))
    with pytest.raises(DataImportError):
        dry_run(str(tmp_path))  # no template
