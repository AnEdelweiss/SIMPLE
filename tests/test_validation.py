"""Tests for the pure MIAPPE validation used by the offline dry run."""

import pandas as pd

from simple.validation import validate_miappe_template


def _write_template(
    tmp_path,
    experiment_headers=None,
    experiment_values=None,
    include_sheets=(
        "experiment",
        "factors",
        "germplasm",
        "mapping_table_variables",
    ),
):
    path = tmp_path / "filled_miappe.xlsx"
    experiment_headers = experiment_headers or [
        "name",
        "start_date",
        "end_date",
        "objective",
        "scientific_object_type",
    ]
    experiment_values = experiment_values or [
        "Exp_Test",
        "2023-01-01",
        "2023-12-31",
        "objective",
        "vocabulary:Plant",
    ]

    sheets = {
        "experiment": pd.DataFrame(
            [["--"] * len(experiment_headers), experiment_headers, experiment_values]
        ),
        "factors": pd.DataFrame(
            [["--", "--"], ["name", "levels"], ["Watering", "low"]]
        ),
        "germplasm": pd.DataFrame(
            [
                ["--", "--", "--"],
                ["is_public", "name", "rdf_type"],
                [1, "Species A", "vocabulary:Species"],
            ]
        ),
        "mapping_table_variables": pd.DataFrame(
            [
                ["column_in_data_table", "opensilex_variable_name"],
                ["Taille", "var_taille"],
            ]
        ),
    }
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name in include_sheets:
            sheets[name].to_excel(writer, sheet_name=name, header=False, index=False)
    return str(path)


def test_valid_minimal_template(tmp_path):
    report = validate_miappe_template(_write_template(tmp_path))

    assert report.ok
    assert dict(report.sheet_rows) == {
        "experiment": 1,
        "factors": 1,
        "germplasm": 1,
        "mapping_table_variables": 1,
    }
    assert report.issues == ()


def test_missing_sheet_is_an_error(tmp_path):
    path = _write_template(
        tmp_path,
        include_sheets=("experiment", "factors", "germplasm"),
    )

    report = validate_miappe_template(path)

    assert not report.ok
    assert any("missing sheet 'mapping_table_variables'" in i.message for i in report.issues)


def test_missing_required_column_is_an_error(tmp_path):
    path = _write_template(
        tmp_path,
        experiment_headers=["name", "start_date", "end_date", "scientific_object_type"],
        experiment_values=[
            "Exp_Test",
            "2023-01-01",
            "2023-12-31",
            "vocabulary:Plant",
        ],
    )

    report = validate_miappe_template(path)

    assert not report.ok
    assert any(
        "sheet 'experiment': missing column(s) objective" in i.message
        for i in report.issues
    )


def test_empty_required_cell_is_an_error(tmp_path):
    path = _write_template(
        tmp_path,
        experiment_values=[
            "Exp_Test",
            "2023-01-01",
            "2023-12-31",
            None,
            "vocabulary:Plant",
        ],
    )

    report = validate_miappe_template(path)

    assert not report.ok
    assert any(
        "sheet 'experiment': empty required cell(s) objective" in i.message
        for i in report.issues
    )


def test_unreadable_template_reports_an_issue(tmp_path):
    path = tmp_path / "broken_miappe.xlsx"
    path.write_text("not an excel file")

    report = validate_miappe_template(str(path))

    assert not report.ok
    assert report.sheet_rows == ()
    assert "cannot read template" in report.issues[0].message


def test_report_lines_include_sheets_and_issues(tmp_path):
    path = _write_template(
        tmp_path,
        include_sheets=("experiment",),
    )

    lines = validate_miappe_template(path).lines()

    assert "  sheet 'experiment': 1 row(s)" in lines
    assert any("[ERROR] missing sheet 'factors'" in line for line in lines)
