"""Pure validation of a filled MIAPPE template.

This module deliberately has no Rich/console imports: the offline dry run and
the importers can share the same checks, and callers format the report.
"""

import zipfile
from dataclasses import dataclass

import openpyxl.utils.exceptions
import pandas as pd

READ_ERRORS = (
    OSError,
    ValueError,
    TypeError,
    zipfile.BadZipFile,
    openpyxl.utils.exceptions.InvalidFileException,
)

REQUIRED_SHEETS = (
    "experiment",
    "factors",
    "germplasm",
    "mapping_table_variables",
)

# The template has a title row above the real headers on most sheets; the
# mapping sheet has its headers on the first row.
HEADER_ROW = {
    "experiment": 1,
    "factors": 1,
    "germplasm": 1,
    "mapping_table_variables": 0,
}

REQUIRED_COLUMNS = {
    "experiment": ("name", "start_date", "objective", "scientific_object_type"),
    "factors": ("name", "levels"),
    "germplasm": ("name", "rdf_type"),
    "mapping_table_variables": ("column_in_data_table", "opensilex_variable_name"),
}

# Required cells in the first data row of each sheet.
REQUIRED_FIRST_ROW_VALUES = REQUIRED_COLUMNS


@dataclass(frozen=True)
class Issue:
    """One problem found while validating a template."""

    level: str  # "error" (blocks the dry run) or "warning"
    message: str


@dataclass(frozen=True)
class TemplateReport:
    """Structured result of :func:`validate_miappe_template`."""

    path: str
    sheet_rows: tuple
    issues: tuple

    @property
    def ok(self):
        return not any(issue.level == "error" for issue in self.issues)

    def lines(self):
        """Human-readable report lines (no Rich markup)."""
        lines = [f"  sheet '{name}': {rows} row(s)" for name, rows in self.sheet_rows]
        lines.extend(
            f"  [{issue.level.upper()}] {issue.message}" for issue in self.issues
        )
        return lines


def read_miappe_sheet(document, sheet_name):
    """Read a MIAPPE sheet with its real header row and clean column names."""
    dataframe = pd.read_excel(
        document, sheet_name=sheet_name, header=HEADER_ROW[sheet_name]
    )
    unnamed = [c for c in dataframe.columns if "unnamed" in str(c).lower()]
    if unnamed:
        dataframe = dataframe.drop(columns=unnamed)
    dataframe.columns = [str(c).strip() for c in dataframe.columns]
    return dataframe


def validate_miappe_template(document):
    """Validate the required sheets, columns and first-row cells of *document*."""
    try:
        sheet_names = pd.ExcelFile(document).sheet_names
    except READ_ERRORS as exc:
        return TemplateReport(
            path=document,
            sheet_rows=(),
            issues=(Issue("error", f"cannot read template: {exc}"),),
        )

    sheet_rows, issues = [], []
    for name in REQUIRED_SHEETS:
        if name not in sheet_names:
            issues.append(Issue("error", f"missing sheet '{name}'"))
            continue
        try:
            dataframe = read_miappe_sheet(document, name)
        except READ_ERRORS as exc:
            issues.append(Issue("error", f"sheet '{name}': cannot read ({exc})"))
            continue

        data = dataframe.dropna(how="all")
        sheet_rows.append((name, len(data)))

        missing_columns = [
            column for column in REQUIRED_COLUMNS[name] if column not in dataframe.columns
        ]
        if missing_columns:
            issues.append(
                Issue(
                    "error",
                    f"sheet '{name}': missing column(s) {', '.join(missing_columns)}",
                )
            )
            continue
        if data.empty:
            issues.append(Issue("error", f"sheet '{name}': no data row"))
            continue

        first_row = data.iloc[0]
        empty_cells = [
            column
            for column in REQUIRED_FIRST_ROW_VALUES[name]
            if pd.isna(first_row.get(column))
        ]
        if empty_cells:
            issues.append(
                Issue(
                    "error",
                    f"sheet '{name}': empty required cell(s) {', '.join(empty_cells)}",
                )
            )

    return TemplateReport(path=document, sheet_rows=tuple(sheet_rows), issues=tuple(issues))
