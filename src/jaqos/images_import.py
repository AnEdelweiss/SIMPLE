import sys
import os
import json
from lxml import etree as ET
import pandas as pd
import opensilexClientToolsPython as silex
from rich.progress import track
from rich.table import Table
from jaqos.ui import console
from jaqos.auth import connexion
from jaqos.data_import import create_sci_obj,create_provenances
import datetime
from rich.prompt import Prompt

def create_images(wd_experience,document_data,document_miappe,repertoire_photos,login,silex_API_Client):

    TimeStamp=link_image_time(document_data)
    prov_dict=create_provenances(document_data,document_miappe,silex_API_Client)
    ScObj_uri=create_sci_obj(document_data,document_miappe,silex_API_Client)
    import_images(document_miappe,document_data,wd_experience,TimeStamp,prov_dict,ScObj_uri,repertoire_photos,login,silex_API_Client)
    return prov_dict
    
def get_round_protocol_info(wd_experience,document_data):
        ### Get RoundProtocol Infos 
    Round_folder = os.path.join(wd_experience, '00-RoundProtocol')
    Round_files = []
    for (root, dirs, files) in os.walk(Round_folder):
        for name in files:
            Round_files.append(os.path.join(root, name))

    ## Link RoundProtocol wd with Experiment and Round Numbers 
    Exp_Rd_Dict = {}
    for wd_round in Round_files:
        Exp_Rd_temp = str.replace(wd_round, str(Round_folder+r"\RoundProtocol-"), "")
        Exp_Rd = str.replace(Exp_Rd_temp, ".txt", "")
        Exp_Rd_ls = Exp_Rd.split("121")
        Exp_Rd_Dict.update({wd_round: {"Experiment": Exp_Rd_ls[0], "Round": (Exp_Rd_ls[1][0:3]).replace("_","")}})
    ## Create Dictionary for all parameters 
    PlantMask = {}
    CamPos = {}
    df_data = pd.read_excel(document_data)
    PID = df_data['PID'].unique()[0]
    ## Transform RoundProtocol to xml 
    for key, value in Exp_Rd_Dict.items():
        with open(key) as file:
            xml_str = file.read().replace("\x00", "")
        root = ET.fromstring(xml_str)

    ## Get PlantMask Info for all rounds 
        PlantMask_rd = {}
        for child in root.iter(PID):
            for subchild in child.iter("PlantMask"):
                PlantMask_rd = {elem.tag: elem.text for elem in subchild}
                round_index = int(value["Round"])
                PlantMask[round_index] = PlantMask_rd

    # ## Get Camera Position Info for all rounds 
        CamPos_rd = {}
        for child in root.iter(PID):
            CamPos_rd.update(child.attrib)
        for child in root.iter(PID):
            for subchild in child.iter("Offset"):
                CamPos_rd.update({subchild.tag: subchild.text})
                round_index = int(value["Round"])
                CamPos[round_index] = CamPos_rd
    # console.print(PlantMask)
    # console.print(CamPos)
    console.print("[bold green]PlantMask and Camera Position Info found ![/bold green]")
    return CamPos,PlantMask

def link_image_time(document_data):
    
    df_data = pd.read_excel(document_data)
    desired_format = "%Y-%m-%dT%H:%M:%S%z"
    df_data['Measuring Date'] = df_data['Measuring Date'].dt.date
    df_data['Measuring Time'] = df_data['Measuring Time'].dt.tz_localize('UTC').dt.tz_convert('Europe/Helsinki').dt.strftime(desired_format)
    if 'Angle' in df_data.columns:
        df_data['Img Name'] = df_data.apply(lambda row: f"{row['Experiment ID']}-{row['Round Order']}-{row['Tray ID']}-{row['PID']}-{row['Angle']:03}", axis=1)
    else:
        df_data['Img Name'] = df_data.apply(lambda row: f"{row['Experiment ID']}-{row['Round Order']}-{row['Tray ID']}-{row['PID']}", axis=1)
    print(df_data['Img Name'])
    # Get Round Info in Dict 
    TimeStamp={}
    for index, row in df_data.iterrows():
        TimeStamp.update({row["Img Name"]: row['Measuring Time']})
    return TimeStamp

def parse_image_filename(filepath, timestamp_dict, prov_uri,pid):
    #Extrait metadata depuis le nom de fichier.
    filename = os.path.basename(filepath).split(".")[0]
    filename_clean = filename.replace("_FishEyeCorrected", "").replace("_FishEyeMasked", "")
    
    parts = filename_clean.replace("_", "-").split("-")
    
    print(parts)
    tray_id = f"{parts[8]}_{parts[9]}_{parts[10]}_{parts[11]}"
    print(tray_id)
    if len(parts)>=14:
        parts[13] = parts[13].replace("A", "")
        date_key = f"{parts[0]}-{parts[1]}-{tray_id}-{parts[12]}-{parts[13]}"
    else :
        date_key = f"{parts[0]}-{parts[1]}-{tray_id}-{parts[12]}"
        print(date_key)
    
    metadata = {
        "Path": filepath,
        "Experiment ID": parts[0],
        "Round Order": parts[1],
        "Date": str(timestamp_dict[date_key]),
        "Tray ID": tray_id,
        "PID": parts[12],
        "Prov": prov_uri,
        "ImgType": filename.split("_")[-1]
    }
    
    if pid == 'RGB1':
        metadata["Angle"] = parts[13]
        
    return metadata

def get_existing_images(dat_api, prov_uri, exp_uri):
    # On prends le set de tuples (target, date, angle, round_order) existants
    dat_src = dat_api.get_data_file_descriptions_by_search(
        provenances=[prov_uri], experiments=[exp_uri], page_size=100000
    )["result"]
    
    return {
        (elts.target, elts._date, elts.provenance.settings.get("Camera Angle"), elts.metadata.get('Round Order'))
        for elts in dat_src
    }

def import_images(document_miappe,document_data,wd_experience,TimeStamp,prov_dict,ScObj_uri,repertoire_photos,login,silex_API_Client):
    #getting experiment uri
    connexion(login, silex_API_Client)
    dataframe = pd.read_excel(document_miappe, sheet_name="experiment", header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    NameExp = dataframe['name'].dropna().iloc[0]
    facility = str(dataframe['facilities'].iloc[0]).replace(",","_").replace(" ","_")
    Exp_Src = silex.ExperimentsApi(silex_API_Client).search_experiments(name=NameExp)["result"]
    exp_uri = Exp_Src[0].uri
    #GETTING PID
    df_data = pd.read_excel(document_data)
    pid = df_data['PID'].unique()[0]
    if 'Angle' not in df_data.columns:
        df_data["Angle"]=None

    console.print(f'[bold cyan]PID found:[/bold cyan] {pid}')
    #Liste des images
    wd_img = repertoire_photos
    ls_files = []
    for (root, dirs, files) in os.walk(wd_img):
        for filename in files:
            if filename.endswith(".png"):
                ls_files.append(os.path.join(root, filename))

    ls_fec = [x for x in ls_files if "_FishEyeCorrected" in x]
    ls_fem = [x for x in ls_files if "_FishEyeMasked" in x ]

    console.print(f'[bold cyan]Numbers of FEC Img:[/bold cyan] [bold green]{len(ls_fec)}\n[bold cyan]Numbers of FEM:[/bold cyan] [bold green]{len(ls_fem)}')    
    stop = Prompt.ask("[bold green]Do you want to continue to import images?[/bold green]", choices=["y", "n"], default="y")
    if stop =="n":
        console.print("[bold red]OK, exiting client ![/bold red]")
        sys.exit()
    #Fin de liste des images
    #Pour TESTS
    sorted_ls_fec=sorted(ls_fec)
    sorted_ls_fem=sorted(ls_fem)
    ls_fec = sorted_ls_fec[-6:-1] # On trie les deux listes dans l'ordre AZ puis on prends que les 5/10 derniers (en l'occurence les 5 derniers)
    ls_fem = sorted_ls_fem[-6:-1] # Et on utilise ça à la place de la giga-liste 
    print (ls_fec)
    print (ls_fem) 
    #Pour TESTS

    CamPos,PlantMask=get_round_protocol_info(wd_experience,document_data)
    print("protocol info ok")
    dat_api = silex.DataApi(silex_API_Client)
    #Traitement des images FishEyeCorrected (FEC)

    prov_fec = prov_dict[f'{facility}_{pid}_FishEyeCorrectedImages']
    print("prov_fec ok")
    corr_data = [parse_image_filename(f, TimeStamp, prov_fec, pid) for f in ls_fec]
    print("cor data ok")
    existing_fec_keys = get_existing_images(dat_api, prov_fec, exp_uri)
    print("existing_fec_key ok")

    corr_to_upload = [
        img for img in corr_data 
        if (ScObj_uri[img["Tray ID"]], img["Date"].replace('+', '.000+'), img.get("Angle"), img["Round Order"]) not in existing_fec_keys
    ]
    
    console.print(f"[bold green]{len(corr_data) - len(corr_to_upload)} [cyan]FEC existantes sur[/cyan] {len(corr_data)}[/bold green]")

    timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)
    
    for img in track(corr_to_upload, description="[bold green]Uploading FEC[/bold green]"):
        if datetime.datetime.now() > timelimit:
            connexion(login, silex_API_Client)
            timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)

        desc = {
            "rdf_type": "vocabulary:RGBImage",
            "date": img["Date"],
            "target": ScObj_uri[img["Tray ID"]],
            "metadata": {"Round Order": img["Round Order"]},
            "provenance": {
                "uri": img["Prov"],
                "settings": {
                    "Camera Angle": img["Angle"] if 'Angle' in img else None ,
                    "Camera Height": CamPos[int(img["Round Order"])]["height"],
                    "Offset": CamPos[int(img["Round Order"])]["Offset"]
                },
                "experiments": [exp_uri]
            }
        }
        dat_api.post_data_file(description=json.dumps(desc), file=img["Path"])
    #Création du dictionnaire de liaison FEC -> FEM
    fec_uri_map = {
        (elts.target, elts._date): elts.uri
        for elts in dat_api.get_data_file_descriptions_by_search(
            provenances=[prov_fec], experiments=[exp_uri], page_size=100000
        )["result"]
    }

    #Traitement des images FishEyeMasked (FEM)
    prov_fem = prov_dict[f'{facility}_{pid}_FishEyeMaskedImages']
    mask_data = [parse_image_filename(f, TimeStamp, prov_fem, pid) for f in ls_fem]
    
    # Association de l'URI parente
    for img in mask_data:
        target = ScObj_uri[img["Tray ID"]]
        date = img["Date"].replace('+', '.000+')
        img["Prov_Used"] = fec_uri_map.get((target, date))

    existing_fem_keys = get_existing_images(dat_api, prov_fem, exp_uri)

    mask_to_upload = [
        img for img in mask_data 
        if (ScObj_uri[img["Tray ID"]], img["Date"].replace('+', '.000+'), img.get("Angle"), img["Round Order"]) not in existing_fem_keys
    ]
    
    console.print(f"[bold green]Found {len(mask_data) - len(mask_to_upload)} [cyan]FEC on[/cyan] {len(mask_data)} total[/bold green]")

    for img in track(mask_to_upload, description="[bold blue]Uploading FEM[/bold blue]"):
        if datetime.datetime.now() > timelimit:
            connexion(login, silex_API_Client)
            timelimit = datetime.datetime.now() + datetime.timedelta(minutes=30)

        if "Angle" in img: 
            settings = {"Camera Angle": img["Angle"]}
        else:
            settings={"Camera Angle": None}

        settings.update(PlantMask[int(img["Round Order"])])

        desc = {
            "rdf_type": "vocabulary:RGBImage",
            "date": img["Date"],
            "target": ScObj_uri[img["Tray ID"]],
            "metadata": {"Round Order": img["Round Order"]},
            "provenance": {
                "uri": img["Prov"],
                "prov_used": [{"uri": img["Prov_Used"], "rdf_type": "vocabulary:RGBImage"}] if img.get("Prov_Used") else [],
                "settings": settings,
                "experiments": [exp_uri]
            }
        }
        dat_api.post_data_file(description=json.dumps(desc), file=img["Path"])

    console.print('[bold green]Suceeded in importing images ![/bold green]')
