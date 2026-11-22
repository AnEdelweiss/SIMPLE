"""Core import workflows, free of any console or prompt handling.

The CLI and the GUI both drive these functions. User interaction is injected
through callbacks: a callback displays something and/or returns a decision,
while this module only performs validation, API calls and uploads. Errors are
raised as :mod:`simple.errors` exceptions so each front-end can present them
the way it wants.

``status_factory`` receives a phase identifier (the ``PHASE_*`` constants) and
must return a context manager. The CLI maps those identifiers to its Rich
spinners; the GUI passes ``None``.
"""

import zipfile
from contextlib import nullcontext
from dataclasses import dataclass

import openpyxl.utils.exceptions
import opensilexClientToolsPython as silex
import urllib3

from simple.data_import import (
    create_data,
    create_sci_obj,
    data_mapping,
    get_provenances,
)
from simple.datafile_import import (
    check_for_datafiles,
    execute_datafiles_upload,
    get_round_protocol_info,
)
from simple.errors import SimpleBaseException
from simple.logging_setup import logger
from simple.upload import UploadSummary

PHASE_CHECKING_VARIABLE_MAP = "checking_variable_map"
PHASE_CHECKING_PROVENANCES = "checking_provenances"
PHASE_CREATING_PROVENANCES = "creating_provenances"
PHASE_SCIENTIFIC_OBJECTS = "scientific_objects"
PHASE_UPLOADING_DATA = "uploading_data"
PHASE_ROUND_PROTOCOL = "round_protocol"
PHASE_COMPARING_DATAFILES = "comparing_datafiles"

# Errors an import step can realistically raise: API/network failures, file
# and workbook read errors, bad data, and SIMPLE's own errors (the upload
# helpers re-authenticate internally, so AuthenticationError lands here).
IMPORT_STEP_ERRORS = (
    silex.rest.ApiException,
    urllib3.exceptions.HTTPError,
    OSError,
    KeyError,
    ValueError,
    TypeError,
    zipfile.BadZipFile,
    openpyxl.utils.exceptions.InvalidFileException,
    SimpleBaseException,
)

DATA_IMPORT_FAILED_MESSAGE = (
    "Import Failed : This is probably because one of the variable you declared in the MIAPPE 'mapping table' sheet was not found on your Phis instance \nPlease check the sheet for typos or check that the variable really exists. "
)


@dataclass(frozen=True)
class TabularImportResult:
    """Outcome of :func:`run_tabular_import`."""

    morpho_info: dict
    prov_dict: dict
    datafile_provenance: dict
    sci_obj_uri: dict
    created_sci_obj: int
    upload_summary: UploadSummary

    @property
    def found_sci_obj(self):
        return len(self.sci_obj_uri) - self.created_sci_obj


@dataclass(frozen=True)
class DatafileImportResult:
    """Outcome of :func:`run_datafiles_import`."""

    prov_dict: dict
    datafile_provenance: dict
    sci_obj_uri: dict
    created_sci_obj: int
    cam_pos: dict
    plant_mask: dict
    protocol_found: bool
    dict_datafile1: dict
    missing_datafile1: set
    dict_datafile2: dict
    missing_datafile2: set
    has_datafile2: bool
    df_data: object

    @property
    def found_sci_obj(self):
        return len(self.sci_obj_uri) - self.created_sci_obj


def _status(status_factory, phase):
    """Build the injected status context manager (or a no-op)."""
    return status_factory(phase) if status_factory is not None else nullcontext()


def _notify(callback, *args):
    if callback is not None:
        callback(*args)


def _resolve_provenances(
    data_path,
    miappe_path,
    api_client,
    confirm_create_default,
    status_factory,
):
    """Look provenances up, asking whether to create defaults when missing."""
    with _status(status_factory, PHASE_CHECKING_PROVENANCES):
        prov_dict, datafile_provenance, missing_provs = get_provenances(
            data_path, miappe_path, api_client
        )
    if missing_provs:
        if not confirm_create_default(missing_provs):
            raise SimpleBaseException(
                "Action cancelled. Please edit your MIAPPE file or create provenances manually."
            )
        with _status(status_factory, PHASE_CREATING_PROVENANCES):
            prov_dict, datafile_provenance, _ = get_provenances(
                data_path, miappe_path, api_client, create_default=True
            )
    return prov_dict, datafile_provenance, missing_provs


def run_tabular_import(
    data_path,
    miappe_path,
    login,
    api_client,
    *,
    confirm_data_mapping,
    confirm_create_default_provenances,
    on_provenances_ready=None,
    on_scientific_objects_ready=None,
    progress_callback=None,
    status_factory=None,
    provenances=None,
    sci_obj=None,
):
    """Validate inputs and upload tabular data.

    ``confirm_data_mapping(morpho_info)`` and
    ``confirm_create_default_provenances(missing)`` return ``True`` to go on
    and ``False`` to cancel. The remaining callbacks are display-only.
    ``provenances`` and ``sci_obj`` let a caller that already resolved them
    (e.g. the GUI batch import) skip the duplicate API lookups.
    """
    with _status(status_factory, PHASE_CHECKING_VARIABLE_MAP):
        morpho_info = data_mapping(data_path, miappe_path)
    if not confirm_data_mapping(morpho_info):
        raise SimpleBaseException("Data import cancelled by the user.")

    if provenances is None:
        prov_dict, datafile_provenance, _ = _resolve_provenances(
            data_path,
            miappe_path,
            api_client,
            confirm_create_default_provenances,
            status_factory,
        )
    else:
        prov_dict, datafile_provenance = provenances
    _notify(on_provenances_ready, prov_dict)

    if sci_obj is None:
        with _status(status_factory, PHASE_SCIENTIFIC_OBJECTS):
            sci_obj_uri, created_sci_obj = create_sci_obj(
                data_path, miappe_path, api_client
            )
    else:
        sci_obj_uri, created_sci_obj = sci_obj
    _notify(
        on_scientific_objects_ready,
        len(sci_obj_uri) - created_sci_obj,
        created_sci_obj,
    )

    try:
        with _status(status_factory, PHASE_UPLOADING_DATA):
            upload_summary = create_data(
                data_path,
                miappe_path,
                login,
                api_client,
                morpho_info,
                prov_dict,
                datafile_provenance,
                sci_obj_uri,
                upload_progress=progress_callback,
            )
    except IMPORT_STEP_ERRORS as e:
        logger.error(DATA_IMPORT_FAILED_MESSAGE)
        raise SimpleBaseException(f"Error during import : {e}")

    return TabularImportResult(
        morpho_info=morpho_info,
        prov_dict=prov_dict,
        datafile_provenance=datafile_provenance,
        sci_obj_uri=sci_obj_uri,
        created_sci_obj=created_sci_obj,
        upload_summary=upload_summary,
    )


def plan_datafiles_import(
    miappe_path,
    data_path,
    experiment_directory,
    api_client,
    photos_dir,
    *,
    confirm_create_default_provenances,
    confirm_protocol,
    confirm_discrepancies,
    confirm_upload,
    datafile_check=None,
    on_provenances_ready=None,
    on_scientific_objects_ready=None,
    status_factory=None,
    provenances=None,
    sci_obj=None,
):
    """Validate everything needed before uploading datafiles.

    ``confirm_protocol(protocol_found)``, ``confirm_discrepancies(missing1,
    missing2)`` and ``confirm_upload()`` return ``True`` to continue. When a
    front-end already ran :func:`check_for_datafiles` (to ask its question on
    the main thread), it can pass the result as ``datafile_check``.

    Returns a :class:`DatafileImportResult` used as the upload plan.
    """
    if provenances is None:
        prov_dict, datafile_provenance, _ = _resolve_provenances(
            data_path,
            miappe_path,
            api_client,
            confirm_create_default_provenances,
            status_factory,
        )
    else:
        prov_dict, datafile_provenance = provenances
    _notify(on_provenances_ready, prov_dict)

    if sci_obj is None:
        with _status(status_factory, PHASE_SCIENTIFIC_OBJECTS):
            sci_obj_uri, created_sci_obj = create_sci_obj(
                data_path, miappe_path, api_client
            )
    else:
        sci_obj_uri, created_sci_obj = sci_obj
    _notify(
        on_scientific_objects_ready,
        len(sci_obj_uri) - created_sci_obj,
        created_sci_obj,
    )

    with _status(status_factory, PHASE_ROUND_PROTOCOL):
        cam_pos, plant_mask, protocol_found = get_round_protocol_info(
            experiment_directory, data_path
        )
    if not confirm_protocol(protocol_found):
        raise SimpleBaseException("User cancelled import at Round protocol phase.")

    if datafile_check is None:
        with _status(status_factory, PHASE_COMPARING_DATAFILES):
            datafile_check = check_for_datafiles(data_path, photos_dir)
    (
        dict_datafile1,
        missing_datafile1,
        dict_datafile2,
        missing_datafile2,
        has_datafile2,
        df_data,
    ) = datafile_check

    if not confirm_discrepancies(missing_datafile1, missing_datafile2):
        raise SimpleBaseException(
            "User cancelled action after database discrepancies were found."
        )

    if not confirm_upload():
        raise SimpleBaseException("User aborted datafile import")

    return DatafileImportResult(
        prov_dict=prov_dict,
        datafile_provenance=datafile_provenance,
        sci_obj_uri=sci_obj_uri,
        created_sci_obj=created_sci_obj,
        cam_pos=cam_pos,
        plant_mask=plant_mask,
        protocol_found=protocol_found,
        dict_datafile1=dict_datafile1,
        missing_datafile1=missing_datafile1,
        dict_datafile2=dict_datafile2,
        missing_datafile2=missing_datafile2,
        has_datafile2=has_datafile2,
        df_data=df_data,
    )


def upload_datafiles(
    plan,
    miappe_path,
    data_path,
    login,
    api_client,
    *,
    status_callback=None,
    progress_callback=None,
):
    """Upload the datafiles described by a :func:`plan_datafiles_import` plan.

    Returns the created/failed/skipped :class:`UploadSummary`.
    """
    try:
        summary = execute_datafiles_upload(
            miappe_path,
            data_path,
            plan.df_data,
            plan.dict_datafile1,
            plan.dict_datafile2,
            plan.has_datafile2,
            plan.prov_dict,
            plan.datafile_provenance,
            plan.sci_obj_uri,
            plan.cam_pos,
            plan.plant_mask,
            login,
            api_client,
            status_callback=status_callback,
            progress_callback=progress_callback,
        )
    except IMPORT_STEP_ERRORS as e:
        logger.exception(f"Datafile upload failed : {e}")
        raise SimpleBaseException(
            "An error occurred during datafile upload. Please see the logs for more information."
        )
    return summary


def run_datafiles_import(
    miappe_path,
    data_path,
    experiment_directory,
    login,
    api_client,
    photos_dir,
    *,
    confirm_create_default_provenances,
    confirm_protocol,
    confirm_discrepancies,
    confirm_upload,
    datafile_check=None,
    on_provenances_ready=None,
    on_scientific_objects_ready=None,
    status_callback=None,
    progress_callback=None,
    status_factory=None,
    provenances=None,
    sci_obj=None,
):
    """Plan then upload datafiles in one call (used by the GUI)."""
    plan = plan_datafiles_import(
        miappe_path,
        data_path,
        experiment_directory,
        api_client,
        photos_dir,
        confirm_create_default_provenances=confirm_create_default_provenances,
        confirm_protocol=confirm_protocol,
        confirm_discrepancies=confirm_discrepancies,
        confirm_upload=confirm_upload,
        datafile_check=datafile_check,
        on_provenances_ready=on_provenances_ready,
        on_scientific_objects_ready=on_scientific_objects_ready,
        status_factory=status_factory,
        provenances=provenances,
        sci_obj=sci_obj,
    )
    return upload_datafiles(
        plan,
        miappe_path,
        data_path,
        login,
        api_client,
        status_callback=status_callback,
        progress_callback=progress_callback,
    )
