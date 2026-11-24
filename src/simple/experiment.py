import opensilexClientToolsPython as silex
import pandas as pd

from simple.cancellation import check_cancelled
from simple.errors import DataImportError
from simple.logging_setup import logger


def api_find_experiment_by_name(api_client, name_exp):
    exp_api = silex.ExperimentsApi(api_client)
    exp_data=None
    exp_data = exp_api.search_experiments(name=name_exp)
    if exp_data["result"] :
        logger.info(f"User looked for the experiment : {name_exp}. It exists.")
    else:
        logger.info(f"User looked for the experiment : {name_exp}. It does not exist.")
    return exp_data["result"]


def create_experiment(
    miappe_path, api_client, status_callback=None, should_cancel=None
):

    check_cancelled(should_cancel)
    dataframe = pd.read_excel(miappe_path, sheet_name="experiment", header=1)
    dataframe.drop(
        dataframe.columns[dataframe.columns.str.contains("unnamed", case=False)],
        axis=1,
        inplace=True,
    )

    dataframe["start_date"] = pd.to_datetime(dataframe["start_date"]).dt.strftime("%Y-%m-%d")
    dataframe["end_date"] = pd.to_datetime(dataframe["end_date"]).dt.strftime("%Y-%m-%d")
    
    records = dataframe.where(pd.notnull(dataframe), None).to_dict("records")

    experiments_api = silex.ExperimentsApi(api_client)
    organizations_api = silex.OrganizationsApi(api_client)
    security_api = silex.SecurityApi(api_client)
    projects_api = silex.ProjectsApi(api_client)

    name_to_uri = {}
    for row_dict in records:
        check_cancelled(should_cancel)
        name_to_uri = {}

        # Fonction pour split, strip et retourner un truc vide si la case est vide
        def to_list(key):
            val = row_dict.get(key)
            return [x.strip() for x in str(val).split(",")] if val is not None else []

        # get the info of everythng for the experiment
        experiment_name = row_dict.get("name")
        start_date = row_dict.get("start_date")
        end_date = row_dict.get("end_date")
        description = row_dict.get("description", "")
        objective = row_dict.get("objective")
        is_public = bool(row_dict.get("is_public", True))
        # look for the experiment, if found, no creation !
        exp_result = experiments_api.search_experiments(name=experiment_name)["result"]
        if exp_result:
            name_to_uri[experiment_name] = exp_result[0].uri
            if status_callback:
                status_callback(
                    f"[bold green][✓][/bold green] [bold yellow]An experiment was found with this URI :[/bold yellow]  {name_to_uri[experiment_name]}"
                )
            continue

        if not objective:
            logger.error("Objective Missing From MIAPPE file experiment sheet")
            raise DataImportError("Objective Missing From MIAPPE file experiment sheet")
        if not start_date:
            logger.error("Starting Date Missing From MIAPPE file experiment sheet")
            raise DataImportError(
                "Starting Date Missing From MIAPPE file experiment sheet"
            )
        if not end_date:
            logger.warning("Ending Date Missing From MIAPPE file experiment sheet")
        if status_callback:
            status_callback(
                f"[bold green]Start Date:[/bold green] [bold cyan]{start_date}"
            )
            status_callback(
                f"[bold green]Objective:[/bold green] [bold cyan]{str(objective)[0:400]}..."
            )
            status_callback(
                f"[bold green]Description:[/bold green] [bold cyan]{str(description)[0:400]}...[/bold cyan]"
            )

        # get the lists
        organisation_uris = to_list("organisations")
        project_uris = to_list("projects")
        facility_uris = to_list("facilities")
        scientific_supervisor_uris = to_list("scientific_supervisors")
        technical_supervisor_uris = to_list("technical_supervisors")
        group_uris = to_list("groups")

        organisation_uri_map = {}
        for organisation in organisation_uris:
            if organisation is None:
                logger.warning(
                    "Organisation Missing From MIAPPE file experiment sheet"
                )
                organisation_uris = None
            else:
                org_result = organizations_api.search_organizations(pattern=organisation)["result"]
                if org_result:
                    organisation_uri_map.update({organisation: org_result[0].uri})
                    if status_callback:
                        status_callback(
                            f"[bold green][✓][/bold green] [green]{organisation}[/green] URI: {org_result[0].uri}"
                        )
                    organisation_uris = list(organisation_uri_map.values())
                else:
                    logger.warning(
                        f"{organisation}: Unknown Organisation "
                    )
                    organisation_uris = None

        group_uri_map = {}
        for group in group_uris:
            if group is None:
                logger.warning(
                    "Group Missing From MIAPPE file experiment sheet"
                )
                group_uris = None
            else:
                sec_result = security_api.search_groups(name=group)["result"]
                if sec_result:
                    group_uri_map.update({group: sec_result[0].uri})
                    if status_callback:
                        status_callback(
                            f"[bold green][✓][/bold green] [green]{group}[/green] URI: {sec_result[0].uri}"
                        )
                    group_uris = list(group_uri_map.values())
                else:
                    logger.warning(f"{group}: Unknown Group")
                    group_uris = None
        project_uri_map = {}
        for project in project_uris:
            if project is None:
                logger.warning(
                    "[bold yellow]Project Missing From MIAPPE experiment sheet[/bold yellow]"
                )
                project_uris = None
            else:
                proj_result = projects_api.search_projects(name=project)["result"]
                if proj_result:
                    project_uri_map.update({project: proj_result[0].uri})
                    if status_callback:
                        status_callback(
                            f"[bold green][✓][/bold green] [green]{project}[/green] URI: {proj_result[0].uri}"
                        )
                    project_uris = list(project_uri_map.values())
                else:
                    logger.warning(f"[bold red]{project}: Unknown Project[/bold red]")
                    project_uris = None

        facility_uri_map = {}
        for facility in facility_uris:
            if facility is None:
                logger.warning(
                    "[bold yellow]Organisation Missing from MIAPPE experiment sheet[/bold yellow]"
                )
                facility_uris = None
            else:
                org_result = organizations_api.search_facilities(pattern=facility)["result"]
                if org_result:
                    facility_uri_map.update({facility: org_result[0].uri})
                    if status_callback:
                        status_callback(
                            f"[bold green][✓][/bold green] [green]{facility}[/green] URI: {org_result[0].uri}"
                        )
                    facility_uris = list(facility_uri_map.values())
                else:
                    logger.warning(
                        f"[bold red] {facility}: Unknown Facility[/bold red]"
                    )
                    facility_uris = None
        scientific_supervisor_uri_map = {}
        for scisup in scientific_supervisor_uris:
            if scisup is None:
                logger.warning(
                    "[bold yellow]Scientific Supervisors Missing from MIAPPE experiment sheet[/bold yellow]"
                )
                scientific_supervisor_uris = None
            else:
                sec_result = security_api.search_persons(name=str(scisup))["result"]
                if sec_result:
                    scientific_supervisor_uri_map.update({scisup: sec_result[0].uri})
                    if status_callback:
                        status_callback(
                            f"[bold green][✓][/bold green] [green]{scisup}[/green] URI: {sec_result[0].uri}"
                        )
                    scientific_supervisor_uris = list(
                        scientific_supervisor_uri_map.values()
                    )
                else:
                    logger.warning(
                        f"[bold red]{scisup}: Unknown Scientific Supervisors[/bold red]"
                    )
                    scientific_supervisor_uris = None
        technical_supervisor_uri_map = {}
        for techsup in technical_supervisor_uris:
            if techsup is None:
                logger.warning(
                    " [bold yellow]Technical Supervisors Missing from MIAPPE experiment sheet[/bold yellow]"
                )
                technical_supervisor_uris = None
            else:
                sec_result = security_api.search_persons(name=techsup)["result"]
                if sec_result:
                    technical_supervisor_uri_map.update({techsup: sec_result[0].uri})
                    if status_callback:
                        status_callback(
                            f"[bold green][✓][/bold green] [green]{techsup}[/green] URI: {sec_result[0].uri}"
                        )
                    technical_supervisor_uris = list(technical_supervisor_uri_map.values())
                else:
                    logger.warning(
                        f"[bold red] {techsup}: Unknown Technical Supervisors[/bold red]"
                    )
                    technical_supervisor_uris = None
        body = silex.ExperimentCreationDTO(
            name=experiment_name,
            start_date=start_date,
            end_date=end_date,
            description=description,
            objective=objective,
            organisations=organisation_uris,
            projects=project_uris,
            facilities=facility_uris,
            scientific_supervisors=scientific_supervisor_uris,
            technical_supervisors=technical_supervisor_uris,
            groups=group_uris,
            is_public=is_public,
        )

        experiments_api.create_experiment(body=body)
        logger.info(name_to_uri)
        exp_result = experiments_api.search_experiments(name=experiment_name)
        name_to_uri.update({experiment_name: exp_result["result"][0].uri})

    return name_to_uri
