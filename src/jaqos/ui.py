import os
from jaqos.__init__ import __version__
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich.table import Table

console = Console()

BANNER = f"""[green]
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⣶⣶⠿⠿⠿⠿⠿⠿⠿⣶⣶⣤⣀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣠⣴⡿⠟⠋⠁⠀⠀⣴⣶⣄⡀⠀⠀⠀⠈⠉⠛⢿⣦⣄⠀⠀⠀⠀⠀
⠀⠀⠀⣠⣾⠟⠉⠀⠀⠀⠀⢀⣾⡟⢻⣿⠿⣷⣤⣀⠀⠀⠀⠀⠈⠻⣷⣄⠀⠀⠀
⠀⠀⣴⡿⠁⠀⠀⠀⠀⠀⢠⣾⠏⠀⠀⢻⣧⡀⠙⠻⢷⣦⣄⠀⠀⠀⠈⢿⣦⠀⠀
⠀⣼⡟⠀⠀⠀⠀⠀⠀⣰⣿⠃⠀⠀⠀⠀⢻⣷⡀⠀⠀⠉⠛⢿⣶⠀⠀⠀⢻⣧⠀
⣸⡿⠀⠀⠀⠀⠀⠀⣴⡿⠁⠀⠀⠀⠀⠀⠀⢻⣷⡀⠀⠀⣴⣿⣿⡆⠀⠀⠀⢿⡇
⣿⡇⠀⠀⠀⠀⢀⣾⡟⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣷⣠⣾⠟⠁⢿⣇⠀⠀⠀⢸⣿
⣿⡁⠀⠀⠀⢠⣿⢏⣀⣀⣀⣠⣤⣤⣤⣤⣶⣶⣶⣿⣿⣧⣤⣀⣸⣿⠀⠀⠀⢸⣿    [cyan]⊹₊˚‧︵‿₊୨ [bold green]Bienvenue sur OpenSilexScript [cyan]୧₊‿︵‧˚₊⊹[green]
⣿⡇⠀⠀⠀⢿⣿⣿⣿⣟⣛⠋⠉⠉⠉⠉⠀⠀⠀⢸⣿⠈⠉⠛⢻⣿⠀⠀⠀⢸⣿
⢹⣷⠀⠀⠀⠈⢿⣯⠉⠙⠛⠿⢷⣶⣤⣄⣀⠀⠀⢸⣿⠀⠀⣰⡿⠃⠀⠀⠀⣾⡏
⠀⢿⣧⠀⠀⠀⠈⢿⣧⠀⠀⠀⠀⠀⠉⠙⠛⠿⣷⣾⣿⠀⣴⡿⠁⠀⠀⠀⣼⡿⠀
⠀⠈⢻⣧⡀⠀⠀⠀⢻⣧⠀⠀⠀⢀⣠⣤⣶⡿⠟⢻⣿⣼⡟⠁⠀⠀⢀⣼⡟⠁⠀
⠀⠀⠀⠙⢿⣦⡀⠀⠀⢻⣷⣴⣾⣿⣛⣉⣀⣀⣀⣸⣿⡟⠀⠀⢀⣴⣿⠏⠀⠀⠀
⠀⠀⠀⠀⠀⠙⢿⣶⣤⣀⠛⠛⠛⠛⠛⠛⠛⠛⠛⠛⠛⣀⣤⣶⡿⠋⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠈⠙⠻⠿⣷⣶⣦⣤⣤⣤⣴⣶⣾⠿⠟⠋⠁⠀⠀⠀⠀⠀⠀⠀         

⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
  \\[+] Script pour la création & modification de données sur Opensilex
  [cyan]\\[+] Veuillez sélectionner une des options en tapant un numéro puis 'enter'
  [yellow]\\[+] Connectez-vous pour commencer[/yellow]

    [white]VERSION[/white]    = [bold green]{__version__} MIAPPE & RICH[/bold green]
  [white]VERSION-PHIS[/white] = [bold green]1.4[/bold green]
    [white]Made By[/white]    = [bold green]•┈••✦ Edelweiss ✦••┈•[/bold green]
"""

MENU_CREATION = """
[bold]Veuillez suivre l'ordre de création (ou compléter en fonction de ceux déjà existants)[/bold]
  [red]\\[1][/red] Je souhaite créer une expérience.
  [green]\\[2][/green] Je souhaite créer un/des germplasms.
  [cyan]\\[3][/cyan] Je souhaite créer des facteurs.
  [yellow]\\[4][/yellow] Je souhaite créer des objets scientifiques.
  [magenta]\\[5][/magenta] Je souhaite importer des images.
  [green]\\[6][/green] Toutes les options ci-dessus.
  [green]\\[6][/green] Importer des données.
  [red]\\[9][/red] Je souhaite retourner au menu de base.
"""

def menu(etat):
    menu_text = f"""[green]
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⢀⣠⡴⠖⠛⣛⠛⠛⠛⠲⢦⣄⡀⠀⠀⠀
    ⠀⢀⣴⠟⠁⠀⠀⣴⠟⣿⠶⣤⡀⠀⠈⠻⣦⡀⠀
    ⢀⡾⠁⠀⠀⢀⡼⠃⠀⠘⣧⠈⠙⠳⢦⡀⠈⢷⡀
    ⣾⠁⠀⠀⢠⡞⠁⠀⠀⠀⠘⣧⠀⣴⠿⡇⠀⠈⣷
    ⣿⠀⠀⣰⣟⣀⣠⣤⣤⡤⠤⠾⣿⣥⣄⣿⠀⠀⣿   [bold white]{etat}[/bold white]
    ⢿⡀⠀⠹⣟⠳⠶⣤⣄⣀⠀⠀⣿⠀⣨⡟⠀⢀⡿   
    ⠘⢧⡀⠀⠹⣆⠀⠀⠀⢉⣹⣷⣿⣰⠏⠀⢀⡼⠃
    ⠀⠈⠳⣄⡀⠘⣧⣴⣞⣋⣁⣀⣿⠋⢀⣠⠞⠁⠀
    ⠀⠀⠀⠈⠙⠶⢦⣤⣄⣀⣠⣤⡴⠶⠛⠁⠀
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/green]
    [red]\\[1][/red] Je souhaite me connecter.
    [green]\\[2][/green] Je souhaite chercher une expérience.
    [cyan]\\[3][/cyan] Je souhaite importer des données...
    [yellow]\\[4][/yellow] Je souhaite Importer des images.
    [magenta]\\[5][/magenta] Je souhaite ajouter/modifier des données.
    [blue]\\[6][/blue] Ipsum.
    [red]\\[7][/red] Dolor.
    [green]\\[8][/green] Sit Amet.
    [cyan]\\[9][/cyan] Je souhaite quitter le client.
    """
    console.print(Panel(menu_text, title="[bold]Menu Principal[/bold]", border_style="cyan", expand=False))

def choix_repertoire_travail():
    working_dir_path = Prompt.ask("[cyan]Veuillez coller le chemin d'accès COMPLET qui mène au répertoire parent de vos experiences (ctrl+maj+V dans la console)[/cyan]\n")
    working_dir = os.path.normpath(rf"{working_dir_path}")
    
    liste_dossiers = os.listdir(working_dir)
    nombre = len(liste_dossiers)
    
    table = Table(title="Dossiers trouvés", header_style="bold magenta")
    table.add_column("Index", style="cyan")
    table.add_column("Nom", style="green")
    for index, nom in enumerate(liste_dossiers):
        table.add_row(str(index), nom)
    console.print(table)
    
    while True:
        choix_exp = IntPrompt.ask(f"[green]Choisissez le dossier qui contient votre expérience (0-{nombre-1})[/green]")
        if 0 <= choix_exp < nombre:
            choix_dossier = liste_dossiers[choix_exp]
            wd_experience = os.path.join(working_dir, choix_dossier)
            console.print(f"[cyan]Votre répertoire de travail est :[/cyan] [bold green]{wd_experience}[/bold green]")

            listedfiles = os.listdir(wd_experience)
            nombre_fichiers = len(listedfiles)
            
            table_fichiers = Table(title="Fichiers trouvés", header_style="bold magenta")
            table_fichiers.add_column("Index", style="cyan")
            table_fichiers.add_column("Nom", style="yellow")
            for index, nom in enumerate(listedfiles):
                table_fichiers.add_row(str(index), nom)
            console.print(table_fichiers)
            
            while True:
                choix_temp = IntPrompt.ask(f"[green]Choisissez le template miappe rempli (0-{nombre_fichiers-1})[/green]")
                if 0 <= choix_temp < nombre_fichiers:
                    choix_doc = listedfiles[choix_temp]
                    console.print(f"[cyan]Votre document miappe est :[/cyan] [bold green]{choix_doc}[/bold green]")
                    document_miappe = os.path.join(wd_experience, choix_doc)
                    break
                else:
                    console.print("[bold red]La sélection est incorrecte..[/bold red]")
            console.print(table_fichiers)
            while True:
                choix_temp = IntPrompt.ask(f"[green]Choisissez le fichier qui contient vos données tabulaires (0-{nombre_fichiers-1})[/green]")
                if 0 <= choix_temp < nombre_fichiers:
                    choix_data = listedfiles[choix_temp]
                    console.print(f"[cyan]Vos données tabulaires sont dans :[/cyan] [bold green]{choix_data}[/bold green]")
                    document_data = os.path.join(wd_experience, choix_data)
                    return wd_experience,choix_dossier,document_miappe,document_data
                else:
                    console.print("[bold red]La sélection est incorrecte..[/bold red]")
        else:
            console.print("[bold red]La sélection est incorrecte..[/bold red]")