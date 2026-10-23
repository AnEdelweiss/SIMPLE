"""Regression tests that drive the *real* pd.read_excel path.

These deliberately do NOT mock ``pd.read_excel`` (unlike the rest of the
suite): they write genuine .xlsx files with pandas/openpyxl and let the
production code parse them, with only the OpenSilex API client stubbed.
Each one currently fails on master and pins a specific bug.
"""
import os
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from simple.data_import import create_data, create_sci_obj
from simple.datafile_import import parse_excel_for_metadata
from simple.erreurs import SimpleBaseException


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _write_miappe(tmp_path, extra_exp_cols=None):
    """MIAPPE workbook with header=1 layout (title row, then header row)."""
    path = tmp_path / "miappe.xlsx"
    exp_cols = ["name", "start_date", "end_date", "scientific_object_type"]
    exp_values = ["Exp_Test", "2023-01-01", "2023-12-31", "vocabulary:Plant"]
    if extra_exp_cols:
        exp_cols = exp_cols + list(extra_exp_cols)
        exp_values = exp_values + [extra_exp_cols[k] for k in extra_exp_cols]

    exp = pd.DataFrame([["--"] * len(exp_cols), exp_cols, exp_values])
    factors = pd.DataFrame(
        [["--", "--", "--", "--"],
         ["name", "levels", "description", "factor_level_desc"],
         ["Watering", "low", "water", "low level"]]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        exp.to_excel(w, sheet_name="experiment", header=False, index=False)
        factors.to_excel(w, sheet_name="factors", header=False, index=False)
    return str(path)


def _stub_experiments():
    exp_api = MagicMock()
    exp = MagicMock()
    exp.uri = "http://fake-base.com/exp/1"
    exp_api.search_experiments.return_value = {"result": [exp]}
    level = MagicMock()
    level.name = "low"
    level.uri = "http://fake-base.com/factor/level/low"
    exp_api.get_available_factors.return_value = {"result": [MagicMock(levels=[level])]}
    return exp_api


# --------------------------------------------------------------------------- #
# 1. first run must create the output workbook, and empty Germplasm must not
#    be looked up as the literal name "nan"
# --------------------------------------------------------------------------- #
@patch("simple.data_import.get_name_space")
@patch("simple.data_import.silex.GermplasmApi")
@patch("simple.data_import.silex.ScientificObjectsApi")
@patch("simple.data_import.silex.OntologyApi")
@patch("simple.data_import.silex.ExperimentsApi")
def test_create_sci_obj_first_run_and_empty_germplasm(
    MockExpApi, MockOntologyApi, MockSciObjApi, MockGermplasmApi, mock_get_ns, tmp_path
):
    mock_get_ns.return_value = ("fake:", "http://fake-base.com/")

    MockExpApi.return_value = _stub_experiments()

    onto = MagicMock()
    onto.children = [MagicMock(uri="vocabulary:Plant")]
    MockOntologyApi.return_value.search_sub_classes_of.return_value = {"result": [onto]}

    sci_api = MagicMock()
    sci_api.search_scientific_objects.return_value = {"result": []}
    sci_api.create_scientific_object.side_effect = [
        {"result": ["http://fake-base.com/so/1"]},
        {"result": ["http://fake-base.com/so/2"]},
    ]
    MockSciObjApi.return_value = sci_api

    germ = MagicMock()
    germ.uri = "germplasm:varietyA"
    MockGermplasmApi.return_value.search_germplasm.return_value = {"result": [germ]}

    # P2 has an EMPTY Germplasm cell -> must not trigger a "nan" lookup
    data = tmp_path / "data.xlsx"
    pd.DataFrame(
        [{"Plant ID": "P1", "Germplasm": "variety A", "Watering": "low"},
         {"Plant ID": "P2", "Germplasm": "", "Watering": "low"}]
    ).to_excel(data, index=False)

    miappe = _write_miappe(tmp_path)

    uris, created = create_sci_obj(str(data), miappe, MagicMock())

    assert created == 2
    assert set(uris) == {"P1", "P2"}

    # Germplasm should have been looked up exactly once (for "variety A")
    assert MockGermplasmApi.return_value.search_germplasm.call_count == 1

    # The output workbook must now exist (previously FileNotFoundError on 1st run)
    out = tmp_path / "output" / "miappe_template_filled.xlsx"
    assert out.exists()
    sheet = pd.read_excel(out, sheet_name="Observation Unit")
    by_id = dict(zip(sheet["externalId"], sheet["biologicalMaterialId"]))
    assert by_id["P1"] == "germplasm:varietyA"
    assert pd.isna(by_id["P2"])  # empty germplasm -> no biological material


# --------------------------------------------------------------------------- #
# 2. create_data must accept real (string) timestamps, with and without offset
# --------------------------------------------------------------------------- #
@patch("simple.data_import.connexion")
@patch("simple.data_import.silex.DataApi")
@patch("simple.data_import.silex.VariablesApi")
@patch("simple.data_import.silex.ExperimentsApi")
def test_create_data_parses_real_timestamps(
    MockExpApi, MockVarApi, MockDataApi, mock_connexion, tmp_path
):
    MockExpApi.return_value = _stub_experiments()

    var = MagicMock()
    var.uri = "http://fake-base.com/var/taille"
    MockVarApi.return_value.search_variables.return_value = {"result": [var]}

    data_api = MagicMock()
    data_api.search_data_list.return_value = {"result": []}
    MockDataApi.return_value = data_api

    # experiment_timezone exercises the tz_convert step
    miappe = _write_miappe(tmp_path, extra_exp_cols={"experiment_timezone": "Europe/Paris"})

    data = tmp_path / "data.xlsx"
    pd.DataFrame(
        [
            {"Plant ID": "Plant_1", "timestamp": "2026-08-26T14:12:12+02:00",
             "Angle": 45, "Round Order": 1, "Taille": 15.5},
            {"Plant ID": "Plant_2", "timestamp": "2026-08-26T14:12:12",
             "Angle": 90, "Round Order": 1, "Taille": 20.0},
        ]
    ).to_excel(data, index=False)

    create_data(
        str(data), miappe, "login", MagicMock(),
        morpho_info={"Taille": "var_taille"},
        prov_dict={"Prov_Test": "http://fake-base.com/prov/1"},
        datafile_provenance={os.path.basename(str(data)): {"prov_morpho_parameters": "Prov_Test"}},
        sci_obj_uri={"Plant_1": "so:1", "Plant_2": "so:2"},
    )

    assert data_api.add_list_data.called
    bodies = data_api.add_list_data.call_args.kwargs["body"]
    assert len(bodies) == 2
    # offset-aware timestamp converted to Europe/Paris (CEST in August = +02:00)
    assert bodies[0]._date == "2026-08-26T14:12:12+0200"
    # naive timestamp treated as UTC then converted to Europe/Paris
    assert bodies[1]._date == "2026-08-26T16:12:12+0200"


# --------------------------------------------------------------------------- #
# 3. the datafile metadata path must also accept offset timestamps
# --------------------------------------------------------------------------- #
def test_parse_excel_for_metadata_accepts_offset_timestamps():
    df = pd.DataFrame(
        [
            {"Experiment ID": "Exp_Test", "Plant ID": "Plant_1", "PID": "P1",
             "Datafile1_Filename": "img_001.png",
             "timestamp": "2026-08-26T14:12:12+02:00", "Angle": 45, "Round Order": 1},
        ]
    )
    out = parse_excel_for_metadata(
        df, {"img_001.png": "/photos/img_001.png"}, "prov:1", "datafile1",
        timezone_exp="Europe/Paris",
    )
    assert out["img_001.png"]["Date"] == "2026-08-26T14:12:12+0200"


def test_parse_excel_for_metadata_raises_on_missing_file():
    df = pd.DataFrame(
        [{"Experiment ID": "Exp_Test", "Plant ID": "Plant_1", "PID": "P1",
          "Datafile1_Filename": "img_001.png", "timestamp": "2026-08-26 14:12:12"}]
    )
    with pytest.raises(SimpleBaseException):
        parse_excel_for_metadata(
            df, {}, "prov:1", "datafile1", timezone_exp="UTC"
        )
