import os

from rich.panel import Panel
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

from simple.__init__ import __version__
from simple.console import console
from simple.errors import SimpleBaseException
from simple.logging_setup import logger

BANNER = f"""[green]
⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠀⣀⣤⣶⣶⠿⠿⠿⠿⠿⠿⠿⣶⣶⣤⣀⠀⠀⠀⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⣠⣴⡿⠟⠋⠁⠀⠀⣴⣶⣄⡀⠀⠀⠀⠈⠉⠛⢿⣦⣄⠀⠀⠀⠀⠀
⠀⠀⠀⣠⣾⠟⠉⠀⠀⠀⠀⢀⣾⡟⢻⣿⠿⣷⣤⣀⠀⠀⠀⠀⠈⠻⣷⣄⠀⠀⠀
⠀⠀⣴⡿⠁⠀⠀⠀⠀⠀⢠⣾⠏⠀⠀⢻⣧⡀⠙⠻⢷⣦⣄⠀⠀⠀⠈⢿⣦⠀⠀
⠀⣼⡟⠀⠀⠀⠀⠀⠀⣰⣿⠃⠀⠀⠀⠀⢻⣷⡀⠀⠀⠉⠛⢿⣶⠀⠀⠀⢻⣧⠀
⣸⡿⠀⠀⠀⠀⠀⠀⣴⡿⠁⠀⠀⠀⠀⠀⠀⢻⣷⡀⠀⠀⣴⣿⣿⡆⠀⠀⠀⢿⡇
⣿⡇⠀⠀⠀⠀⢀⣾⡟⠀⠀⠀⠀⠀⠀⠀⠀⠀⢻⣷⣠⣾⠟⠁⢿⣇⠀⠀⠀⢸⣿
⣿⡁⠀⠀⠀⢠⣿⢏⣀⣀⣀⣠⣤⣤⣤⣤⣶⣶⣶⣿⣿⣧⣤⣀⣸⣿⠀⠀⠀⢸⣿    [cyan]⊹₊˚‧︵‿₊୨ [bold green]Welcome on SIMPLE [cyan]୧₊‿︵‧˚₊⊹[green]
⣿⡇⠀⠀⠀⢿⣿⣿⣿⣟⣛⠋⠉⠉⠉⠉⠀⠀⠀⢸⣿⠈⠉⠛⢻⣿⠀⠀⠀⢸⣿
⢹⣷⠀⠀⠀⠈⢿⣯⠉⠙⠛⠿⢷⣶⣤⣄⣀⠀⠀⢸⣿⠀⠀⣰⡿⠃⠀⠀⠀⣾⡏
⠀⢿⣧⠀⠀⠀⠈⢿⣧⠀⠀⠀⠀⠀⠉⠙⠛⠿⣷⣾⣿⠀⣴⡿⠁⠀⠀⠀⣼⡿⠀
⠀⠈⢻⣧⡀⠀⠀⠀⢻⣧⠀⠀⠀⢀⣠⣤⣶⡿⠟⢻⣿⣼⡟⠁⠀⠀⢀⣼⡟⠁⠀
⠀⠀⠀⠙⢿⣦⡀⠀⠀⢻⣷⣴⣾⣿⣛⣉⣀⣀⣀⣸⣿⡟⠀⠀⢀⣴⣿⠏⠀⠀⠀
⠀⠀⠀⠀⠀⠙⢿⣶⣤⣀⠛⠛⠛⠛⠛⠛⠛⠛⠛⠛⠛⣀⣤⣶⡿⠋⠀⠀⠀⠀⠀
⠀⠀⠀⠀⠀⠀⠀⠈⠙⠻⠿⣷⣶⣦⣤⣤⣤⣴⣶⣾⠿⠟⠋⠁⠀⠀⠀⠀⠀⠀⠀       

  \\[+] Simple Interface MIAPPE-Phis Lightweight & Efficient
  [cyan]\\[+] You can chose an option by typing the associated number and pressing 'enter'
  [yellow]\\[+] You will be logged as a guest by default, you can log in to change user.[/yellow]
  [green]\\[+] Please read the README.md file available on the github for guidance.
  
  [white]VERSION-SIMPLE[/white]    = [bold green]{__version__} Try out the gui ! [/bold green]
  [white]VERSION-OpenSilex[/white] = [bold green]1.5.2[/bold green]
  [white]VERSION-MIAPPE[/white]    = [bold green]1.2[/bold green]
  [white]Made By[/white]           = [bold green]•┈••✦ Edelweiss ✦••┈•[/bold green]
"""

MENU_CREATION = """
  [red]\\[1][/red] I want to create an experiment. 
  [green]\\[2][/green] I want to create/check germplasms.
  [cyan]\\[3][/cyan] I want to create/check factors for this experiment.
  [yellow]\\[4][/yellow] I want to create scientific objects for this experiment.
  [magenta]\\[5][/magenta] I want to import datafiles. 
  [green]\\[6][/green] I want to import tabular data.
  [green]\\[7][/green] All of the above.
  [green]\\[8][/green] Change tabular data file.
  [red]\\[9][/red] I want to return to the main menu...
"""
HELP_MENU = """
[bold red]Q. : What is SIMPLE?[/bold red]
[yellow]
A. : A Command Line Interface coded in python with a focus on ease of use, rapidity and flexibility.
This tool can help researchers uppload MIAPPE compliant phenotyping data on OpenSilex instances without any efforts.
Allowing them to keep germplasm banks up to date, to create experiments, create or add scientific objects to an experiment, add pictures, DATA and more.
[/yellow]
[bold red]Q. : How can I use SIMPLE ?
[yellow] 
A. : If you don't know yet how to use SIMPLE, please follow this link with the documentations : https://github.com/AnEdelweiss/SIMPLE/blob/master/README.md 

Here is a quick start :

1. Connect to the phis instance of your liking : 
    on the main menu, you can press '1' then enter.
    You can now select an instance, input your username and you password. Voilà, you are logged in !

2. Search infos about an experiment : 
    On the main menu, press '2' then enter.
    You can now enter the name of the experiment you are looking for!

3. Import data on PHIS : 
    On the main menu, press '3' then enter.
    You can now follow the instructions and enter the paths to your folders and files.
    (The recommended/correct arborescence is dispayed on the github.)
    You can now create anything, ranging from experiments to scientific objects.
    Please be careful when filling the MIAPPE file, as this one of the most crucial steps.[/yellow]
"""


def menu(status):
    menu_text = f"""[green]
    ⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀
    ⠀⠀⠀⢀⣠⡴⠖⠛⣛⠛⠛⠛⠲⢦⣄⡀⠀⠀⠀
    ⠀⢀⣴⠟⠁⠀⠀⣴⠟⣿⠶⣤⡀⠀⠈⠻⣦⡀⠀
    ⢀⡾⠁⠀⠀⢀⡼⠃⠀⠘⣧⠈⠙⠳⢦⡀⠈⢷⡀
    ⣾⠁⠀⠀⢠⡞⠁⠀⠀⠀⠘⣧⠀⣴⠿⡇⠀⠈⣷
    ⣿⠀⠀⣰⣟⣀⣠⣤⣤⡤⠤⠾⣿⣥⣄⣿⠀⠀⣿   [bold white]{status}[/bold white]
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
    console.print(
        Panel(
            menu_text, title="[bold]Main Menu[/bold]", border_style="cyan", expand=False
        )
    )


def choose_working_directory():

    working_dir_path = Prompt.ask(
        "[cyan]Please paste the complete ABSOLUTE file path to the parent directory of your experiments.[/cyan]\n[magenta](use ctrl+maj+V when pasting in the console)[/magenta]\n"
    )
    working_dir = os.path.normpath(rf"{working_dir_path}")
    try:
        folders = os.listdir(working_dir)
    except FileNotFoundError:
        logger.warning(f"{working_dir_path} doesn't exist")
        raise SimpleBaseException(
            f"{working_dir_path} was not found on your computer, please check for typos"
        )
    except PermissionError:
        logger.warning(f"user doesn't have reading permissions on {working_dir_path}")
        raise SimpleBaseException(
            f"You don't have the permission to read from {working_dir_path}"
        )
    count = len(folders)

    table = Table(title="Files found !", header_style="bold magenta")
    table.add_column("Index", style="cyan")
    table.add_column("Nom", style="green")
    for index, name in enumerate(folders):
        table.add_row(str(index), name)
    console.print(table)

    while True:
        experiment_choice = IntPrompt.ask(
            f"[green]Chose the file containing your experiment : (0-{count - 1})[/green]"
        )
        if 0 <= experiment_choice < count:
            chosen_folder = folders[experiment_choice]
            experiment_directory = os.path.join(working_dir, chosen_folder)
            console.print(
                f"[cyan]Your working directory is now :[/cyan] [bold green]{experiment_directory}[/bold green]"
            )

            listed_files = os.listdir(experiment_directory)
            file_count = len(listed_files)

            files_table = Table(title="Files found !", header_style="bold magenta")
            files_table.add_column("Index", style="cyan")
            files_table.add_column("Nom", style="yellow")
            for index, name in enumerate(listed_files):
                files_table.add_row(str(index), name)
            console.print(files_table)

            while True:
                selection = IntPrompt.ask(
                    f"[green]Please chose the filled MIAPPE template (0-{file_count - 1})[/green]"
                )
                if 0 <= selection < file_count:
                    miappe_name = listed_files[selection]
                    console.print(
                        f"[cyan]Your MIAPPE template is :[/cyan] [bold green]{miappe_name}[/bold green]"
                    )
                    miappe_path = os.path.join(experiment_directory, miappe_name)
                    break
                else:
                    console.print("[bold red]Incorrect selection... :([/bold red]")
            console.print(files_table)

            while True:
                selection = IntPrompt.ask(
                    f"[green]Please chose the tabular data file (0-{file_count - 1})[/green]"
                )
                if 0 <= selection < file_count:
                    selected_name = listed_files[selection]
                    console.print(
                        f"[cyan]Your tabular data file is :[/cyan] [bold green]{selected_name}[/bold green]"
                    )
                    data_path = os.path.join(experiment_directory, selected_name)
                    return experiment_directory, chosen_folder, miappe_path, data_path
        else:
            console.print("[bold red]Incorrect selection... :([/bold red]")


def choose_datafile_directory(experiment_directory):

    listed_files = os.listdir(experiment_directory)
    file_count = len(listed_files)

    files_table = Table(title="Files found !", header_style="bold magenta")
    files_table.add_column("Index", style="cyan")
    files_table.add_column("Nom", style="yellow")
    for index, name in enumerate(listed_files):
        files_table.add_row(str(index), name)
    console.print(files_table)

    while True:
        selection = IntPrompt.ask(
            f"[green]Please chose the folder containing the pictures you want to upload (0-{file_count - 1})[/green]"
        )
        if 0 <= selection < file_count:
            selected_name = listed_files[selection]
            console.print(
                f"[cyan]The folder is :[/cyan] [bold green]{selected_name}[/bold green]"
            )
            photos_directory = os.path.join(experiment_directory, selected_name)

            return experiment_directory, photos_directory
        else:
            console.print("[bold red]Incorrect selection... :([/bold red]")


def change_tabular_data(experiment_directory):

    listed_files = os.listdir(experiment_directory)
    file_count = len(listed_files)

    files_table = Table(title="Files found !", header_style="bold magenta")
    files_table.add_column("Index", style="cyan")
    files_table.add_column("Nom", style="yellow")
    for index, name in enumerate(listed_files):
        files_table.add_row(str(index), name)
    console.print(files_table)
    while True:
        selection = IntPrompt.ask(
            f"[green]Please chose the tabular data file (0-{file_count - 1})[/green]"
        )
        if 0 <= selection < file_count:
            selected_name = listed_files[selection]
            console.print(
                f"[cyan]Your tabular data file is :[/cyan] [bold green]{selected_name}[/bold green]"
            )
            data_path = os.path.join(experiment_directory, selected_name)
            break
    console.print(files_table)

    while True:
        selection = IntPrompt.ask(
            f"[green]Please chose the folder containing the pictures you want to upload (0-{file_count - 1})[/green]"
        )
        if 0 <= selection < file_count:
            selected_name = listed_files[selection]
            console.print(
                f"[cyan]The folder is :[/cyan] [bold green]{selected_name}[/bold green]"
            )
            photos_directory = os.path.join(experiment_directory, selected_name)

            return experiment_directory, data_path, photos_directory
        else:
            console.print("[bold red]Incorrect selection... :([/bold red]")


def show_data_panel(panel_name, exp_data, names_to_attribute_map):
    details = ""
    for name, attribut in names_to_attribute_map.items():
        value = getattr(exp_data, attribut, "NA")
        details = details + f"[bold cyan]{name}:[/bold cyan]{value}\n"
    console.print(
        Panel(details.strip(), title=f"[bold]{panel_name}[/bold]", border_style="green")
    )


def show_data_table_dictionary(table_name, dictionary):
    table = Table(title=f"{table_name}", show_header=False)
    table.add_column("Index", style="cyan")
    table.add_column("Nom", style="green")
    for i in dictionary:
        table.add_row(i, dictionary[i])
    console.print(table)
