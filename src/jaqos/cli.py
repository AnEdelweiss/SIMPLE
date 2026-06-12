import sys
import os
import opensilexClientToolsPython as silex
from rich.prompt import Prompt, IntPrompt
from rich.panel import Panel
from rich.table import Table

from jaqos.ui import console, BANNER, MENU_CREATION, menu, choix_repertoire_travail
from jaqos.auth import INSTANCES, connexion, is_connected
from jaqos.experiment import find_Exp, create_experiment
from jaqos.data_import import create_factor, create_germplasm, create_sci_obj,create_data
from jaqos.images_import import create_images

def main():
    console.print(BANNER)
    console.print('[bold][green]______________________________________________________________________________________[/green][/bold]\n')
    Prompt.ask("Press a key to start")
    # INITIALISATION DES VARIABLES et de l'api ~
    choix_dossier = None
    document_miappe = None
    wd_experience = None
    Factors_Levels_uri = None
    Germplasms_uri = None
    ScObj_uri=None
    silex_API_Client = silex.ApiClient(verbose=False)
    # CONNECTING AS GUEST ON THE SANDBOX BY DEFAULT ~
    silex_API_Client.connect_to_opensilex_ws(identifier='guest@opensilex.org',password='guest',host="https://opensilex.org/sandbox/rest")
    etat = "[cyan]Logged in as[/cyan] [bold green]guest@opensilex.org[/bold green] [cyan]on [/cyan] [bold green]Sandbox[/bold green]."
    #BOUCLE PRINCIPALE
    while True:
        try:
            menu(etat)
            user_input = IntPrompt.ask("[green]\\[+][/green] [cyan]What would you like to do?[/cyan]")
            
            if user_input == 9:
                sys.exit(0)

            elif user_input == 1:
                console.print("[cyan]Connection :[/cyan]")
                login = {}
                liste_url = list(INSTANCES.keys())
                liste_instances = list(INSTANCES.values())
        
                table = Table(title="Available instances", show_header=False)
                table.add_column("Index", style="cyan")
                table.add_column("Nom", style="green")
                for index, nom in enumerate(liste_instances):
                    table.add_row(str(index), nom)
                console.print(table)
                while True:
                    temp_Inst = IntPrompt.ask(f"[green]\\[+][/green]On which instance would you like to log in (0-{len(liste_instances)-1})")
                    if 0<=temp_Inst<=len(liste_instances)-1:
                        login["instance"] = liste_url[temp_Inst]
                        break
                    else:
                        console.print(f"[red][bold]Please type a number between [white]0[/white] and [white]{len(liste_instances)-1}[/white][/red][/bold]")
                login["id"] = Prompt.ask(f"[green]\\[+][/green] Username/mail on : {INSTANCES[login['instance']]}")
                login["mdp"] = Prompt.ask("[green]\\[+][/green] Password", password=True)
                
                connecte = connexion(login, silex_API_Client)
                if connecte:
                    etat = f"[cyan]Your are logged in as[/cyan] [bold green]{login['id']}[/bold green] [cyan]on[/cyan] [bold green]{liste_instances[temp_Inst]}[/bold green]."
                else:
                    etat = "[bold red]You are not logged in, please try again...[/bold red]"

            elif user_input == 2:
                if is_connected(silex_API_Client):
                    find_Exp(silex_API_Client)
                else:
                    console.print("[red]Please try to log in first.[/red]")

            elif user_input == 3:
                if is_connected(silex_API_Client):
                    if choix_dossier:
                        changement_repertoire = Prompt.ask(f"Would you like to continue to work on this experiment ? [bold]{choix_dossier}[/bold] ?", choices=["y", "n"], default="y")
                        if changement_repertoire == 'n':
                            wd_experience, choix_dossier, document_miappe,document_data = choix_repertoire_travail()
                    else:
                        console.print("[cyan]You chose to import data on OpenSilex[/cyan]")
                        result = choix_repertoire_travail()
                        if result[0] is not None:
                            wd_experience, choix_dossier, document_miappe,document_data = result
                        else:
                            break
                    if not wd_experience:
                        break
                    while True:
                        if choix_dossier is None:
                            console.print("[cyan]You chose to import data on OpenSilex[/cyan]")
                            wd_experience, choix_dossier, document_miappe,document_data = choix_repertoire_travail()

                        console.print(Panel(MENU_CREATION, title="[bold]Experiment Menu[/bold]", border_style="cyan"))
                        choix_creation = IntPrompt.ask("[green]Please make your choice[/green]")

                        if choix_creation == 1:
                            experiment_ok = create_experiment(document_miappe, choix_dossier, silex_API_Client)

                        elif choix_creation == 2:
                            Germplasms_uri, _ = create_germplasm(document_miappe, silex_API_Client)

                        elif choix_creation == 3: 
                            Factors_Levels_uri, _ = create_factor(document_miappe, silex_API_Client)

                        elif choix_creation == 4:
                            ScObj_uri = create_sci_obj(document_data,document_miappe,silex_API_Client)

                        elif choix_creation == 5:
                            prov_dict=create_images(wd_experience,document_data,document_miappe,silex_API_Client)
                            
                        elif choix_creation == 6:
                            experiment_ok = create_experiment(document_miappe, choix_dossier, silex_API_Client)
                            Germplasms_uri, _ = create_germplasm(document_miappe, silex_API_Client)
                            Factors_Levels_uri, _ = create_factor(document_miappe, silex_API_Client)
                            ScObj_uri = create_sci_obj(document_data,document_miappe,silex_API_Client)
                            prov_dict=create_images(wd_experience,document_data,document_miappe,silex_API_Client)
                            break
                        elif choix_creation == 7:
                            create_data(document_data, document_miappe, silex_API_Client,wd_experience,ScObj_uri)
                            
                        elif choix_creation == 9:
                            break
                else:
                    console.print("[bold red]Your are not logged in[/bold red]")

            elif user_input in [4, 5, 6, 7, 8]:
                print("under development")
            else:
                print("Invalid input")

        except Exception as e:
            print(f'There was an error : :\n{e}')
        except KeyboardInterrupt:
            print("\n[!] User abort!")
            sys.exit(1)
