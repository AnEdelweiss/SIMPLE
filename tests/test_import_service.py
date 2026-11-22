"""Tests for the UI-free import workflows in simple.import_service."""

from unittest.mock import MagicMock, patch

import opensilexClientToolsPython as silex
import pytest

from simple.erreurs import SimpleBaseException
from simple.import_service import (
    PHASE_CHECKING_PROVENANCES,
    PHASE_CHECKING_VARIABLE_MAP,
    PHASE_COMPARING_DATAFILES,
    PHASE_CREATING_PROVENANCES,
    PHASE_ROUND_PROTOCOL,
    PHASE_SCIENTIFIC_OBJECTS,
    PHASE_UPLOADING_DATA,
    plan_datafiles_import,
    run_datafiles_import,
    run_tabular_import,
    upload_datafiles,
)


class RecordingStatus:
    def __init__(self, phases, phase):
        self.phases = phases
        self.phase = phase

    def __enter__(self):
        self.phases.append(("start", self.phase))
        return self

    def __exit__(self, *exc_info):
        self.phases.append(("end", self.phase))
        return False


def status_factory(phases):
    return lambda phase: RecordingStatus(phases, phase)


def always(decision=True):
    return lambda *args: decision


def datafile_check():
    return ({"a.png": "/tmp/a.png"}, {"missing1"}, {}, set(), True, "DF_DATA")


def _assert_raises_message(message, func, *args, **kwargs):
    with pytest.raises(SimpleBaseException) as error_info:
        func(*args, **kwargs)
    assert str(error_info.value) == message


class TestRunTabularImport:
    @patch("simple.import_service.create_data")
    @patch("simple.import_service.create_sci_obj")
    @patch("simple.import_service.get_provenances")
    @patch("simple.import_service.data_mapping")
    def test_happy_path(
        self, mock_mapping, mock_provenances, mock_sci_obj, mock_create_data
    ):
        mock_mapping.return_value = {"Taille": "var_taille"}
        mock_provenances.return_value = ({"Prov": "prov:1"}, {"d.csv": {}}, [])
        mock_sci_obj.return_value = ({"P1": "so:1", "P2": "so:2"}, 1)

        phases, events = [], []

        def progress(variable, lines):
            events.append(("progress", variable, lines))

        result = run_tabular_import(
            "data.xlsx",
            "miappe.xlsx",
            "login",
            "client",
            confirm_data_mapping=always(True),
            confirm_create_default_provenances=always(True),
            on_provenances_ready=lambda prov: events.append(("prov", prov)),
            on_scientific_objects_ready=lambda found, created: events.append(
                ("sci", found, created)
            ),
            progress_callback=progress,
            status_factory=status_factory(phases),
        )

        assert result.morpho_info == {"Taille": "var_taille"}
        assert result.created_sci_obj == 1
        assert result.found_sci_obj == 1
        assert events == [
            ("prov", {"Prov": "prov:1"}),
            ("sci", 1, 1),
        ]
        assert phases == [
            ("start", PHASE_CHECKING_VARIABLE_MAP),
            ("end", PHASE_CHECKING_VARIABLE_MAP),
            ("start", PHASE_CHECKING_PROVENANCES),
            ("end", PHASE_CHECKING_PROVENANCES),
            ("start", PHASE_SCIENTIFIC_OBJECTS),
            ("end", PHASE_SCIENTIFIC_OBJECTS),
            ("start", PHASE_UPLOADING_DATA),
            ("end", PHASE_UPLOADING_DATA),
        ]
        mock_create_data.assert_called_once_with(
            "data.xlsx",
            "miappe.xlsx",
            "login",
            "client",
            {"Taille": "var_taille"},
            {"Prov": "prov:1"},
            {"d.csv": {}},
            {"P1": "so:1", "P2": "so:2"},
            avancement_upload=progress,
        )

    @patch("simple.import_service.create_data")
    @patch("simple.import_service.data_mapping")
    def test_mapping_cancelled(self, mock_mapping, mock_create_data):
        mock_mapping.return_value = {"Taille": "var_taille"}

        _assert_raises_message(
            "Data import cancelled by the user.",
            run_tabular_import,
            "data.xlsx",
            "miappe.xlsx",
            "login",
            "client",
            confirm_data_mapping=always(False),
            confirm_create_default_provenances=always(True),
        )
        mock_create_data.assert_not_called()

    @patch("simple.import_service.create_sci_obj")
    @patch("simple.import_service.get_provenances")
    @patch("simple.import_service.data_mapping")
    def test_missing_provenances_declined(
        self, mock_mapping, mock_provenances, mock_sci_obj
    ):
        mock_mapping.return_value = {}
        mock_provenances.return_value = ({}, {}, ["MissingProv"])
        seen = []

        def decline(missing):
            seen.append(missing)
            return False

        _assert_raises_message(
            "Action cancelled. Please edit your MIAPPE file or create provenances manually.",
            run_tabular_import,
            "data.xlsx",
            "miappe.xlsx",
            "login",
            "client",
            confirm_data_mapping=always(True),
            confirm_create_default_provenances=decline,
        )
        assert seen == [["MissingProv"]]
        mock_provenances.assert_called_once()
        mock_sci_obj.assert_not_called()

    @patch("simple.import_service.create_data")
    @patch("simple.import_service.create_sci_obj")
    @patch("simple.import_service.get_provenances")
    @patch("simple.import_service.data_mapping")
    def test_missing_provenances_accepted_creates_defaults(
        self, mock_mapping, mock_provenances, mock_sci_obj, mock_create_data
    ):
        mock_mapping.return_value = {}
        mock_provenances.side_effect = [
            ({}, {}, ["MissingProv"]),
            ({"MissingProv": "prov:1"}, {}, []),
        ]
        mock_sci_obj.return_value = ({}, 0)

        result = run_tabular_import(
            "data.xlsx",
            "miappe.xlsx",
            "login",
            "client",
            confirm_data_mapping=always(True),
            confirm_create_default_provenances=always(True),
        )

        assert result.prov_dict == {"MissingProv": "prov:1"}
        assert mock_provenances.call_count == 2
        assert mock_provenances.call_args_list[1].kwargs == {"create_default": True}

    @patch("simple.import_service.create_data")
    @patch("simple.import_service.create_sci_obj")
    @patch("simple.import_service.get_provenances")
    @patch("simple.import_service.data_mapping")
    def test_upload_error_is_wrapped(
        self, mock_mapping, mock_provenances, mock_sci_obj, mock_create_data
    ):
        mock_mapping.return_value = {}
        mock_provenances.return_value = ({}, {}, [])
        mock_sci_obj.return_value = ({}, 0)
        mock_create_data.side_effect = silex.rest.ApiException(
            status=500, reason="boom"
        )

        with pytest.raises(SimpleBaseException) as error_info:
            run_tabular_import(
                "data.xlsx",
                "miappe.xlsx",
                "login",
                "client",
                confirm_data_mapping=always(True),
                confirm_create_default_provenances=always(True),
            )

        assert str(error_info.value).startswith("Error during import :")


class TestPlanDatafilesImport:
    @patch("simple.import_service.check_for_datafiles")
    @patch("simple.import_service.get_round_protocol_info")
    @patch("simple.import_service.create_sci_obj")
    @patch("simple.import_service.get_provenances")
    def test_happy_path(
        self, mock_provenances, mock_sci_obj, mock_protocol, mock_check
    ):
        mock_provenances.return_value = ({"Prov": "prov:1"}, {"d.csv": {}}, [])
        mock_sci_obj.return_value = ({"P1": "so:1", "P2": "so:2"}, 1)
        mock_protocol.return_value = ({"1": {}}, {"1": {}}, True)
        mock_check.return_value = datafile_check()

        phases, events = [], []
        plan = plan_datafiles_import(
            "miappe.xlsx",
            "data.xlsx",
            "wd",
            "client",
            "photos",
            confirm_create_default_provenances=always(True),
            confirm_protocol=lambda found: events.append(("protocol", found)) or True,
            confirm_discrepancies=lambda m1, m2: events.append(("discrepancies", m1, m2))
            or True,
            confirm_upload=lambda: events.append(("upload",)) or True,
            on_provenances_ready=lambda prov: events.append(("prov", prov)),
            on_scientific_objects_ready=lambda found, created: events.append(
                ("sci", found, created)
            ),
            status_factory=status_factory(phases),
        )

        assert plan.prov_dict == {"Prov": "prov:1"}
        assert plan.sci_obj_uri == {"P1": "so:1", "P2": "so:2"}
        assert plan.created_sci_obj == 1
        assert plan.found_sci_obj == 1
        assert plan.protocol_found is True
        assert plan.missing_datafile1 == {"missing1"}
        assert plan.df_data == "DF_DATA"
        assert events == [
            ("prov", {"Prov": "prov:1"}),
            ("sci", 1, 1),
            ("protocol", True),
            ("discrepancies", {"missing1"}, set()),
            ("upload",),
        ]
        assert phases == [
            ("start", PHASE_CHECKING_PROVENANCES),
            ("end", PHASE_CHECKING_PROVENANCES),
            ("start", PHASE_SCIENTIFIC_OBJECTS),
            ("end", PHASE_SCIENTIFIC_OBJECTS),
            ("start", PHASE_ROUND_PROTOCOL),
            ("end", PHASE_ROUND_PROTOCOL),
            ("start", PHASE_COMPARING_DATAFILES),
            ("end", PHASE_COMPARING_DATAFILES),
        ]

    @patch("simple.import_service.check_for_datafiles")
    @patch("simple.import_service.get_round_protocol_info")
    @patch("simple.import_service.create_sci_obj")
    @patch("simple.import_service.get_provenances")
    def test_protocol_cancelled(
        self, mock_provenances, mock_sci_obj, mock_protocol, mock_check
    ):
        mock_provenances.return_value = ({}, {}, [])
        mock_sci_obj.return_value = ({}, 0)
        mock_protocol.return_value = ({}, {}, False)

        _assert_raises_message(
            "User cancelled import at Round protocol phase.",
            plan_datafiles_import,
            "miappe.xlsx",
            "data.xlsx",
            "wd",
            "client",
            "photos",
            confirm_create_default_provenances=always(True),
            confirm_protocol=always(False),
            confirm_discrepancies=always(True),
            confirm_upload=always(True),
        )
        mock_check.assert_not_called()

    @patch("simple.import_service.check_for_datafiles")
    @patch("simple.import_service.get_round_protocol_info")
    @patch("simple.import_service.create_sci_obj")
    @patch("simple.import_service.get_provenances")
    def test_discrepancies_cancelled(
        self, mock_provenances, mock_sci_obj, mock_protocol, mock_check
    ):
        mock_provenances.return_value = ({}, {}, [])
        mock_sci_obj.return_value = ({}, 0)
        mock_protocol.return_value = ({}, {}, True)
        mock_check.return_value = datafile_check()

        _assert_raises_message(
            "User cancelled action after database discrepancies were found.",
            plan_datafiles_import,
            "miappe.xlsx",
            "data.xlsx",
            "wd",
            "client",
            "photos",
            confirm_create_default_provenances=always(True),
            confirm_protocol=always(True),
            confirm_discrepancies=always(False),
            confirm_upload=always(True),
        )

    @patch("simple.import_service.check_for_datafiles")
    @patch("simple.import_service.get_round_protocol_info")
    @patch("simple.import_service.create_sci_obj")
    @patch("simple.import_service.get_provenances")
    def test_upload_cancelled(
        self, mock_provenances, mock_sci_obj, mock_protocol, mock_check
    ):
        mock_provenances.return_value = ({}, {}, [])
        mock_sci_obj.return_value = ({}, 0)
        mock_protocol.return_value = ({}, {}, True)
        mock_check.return_value = datafile_check()

        _assert_raises_message(
            "User aborted datafile import",
            plan_datafiles_import,
            "miappe.xlsx",
            "data.xlsx",
            "wd",
            "client",
            "photos",
            confirm_create_default_provenances=always(True),
            confirm_protocol=always(True),
            confirm_discrepancies=always(True),
            confirm_upload=always(False),
        )

    @patch("simple.import_service.check_for_datafiles")
    @patch("simple.import_service.get_round_protocol_info")
    @patch("simple.import_service.create_sci_obj")
    @patch("simple.import_service.get_provenances")
    def test_precomputed_check_is_reused(
        self, mock_provenances, mock_sci_obj, mock_protocol, mock_check
    ):
        mock_provenances.return_value = ({}, {}, [])
        mock_sci_obj.return_value = ({}, 0)
        mock_protocol.return_value = ({}, {}, True)
        precomputed = datafile_check()

        plan = plan_datafiles_import(
            "miappe.xlsx",
            "data.xlsx",
            "wd",
            "client",
            "photos",
            confirm_create_default_provenances=always(True),
            confirm_protocol=always(True),
            confirm_discrepancies=always(True),
            confirm_upload=always(True),
            datafile_check=precomputed,
        )

        assert plan.df_data == "DF_DATA"
        mock_check.assert_not_called()


class TestUploadDatafiles:
    @patch("simple.import_service.execute_datafiles_upload")
    def test_upload_uses_plan(self, mock_execute):
        plan = MagicMock(
            prov_dict={"Prov": "prov:1"},
            datafile_provenance={"d.csv": {}},
            sci_obj_uri={"P1": "so:1"},
            cam_pos={},
            plant_mask={},
            dict_datafile1={},
            dict_datafile2={},
            has_datafile2=False,
            df_data="DF_DATA",
        )

        status = MagicMock()
        progress = MagicMock()
        returned = upload_datafiles(
            plan,
            "miappe.xlsx",
            "data.xlsx",
            "login",
            "client",
            status_callback=status,
            progress_callback=progress,
        )

        assert returned is plan
        mock_execute.assert_called_once_with(
            "miappe.xlsx",
            "data.xlsx",
            "DF_DATA",
            {},
            {},
            False,
            {"Prov": "prov:1"},
            {"d.csv": {}},
            {"P1": "so:1"},
            {},
            {},
            "login",
            "client",
            status_callback=status,
            progress_callback=progress,
        )

    @patch("simple.import_service.execute_datafiles_upload")
    def test_upload_error_is_wrapped(self, mock_execute):
        mock_execute.side_effect = OSError("disk gone")
        plan = MagicMock()

        with pytest.raises(SimpleBaseException) as error_info:
            upload_datafiles(plan, "m", "d", "login", "client")

        assert str(error_info.value) == (
            "An error occurred during datafile upload. Please see the logs for more information."
        )

    @patch("simple.import_service.upload_datafiles")
    @patch("simple.import_service.plan_datafiles_import")
    def test_run_datafiles_import_composes_both_steps(self, mock_plan, mock_upload):
        plan = object()
        mock_plan.return_value = plan
        mock_upload.return_value = plan

        result = run_datafiles_import(
            "miappe.xlsx",
            "data.xlsx",
            "wd",
            "login",
            "client",
            "photos",
            confirm_create_default_provenances=always(True),
            confirm_protocol=always(True),
            confirm_discrepancies=always(True),
            confirm_upload=always(True),
        )

        assert result is plan
        mock_upload.assert_called_once_with(
            plan,
            "miappe.xlsx",
            "data.xlsx",
            "login",
            "client",
            status_callback=None,
            progress_callback=None,
        )
