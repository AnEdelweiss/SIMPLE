import ast
import datetime
import os

import opensilexClientToolsPython as silex
import pandas as pd
import urllib3

from simple.__init__ import __version__
from simple.auth import connect
from simple.errors import DataImportError
from simple.logging_setup import logger
from simple.upload import RETRYABLE_ERRORS, UploadSummary, with_retry


def format_timestamps(series, timezone="UTC"):
    """Parse a timestamp column into "%Y-%m-%dT%H:%M:%S%z" strings in `timezone`.

    ``format="ISO8601"`` + ``utc=True`` normalises every shape the two import
    paths can meet — ISO-8601 with an offset, ISO-8601 without one, or
    "YYYY-MM-DD HH:MM:SS" — to a tz-aware UTC index, converted a single time.
    """
    desired_format = "%Y-%m-%dT%H:%M:%S%z"
    return (
        pd.to_datetime(series, format="ISO8601", utc=True)
        .dt.tz_convert(timezone)
        .dt.strftime(desired_format)
    )


def get_name_space(api_client):
    ontology_api = silex.OntologyApi(api_client)
    instance_uri = ontology_api.get_base_uri()["result"]
    name_space_dict = ast.literal_eval(ontology_api.get_name_space()["result"])
    name_space = str(
        [key for key, value in name_space_dict.items() if value == instance_uri]
    )
    name_space_clean = (
        name_space.replace("'", "").replace("[", "").replace("]", "") + ":"
    )
    logger.info(
        f"Name Space is : {name_space_clean} & instance uri is : {instance_uri}"
    )
    return name_space_clean, instance_uri


def create_factor(miappe_path, api_client):
    # getting experiment name
    dataframe = pd.read_excel(miappe_path, sheet_name="experiment", header=1)
    dataframe.drop(
        dataframe.columns[dataframe.columns.str.contains("unnamed", case=False)],
        axis=1,
        inplace=True,
    )
    name_exp = dataframe["name"].dropna().iloc[0]
    # getting factors
    dataframe = pd.read_excel(miappe_path, sheet_name="factors", header=1)
    dataframe.drop(
        dataframe.columns[dataframe.columns.str.contains("unnamed", case=False)],
        axis=1,
        inplace=True,
    )
    factor_api = silex.FactorsApi(api_client)
    factors_uri = {}
    factors_levels_uri = {}

    exp_api = silex.ExperimentsApi(api_client)
    exp_search = exp_api.search_experiments(name=name_exp)["result"]
    name_exp_uri = {name_exp: exp_search[0].uri}
    experiment_name, experiment_uri = next(iter(name_exp_uri.items()))
    logger.info(f"You are working on experiment : {experiment_name} URI :{experiment_uri} ")
    factors_data = {}

    for row in list(dataframe.to_dict("records")):
        factor = str(row["name"]).strip() if pd.notna(row["name"]) else ""
        factor_level = str(row["levels"]).strip() if pd.notna(row["levels"]) else None
        description_factor = (
            row["description"] if pd.notna(row["description"]) else None
        )
        description_level = (
            row["factor_level_desc"] if pd.notna(row["factor_level_desc"]) else None
        )

        if factor not in factors_data:
            factors_data[factor] = {"description": description_factor, "levels": []}

        if factor_level:
            factors_data[factor]["levels"].append(
                {"name": factor_level, "description": description_level}
            )

    for factor_name, factor_data in factors_data.items():
        factor_search = factor_api.search_factors(
            name=factor_name, experiment=name_exp_uri[name_exp]
        )["result"]

        if factor_search:
            factors_uri[factor_name] = factor_search[0].uri
        else:
            DTO_list = [
                silex.FactorLevelCreationDTO(
                    name=lvl["name"], description=lvl["description"]
                )
                for lvl in factor_data["levels"]
            ]

            body = silex.FactorCreationDTO(
                name=factor_name,
                levels=DTO_list,
                experiment=name_exp_uri[name_exp],
                description=factor_data["description"],
            )
            factor_api.create_factor(body=body)
            factor_search = factor_api.search_factors(
                name=factor_name, experiment=name_exp_uri[name_exp]
            )["result"]
            factors_uri[factor_name] = factor_search[0].uri

    for fac_name,fac_uri in factors_uri.items():
        fac_get = factor_api.get_factor_levels(uri=fac_uri)["result"]
        logger.info(f"Level : {fac_name}")
        for lvl in fac_get:
            factors_levels_uri[lvl.name] = lvl.uri
            logger.info(f"Factor level : {lvl.name}")

    logger.info("Factors have been found/created with sucess.")
    return factors_levels_uri, factors_uri


def create_germplasm(miappe_path, api_client):

    dataframe = pd.read_excel(miappe_path, sheet_name="germplasm", header=1)
    dataframe.drop(
        dataframe.columns[dataframe.columns.str.contains("unnamed", case=False)],
        axis=1,
        inplace=True,
    )
    germplasm_api = silex.GermplasmApi(api_client)
    species_uri = {}
    germplasms_uri = {}
    # on evite les problèmes de lignes vides ou fantome jsp frr
    dataframe = dataframe.dropna(subset=["name"])
    dataframe = dataframe.replace({float("nan"): None})

    for row in list(dataframe.to_dict("records")):
        germ_name = row["name"]
        germ_species = row.get("species")
        rdf_type = str(row["rdf_type"])

        if germ_name not in germplasms_uri:
            try:
                # On verifie l'existence de l'éspèce si on est sur une ligne Variété
                if germ_species not in species_uri and rdf_type != "vocabulary:Species":
                    spec_src = germplasm_api.search_germplasm(
                        name=f"^{germ_species}$", rdf_type="vocabulary:Species"
                    )["result"]
                    if not spec_src:
                        logger.error(
                            f"The species {germ_species} associated with {germ_name} was not found... Please declare species before varieties and check for typos in the Miappe"
                        )
                        raise DataImportError(
                            f"[bold red]\nPlease check if the species you associated with [cyan]{germ_name}[/cyan] in the miappe template is correct \n Tip : You have to declare all the species before the varieties"
                        )
                    species_uri[germ_species] = spec_src[0].uri
                # On check si notre variété/espèce existe, et si elle existe batch_size on la crée
                germ_search = germplasm_api.search_germplasm(
                    name=f"^{germ_name}$", rdf_type=rdf_type
                )["result"]
                if not germ_search:
                    row.pop("species", None)
                    if rdf_type != "vocabulary:Species":
                        row["species"] = species_uri[germ_species]
                    row["metadata"] = {"Imported with": f"SIMPLE {__version__}"}
                    body = silex.GermplasmCreationDTO(**row)
                    germplasm_api.create_germplasm(body=body, check_only=False)
                    germ_search = germplasm_api.search_germplasm(
                        name=f"^{germ_name}$", rdf_type=rdf_type
                    )["result"]
                    logger.info(f"Germplasm : {germ_name} created with URI : {germ_search[0].uri}")
                else:
                    logger.info(f"Germplasm : {germ_name} found with URI : {germ_search[0].uri}")
                germplasms_uri[germ_name] = germ_search[0].uri
            except (
                silex.rest.ApiException,
                urllib3.exceptions.HTTPError,
                OSError,
                KeyError,
                IndexError,
                AttributeError,
                ValueError,
                TypeError,
                DataImportError,
            ) as e:
                # DataImportError is listed because the missing-species error
                # raised a few lines above was historically caught and
                # re-wrapped by this block; keep that message behaviour.
                logger.error(f"Creation of germplasm : '{germ_name}' Failed this may be caused by a duplicate uri, please check the MIAPPE 'germplasm' sheet, more infos in logs")
                logger.debug(e)
                raise DataImportError("Error during germplasm import")

    logger.info("All germplasms have been found/created with sucess.")
    return germplasms_uri, species_uri


def create_sci_obj(
    data_path, miappe_path, api_client, status_callback=None
):
    # Récupération du excel page experiment
    dataframe = pd.read_excel(miappe_path, sheet_name="experiment", header=1)
    dataframe.drop(
        dataframe.columns[dataframe.columns.str.contains("unnamed", case=False)],
        axis=1,
        inplace=True,
    )
    if "start_date" in dataframe.columns:
        dataframe["start_date"] = pd.to_datetime(dataframe["start_date"]).dt.strftime("%Y-%m-%d")
    if "end_date" in dataframe.columns:
        dataframe["end_date"] = pd.to_datetime(dataframe["end_date"]).dt.strftime("%Y-%m-%d")

    records = dataframe.where(pd.notnull(dataframe), None).to_dict("records")
    row = records[0] if records else {}

    name_exp = row.get("name")
    start_exp = row.get("start_date")
    end_exp = row.get("end_date")
    
    bio_mat_raw = row.get("scientific_object_type")
    bio_mat_type = [x.strip() for x in str(bio_mat_raw).split(",")] if bio_mat_raw else []

    df_factors = pd.read_excel(miappe_path, sheet_name="factors", header=1)
    df_factors.drop(
        df_factors.columns[df_factors.columns.str.contains("unnamed", case=False)],
        axis=1,
        inplace=True,
    )
    # Extract unique factor names as a list
    factors = df_factors["name"].dropna().astype(str).str.strip().unique().tolist()

    # Ici on récupère les données tabulaires pour créer les objets scientifiques.
    df_data = pd.read_excel(data_path)
    # on garde seulement les Plant ID uniques
    df_sci_obj = df_data.drop_duplicates(subset=["Plant ID"])
    general_relations = []

    # on cherche si l'expérience éxiste pour en extraire l'uri
    exp_search = silex.ExperimentsApi(api_client).search_experiments(
        name=name_exp
    )
    results = exp_search.get("result", [])
    if not results:
        logger.error(
            f"Experiment {name_exp} was not found, check if the name is correct or create the experiment before scientific objects"
        )
        raise DataImportError(
            f"[bold red]This experiment doesn't exist, please check if the name is correct : {name_exp}[/bold red]"
        )
    name_exp_uri = {name_exp: results[0].uri}
    experiment_name, experiment_uri = next(iter(name_exp_uri.items()))
    logger.info(f"You are working on experiment : {experiment_name} URI :{experiment_uri} ")
    # Récupérer un dictionary de facteurs levels pour cette experience
    api_response = silex.ExperimentsApi(api_client).get_available_factors(
        exp_search["result"][0].uri
    )
    if api_response["result"]:
        factors_levels_uri = {}
        for factor_result in api_response["result"]:
            for factor_level in factor_result.levels:
                factors_levels_uri[factor_level.name] = factor_level.uri
    else:
        factors_levels_uri, _ = create_factor(miappe_path, api_client)

    # création des relations
    if start_exp:
        relation_temp = silex.RDFObjectRelationDTO(
            _property="vocabulary:hasCreationDate", value=start_exp
        )
        general_relations.append(relation_temp)
    else:
        logger.warning("Start Date Missing")

    if end_exp:
        relation_temp = silex.RDFObjectRelationDTO(
            _property="vocabulary:hasDestructionDate", value=end_exp
        )
        general_relations.append(relation_temp)
    else:
        logger.warning("End Date Missing")

    if not bio_mat_type:
        logger.error(
            "The column 'Scientific Object RDF Type' in the 'Experiment sheet' is empty"
        )
        raise DataImportError("Scientific Object RDF Type Missing")
    else:
        for biomat in bio_mat_type:
            ontology_api = silex.OntologyApi(api_client)
            ontology_search = ontology_api.search_sub_classes_of(
                name=biomat, parent_type="vocabulary:ScientificObject"
            )["result"]
            if ontology_search:
                rdf_type = ontology_search[0].children[0].uri
            else:
                logger.error(f"Scientific Object RDF Type Unknown: {biomat}")
                raise DataImportError(f"Scientific Object RDF Type Unknown: {biomat}")

    sci_obj_api = silex.ScientificObjectsApi(api_client)
    sci_obj_uri = {}
    dtos_to_export = []
    germplasm_cache = {}
    created_sci_obj = 0
    base_uri_namespace, base_uri = get_name_space(api_client)
    # JE RECUPERE TOUS LES OBJETS SCIENTIFIQUES LIES A L'EXPERIENCE
    # JE LES METS DANS UN DICTIONNAIRE ET JE VERIFIE CHAQUE Plant ID AVEC LE NOM DANS LE DICTIONNAIRE
    all_existing_objs = sci_obj_api.search_scientific_objects(
        experiment=name_exp_uri[name_exp], page_size=10000
    )["result"]
    sci_obj_cache = {obj.name: obj.uri for obj in all_existing_objs}
    # on envoie pour chaque ligne de la df scobj(sans les duplicatas)
    for row in list(df_sci_obj.to_dict("records")):
        plant_id = row["Plant ID"]
        if plant_id in sci_obj_cache:
            sci_obj_uri.update({plant_id: sci_obj_cache[plant_id]})
        else:
            sci_obj_relations = []
            all_factors = []
            germplasm_value = None
            # ici on à la logique de vérification des germplasmes dans les objets scientifiques, on vérifie si il est dans la liste des germplasmes connus, et si oui on prends son uri
            germ_name = row.get("Germplasm")
            if pd.notna(germ_name) and germ_name:
                if germ_name not in germplasm_cache:
                    germ_search = silex.GermplasmApi(api_client).search_germplasm(
                        name=f"^{germ_name}$"
                    )["result"]
                    if germ_search:
                        germplasm_cache[germ_name] = germ_search[0].uri
                        germplasm_value = germplasm_cache[germ_name]
                        relation_temp = silex.RDFObjectRelationDTO(
                            _property="vocabulary:hasGermplasm", value=germplasm_value
                        )
                        sci_obj_relations.append(relation_temp)
                        logger.info(f"Germplasm {germ_name} found")
                    else:
                        logger.error(f"Germplasm {germ_name} cannot be found.")
                        raise DataImportError(
                            f"[bold red] Germplasm [cyan]{germ_name}[/cyan] cannot be found, please check for typos or if they exist.[/bold red]"
                        )
                else:
                    germplasm_value = germplasm_cache[germ_name]
                    relation_temp = silex.RDFObjectRelationDTO(
                        _property="vocabulary:hasGermplasm", value=germplasm_value
                    )
                    sci_obj_relations.append(relation_temp)
            # on récupère les uri des niveaux de facteur
            for one_factor in factors:
                if one_factor in row and pd.notna(row[one_factor]):
                    factor_level = str(row[one_factor]).strip()
                    if factor_level and factors_levels_uri is not None:
                        if factor_level not in factors_levels_uri:
                            logger.warning(
                                "The factor level was not found. Starting factor import from the MIAPPE document"
                            )
                            factors_levels_uri, _ = create_factor(
                                miappe_path, api_client
                            )

                            if factor_level not in factors_levels_uri:
                                logger.error(
                                    f"This factor level : {factor_level} cannot be found."
                                )
                                raise DataImportError(
                                    f"[bold red] This factor level : [cyan]{factor_level}[/cyan] cannot be found, please check for typos or if they really exist.[/bold red]"
                                )

                        factor_level_value = factors_levels_uri.get(factor_level)
                        all_factors.append(factor_level_value)
                        relation_temp = silex.RDFObjectRelationDTO(
                            _property="vocabulary:hasFactorLevel",
                            value=factor_level_value,
                        )
                        sci_obj_relations.append(relation_temp)
                else:
                    logger.error(
                        f"No column with the name : {one_factor} can be found in your tabular data file."
                    )
                    raise DataImportError(
                        f"[bold red] This factor cannot be found in the tabular data file : [cyan]{one_factor}[/cyan]\nPlease check for typos in your tabular data or if the column really has the name you declared in the 'factor' sheet of the MIAPPE file.[/bold red]"
                    )
            # on concatène les infos générales et les uri des germplasmes/facteurs puis on envoie le body et on le stock dans un dictionary
            relations = general_relations + sci_obj_relations
            body = silex.ScientificObjectCreationDTO(
                name=row["Plant ID"],
                rdf_type=rdf_type,
                relations=relations,
                experiment=name_exp_uri[name_exp],
            )
            api_resp = sci_obj_api.create_scientific_object(body)
            url_api = api_resp["result"][0]
            ##ATTENTION NE FONCTIONNE QUE SUR LA SANDBOX, DEMANDER A OPENSILEX POUR RENVOYER L'URI DANS L'API
            sci_obj_search = url_api.replace(base_uri, base_uri_namespace)
            sci_obj_uri.update({row["Plant ID"]: sci_obj_search})
            sci_obj_cache[row["Plant ID"]] = sci_obj_search
            # Ici je stock les données qui m'interessent dans le dto d'avant dans un dictionary, que j'écris après dans le excel
            dtos_to_export.append(
                {
                    "studyId": body.experiment,
                    "obsUnitType": body.rdf_type,
                    "obsUnitId": sci_obj_search,
                    "externalId": body.name,
                    "biologicalMaterialId": germplasm_value
                    if germplasm_value
                    else None,
                    "obsUnitFactorValue": all_factors if all_factors else None,
                    "Date Import": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                }
            )
            created_sci_obj += 1

            if status_callback and (
                created_sci_obj % 50 == 0 or created_sci_obj == len(df_sci_obj)
            ):
                # Plain text: the CLI/GUI adds its own prefix and colours.
                status_callback(
                    f"{created_sci_obj} scientific objects created on {len(df_sci_obj)} total."
                )
    # écriture des metadata des objets scientifiques sur le excel
    if dtos_to_export:
        parent_folder = os.path.dirname(data_path)
        excel_path = os.path.join(
            parent_folder, "output", "miappe_template_filled.xlsx"
        )
        os.makedirs(os.path.dirname(excel_path), exist_ok=True)
        export_df = pd.DataFrame(dtos_to_export)
        if os.path.exists(excel_path):
            previous_df = pd.read_excel(excel_path, sheet_name="Observation Unit")
            final_df = pd.concat([previous_df, export_df])
            with pd.ExcelWriter(
                excel_path, engine="openpyxl", mode="a", if_sheet_exists="replace"
            ) as writer:
                final_df.to_excel(writer, sheet_name="Observation Unit", index=False)
        else:
            # First run: there is no workbook to append to yet, so create one.
            with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                export_df.to_excel(writer, sheet_name="Observation Unit", index=False)
        logger.info("The scientific object sheet was successfully created/edited.")
    return sci_obj_uri, created_sci_obj


def find_datafile_config(datafile_provenance, data_path):
    """Return the 'data file' sheet row matching *data_path*, if any.

    The same suffix lookup was repeated in get_provenances, create_data and
    the datafile uploader; keeping it in one place makes the offline dry run
    able to reuse it too.
    """
    datafile_name = os.path.basename(data_path)
    for suffix, config in datafile_provenance.items():
        if datafile_name == suffix:
            return config
    return None


def get_provenances(
    data_path, miappe_path, api_client, create_default=False
):

    data_api = silex.DataApi(api_client)
    dataframe1 = pd.read_excel(miappe_path, sheet_name="data file", header=1)
    dataframe1.drop(
        dataframe1.columns[dataframe1.columns.str.contains("unnamed", case=False)],
        axis=1,
        inplace=True,
    )
    dataframe1.columns = dataframe1.columns.str.strip()

    datafile_provenance = {}
    for row in dataframe1.to_dict("records"):
        datafile_provenance.update(
            {
                row.get("dataFileLink"): {
                    "prov_morpho_parameters": row.get("Tabular Data Provenance"),
                    "prov_datafiles1": row.get("Datafiles1 Provenance"),
                    "rdf_type_datafile1": row.get("datafile1_rdf_type"),
                    "prov_datafiles2": row.get("Datafiles2 Provenance"),
                    "rdf_type_datafile2": row.get("datafile2_rdf_type"),
                }
            }
        )

    prov_dict = {}
    missing_prov = []
    config = find_datafile_config(datafile_provenance, data_path)
    if config is not None:
        for prov_name in config.values():
            if (
                pd.isna(prov_name)
                or prov_name == "RGBImage"
                or prov_name == "Archive"
            ):
                continue

            prov_src = data_api.search_provenance(name=prov_name)["result"]
            if prov_src:
                prov_dict[prov_name] = prov_src[0].uri
                logger.info(
                    f"Provenance found : {prov_name} URI: {prov_src[0].uri}"
                )
            else:
                # Création par default si la provenance n'a batch_size été crée manuellement
                if not create_default:
                    missing_prov.append(prov_name)
                else:
                    logger.info(f"Creating default provenance : {prov_name}")
                    body = silex.ProvenanceCreationDTO(
                        name=prov_name,
                        description="This provenance was created by default using SIMPLE. You may want to add agents, activities etc...",
                        prov_agent=[],
                        prov_activity=[],
                    )

                    data_api.create_provenance(body=body)
                    prov_src = data_api.search_provenance(name=prov_name)["result"]
                    prov_dict[prov_name] = prov_src[0].uri

    return prov_dict, datafile_provenance, missing_prov


def data_mapping(data_path, miappe_path):
    df_data = pd.read_excel(data_path)
    dataframe = pd.read_excel(
        miappe_path, sheet_name="mapping_table_variables", header=0
    )

    morpho_info = {
        row["column_in_data_table"]: row["opensilex_variable_name"]
        for row in dataframe.to_dict("records")
    }
    morpho_info = {k: v for k, v in morpho_info.items() if k in df_data.columns}

    return morpho_info


def create_data(
    data_path,
    miappe_path,
    login,
    api_client,
    morpho_info,
    prov_dict,
    datafile_provenance,
    sci_obj_uri,
    upload_progress=None,
):

    dataframe = pd.read_excel(miappe_path, sheet_name="experiment", header=1)
    name_exp = dataframe["name"].dropna().iloc[0]
    exp_search = silex.ExperimentsApi(api_client).search_experiments(
        name=name_exp
    )
    name_exp_uri = {name_exp: exp_search["result"][0].uri}
    logger.info(name_exp_uri)
    # Gestion provenances
    provenance_morpho = None
    provenance_datafile1 = None
    provenance_datafile2 = None
    rdf_type_2 = None
    rdf_type_1 = None
    config = find_datafile_config(datafile_provenance, data_path)
    if config is not None:
        provenance_morpho = (
            config.get("prov_morpho_parameters")
            if not pd.isna(config.get("prov_morpho_parameters"))
            else None
        )
        provenance_datafile1 = (
            config.get("prov_datafiles1")
            if not pd.isna(config.get("prov_datafiles1"))
            else None
        )
        rdf1 = config.get("rdf_type_datafile1")
        rdf_type_1 = rdf1 if not pd.isna(rdf1) else None
        provenance_datafile2 = (
            config.get("prov_datafiles2")
            if not pd.isna(config.get("prov_datafiles2"))
            else None
        )
        rdf2 = config.get("rdf_type_datafile2")
        rdf_type_2 = rdf2 if not pd.isna(rdf2) else None

    # FORMATAGE DONNÉES
    if (
        "experiment_timezone" in dataframe.columns
        and not dataframe["experiment_timezone"].dropna().empty
    ):
        timezone_exp = dataframe["experiment_timezone"].dropna().iloc[0]
    else:
        timezone_exp = "UTC"
    df_data = pd.read_excel(data_path)

    # ON RECUPERE LE TEMPS DANS TIMESTAMP ET ON CONVERTI EVENTUELLEMENT
    df_data["Measuring Time"] = format_timestamps(df_data["timestamp"], timezone_exp)

    if "Angle" not in df_data.columns:
        df_data["Angle"] = None
    if "Round Order" not in df_data.columns:
        df_data["Round Order"] = None

    # ON TENTE DE RECUPERE LES DONNÉES DES DATAFILES QU'ON A UPLOAD PRECEDEMMENT SI DATAFILE IL Y A
    prov = (
        provenance_datafile2
        if provenance_datafile2 is not None
        else provenance_datafile1
    )
    rdf_type = rdf_type_2 if rdf_type_2 is not None else rdf_type_1
    mask_uri = []
    data_api = silex.DataApi(api_client)

    if prov is not None:
        data_search = data_api.get_data_file_descriptions_by_search(
            provenances=[prov_dict[prov]],
            experiments=[name_exp_uri[name_exp]],
            page_size=200000,
        )["result"]

        uri_to_trayid = {v: k for k, v in sci_obj_uri.items()}

        for elts in data_search:
            trayid = uri_to_trayid.get(elts.target)

            if trayid:  # on ajoute seulement si la cible est trouvée
                mask_uri.append(
                    {
                        "Type": "FEM",
                        "Target": elts.target,
                        "Plant ID": trayid,
                        "Date": elts._date,
                        "Round Order": elts.metadata.get("Round Order")
                        if elts.metadata
                        else None,
                        "Angle": elts.provenance.settings.get("Camera Angle")
                        if elts.provenance.settings
                        else None,
                        "uri": elts.uri,
                    }
                )

    # Connexion toutes les 30 mins pour éviter les éventuels kick, mais très peu probable quand même vu la vitesse d'execution :p
    connect(login, api_client)
    timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)
    variables_api = silex.VariablesApi(api_client)
    # On recupère en une fois toutes les données tabulaires existantes pour la variable
    logfile = {}
    summary = UploadSummary()
    for key, value in morpho_info.items():
        logfile[value] = []
        column_name = key
        variable_search = variables_api.search_variables(name=value)["result"]
        all_existing_data = data_api.search_data_list(
            variables=[variable_search[0].uri],
            experiments=[name_exp_uri[name_exp]],
            page_size=200000,
        )["result"]
        existing_data_cache = set()
        if all_existing_data:
            for data in all_existing_data:
                round_order = (
                    data.metadata.get("Round Order") if data.metadata else None
                )
                existing_data_cache.add((data.target, data._date, round_order))
        # GET/CREATE NUMERICAL DATA
        batch_size = 4000
        for slc in range(0, len(df_data), batch_size):
            df_slice = df_data.iloc[slc : slc + batch_size]
            bodies = []
            for row in df_slice.to_dict("records"):
                target_uri = sci_obj_uri[row["Plant ID"]]
                formatted_date = str(row["Measuring Time"]).replace("+", ".000+")
                round_order_val = (
                    row.get("Round Order") if pd.notna(row.get("Round Order")) else None
                )

                # VERIFICATION DE L'EXISTENCE DES DONNÉES EN MÉMOIRE
                if (target_uri, formatted_date, round_order_val) in existing_data_cache:
                    summary.skipped += 1
                    logfile[value].append(
                        {
                            "Angle": row.get("Angle"),
                            "Plant ID": {row["Plant ID"]},
                            "Round Order": {row.get("Round Order")},
                        }
                    )
                else:
                    provenance_used = None
                    setting_dict = {"Camera Angle": row["Angle"]}
                    if (
                        "Datafile1_Filename" in df_data.columns
                        or "Datafile2_Filename" in df_data.columns
                    ):
                        for item in mask_uri:
                            if item["Plant ID"] == row["Plant ID"] and item[
                                "Date"
                            ] == row["Measuring Time"].replace("+", ".000+"):
                                provenance_used = silex.ProvEntityModel(
                                    uri=item["uri"], rdf_type=f"vocabulary:{rdf_type}"
                                )
                                break
                    if pd.notna(row[key]):
                        body = silex.DataCreationDTO(
                            _date=str(row["Measuring Time"]),
                            target=sci_obj_uri[row["Plant ID"]],
                            variable=variable_search[0].uri,
                            value=row[key],
                            metadata={
                                "Round Order": row.get("Round Order"),
                                "Nom Colonne": column_name,
                                "Imported with": f"SIMPLE {__version__}",
                            },
                            provenance=silex.DataProvenanceModel(
                                uri=prov_dict[provenance_morpho],
                                prov_used=[provenance_used] if provenance_used else [],
                                settings=setting_dict,
                                experiments=[name_exp_uri[name_exp]],
                            ),
                        )
                        bodies.append(body)
                    if datetime.datetime.now() > timelimit:
                        connect(login, api_client)

                        data_api = silex.DataApi(api_client)
                        timelimit = datetime.datetime.now() + datetime.timedelta(
                            minutes=30
                        )
            if bodies:
                try:
                    with_retry(lambda: data_api.add_list_data(body=bodies))
                except RETRYABLE_ERRORS as exc:
                    logger.error(
                        f"{len(bodies)} lines of data from {value} failed after retries: {exc}"
                    )
                    summary.failed += len(bodies)
                    summary.failed_items.append(
                        f"{value} batch starting at row {slc}"
                    )
                    continue
                summary.created += len(bodies)
                logger.info(
                    f"{len(bodies)} lines of data from {value} were sucessfully uploaded."
                )
                if upload_progress:
                    upload_progress(value, len(bodies))
            else:
                logger.info(f"all data for {value} was already uploaded")
                if upload_progress:
                    upload_progress(value, 0)

    logger.info(
        f"Data Import complete: {summary.describe()}"
    )
    return summary
