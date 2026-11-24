import concurrent.futures
import datetime
import json
import os

import opensilexClientToolsPython as silex
import pandas as pd
import urllib3
from lxml import etree as ET

from simple.__init__ import __version__
from simple.auth import connect
from simple.cancellation import check_cancelled
from simple.data_import import find_datafile_config, format_timestamps
from simple.errors import DataImportError, ImportCancelled, SimpleBaseException
from simple.logging_setup import logger
from simple.upload import UploadSummary, with_retry

# A single datafile upload failure must not abort the whole batch: these are
# the errors the upload call itself can realistically raise (API/network,
# file access, bad row data or client-side DTO validation).
DATAFILE_UPLOAD_ERRORS = (
    silex.rest.ApiException,
    urllib3.exceptions.HTTPError,
    OSError,
    KeyError,
    IndexError,
    AttributeError,
    ValueError,
    TypeError,
)


def get_round_protocol_info(experiment_directory, data_path):
    # Get RoundProtocol Infos
    plant_mask = {}
    cam_pos = {}
    round_folder = os.path.join(experiment_directory, "00-RoundProtocol")

    if os.path.isdir(round_folder):
        round_file_paths = []
        for root, dirs, files in os.walk(round_folder):
            for name in files:
                round_file_paths.append(os.path.join(root, name))

        round_file_map = {}
        for round_file in round_file_paths:
            filename = os.path.basename(round_file).replace(".txt", "")
            filename_parts = filename.split("-")
            round_file_map.update(
                {
                    round_file: {
                        "Experiment": filename_parts[1],
                        "Round": (filename_parts[2][0:3]).replace("_", ""),
                    }
                }
            )

        # Create Dictionary for all parameters
        df_data = pd.read_excel(data_path)
        PID = df_data["PID"].unique()[0]
        # Transform RoundProtocol to xml
        for key, value in round_file_map.items():
            try:
                with open(key, encoding="utf-16") as file:
                    xml_str = file.read().replace("\x00", "")
                root = ET.fromstring(xml_str)
            except (UnicodeError, ET.XMLSyntaxError):
                # Round-protocol files are usually UTF-16 but some exports are
                # plain UTF-8/ASCII; retry once with the default encoding.
                with open(key) as file:
                    xml_str = file.read().replace("\x00", "")
                root = ET.fromstring(xml_str)
            # Get plant_mask Info for all rounds
            plant_mask_rd = {}
            for child in root.iter(PID):
                for subchild in child.iter("PlantMask"):
                    plant_mask_rd = {elem.tag: elem.text for elem in subchild}
                    round_index = int(value["Round"])
                    plant_mask[round_index] = plant_mask_rd

            cam_pos_rd = {}
            for child in root.iter(PID):
                cam_pos_rd.update(child.attrib)
            for child in root.iter(PID):
                for subchild in child.iter("Offset"):
                    cam_pos_rd.update({subchild.tag: subchild.text})
                    round_index = int(value["Round"])
                    cam_pos[round_index] = cam_pos_rd
        logger.info("Plant_mask and Camera Position Info found !")
    else:
        logger.warning("00-RoundProtocol folder missing (ok if not in use)")
        return cam_pos, plant_mask, False
    return cam_pos, plant_mask, True


def parse_excel_for_metadata(df_data, dict_paths, prov, file_type, timezone_exp="UTC"):

    metadata_dict = {}

    # Process the single timestamp column using the provided timezone
    df_data["Measuring Time"] = format_timestamps(df_data["timestamp"], timezone_exp)

    for row in list(df_data.to_dict("records")):
        exp_id = row["Experiment ID"]
        tray_id = row["Plant ID"]
        pid = row.get("PID", None)

        if file_type == "datafile1":
            filename = row.get("Datafile1_Filename")
        else:
            filename = row.get("Datafile2_Filename")

        if pd.isna(filename) or filename not in dict_paths:
            logger.error(
                f"warning : {filename} in 'data files' sheet of the  MIAPPE file is either empty or maybe there is a typo etc..."
            )
            raise SimpleBaseException(
                f"warning : {filename} in 'data files' sheet of the  MIAPPE file is either empty or maybe there is a typo etc..."
            )
            continue

        date = row["Measuring Time"]

        metadata = {
            "Path": dict_paths[filename],
            "Experiment ID": exp_id,
            "Date": date,
            "Plant ID": tray_id,
            "PID": pid,
            "Prov": prov,
            "ImgType": filename.replace("-", "_").split("_")[-1],
        }

        if "Angle" in row:
            metadata["Angle"] = row["Angle"]
        if "Round Order" in row:
            metadata["Round Order"] = int(row["Round Order"])
        metadata_dict[filename] = metadata

    return metadata_dict


def get_existing_datafiles(dat_api, prov_uri, exp_uri):
    if not prov_uri:
        return set()
    # On prends le set de tuples (target, date, angle, round_order) existants
    dat_src = dat_api.get_data_file_descriptions_by_search(
        provenances=[prov_uri], experiments=[exp_uri], page_size=100000
    )["result"]
    # je convertit en string les camera angle et les round order pour eviter les erreurs lors de la recuperation des metadata après
    return {
        (
            elts.target,
            elts._date,
            str(elts.provenance.settings.get("Camera Angle"))
            if elts.provenance.settings
            and elts.provenance.settings.get("Camera Angle") is not None
            else None,
            str(elts.metadata.get("Round Order"))
            if elts.metadata and elts.metadata.get("Round Order") is not None
            else None,
        )
        for elts in dat_src
    }


def check_for_datafiles(data_path, photos_directory):
    # Liste des datafiles
    ls_files_dict = {}
    for root, dirs, files in os.walk(photos_directory):
        for filename in files:
            ls_files_dict[filename] = os.path.join(root, filename)

    df_data = pd.read_excel(data_path)
    # traitement des datafiles1
    dict_datafile1 = {}
    missing_datafile1 = set()
    if "Datafile1_Filename" in df_data.columns:
        set_ls_datafile1 = set(df_data["Datafile1_Filename"].dropna().unique())
        dict_datafile1 = {
            f: ls_files_dict[f] for f in set_ls_datafile1 if f in ls_files_dict
        }
        missing_datafile1 = set_ls_datafile1 - set(dict_datafile1.keys())
    else:
        logger.error(
            "User tried to import datafiles without 'datafile1_Filename column"
        )
        raise DataImportError(
            "You are importing datafiles, you have to specify the name of the file for each row in a column named 'Datafile1_Filename'."
        )
    # traitement des datafiles2
    has_datafile2 = "Datafile2_Filename" in df_data.columns
    dict_datafile2 = {}
    missing_datafile2 = set()
    if has_datafile2:
        set_ls_datafile2 = set(df_data["Datafile2_Filename"].dropna().unique())
        dict_datafile2 = {
            f: ls_files_dict[f] for f in set_ls_datafile2 if f in ls_files_dict
        }
        missing_datafile2 = set_ls_datafile2 - set(dict_datafile2.keys())

    return (
        dict_datafile1,
        missing_datafile1,
        dict_datafile2,
        missing_datafile2,
        has_datafile2,
        df_data,
    )


def execute_datafiles_upload(
    miappe_path,
    data_path,
    df_data,
    dict_datafile1,
    dict_datafile2,
    has_datafile2,
    prov_dict,
    datafile_provenance,
    sci_obj_uri,
    cam_pos,
    plant_mask,
    login,
    api_client,
    status_callback=None,
    progress_callback=None,
    should_cancel=None,
):

    connect(login, api_client)
    check_cancelled(should_cancel)
    dataframe = pd.read_excel(miappe_path, sheet_name="experiment", header=1)
    dataframe.drop(
        dataframe.columns[dataframe.columns.str.contains("unnamed", case=False)],
        axis=1,
        inplace=True,
    )
    name_exp = dataframe["name"].dropna().iloc[0]
    exp_search = silex.ExperimentsApi(api_client).search_experiments(
        name=name_exp
    )["result"]
    exp_uri = exp_search[0].uri
    logger.info(f"exp name : {name_exp}  exp uri : {exp_uri}")
    # Setting timezone
    if (
        "experiment_timezone" in dataframe.columns
        and not dataframe["experiment_timezone"].dropna().empty
    ):
        timezone_exp = dataframe["experiment_timezone"].dropna().iloc[0]
    else:
        timezone_exp = "UTC"
    logger.info(f"timezone : {timezone_exp}")
    # GETTING PID and angle
    if "PID" in df_data.columns:
        pid = df_data["PID"].unique()[0]
        if status_callback:
            status_callback(f"[bold cyan][✓] PID found:[/bold cyan] {pid}")
        logger.info(f"[bold cyan][✓] PID found:[/bold cyan] {pid}")
    else:
        pid = None
    if "Angle" not in df_data.columns:
        df_data["Angle"] = None
        if status_callback:
            status_callback(
                "No angle data was found in the tabular data. It is not a problem, if it is intentional."
            )
        logger.info(
            "No angle data was found in the tabular data. It is not a problem, if it is intentional."
        )

    dat_api = silex.DataApi(api_client)
    provenance_datafile1 = None
    provenance_datafile2 = None
    rdf_type_1 = None
    rdf_type_2 = None
    config = find_datafile_config(datafile_provenance, data_path)
    if config is not None:
        val1 = config.get("prov_datafiles1")
        rdf1 = config.get("rdf_type_datafile1")
        val2 = config.get("prov_datafiles2")
        rdf2 = config.get("rdf_type_datafile2")
        provenance_datafile1 = prov_dict.get(val1) if not pd.isna(val1) else None
        rdf_type_1 = rdf1 if not pd.isna(rdf1) else None
        provenance_datafile2 = prov_dict.get(val2) if not pd.isna(val2) else None
        rdf_type_2 = rdf2 if not pd.isna(rdf2) else None
    if status_callback:
        status_callback(
            f"[green][✓] Provenance for datafile1 found : {provenance_datafile1}[/green]"
        )
    logger.info(
        f"[green][✓] Provenance for datafile1 found : {provenance_datafile1}[/green]"
    )
    if provenance_datafile2 is not None:
        if status_callback:
            status_callback(
                f"[green][✓] Provenance for datafile2 found : {provenance_datafile2}[/green]"
            )
        logger.info(
            f"[green][✓] Provenance for datafile2 found : {provenance_datafile2}[/green]"
        )

    summary = UploadSummary()
    # IMPORT DATAFILE 1
    corr_data = parse_excel_for_metadata(
        df_data, dict_datafile1, provenance_datafile1, "datafile1", timezone_exp
    )
    if status_callback:
        status_callback("[green][✓] datafile1 data parsing OK [/green]")
    logger.info("[green][✓] datafile1 data parsing OK [/green]")
    existing_datafile1_keys = get_existing_datafiles(
        dat_api, provenance_datafile1, exp_uri
    )
    if status_callback:
        status_callback("[green][✓] Search for existing datafiles1 OK [/green]")
    logger.info("[green][✓] Search for existing datafiles1 OK [/green]")

    # Meme conversion que précédemment ça devrait fonctionner du coup
    corr_to_upload = [
        img
        for img in corr_data.values()
        if (
            sci_obj_uri[img["Plant ID"]],
            img["Date"][:-5] + ".000" + img["Date"][-5:],
            str(img.get("Angle")) if pd.notna(img.get("Angle")) else None,
            str(img.get("Round Order")) if pd.notna(img.get("Round Order")) else None,
        )
        not in existing_datafile1_keys
    ]
    summary.skipped += len(corr_data) - len(corr_to_upload)

    # # ####TEST :
    # toutes_datafile1_triees = sorted(corr_data.values(), key=lambda x: x["Path"])

    # # On isole les 5 premières pour le test
    # datafile1_test_subset = toutes_datafile1_triees[1210:1215]

    # corr_to_upload = [
    #     img for img in corr_data.values()
    #     if (
    #         sci_obj_uri[img["Plant ID"]],
    #         img["Date"][:-5] + ".000" + img["Date"][-5:],
    #         str(img.get("Angle")) if pd.notna(img.get("Angle")) else None,
    #         str(img.get("Round Order")) if pd.notna(img.get("Round Order")) else None
    #     ) not in existing_datafile1_keys
    # ]
    # # ###TEST

    if status_callback:
        status_callback(
            f"[bold green]{len(corr_data) - len(corr_to_upload)}[cyan] Datafiles1 exists on [bold green]{len(corr_data)}[/bold green] total [/cyan]"
        )
    logger.info(
        f"[bold green]{len(corr_data) - len(corr_to_upload)}[cyan] Datafiles1 exists on [bold green]{len(corr_data)}[/bold green] total [/cyan]"
    )

    timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)

    def process_datafile1(img):
        check_cancelled(should_cancel)
        path_or_post = 0
        round_order = img.get("Round Order")
        cam_pos_round = cam_pos.get(round_order, {})
        settings_dict = {}
        if img.get("Angle") is not None:
            settings_dict["Camera Angle"] = img.get("Angle")
        if cam_pos_round.get("height") is not None:
            settings_dict["Camera Height"] = cam_pos_round.get("height")
        if cam_pos_round.get("Offset") is not None:
            settings_dict["Offset"] = cam_pos_round.get("Offset")

        desc = {
            "rdf_type": f"vocabulary:{rdf_type_1}",
            "date": img["Date"],
            "target": sci_obj_uri[img["Plant ID"]],
            "metadata": {
                "Round Order": round_order,
                "Imported with": f"SIMPLE {__version__}",
            },
            "provenance": {
                "uri": img["Prov"],
                "settings": settings_dict,
                "experiments": [exp_uri],
            },
        }
        if path_or_post == 1:
            with_retry(
                lambda: dat_api.post_data_file_paths(
                    body=[
                        silex.DataFilePathCreationDTO(
                            rdf_type=f"vocabulary:{rdf_type_1}",
                            _date=img["Date"],
                            target=sci_obj_uri[img["Plant ID"]],
                            metadata={
                                "Round Order": round_order,
                                "Imported with": f"SIMPLE {__version__}",
                            },
                            provenance={
                                "uri": img["Prov"],
                                "settings": settings_dict,
                                "experiments": [exp_uri],
                            },
                            relative_path="datafile/" + os.path.basename(img["Path"]),
                        )
                    ]
                )
            )
        else:
            with_retry(
                lambda: dat_api.post_data_file(
                    description=json.dumps(desc), file=img["Path"]
                )
            )

    datafile1_task_name = "[bold blue]Uploading datafiles 1...[/bold blue]"
    if progress_callback and len(corr_to_upload) > 0:
        progress_callback(datafile1_task_name, total=len(corr_to_upload))

    check_cancelled(should_cancel)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(process_datafile1, img): img for img in corr_to_upload
        }
        for future in concurrent.futures.as_completed(futures):
            if datetime.datetime.now() > timelimit:
                connect(login, api_client)
                timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)

            try:
                future.result()
                summary.created += 1
            except ImportCancelled:
                for pending in futures:
                    pending.cancel()
                raise
            except DATAFILE_UPLOAD_ERRORS as e:
                summary.failed += 1
                summary.failed_items.append(futures[future]["Path"])
                logger.error(f"failed to upload image :{e} ")
                if status_callback:
                    status_callback(
                        "[bold yellow] [!] A datafile failed to upload, please check the logs for informations, continuing...[/bold yellow]"
                    )
            if progress_callback:
                progress_callback(datafile1_task_name, advance=1)

    if len(corr_to_upload) > 0:
        if status_callback:
            status_callback(
                f"[green][✓] Datafile1 upload complete! : {len(corr_to_upload)} uploads! [/green]"
            )
            logger.info(
                f"[green][✓] Datafile1 upload complete! {len(corr_to_upload)} uploads![/green]"
            )
    else:
        if status_callback:
            status_callback(
                "[green][✓] All Datafiles 1 were already uploaded (or there was no datafiles1)[/green]"
            )
        logger.info(
            "[green][✓] All Datafiles 1 were already uploaded (or there was no datafiles1) [/green]"
        )

    # IMPORT DATAFILE 2 (OPTIONNEL)
    if has_datafile2 and provenance_datafile2:
        datafile1_uri_map = {
            (elts.target, elts._date): elts.uri
            for elts in dat_api.get_data_file_descriptions_by_search(
                provenances=[provenance_datafile1],
                experiments=[exp_uri],
                page_size=100000,
            )["result"]
        }

        mask_data = parse_excel_for_metadata(
            df_data, dict_datafile2, provenance_datafile2, "datafile2", timezone_exp
        )
        if status_callback:
            status_callback("[green][✓] datafile2 data parsing OK [/green]")
        logger.info("[green][✓] datafile2 data parsing OK [/green]")

        for img in mask_data.values():
            target = sci_obj_uri[img["Plant ID"]]
            date = img["Date"].replace("+", ".000+")
            found_uri = datafile1_uri_map.get((target, date))
            img["Prov_Used"] = found_uri

        existing_datafile2_keys = get_existing_datafiles(
            dat_api, provenance_datafile2, exp_uri
        )
        if status_callback:
            status_callback("[green][✓] Search for existing datafiles2 OK [/green]")
        logger.info("[green][✓] Search for existing datafiles2 OK [/green]")

        mask_to_upload = [
            img
            for img in mask_data.values()
            if (
                sci_obj_uri[img["Plant ID"]],
                img["Date"][:-5] + ".000" + img["Date"][-5:],
                str(img.get("Angle")) if pd.notna(img.get("Angle")) else None,
                str(img.get("Round Order"))
                if pd.notna(img.get("Round Order"))
                else None,
            )
            not in existing_datafile2_keys
        ]

        summary.skipped += len(mask_data) - len(mask_to_upload)
        # # # TEST TEST TEST
        # toutes_datafile2_triees = sorted(mask_data.values(), key=lambda x: x["Path"])

        # datafile2_test_subset = toutes_datafile2_triees[1210:1215]

        # mask_to_upload = [
        #     img for img in mask_data.values()
        #     if (
        #         sci_obj_uri[img["Plant ID"]],
        #         img["Date"][:-5] + ".000" + img["Date"][-5:],
        #         str(img.get("Angle")) if pd.notna(img.get("Angle")) else None,
        #         str(img.get("Round Order")) if pd.notna(img.get("Round Order")) else None
        #     ) not in existing_datafile2_keys
        # ]
        #  # # TEST TEST TEST

        if status_callback:
            status_callback(
                f"[bold green]{len(mask_data) - len(mask_to_upload)} [cyan]Datafiles2 exists on[/cyan] {len(mask_data)}[cyan] total[/bold green]"
            )
        logger.info(
            f"[bold green]{len(mask_data) - len(mask_to_upload)} [cyan]Datafiles2 exists on[/cyan] {len(mask_data)}[cyan] total[/bold green]"
        )

        def process_datafile2(img):
            check_cancelled(should_cancel)
            round_order = img.get("Round Order")
            settings = {"Camera Angle": img.get("Angle")}
            if round_order in plant_mask:
                settings.update(plant_mask[round_order])

            desc = {
                "rdf_type": f"vocabulary:{rdf_type_2}",
                "date": img["Date"],
                "target": sci_obj_uri[img["Plant ID"]],
                "metadata": {
                    "Round Order": round_order,
                    "Imported with": f"SIMPLE {__version__}",
                },
                "provenance": {
                    "uri": img["Prov"],
                    "prov_used": [
                        {
                            "uri": img["Prov_Used"],
                            "rdf_type": f"vocabulary:{rdf_type_1}",
                        }
                    ]
                    if img.get("Prov_Used")
                    else [],
                    "settings": settings,
                    "experiments": [exp_uri],
                },
            }
            with_retry(
                lambda: dat_api.post_data_file(
                    description=json.dumps(desc), file=img["Path"]
                )
            )

        datafile2_task_name = "[bold blue]Uploading datafiles 2...[/bold blue]"

        if progress_callback and len(mask_to_upload) > 0:
            progress_callback(datafile2_task_name, total=len(mask_to_upload))

        check_cancelled(should_cancel)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(process_datafile2, img): img for img in mask_to_upload
            }
            for future in concurrent.futures.as_completed(futures):
                if datetime.datetime.now() > timelimit:
                    connect(login, api_client)
                    timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)
                try:
                    future.result()
                    summary.created += 1
                except ImportCancelled:
                    for pending in futures:
                        pending.cancel()
                    raise
                except DATAFILE_UPLOAD_ERRORS as e:
                    summary.failed += 1
                    summary.failed_items.append(futures[future]["Path"])
                    logger.error(f"failed to upload image :{e} ")
                    if status_callback:
                        status_callback(
                            "[bold yellow] [!] A datafile failed to upload, please check the logs for informations, continuing...[/bold yellow]"
                        )

                if progress_callback:
                    progress_callback(datafile2_task_name, advance=1)

        if len(mask_to_upload) > 0:
            if status_callback:
                status_callback(
                    f"[green][✓] Datafile 2 upload complete! : {len(mask_to_upload)} uploads! [/green]"
                )
                logger.info(
                    f"[green][✓] Datafile 2 upload complete! {len(mask_to_upload)} uploads![/green]"
                )
        else:
            if status_callback:
                status_callback(
                    "[green][✓] All Datafiles 2 were already uploaded (or there was no datafiles2)[/green]"
                )
            logger.info(
                "[green][✓] All Datafiles 2 were already uploaded (or there was no datafiles2) [/green]"
            )
    logger.info(f"Datafiles import complete: {summary.describe()}")
    return summary
