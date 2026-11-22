"""Tests for the datafile validation/upload core."""

from unittest.mock import MagicMock, patch

import opensilexClientToolsPython as silex
import pandas as pd
import pytest

from simple.datafile_import import (
    check_for_datafiles,
    execute_datafiles_upload,
    get_round_protocol_info,
)
from simple.errors import DataImportError


def _miappe(tmp_path):
    path = tmp_path / "miappe.xlsx"
    df = pd.DataFrame(
        [["--", "--"], ["name", "experiment_timezone"], ["Exp_Test", "UTC"]]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="experiment", header=False, index=False)
    return str(path)


def _df_data(datafile2=False):
    row = {
        "Experiment ID": "Exp_Test",
        "Plant ID": "Plant_1",
        "PID": "PID1",
        "Datafile1_Filename": "img_a.png",
        "timestamp": "2026-08-26T14:12:12+02:00",
        "Angle": 45,
        "Round Order": 1,
    }
    if datafile2:
        row["Datafile2_Filename"] = "mask_a.png"
    return pd.DataFrame([row])


def _config(datafile2=False):
    config = {
        "prov_morpho_parameters": "Prov_Morpho",
        "prov_datafiles1": "Prov_Raw",
        "rdf_type_datafile1": "RGBImage",
    }
    if datafile2:
        config.update(
            {
                "prov_datafiles2": "Prov_Derived",
                "rdf_type_datafile2": "RGBImage",
            }
        )
    return config


def _upload_kwargs(tmp_path, datafile2=False):
    return {
        "miappe_path": _miappe(tmp_path),
        "data_path": str(tmp_path / "data.xlsx"),
        "df_data": _df_data(datafile2),
        "dict_datafile1": {"img_a.png": str(tmp_path / "img_a.png")},
        "dict_datafile2": ({"mask_a.png": str(tmp_path / "mask_a.png")} if datafile2 else {}),
        "has_datafile2": datafile2,
        "prov_dict": {"Prov_Raw": "prov:raw", "Prov_Derived": "prov:derived"},
        "datafile_provenance": {
            "data.xlsx": _config(datafile2),
        },
        "sci_obj_uri": {"Plant_1": "so:1"},
        "cam_pos": {1: {"height": "2", "Offset": "5"}},
        "plant_mask": {1: {"PlantMask": "mask"}},
        "login": "login",
        "api_client": "client",
    }


class TestExecuteDatafilesUpload:
    @patch("simple.datafile_import.connect")
    @patch("simple.datafile_import.get_existing_datafiles")
    @patch("simple.datafile_import.silex.DataApi")
    @patch("simple.datafile_import.silex.ExperimentsApi")
    def test_uploads_missing_datafiles1(
        self, MockExpApi, MockDataApi, mock_existing, mock_connect, tmp_path
    ):
        exp = MagicMock(uri="exp:1")
        MockExpApi.return_value.search_experiments.return_value = {"result": [exp]}
        data_api = MockDataApi.return_value
        mock_existing.return_value = {
            ("so:1", "2026-08-26T12:12:12.000+0000", "45", "1")
        }

        status = MagicMock()
        progress = MagicMock()
        result = execute_datafiles_upload(
            **_upload_kwargs(tmp_path),
            status_callback=status,
            progress_callback=progress,
        )

        assert result == 1
        # img_a already exists according to the mocked cache -> nothing posted.
        data_api.post_data_file.assert_not_called()
        progress.assert_not_called()
        status.assert_any_call("[green][✓] datafile1 data parsing OK [/green]")
        status.assert_any_call(
            "[green][✓] All Datafiles 1 were already uploaded (or there was no datafiles1)[/green]"
        )

    @patch("simple.datafile_import.connect")
    @patch("simple.datafile_import.get_existing_datafiles")
    @patch("simple.datafile_import.silex.DataApi")
    @patch("simple.datafile_import.silex.ExperimentsApi")
    def test_uploads_new_datafile1_and_datafile2(
        self, MockExpApi, MockDataApi, mock_existing, mock_connect, tmp_path
    ):
        exp = MagicMock(uri="exp:1")
        MockExpApi.return_value.search_experiments.return_value = {"result": [exp]}
        data_api = MockDataApi.return_value
        # First call (datafile1) and third call (datafile2) are empty; the
        # second call is the datafile1 URI map used to link datafile2.
        mock_existing.return_value = set()
        data_api.get_data_file_descriptions_by_search.return_value = {
            "result": [
                MagicMock(
                    target="so:1",
                    _date="2026-08-26T12:12:12.000+0000",
                    uri="datafile:1",
                )
            ]
        }

        status = MagicMock()
        execute_datafiles_upload(
            **_upload_kwargs(tmp_path, datafile2=True),
            status_callback=status,
            progress_callback=MagicMock(),
        )

        assert data_api.post_data_file.call_count == 2
        assert status.call_args_list
        assert any(
            "Datafile 2 upload complete" in call.args[0]
            for call in status.call_args_list
        )

    @patch("simple.datafile_import.connect")
    @patch("simple.datafile_import.get_existing_datafiles")
    @patch("simple.datafile_import.silex.DataApi")
    @patch("simple.datafile_import.silex.ExperimentsApi")
    def test_failed_upload_is_reported_and_batch_continues(
        self, MockExpApi, MockDataApi, mock_existing, mock_connect, tmp_path
    ):
        exp = MagicMock(uri="exp:1")
        MockExpApi.return_value.search_experiments.return_value = {"result": [exp]}
        data_api = MockDataApi.return_value
        mock_existing.return_value = set()
        data_api.post_data_file.side_effect = silex.rest.ApiException(
            status=500, reason="boom"
        )

        status = MagicMock()
        progress = MagicMock()
        execute_datafiles_upload(
            **_upload_kwargs(tmp_path),
            status_callback=status,
            progress_callback=progress,
        )

        assert any(
            "A datafile failed to upload" in call.args[0]
            for call in status.call_args_list
        )
        progress.assert_any_call(
            "[bold blue]Uploading datafiles 1...[/bold blue]", advance=1
        )


class TestGetRoundProtocolInfo:
    def test_reads_utf16_round_files(self, tmp_path):
        round_folder = tmp_path / "00-RoundProtocol"
        round_folder.mkdir()
        xml = (
            "<root><PID><PlantMask><mask>1</mask></PlantMask>"
            "<Offset>5</Offset></PID></root>"
        )
        (round_folder / "exp-Round-001.txt").write_text(xml, encoding="utf-16")

        data = tmp_path / "data.xlsx"
        pd.DataFrame({"PID": ["PID"]}).to_excel(data, index=False)

        cam_pos, plant_mask, found = get_round_protocol_info(
            str(tmp_path), str(data)
        )

        assert found is True
        assert cam_pos[1]["Offset"] == "5"
        assert plant_mask[1] == {"mask": "1"}

    def test_missing_folder_returns_false(self, tmp_path):
        data = tmp_path / "data.xlsx"
        pd.DataFrame({"PID": ["PID"]}).to_excel(data, index=False)

        assert get_round_protocol_info(str(tmp_path), str(data)) == ({}, {}, False)


class TestCheckForDatafiles:
    def test_maps_present_files_and_reports_missing(self, tmp_path):
        photos = tmp_path / "photos"
        photos.mkdir()
        (photos / "a.png").write_bytes(b"a")
        data = tmp_path / "data.xlsx"
        pd.DataFrame({"Datafile1_Filename": ["a.png", "missing.png"]}).to_excel(
            data, index=False
        )

        (
            dict1,
            missing1,
            dict2,
            missing2,
            has_datafile2,
            df_data,
        ) = check_for_datafiles(str(data), str(photos))

        assert dict1 == {"a.png": str(photos / "a.png")}
        assert missing1 == {"missing.png"}
        assert dict2 == {}
        assert missing2 == set()
        assert has_datafile2 is False
        assert len(df_data) == 2

    def test_missing_datafile1_column_raises(self, tmp_path):
        data = tmp_path / "data.xlsx"
        pd.DataFrame({"Other": ["x"]}).to_excel(data, index=False)

        with pytest.raises(DataImportError):
            check_for_datafiles(str(data), str(tmp_path))
