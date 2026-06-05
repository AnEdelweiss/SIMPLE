import opensilexClientToolsPython as silex
from jaqos.ui import console, Prompt
import json

# Initiatialisation des différentes instances
INSTANCES = {
    "https://opensilex.org/sandbox/rest": "Sandbox",
    "https://phis.emphasis.fedcloud.eu/uh/rest": "Helsinki/UH",
    "https://opensilex.org/demo2/rest": "test1.5.1"
}
#On deconnecte le client avant toute nouvelle connexion
def deconnexion(silex_API_Client) -> bool:
    if 'Authorization' in silex_API_Client.default_headers:
        try:
            silex.AuthenticationApi(silex_API_Client).logout
            if 'Authorization' in silex_API_Client.default_headers:
                del silex_API_Client.default_headers['Authorization']
            console.print("[bold green]Déconnexion réussie.[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Note: Erreur lors de la déconnexion : {e}[/bold red]")
            return False
    return True
#Check rapide de la connexion
def is_connected(silex_API_Client) -> bool:
    if silex_API_Client is not None and 'Authorization' in silex_API_Client.default_headers:
        return True
    return False
#Connexion et gestion des erreurs de connexion
def connexion(login, silex_API_Client) -> bool:
    deconnexion(silex_API_Client)
    try:
        silex_API_Client.connect_to_opensilex_ws(identifier=login['id'],password=login['mdp'],host=login["instance"])#Connexion avec le login reçu via la CLI
        return True

    except Exception as e:
        error_str = str(e) #exception sous string
        try:
            if "HTTP response body:" in error_str:
                json_part = error_str.split("HTTP response body:")[1].strip() #on garde seulement le json
                error_data = json.loads(json_part)
                Prompt.ask(f"[red]{error_data['result']['message']}[/red]") # j'affiche seulement le lessage d'erreur renvoyé ("utilisateur inconnu etc..")
            else:
                Prompt.ask(f"[red]Erreur brute : {error_str}[/red]") # si je reçois qqc de bizarre
            return False

        except (json.JSONDecodeError, KeyError, IndexError):
            Prompt.ask(f"Impossible de parser l'erreur. Erreur brute : {error_str}")#si je reçois qqc de vraiment bizarre
            return False
        
    
