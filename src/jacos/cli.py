import sys
import os
import opensilexClientToolsPython as silex
from rich.prompt import Prompt, IntPrompt
from rich.panel import Panel
from rich.table import Table

from jacos.ui import console, BANNER, MENU_CREATION, menu, choix_repertoire_travail
from jacos.auth import INSTANCES, connexion, is_connected
from jacos.experiment import find_Exp, create_experiment
from jacos.data_import import create_factor, create_germplasm, create_sci_obj
from jacos.images_import import create_images

def main():
    console.print(BANNER)
    console.print('[bold][green]______________________________________________________________________________________[/green][/bold]\n')
    Prompt.ask("Appuyez sur une touche pour continuer")
    # INITIALISATION DES VARIABLES et de l'api ~
    choix_dossier = None
    document_miappe = None
    wd_experience = None
    Factors_Levels_uri = None
    Germplasms_uri = None
    silex_API_Client = silex.ApiClient(verbose=False)
    # CONNECTING AS GUEST ON THE SANDBOX BY DEFAULT ~
    silex_API_Client.connect_to_opensilex_ws(identifier='guest@opensilex.org',password='guest',host="https://opensilex.org/sandbox/rest")
    etat = "[cyan]Connecté en tant que[/cyan] [bold green]guest@opensilex.org[/bold green] [cyan]sur la[/cyan] [bold green]Sandbox[/bold green]."
    #BOUCLE PRINCIPALE
    while True:
        try:
            menu(etat)
            user_input = IntPrompt.ask("[green]\\[+][/green] [cyan]Que souhaitez-vous faire ?[/cyan]")
            
            if user_input == 9:
                sys.exit(0)

            elif user_input == 1:
                console.print("[cyan]Vous avez choisi de vous connecter[/cyan]")
                login = {}
                liste_url = list(INSTANCES.keys())
                liste_instances = list(INSTANCES.values())
        
                table = Table(title="Instances disponibles", show_header=False)
                table.add_column("Index", style="cyan")
                table.add_column("Nom", style="green")
                for index, nom in enumerate(liste_instances):
                    table.add_row(str(index), nom)
                console.print(table)
                while True:
                    temp_Inst = IntPrompt.ask(f"[green]\\[+][/green] Sur quelle instance souhaitez-vous vous connecter ? (0-{len(liste_instances)-1})")
                    if 0<=temp_Inst<=len(liste_instances)-1:
                        login["instance"] = liste_url[temp_Inst]
                        break
                    else:
                        console.print(f"[red][bold]Veuillez choisir un nombre entre [white]0[/white] et [white]{len(liste_instances)-1}[/white][/red][/bold]")
                login["id"] = Prompt.ask(f"[green]\\[+][/green] Identifiant sur {INSTANCES[login['instance']]}")
                login["mdp"] = Prompt.ask("[green]\\[+][/green] Mot de passe", password=True)
                
                connecte = connexion(login, silex_API_Client)
                if connecte:
                    etat = f"[cyan]Connecté en tant que[/cyan] [bold green]{login['id']}[/bold green] [cyan]sur[/cyan] [bold green]{liste_instances[temp_Inst]}[/bold green]."
                else:
                    etat = "[bold red]Vous n'êtes pas connecté, veuillez réessayer.[/bold red]"

            elif user_input == 2:
                if is_connected(silex_API_Client):
                    find_Exp(silex_API_Client)
                else:
                    print("Vous n'êtes pas connecté.")

            elif user_input == 3:
                if is_connected(silex_API_Client):
                    if choix_dossier:
                        changement_repertoire = Prompt.ask(f"Souhaitez-vous rester dans l'expérience [bold]{choix_dossier}[/bold] ?", choices=["y", "n"], default="y")
                        if changement_repertoire == 'n':
                            wd_experience, choix_dossier, document_miappe,document_data = choix_repertoire_travail()
                    else:
                        console.print("[cyan]Vous avez choisi d'importer des données sur OpenSilex:[/cyan]")
                        result = choix_repertoire_travail()
                        if result[0] is not None:
                            wd_experience, choix_dossier, document_miappe,document_data = result
                        else:
                            break
                    if not wd_experience:
                        break
                    while True:
                        if choix_dossier is None:
                            console.print("[cyan]Vous avez choisi d'importer des données sur OpenSilex:[/cyan]")
                            wd_experience, choix_dossier, document_miappe,document_data = choix_repertoire_travail()

                        console.print(Panel(MENU_CREATION, title="[bold]Menu de Création[/bold]", border_style="cyan"))
                        choix_creation = IntPrompt.ask("[green]Effectuez votre choix[/green]")

                        if choix_creation == 1:
                            experiment_ok = create_experiment(document_miappe, choix_dossier, silex_API_Client)

                        elif choix_creation == 2:
                            Germplasms_uri, _ = create_germplasm(document_miappe, silex_API_Client)

                        elif choix_creation == 3: 
                            Factors_Levels_uri, _ = create_factor(document_miappe, silex_API_Client)

                        elif choix_creation == 4:
                            sci_obj = create_sci_obj(document_data,document_miappe,silex_API_Client)

                        elif choix_creation == 5:
                            create_images(wd_experience,document_data,document_miappe,silex_API_Client)
                            
                        elif choix_creation == 6:
                            create_experiment(document_miappe, choix_dossier, silex_API_Client)
                            create_germplasm(document_miappe, silex_API_Client)
                            create_factor(document_miappe, silex_API_Client)
                            create_sci_obj(document_data,document_miappe,silex_API_Client)
                            break
                        elif choix_creation == 9:
                            break
                else:
                    console.print("[bold red]Vous n'êtes pas connecté.[/bold red]")

            elif user_input in [4, 5, 6, 7, 8]:
                print("en developpement")
            else:
                print("Choix invalide")

        except Exception as e:
            print(f'attention quand meme ahah :\n{e}')
        except KeyboardInterrupt:
            print("\n[!] Abort")
            sys.exit(1)