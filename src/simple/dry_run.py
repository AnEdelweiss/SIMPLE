"""Offline validation of an experiment folder (``simple --dry-run <folder>``).

Nothing is sent to any server and no login is needed: the MIAPPE template is
parsed, its sheets are counted, and every datafile referenced by the tabular
data files is looked up on disk.
"""

import os

import pandas as pd

from simple.datafile_import import check_for_datafiles
from simple.erreurs import DataImportError

MIAPPE_SHEETS = ("experiment", "factors", "germplasm", "mapping_table_variables")


def find_miappe(folder):
    """Return the filled MIAPPE template in *folder* (not the generated output)."""
    hits = sorted(
        f
        for f in os.listdir(folder)
        if f.lower().endswith(".xlsx") and "miappe" in f.lower()
    )
    if not hits:
        raise DataImportError(f"No MIAPPE template (*miappe*.xlsx) found in {folder}")
    return os.path.join(folder, hits[0])


def dry_run(folder):
    """Validate *folder*; return ``(report_lines, ok)``."""
    if not os.path.isdir(folder):
        raise DataImportError(f"{folder} is not a directory")
    lines, ok = [], True
    miappe = find_miappe(folder)
    lines.append(f"MIAPPE template: {os.path.basename(miappe)}")
    sheets = pd.ExcelFile(miappe).sheet_names
    for name in MIAPPE_SHEETS:
        if name not in sheets:
            ok = False
            lines.append(f"  [ERROR] missing sheet '{name}'")
            continue
        rows = len(pd.read_excel(miappe, sheet_name=name, header=1).dropna(how="all"))
        lines.append(f"  sheet '{name}': {rows} row(s)")

    for f in sorted(os.listdir(folder)):
        path = os.path.join(folder, f)
        if not f.endswith("_tabular_data.xlsx"):
            continue
        try:
            _, missing1, _, missing2, _, df = check_for_datafiles(path, folder)
        except DataImportError as e:
            ok = False
            lines.append(f"{f}: [ERROR] {e}")
            continue
        missing = sorted(missing1 | missing2)
        ok &= not missing
        status = "OK" if not missing else f"[ERROR] {len(missing)} missing file(s)"
        lines.append(f"{f}: {len(df)} row(s), {status}")
        lines.extend(f"    missing: {m}" for m in missing[:10])
    return lines, ok
