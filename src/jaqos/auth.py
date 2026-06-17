import opensilexClientToolsPython as silex
from jaqos.ui import console, Prompt,IntPrompt,Table
import json
import requests
import sys
# Initiatialisation des différentes instances
INSTANCES = {
    "https://opensilex.org/sandbox/rest": "Sandbox",
    "https://phis.emphasis.fedcloud.eu/uh/rest": "Helsinki/UH",
    "https://opensilex.org/demo2/rest": "test1.5.1"
    
}

def get_login():
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
        temp_Inst = IntPrompt.ask(f"[green]\\[+][/green][cyan]On which instance would you like to log in (0-{len(liste_instances)-1})[/cyan]")
        if 0<=temp_Inst<=len(liste_instances)-1:
            login["host"] = liste_url[temp_Inst]
            break
        else:
            console.print(f"[red][bold]Please type a number between [white]0[/white] and [white]{len(liste_instances)-1}[/white][/red][/bold]")
    login["identifier"] = Prompt.ask(f"[green]\\[+][/green]  [cyan]Username/mail on [/cyan] [green]{INSTANCES[login['host']]}[/green]")
    login["password"] = Prompt.ask("[green]\\[+][/green] [cyan] Password[/cyan] [red](it is invisible for security reasons)[/red]", password=True)
    return login 
#On deconnecte le client avant toute nouvelle connexion
def deconnexion(silex_API_Client) -> bool:
    if 'Authorization' in silex_API_Client.default_headers:
        try:
            silex.AuthenticationApi(silex_API_Client).logout
            if 'Authorization' in silex_API_Client.default_headers:
                del silex_API_Client.default_headers['Authorization']
            #console.print("[bold green]Successfully disconnected[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Error durring disconnection : {e}[/bold red]")
            return False
    return True
#Je verifie que l'utilisateur a accès à internet.
def check_connection_internet():
    # initializing URL
    url = "https://www.aube-asso.org/"
    timeout = 10
    try:
        # requesting URL
        requests.get(url,timeout=timeout)
        return
    # catching exception
    except (requests.ConnectionError,requests.Timeout):
        sys.exit("You are not connected to internet :( \n Please check your connection and try again.")    
#Check rapide de la connexion
def is_connected(silex_API_Client) -> bool:
    if silex_API_Client is not None and 'Authorization' in silex_API_Client.default_headers:
        return True
    return False
#Connexion et gestion des erreurs de connexion
def connexion(login, silex_API_Client) -> bool:
    deconnexion(silex_API_Client)
    try:
        silex_API_Client.connect_to_opensilex_ws(**login)#Connexion avec le login reçu via la CLI

        return True

    except Exception as e:
        error_str = str(e) #exception sous string
        try:
            if "HTTP response body:" in error_str:
                json_part = error_str.split("HTTP response body:")[1].strip() #on garde seulement le json
                error_data = json.loads(json_part)
                Prompt.ask(f"[red]{error_data['result']['message']}[/red]") # j'affiche seulement le lessage d'erreur renvoyé ("utilisateur inconnu etc..")
            else:
                Prompt.ask(f"[red]error : {error_str}[/red]") # si je reçois qqc de bizarre
            return False

        except (json.JSONDecodeError, KeyError, IndexError):
            Prompt.ask(f"error is impossible to decode : {error_str}")#si je reçois qqc de vraiment bizarre
            return False