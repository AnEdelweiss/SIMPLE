import logging
import sys

import opensilexClientToolsPython as silex
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.prompt import IntPrompt, Prompt

from simple.auth import (
    INSTANCES,
    check_connection_internet,
    connexion,
    get_login,
    is_connected,
)
from simple.console import console
from simple.data_import import (
    create_factor,
    create_germplasm,
    create_sci_obj,
)
from simple.erreurs import (
    AuthenticationError,
    DataImportError,
    NetworkError,
    SimpleBaseException,
)
from simple.experiment import api_find_experiment_by_name, create_experiment
from simple.import_service import (
    PHASE_CHECKING_PROVENANCES,
    PHASE_CHECKING_VARIABLE_MAP,
    PHASE_COMPARING_DATAFILES,
    PHASE_CREATING_PROVENANCES,
    PHASE_ROUND_PROTOCOL,
    PHASE_SCIENTIFIC_OBJECTS,
    PHASE_UPLOADING_DATA,
    plan_datafiles_import,
    run_tabular_import,
    upload_datafiles,
)
from simple.systeme_logs import logger
from simple.ui import (
    BANNER,
    HELP_MENU,
    MENU_CREATION,
    change_tabular_data,
    choix_dossier_datafile,
    choix_repertoire_travail,
    menu,
    show_data_panel,
    show_data_table_dictionnaire,
)

# Display mapping for the semantic phases emitted by simple.import_service.
_IMPORT_STATUS = {
    PHASE_CHECKING_VARIABLE_MAP: ("[green]Checking variable map...[/green]", "aesthetic"),
    PHASE_CHECKING_PROVENANCES: ("[green]Checking provenances...[/green]", "aesthetic"),
    PHASE_CREATING_PROVENANCES: (
        "[green]Creating default provenances...[/green]",
        "aesthetic",
    ),
    PHASE_SCIENTIFIC_OBJECTS: (
        "[green]Importing/Searching Scientific objects on OpenSilex instance...[/green]",
        "aesthetic",
    ),
    PHASE_UPLOADING_DATA: (
        "[green]Uploading data to OpenSilex... This will be quick.[/green]",
        "aesthetic",
    ),
    PHASE_ROUND_PROTOCOL: (
        "[green]Looking for camera position and plant mask info[/green]",
        "aesthetic",
    ),
    PHASE_COMPARING_DATAFILES: (
        "Comparing datafile database and tabular data filenames...",
        "dots",
    ),
}


def _import_status(phase):
    message, spinner = _IMPORT_STATUS[phase]
    return console.status(message, spinner=spinner)


def ui_find_experiment(silex_API_Client):
    name_exp = Prompt.ask("[cyan]What experiment are you looking for?[/cyan]")

    with console.status("[bold green]Searching...[/bold green]"):
        exp_data = api_find_experiment_by_name(silex_API_Client, name_exp)

    if not exp_data:
        Prompt.ask(
            "[bold red]No experiment with that name were found.([/bold red]\nPress Enter to go back to the main menu"
        )
        return

    exp_data = exp_data[0]
    names_to_attribute_map = {
        "URI": "uri",
        "Name": "name",
        "Description": "description",
        "Objectives": "objective",
    }
    show_data_panel("Experiment infos", exp_data, names_to_attribute_map)
    Prompt.ask("Press Enter to go back to the main menu")


def ui_create_experiment(document_miappe, silex_API_Client):
    console.print(
        "[bold green]__________________________Experiment Importation__________________________[/bold green]"
    )

    def afficher_statut(mess):
        console.print(mess)

    try:
        with console.status("[bold green]Processing experiment data...[/bold green]"):
            results = create_experiment(
                document_miappe, silex_API_Client, status_callback=afficher_statut
            )
        # affichage final
        for nom, uri in results.items():
            console.print(
                f"[bold green][✓][/bold green] [bold cyan]Your experiment {nom} has the following uri:[/bold cyan] {uri}"
            )
    except DataImportError as e:
        # Gestion erreurs
        console.print(f"\n[bold red]Import Aborted:[/bold red] {e}")


def ui_import_factor(document_miappe, silex_API_Client):
    console.print(
        "[bold green]__________________________Factor Importation__________________________[bold green]"
    )
    console.print(f"[cyan]Miappe file :[/cyan] {document_miappe}")
    logger.info(f"Miappe file : {document_miappe}")

    with console.status(
        "[green]Importing/Searching for factors on Phis Instance...[/green]",
        spinner="aesthetic",
    ):
        factors_levels_uri, factors_uri = create_factor(
            document_miappe, silex_API_Client
        )

    logger.info(f"{factors_uri},\n{factors_uri}")
    show_data_table_dictionnaire("Factors", factors_uri)
    show_data_table_dictionnaire("Factor levels", factors_levels_uri)

    return factors_levels_uri, factors_uri


def ui_import_germplasm(document_miappe, silex_API_Client):
    console.print(
        "[bold green]__________________________Germplasm Importation__________________________[bold green]"
    )
    logger.info(f"Miappe file : {document_miappe}")

    with console.status(
        "[green]Importing/searching for germplasms on Phis instance...[/green]",
        spinner="aesthetic",
    ):
        germplasms_uri, species_uri = create_germplasm(
            document_miappe, silex_API_Client
        )

    logger.info(f"{germplasms_uri},\n{species_uri}")
    show_data_table_dictionnaire("Created/Found Germplasms", germplasms_uri)

    return germplasms_uri, species_uri


def ui_import_sci_obj(document_data, document_miappe, silex_API_Client):
    console.print(
        "[bold green]__________________________Scientific objects Importation__________________________[bold green]"
    )

    def afficher_statut(mess):
        console.print(
            f"[bold cyan][+] [bold cyan][bold green][✓] {mess}[/bold green]"
        )

    with console.status(
        "[green]Importing/Searching Scientific objects on OpenSilex instance...[/green]",
        spinner="aesthetic",
    ):
        sci_obj_uri, created_sci_obj = create_sci_obj(
            document_data,
            document_miappe,
            silex_API_Client,
            status_callback=afficher_statut,
        )
    found_sci_obj = len(sci_obj_uri) - created_sci_obj

    console.print(
        f"[bold green]End of search : {found_sci_obj} found, {created_sci_obj} created. [/bold green]"
    )
    if created_sci_obj > 0:
        console.print(
            "Scientific object sheet was sucessfully modified in the output MIAPPE"
        )

    logger.info(len(sci_obj_uri))
    logger.info(sci_obj_uri)

    return sci_obj_uri


def ui_import_data(document_data, document_miappe, login, silex_API_Client):
    console.print(
        "[bold green]__________________________Tabular Data Importation__________________________[bold green]"
    )

    def confirm_data_mapping(morpho_info):
        console.print(
            f"[cyan]Corresponding data found :[/cyan] [bold green]{list(morpho_info.keys())}[/bold green]"
        )
        return (
            Prompt.ask(
                "[bold green]Would you like to import these data?[/bold green]",
                choices=["y", "n"],
                default="y",
            )
            == "y"
        )

    def confirm_create_default_provenances(missing_provs):
        console.print(
            f"[bold red]The following provenances were not found : {missing_provs}[/bold red]"
        )
        return (
            Prompt.ask(
                "[bold yellow]Do you want to create default ones using these names?\n (It is recommended to create them on your PHIS instance manually and then reference them on the MIAPPE in the 'Data Files' sheet) [/bold yellow]",
                choices=["y", "n"],
                default="n",
            )
            == "y"
        )

    def show_provenances(prov_dict):
        show_data_table_dictionnaire("Provenances", prov_dict)
        console.print("[bold green] Provenances are OK !")

    def show_scientific_objects(found_sci_obj, created_sci_obj):
        console.print(
            f"[bold green]End of search : {found_sci_obj} found, {created_sci_obj} created. [/bold green]"
        )

    # on gère l'affichage des progression d'importation de données
    def afficher_progres(nom_variable, nb_lignes):

        if nb_lignes > 0:
            console.print(
                f"[bold cyan] ↳ Sucess : {nb_lignes} lines of data added to [green]{nom_variable}[/green][/bold cyan]"
            )
        else:
            console.print(
                f"[dim white] ↳ Ignored : Data for {nom_variable} were already uploaded.[/dim white]"
            )

    run_tabular_import(
        document_data,
        document_miappe,
        login,
        silex_API_Client,
        confirm_data_mapping=confirm_data_mapping,
        confirm_create_default_provenances=confirm_create_default_provenances,
        on_provenances_ready=show_provenances,
        on_scientific_objects_ready=show_scientific_objects,
        progress_callback=afficher_progres,
        status_factory=_import_status,
    )

    console.print("[bold green]Data Import Over![/bold green]")


def ui_import_datafiles(
    document_miappe, document_data, wd_experience, login, silex_API_Client
):
    console.print(
        "[bold green]__________________________Datafiles Importation__________________________[bold green]"
    )
    # on choisit le dossier photo ici (the function returns (wd, photos))
    _, repertoire_photos = choix_dossier_datafile(wd_experience)

    def confirm_create_default_provenances(missing_provs):
        console.print(
            f"[bold red]The following provenances were not found : {missing_provs}[/bold red]"
        )
        return (
            Prompt.ask(
                "[bold yellow]Do you want to create default ones using these names?\n (It is recommended to create them on your PHIS instance manually and then reference them on the MIAPPE in the 'Data Files' sheet) [/bold yellow]",
                choices=["y", "n"],
                default="n",
            )
            == "y"
        )

    def show_provenances(prov_dict):
        show_data_table_dictionnaire("Provenances", prov_dict)
        console.print("[bold green] Provenances are OK !")

    def show_scientific_objects(found_sci_obj, created_sci_obj):
        console.print(
            f"[bold green]End of search : {found_sci_obj} found,{created_sci_obj} created. [/bold green]"
        )

    def confirm_protocol(protocol_found):
        if not protocol_found:
            return (
                Prompt.ask(
                    "[cyan][X] PlantMask and Camera Position were not found, do you want to continue?\nThis is not a problem if your instance does not use round protocol info..[/cyan]",
                    choices=["y", "n"],
                    default="y",
                )
                == "y"
            )
        console.print(
            "[bold green][✓] PlantMask and Camera Position Info found ![/bold green]"
        )
        return True

    def confirm_discrepancies(missing_datafile1, missing_datafile2):
        if missing_datafile1:
            console.print(
                f"{len(missing_datafile1)} [red][X] datafiles are missing from the datafile1 database.[/red]"
            )
            if (
                Prompt.ask("Show the missing pictures?", choices=["y", "n"], default="y")
                == "y"
            ):
                console.print(missing_datafile1)

        if missing_datafile2:
            console.print(
                f"{len(missing_datafile2)} [red][X] datafiles are missing from the datafile2 database.[/red]"
            )
            if (
                Prompt.ask("Show the missing pictures?", choices=["y", "n"], default="y")
                == "y"
            ):
                console.print(missing_datafile2)

        if missing_datafile1 or missing_datafile2:
            return (
                Prompt.ask(
                    "[red]Continue despite discrepancies ? The import may fail...[/red]",
                    choices=["y", "n"],
                    default="n",
                )
                == "y"
            )
        console.print(
            "[green][✓] The datafile database matches the data, we can continue[/green]"
        )
        return True

    def confirm_upload():
        return (
            Prompt.ask(
                "[bold green]Do you want to continue to import datafiles?[/bold green]",
                choices=["y", "n"],
                default="y",
            )
            == "y"
        )

    plan = plan_datafiles_import(
        document_miappe,
        document_data,
        wd_experience,
        silex_API_Client,
        repertoire_photos,
        confirm_create_default_provenances=confirm_create_default_provenances,
        confirm_protocol=confirm_protocol,
        confirm_discrepancies=confirm_discrepancies,
        confirm_upload=confirm_upload,
        on_provenances_ready=show_provenances,
        on_scientific_objects_ready=show_scientific_objects,
        status_factory=_import_status,
    )

    # enfin on téléverse :

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress_bar:
        taches_actives = {}

        def afficher_statut(mess):
            progress_bar.console.print(
                f"[bold cyan][+][bold cyan][bold green]{mess}[/bold green]"
            )

        def gestion_barre(nom_tache, total=None, avance=0):
            if nom_tache not in taches_actives:
                taches_actives[nom_tache] = progress_bar.add_task(
                    nom_tache, total=total
                )
            if avance > 0:
                progress_bar.advance(taches_actives[nom_tache], advance=avance)

        upload_datafiles(
            plan,
            document_miappe,
            document_data,
            login,
            silex_API_Client,
            status_callback=afficher_statut,
            progress_callback=gestion_barre,
        )
        progress_bar.console.print(
            "[bold green][✓] Succeeded in importing all datafiles ![/bold green]"
        )


def main():
    try:
        check_connection_internet()
    except NetworkError as e:
        console.print(f"[bold red]{e}[/bold red]")
        return
    #Taking care of the display into the console, we want the user to see log.warning,error 
    console_handler = RichHandler(
        console=console, 
        show_time=False, 
        show_path=False, 
        markup=True, 
        rich_tracebacks=True
    )
    console_handler.setLevel(logging.WARNING) 
    if not any(isinstance(h, RichHandler) for h in logger.handlers):
        logger.addHandler(console_handler)

    console.print(BANNER)
    console.print(
        "[bold][green]______________________________________________________________________________________[/green][/bold]\n"
    )
    Prompt.ask("Press a key to start")
    # INITIALISATION DES VARIABLES et de l'api ~
    choix_dossier = None
    document_miappe = None
    wd_experience = None
    # setting default login, here guest on sandbox
    silex_API_Client = silex.ApiClient(verbose=False)
    etat = "[red]Hi, before anything, press [1] to log in.[/red]"
    # BOUCLE PRINCIPALE
    while True:
        try:
            menu(etat)
            user_input = IntPrompt.ask(
                "[green]\\[+][/green] [cyan]What would you like to do?[/cyan]"
            )

            if user_input == 9:
                sys.exit(0)

            elif user_input == 1:
                login = get_login()
                try:
                    connexion(login, silex_API_Client)
                    etat = f"[cyan]Your are logged in as[/cyan] [bold green]{login['identifier']}[/bold green] [cyan]on[/cyan] [bold green]{INSTANCES[login['host']]}[/bold green]."
                except AuthenticationError as e:
                    etat = "[bold red]You are not logged in, please try again...[/bold red]"
                    console.print(e)

            elif user_input == 2:
                if is_connected(silex_API_Client):
                    ui_find_experiment(silex_API_Client)
                else:
                    console.print("[red]Please try to log in first.[/red]")

            elif user_input == 3:
                if is_connected(silex_API_Client):
                    # Gestion du repertoire de travail
                    if choix_dossier:
                        changement_repertoire = Prompt.ask(
                            f"Would you like to continue to work on this experiment ? [bold]{choix_dossier}[/bold] ?",
                            choices=["y", "n"],
                            default="y",
                        )
                        if changement_repertoire == "n":
                            (
                                wd_experience,
                                choix_dossier,
                                document_miappe,
                                document_data,
                            ) = choix_repertoire_travail()
                    else:
                        console.print(
                            "[cyan]You chose to import data on OpenSilex[/cyan]"
                        )
                        result = choix_repertoire_travail()
                        if result[0] is not None:
                            (
                                wd_experience,
                                choix_dossier,
                                document_miappe,
                                document_data,
                            ) = result
                        else:
                            break
                    if not wd_experience:
                        break
                    while True:
                        if choix_dossier is None:
                            console.print(
                                "[cyan]You chose to import data on OpenSilex[/cyan]"
                            )
                            (
                                wd_experience,
                                choix_dossier,
                                document_miappe,
                                document_data,
                            ) = choix_repertoire_travail()
                        # Gestion du repertoire de travail
                        console.print(
                            Panel(
                                MENU_CREATION,
                                title="[bold]Experiment Menu[/bold]",
                                border_style="green",
                            )
                        )
                        choix_creation = IntPrompt.ask(
                            "[green]Please make your choice[/green]"
                        )

                        if choix_creation == 1:
                            ui_create_experiment(document_miappe, silex_API_Client)

                        elif choix_creation == 2:
                            ui_import_germplasm(document_miappe, silex_API_Client)

                        elif choix_creation == 3:
                            ui_import_factor(document_miappe, silex_API_Client)

                        elif choix_creation == 4:
                            ui_import_sci_obj(
                                document_data, document_miappe, silex_API_Client
                            )

                        elif choix_creation == 5:
                            ui_import_datafiles(
                                document_miappe,
                                document_data,
                                wd_experience,
                                login,
                                silex_API_Client,
                            )

                        elif choix_creation == 6:
                            ui_import_data(
                                document_data, document_miappe, login, silex_API_Client
                            )

                        elif choix_creation == 7:
                            ui_create_experiment(document_miappe, silex_API_Client)
                            ui_import_germplasm(document_miappe, silex_API_Client)
                            ui_import_factor(document_miappe, silex_API_Client)
                            ui_import_sci_obj(
                                document_data, document_miappe, silex_API_Client
                            )
                            ui_import_datafiles(
                                document_miappe,
                                document_data,
                                wd_experience,
                                login,
                                silex_API_Client,
                            )
                            ui_import_data(
                                document_data, document_miappe, login, silex_API_Client
                            )
                            break

                        elif choix_creation == 8:
                            wd_experience, document_data, repertoire_photos = (
                                change_tabular_data(wd_experience)
                            )

                        elif choix_creation == 9:
                            break
                else:
                    console.print("[bold red]Your are not logged in[/bold red]")
            elif user_input == 4:
                console.print(
                    Panel(
                        HELP_MENU,
                        title="[bold]Help Menu[/bold]",
                        border_style="yellow",
                        expand=False,
                    )
                )
                Prompt.ask("Press any key to go back to the main menu")
            elif user_input in [5, 6, 7, 8]:
                print("under development")
            else:
                print("Invalid input")

        except SimpleBaseException as e:
            logger.warning(f"Action interrupted : {e} ")
            console.print(f"[bold yellow] \n Warning : {e} [/bold yellow]")

        except Exception as e:
            # Intentional broad catch at the top of the interactive menu loop:
            # one failed action must never kill the whole session. Anything not
            # handled above is logged with a full traceback for debugging.
            logger.exception(
                f"[bold red]Warning, an Unhandled Error was raised {e}[/bold red]"
            )
            console.print(
                "\nPlease try again or check the logs to know what happened..."
            )

        except KeyboardInterrupt:
            logger.info("Manual interruption")
            console.print("\n[bold green] Goodbye ^^[/bold green]")
            break
