"""Tests for the UI-free discovery/validation layer of the --gui2 interface."""

from simple.gui2 import discovery

DUMMY = "exp_database/dummy_experiment"


def test_discover_dummy_experiment():
    result = discovery.discover(DUMMY)

    assert result.error is None
    assert result.miappe.endswith("filled_exemple_Miappe_Template.xlsx")
    assert result.experiment_name == "dummy_experiment"
    assert len(result.tabular_candidates) == 3
    assert result.tabular.endswith("ARC_tabular_data.xlsx")
    assert result.datafiles.endswith("ARC")


def test_discover_missing_template(tmp_path):
    result = discovery.discover(str(tmp_path))

    assert result.miappe is None
    assert result.error


def test_validate_dummy_experiment_is_clean():
    found = discovery.discover(DUMMY)
    report = discovery.validate_all(
        DUMMY, found.miappe, found.tabular, found.datafiles
    )

    assert not report.blocking
    assert report.errors == 0
    assert report.warnings == 0
    assert report.counts.rows == 20
    assert report.counts.sci_objects == 10
    assert report.counts.variables == 6
    assert report.counts.datafiles > 0
    assert report.counts.has_file_column


def test_validate_reports_missing_datafiles(tmp_path):
    import shutil

    folder = tmp_path / "exp"
    shutil.copytree(DUMMY, folder, ignore=shutil.ignore_patterns("*.zip"))
    found = discovery.discover(str(folder))
    tabular = str(folder / "ARC_tabular_data.xlsx")

    report = discovery.validate_all(
        str(folder), found.miappe, tabular, found.datafiles
    )

    assert not report.blocking
    assert report.warnings >= 1
    assert any("missing" in check.text for check in report.checks)


def test_plan_sentence_mentions_counts():
    counts = discovery.Counts(
        germplasms=2, factors=2, sci_objects=10, datafiles=40, rows=20
    )
    sentence = discovery.plan_sentence(counts, "dummy_experiment")

    assert "2 germplasm" in sentence
    assert "10 scientific object" in sentence
    assert "20 data row" in sentence
