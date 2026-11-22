"""Offline validation of an experiment folder (``simple --dry-run <folder>``).

Nothing is sent to any server and no login is needed: the MIAPPE template is
validated, its sheets are counted, and every datafile referenced by the
tabular data files is looked up on disk.
"""

import os

from simple.datafile_import import check_for_datafiles
from simple.errors import DataImportError
from simple.validation import READ_ERRORS, validate_miappe_template


def find_miappe(folder):
    """Return the filled MIAPPE template in *folder* (not the generated output)."""
    try:
        names = os.listdir(folder)
    except OSError as e:
        raise DataImportError(f"Cannot read {folder}: {e}")
    hits = sorted(
        f
        for f in names
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

    report = validate_miappe_template(miappe)
    lines.extend(report.lines())
    ok &= report.ok

    for f in sorted(os.listdir(folder)):
        path = os.path.join(folder, f)
        if not f.endswith("_tabular_data.xlsx"):
            continue
        try:
            _, missing1, _, missing2, _, df = check_for_datafiles(path, folder)
        except (DataImportError, *READ_ERRORS) as e:
            ok = False
            lines.append(f"{f}: [ERROR] {e}")
            continue
        missing = sorted(missing1 | missing2)
        ok &= not missing
        status = "OK" if not missing else f"[ERROR] {len(missing)} missing file(s)"
        lines.append(f"{f}: {len(df)} row(s), {status}")
        lines.extend(f"    missing: {m}" for m in missing[:10])
    return lines, ok
