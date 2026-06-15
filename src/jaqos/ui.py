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
⣿⡁⠀⠀⠀⢠⣿⢏⣀⣀⣀⣠⣤⣤⣤⣤⣶⣶⣶⣿⣿⣧⣤⣀⣸⣿⠀⠀⠀⢸⣿    [cyan]⊹₊˚‧︵‿₊୨ [bold green]Welcome on JAQOS [cyan]୧₊‿︵‧˚₊⊹[green]
⣿⡇⠀⠀⠀⢿⣿⣿⣿⣟⣛⠋⠉⠉⠉⠉⠀⠀⠀⢸⣿⠈⠉⠛⢻⣿⠀⠀⠀⢸⣿
⢹⣷⠀⠀⠀⠈⢿⣯⠉⠙⠛⠿⢷⣶⣤⣄⣀⠀⠀⢸⣿⠀⠀⣰⡿⠃⠀⠀⠀⣾⡏
⠀⢿⣧⠀⠀⠀⠈⢿⣧⠀⠀⠀⠀⠀⠉⠙⠛⠿⣷⣾⣿⠀⣴⡿⠁⠀⠀⠀⣼⡿⠀
⠀⠈⢻⣧⡀⠀⠀⠀⢻⣧⠀⠀⠀⢀⣠⣤⣶⡿⠟⢻⣿⣼⡟⠁⠀⠀⢀⣼⡟⠁⠀
⠀⠀⠀⠙⢿⣦⡀⠀⠀⢻⣷⣴⣾⣿⣛⣉⣀⣀⣀⣸⣿⡟⠀⠀⢀⣴⣿⠏⠀⠀⠀
⠀⠀⠀⠀⠀⠙⢿⣶⣤⣀⠛⠛⠛⠛⠛⠛⠛⠛⠛⠛⠛⣀⣤⣶⡿⠋⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠈⠙⠻⠿⣷⣶⣦⣤⣤⣤⣴⣶⣾⠿⠟⠋⠁⠀⠀⠀⠀⠀⠀⠀       

  \\[+] JAQOS A Quick Opensilex Script
  [cyan]\\[+] You can chose an option by typing the associated number and pressing 'enter'
  [yellow]\\[+] You will be logged as a guest by default, you can log in to change user.[/yellow]
  [green]\\[+] Please read the README.md file available on the github for guidance.
  
  [white]VERSION-JAQOS[/white]     = [bold green]{__version__} MIAPPE & RICH & ENGLISH[/bold green]
  [white]VERSION-OpenSilex[/white] = [bold green]1.5.1-HOTFIX[/bold green]
  [white]VERSION-MIAPPE[/white]    = [bold green]1.2[/bold green]
  [white]Made By[/white]           = [bold green]•┈••✦ Edelweiss ✦••┈•[/bold green]
"""

MENU_CREATION = """
  [red]\\[1][/red] I want to create an experiment. 
  [green]\\[2][/green] I want to create one or more germplasms.
  [cyan]\\[3][/cyan] I want to create factors with factor levels for this experiment.
  [yellow]\\[4][/yellow] I want to create scientific objects for this experiment.
  [magenta]\\[5][/magenta] I want to import images. 
  [green]\\[6][/green] All of the above.
  [green]\\[7][/green] Import tabular data.
  [red]\\[9][/red] I want to return to the main menu...
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
    [red]\\[1][/red] Log in.
    [green]\\[2][/green] Look up experiment info.
    [cyan]\\[3][/cyan] I want to create experiment/factors/scientific object...
    [yellow]\\[4][/yellow] Help.
    [cyan]\\[9][/cyan] Quit the client.
    """
    console.print(Panel(menu_text, title="[bold]Main Menu[/bold]", border_style="cyan", expand=False))

def choix_repertoire_travail():
    working_dir_path = Prompt.ask("[cyan]Please paste the complete ABSOLUTE file path to the parent directory of your experiments.[/cyan]\n[magenta](use ctrl+maj+V when pasting in the console)[/magenta]\n")
    working_dir = os.path.normpath(rf"{working_dir_path}")
    
    liste_dossiers = os.listdir(working_dir)
    nombre = len(liste_dossiers)
    
    table = Table(title="Files found !", header_style="bold magenta")
    table.add_column("Index", style="cyan")
    table.add_column("Nom", style="green")
    for index, nom in enumerate(liste_dossiers):
        table.add_row(str(index), nom)
    console.print(table)
    
    while True:
        choix_exp = IntPrompt.ask(f"[green]Chose the file containing your experiment : (0-{nombre-1})[/green]")
        if 0 <= choix_exp < nombre:
            choix_dossier = liste_dossiers[choix_exp]
            wd_experience = os.path.join(working_dir, choix_dossier)
            console.print(f"[cyan]Your working directory is now :[/cyan] [bold green]{wd_experience}[/bold green]")

            listedfiles = os.listdir(wd_experience)
            nombre_fichiers = len(listedfiles)
            
            table_fichiers = Table(title="Files found !", header_style="bold magenta")
            table_fichiers.add_column("Index", style="cyan")
            table_fichiers.add_column("Nom", style="yellow")
            for index, nom in enumerate(listedfiles):
                table_fichiers.add_row(str(index), nom)
            console.print(table_fichiers)
            
            while True:
                choix_temp = IntPrompt.ask(f"[green]Please chose the filled MIAPPE template (0-{nombre_fichiers-1})[/green]")
                if 0 <= choix_temp < nombre_fichiers:
                    choix_doc = listedfiles[choix_temp]
                    console.print(f"[cyan]Your MIAPPE template is :[/cyan] [bold green]{choix_doc}[/bold green]")
                    document_miappe = os.path.join(wd_experience, choix_doc)
                    break
                else:
                    console.print("[bold red]Incorrect selection... :([/bold red]")
            console.print(table_fichiers)
            while True:
                choix_temp = IntPrompt.ask(f"[green]Please chose the tabular data file (0-{nombre_fichiers-1})[/green]")
                if 0 <= choix_temp < nombre_fichiers:
                    choix_data = listedfiles[choix_temp]
                    console.print(f"[cyan]Your tabular data file is :[/cyan] [bold green]{choix_data}[/bold green]")
                    document_data = os.path.join(wd_experience, choix_data)
                    return wd_experience,choix_dossier,document_miappe,document_data
                else:
                    console.print("[bold red]Incorrect selection... :([/bold red]")
        else:
            console.print("[bold red]Incorrect selection... :([/bold red]")

def show_data_panel(panel_name,exp_data,names_to_attribute_map):
    details=""
    for name,attribut in names_to_attribute_map.items():
        value=getattr(exp_data,attribut,"NA")
        details= details + f"[bold cyan]{name}:[/bold cyan]{value}\n"
    console.print(Panel(details.strip(), title=f"[bold]{panel_name}[/bold]", border_style="green"))
    return

def show_data_table_dictionnaire(table_name,dictionnaire):
    table = Table(title=f"{table_name}", show_header=False)
    table.add_column("Index", style="cyan")
    table.add_column("Nom", style="green")
    for i in dictionnaire:
        table.add_row(i, dictionnaire[i])
    console.print(table)
    return