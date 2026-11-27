"""Pure, UI-free discovery and preflight checks for the dashboard GUI.

Everything here runs without Qt so it can be unit-tested and reused later by
the CLI. Nothing is uploaded and no API client is needed.
"""

import os
from dataclasses import dataclass, field

import pandas as pd

from simple.datafile_import import check_for_datafiles
from simple.dry_run import find_miappe
from simple.validation import read_miappe_sheet, validate_miappe_template

SKIP_DIRS = {"output", "__pycache__", ".git"}


@dataclass
class Discovery:
    folder: str
    miappe: str | None = None
    tabular: str | None = None
    datafiles: str | None = None
    experiment_name: str | None = None
    tabular_candidates: list = field(default_factory=list)
    datafiles_candidates: list = field(default_factory=list)
    error: str | None = None


@dataclass
class Counts:
    germplasms: int = 0
    factors: int = 0
    variables: int = 0
    rows: int = 0
    sci_objects: int = 0
    datafiles: int = 0
    has_file_column: bool = False


@dataclass
class Check:
    level: str  # ok | warn | error
    text: str


@dataclass
class Report:
    checks: list = field(default_factory=list)
    counts: Counts = field(default_factory=Counts)
    blocking: bool = False
    datafile_check: tuple | None = None

    @property
    def warnings(self):
        return sum(1 for check in self.checks if check.level == "warn")

    @property
    def errors(self):
        return sum(1 for check in self.checks if check.level == "error")

    @property
    def passed(self):
        return sum(1 for check in self.checks if check.level == "ok")


def _read_table(path):
    return pd.read_excel(path)


def experiment_name(miappe):
    try:
        sheet = read_miappe_sheet(miappe, "experiment").dropna(how="all")
        return str(sheet.iloc[0]["name"])
    except Exception:
        return None


def _referenced_filenames(tabular):
    try:
        frame = _read_table(tabular)
    except Exception:
        return set()
    names = set()
    for column in ("Datafile1_Filename", "Datafile2_Filename"):
        if column in frame.columns:
            names |= {str(value) for value in frame[column].dropna().unique()}
    return names


def _walk_files(folder):
    found = set()
    for root, _dirs, files in os.walk(folder):
        found.update(files)
    return found


def _datafile_candidates(folder):
    candidates = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if os.path.isdir(path) and name.lower() not in SKIP_DIRS:
            candidates.append(path)
    # A flat folder of images/archives is a valid datafiles folder too.
    direct = {
        name
        for name in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, name))
        and not name.lower().endswith((".xlsx", ".xls", ".txt", ".md"))
    }
    if direct:
        candidates.append(folder)
    return candidates


def _choose_datafiles(tabular, candidates):
    """Pick the candidate folder that contains the most referenced files."""
    if not candidates:
        return None
    referenced = _referenced_filenames(tabular) if tabular else set()
    best, best_key = None, None
    for path in candidates:
        files = _walk_files(path)
        matches = len(referenced & files) if referenced else 0
        key = (matches, len(files))
        if best_key is None or key > best_key:
            best, best_key = path, key
    return best


def discover(folder):
    """Inspect *folder* and return files, candidates and any discovery error."""
    result = Discovery(folder=folder)
    try:
        result.miappe = find_miappe(folder)
    except Exception as exc:  # missing/unreadable folder, no template, ...
        result.error = str(exc)
        return result

    try:
        names = sorted(os.listdir(folder))
    except OSError as exc:
        result.error = str(exc)
        return result

    tabular = [
        os.path.join(folder, name)
        for name in names
        if name.lower().endswith("_tabular_data.xlsx")
    ]
    if not tabular:
        tabular = [
            os.path.join(folder, name)
            for name in names
            if name.lower().endswith(".xlsx")
            and "miappe" not in name.lower()
            and name != "output"
        ]
    result.tabular_candidates = tabular
    result.tabular = tabular[0] if tabular else None

    result.datafiles_candidates = _datafile_candidates(folder)
    result.datafiles = _choose_datafiles(result.tabular, result.datafiles_candidates)
    result.experiment_name = experiment_name(result.miappe) or os.path.basename(
        folder.rstrip(os.sep)
    )
    return result


def compute_counts(miappe, tabular, datafiles=None):
    counts = Counts()
    if miappe:
        try:
            germplasm = read_miappe_sheet(miappe, "germplasm").dropna(how="all")
            counts.germplasms = int(germplasm["name"].dropna().nunique())
        except Exception:
            pass
        try:
            factors = read_miappe_sheet(miappe, "factors").dropna(how="all")
            counts.factors = int(factors["name"].dropna().nunique())
        except Exception:
            pass
        try:
            mapping = read_miappe_sheet(
                miappe, "mapping_table_variables"
            ).dropna(how="all")
            if "column_in_data_table" in mapping and "opensilex_variable_name" in mapping:
                counts.variables = int(
                    mapping.dropna(
                        subset=["column_in_data_table", "opensilex_variable_name"]
                    )["column_in_data_table"].nunique()
                )
        except Exception:
            pass

    frame = None
    if tabular:
        try:
            frame = _read_table(tabular)
            counts.rows = int(len(frame))
            if "Plant ID" in frame.columns:
                counts.sci_objects = int(frame["Plant ID"].dropna().nunique())
        except Exception:
            frame = None

    if frame is not None:
        counts.has_file_column = "Datafile1_Filename" in frame.columns

    if datafiles and tabular:
        try:
            check = check_for_datafiles(tabular, datafiles)
            counts.datafiles = len(check[0]) + len(check[2])
        except Exception:
            counts.datafiles = 0
    return counts


def validate_all(folder, miappe, tabular, datafiles=None):
    """Run the offline preflight and return a :class:`Report`."""
    report = Report(counts=compute_counts(miappe, tabular, datafiles))
    report.checks = []

    if not miappe:
        report.checks.append(Check("error", "No MIAPPE template selected"))
    else:
        template = validate_miappe_template(miappe)
        if template.ok:
            report.checks.append(
                Check(
                    "ok",
                    f"MIAPPE template · {len(template.sheet_rows)} required sheets, "
                    f"{report.counts.germplasms} germplasm(s), "
                    f"{report.counts.factors} factor(s)",
                )
            )
        for issue in template.issues:
            report.checks.append(
                Check("error" if issue.level == "error" else "warn", issue.message)
            )

    if not tabular:
        report.checks.append(Check("error", "No tabular data file selected"))
    else:
        try:
            frame = _read_table(tabular)
            plants = (
                frame["Plant ID"].dropna().nunique()
                if "Plant ID" in frame.columns
                else 0
            )
            report.checks.append(
                Check(
                    "ok",
                    f"Tabular data · {len(frame)} rows, "
                    f"{report.counts.variables} variables, {plants} plant ID(s)",
                )
            )
        except Exception as exc:
            report.checks.append(Check("error", f"Cannot read tabular data: {exc}"))

    if tabular:
        if not datafiles:
            report.checks.append(
                Check("warn", "No datafile folder · tabular data will import alone")
            )
        elif not report.counts.has_file_column:
            report.checks.append(
                Check(
                    "warn",
                    "No Datafile1_Filename column · no files will be linked",
                )
            )
        else:
            try:
                check = check_for_datafiles(tabular, datafiles)
                report.datafile_check = check
                found = len(check[0]) + len(check[2])
                missing = sorted(check[1] | check[3])
                report.counts.datafiles = found
                if missing:
                    preview = ", ".join(missing[:3])
                    more = f" (+{len(missing) - 3} more)" if len(missing) > 3 else ""
                    report.checks.append(
                        Check(
                            "warn",
                            f"{len(missing)} referenced datafile(s) missing · "
                            f"they will be skipped: {preview}{more}",
                        )
                    )
                else:
                    report.checks.append(
                        Check("ok", f"{found} referenced datafile(s) found")
                    )
            except Exception as exc:
                report.checks.append(
                    Check("error", f"Cannot check datafiles: {exc}")
                )

    report.blocking = any(check.level == "error" for check in report.checks)
    return report


def plan_sentence(counts, experiment_name="This experiment"):
    if counts is None:
        return ""
    return (
        f"Creates {experiment_name}, {counts.germplasms} germplasm(s), "
        f"{counts.factors} factor(s), {counts.sci_objects} scientific object(s); "
        f"uploads {counts.datafiles} file(s) and {counts.rows} data row(s)."
    )
