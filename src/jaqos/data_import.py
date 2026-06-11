import sys
import os
from lxml import etree as ET
import pandas as pd
import opensilexClientToolsPython as silex
from rich.progress import track
from rich.table import Table
from jaqos.ui import console
from datetime import datetime

def create_factor(document_miappe, silex_API_Client):
    #getting experiment name
    dataframe = pd.read_excel(document_miappe, sheet_name=2, header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    NameExp = dataframe['name'].dropna().iloc[0]

    #getting factors
    console.print(f"[cyan]Fichier :[/cyan] {document_miappe}")
    dataframe = pd.read_excel(document_miappe, sheet_name=6, header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    Fac_Api = silex.FactorsApi(silex_API_Client)
    Factors_uri = {}
    Factors_Levels_uri = {}
    
    Exp_Api = silex.ExperimentsApi(silex_API_Client)
    Exp_Src = Exp_Api.search_experiments(name=NameExp)["result"]
    NameExp_uri = {NameExp: Exp_Src[0].uri}

    for row in track(list(dataframe.to_dict('records')), description="[green]Importing factors...[/green]"):
    
        factor = str(row["name"]).strip() if pd.notna(row["name"]) else ""
        levels = list(str(row["levels"]).strip().split(",")) if pd.notna(row["levels"]) else []
        description = row["description"]  if pd.notna(row["description"]) else None

        Fac_Src = Fac_Api.search_factors(name=factor, experiment=NameExp_uri[NameExp])["result"]
        if Fac_Src:
            Factors_uri[factor] = Fac_Src[0].uri
        else:
            DTO_list = []
            for level in levels:
                DTO_list.append(silex.FactorLevelCreationDTO(name=level))  
            body = silex.FactorCreationDTO(name=str(factor), levels=DTO_list, experiment=NameExp_uri[NameExp], description=str(description))
            Api_Resp = Fac_Api.create_factor(body=body)
            Fac_Src = Fac_Api.search_factors(name=factor, experiment=NameExp_uri[NameExp])["result"]
            Factors_uri[factor] = Fac_Src[0].uri

    for fac_uri in Factors_uri.values():
        Fac_Get = Fac_Api.get_factor_levels(uri=fac_uri)["result"]
        for lvl in Fac_Get:
            Factors_Levels_uri[lvl.name] = lvl.uri

    table = Table(title="Facteurs", show_header=False)
    table.add_column("Index", style="cyan")
    table.add_column("Nom", style="green")
    for factor in Factors_uri:
        table.add_row(factor, Factors_uri[factor])
    console.print(table)

    table = Table(title="Niveau facteurs", show_header=False)
    table.add_column("Index", style="cyan")
    table.add_column("Nom", style="green")
    for lvl in Factors_Levels_uri:
        table.add_row(lvl,Factors_Levels_uri[lvl])
    console.print(table)

    return Factors_Levels_uri, Factors_uri

def create_germplasm(document_miappe, silex_API_Client):
    console.print(f"[cyan]Miappe file :[/cyan] {document_miappe}")
    dataframe = pd.read_excel(document_miappe, sheet_name=4, header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    Germ_Api = silex.GermplasmApi(silex_API_Client)
    Species_uri = {}
    Germplasms_uri = {}

    for row in track(list(dataframe.to_dict('records')), description="[green]Importing germplasms...[/green]"):
        germ_name = row["name"]
        germ_species = row["species"]
        germ_type_species = row["RDF_Type_Species"]
        germ_type_germplasm = row["rdf_type"]
        public = bool(row["is_public"])

        if germ_name not in Species_uri:
            Germ_Src = Germ_Api.search_germplasm(name=f"^{germ_species}$", rdf_type=germ_type_species)["result"]
            if not Germ_Src:
                body = silex.GermplasmCreationDTO(name=germ_species, rdf_type=germ_type_species, is_public=public)
                Germ_Api.create_germplasm(body=body, check_only=False)
                Germ_Src = Germ_Api.search_germplasm(name=f"^{germ_species}$", rdf_type=germ_type_species)["result"]
            Species_uri[germ_species] = Germ_Src[0].uri

        if germ_name not in Germplasms_uri:
            Germ_Src = Germ_Api.search_germplasm(name=f"^{germ_name}$", rdf_type=germ_type_germplasm)["result"]
            if not Germ_Src:
                row.pop('RDF_Type_Species', None)
                row.pop('Species', None)
                row['species'] = Species_uri[germ_species]
                body = silex.GermplasmCreationDTO(**row)
                Germ_Api.create_germplasm(body=body, check_only=False)
                Germ_Src = Germ_Api.search_germplasm(name=f"^{germ_name}$", rdf_type=germ_type_germplasm)["result"]
            Germplasms_uri[germ_name] = Germ_Src[0].uri

    table = Table(title="Varieties", show_header=False)
    table.add_column("Index", style="cyan")
    table.add_column("Nom", style="green")
    for germplasm in Germplasms_uri:
        table.add_row(germplasm, Germplasms_uri[germplasm])
    console.print(table)

    table = Table(title="Species", show_header=False)
    table.add_column("Index", style="cyan")
    table.add_column("Nom", style="green")
    for species in Species_uri:
        table.add_row((species),Species_uri[species])
    console.print(table)

    return Germplasms_uri, Species_uri

def create_sci_obj(document_data,document_miappe,silex_API_Client):
    # Récupération du excel page experiment
    dataframe = pd.read_excel(document_miappe, sheet_name=2, header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    NameExp = dataframe['name'].dropna().iloc[0]
    StartExp = dataframe['start_date'].dropna().iloc[0]
    EndExp = dataframe['end_date'].dropna().iloc[0]
    BioMat_Type=dataframe['scientifc_object_type'].dropna().iloc[0]
    BioMat_Type=list(map(str.strip, BioMat_Type.split(",")))
    #Ici on récupère les données tabulaires pour créer les objets scientifiques. on choisit de lire du début du doc jusqu'au PID (à adapter)
    df_data = pd.read_excel(document_data)
    PID = df_data['PID'].unique()[0]
    console.print(f'[bold cyan]PID found:[/bold cyan] {PID}')
    #on garde seulement les tray id uniques
    df_ScObj = df_data.loc[:, "Tray ID":"PID"].drop_duplicates()
    Relations_Gen = []
    #on cherche si l'expérience éxiste pour en extraire l'uri
    Exp_Src = silex.ExperimentsApi(silex_API_Client).search_experiments(name=NameExp)
    NameExp_uri = {NameExp: Exp_Src["result"][0].uri}
    #Récupérer un dictionnaire de facteurs levels pour cette experience
    api_response = silex.ExperimentsApi(silex_API_Client).get_available_factors(Exp_Src["result"][0].uri, )
    #print(api_response["result"])
    if api_response["result"]:
        Factors_Levels_uri={}
        for resultat in api_response["result"]:
            for factor_level in resultat.levels :
                Factors_Levels_uri[factor_level.name]=factor_level.uri
    #console.print(f"facteurs liés à l'experience trouvés : {Factors_Levels_uri}")
    else :
        Factors_Levels_uri,_= create_factor(document_miappe, silex_API_Client)

    # création des relations
    if Exp_Src is None:
        console.print(f"[bold red]This experiment doesn't exist, please check if the same is correct : {NameExp}[/bold red]")
        sys.exit()
    #on check les différents points qu'on veut garder pour les metadata des sciobj (start date,end date,material type)
    if StartExp:
        relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasCreationDate", value=StartExp)
        Relations_Gen.append(relation_temp)
    else:
        console.print('[bold yellow]Start Date Missing[/bold yellow]')
    if EndExp:
        relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasDestructionDate", value=EndExp)
        Relations_Gen.append(relation_temp)
    else:
        console.print('[bold yellow]End Date Missing[/bold yellow]')
    if not BioMat_Type:
        sys.exit("Scientific Object RDF Type Missing")
    else:
        for biomat in BioMat_Type:
            Onto_Api = silex.OntologyApi(silex_API_Client)
            Onto_Src = Onto_Api.search_sub_classes_of(name=biomat, parent_type="vocabulary:ScientificObject")["result"]
            if Onto_Src:
                rdf_type = Onto_Src[0].children[0].uri
            else:
                sys.exit("Scientific Object RDF Type Unknown")
    #on initialise des variables, dont celle qui servira à écrire le excel
    ScObj_Api = silex.ScientificObjectsApi(silex_API_Client)
    ScObj_uri = {}
    dtos_to_export = []
    dico_germplasm={}
    created_sci_obj=0
    #on envoie pour chaque ligne de la df scobj(sans les duplicatas)
    for row in track(list(df_ScObj.to_dict('records')), description="[green]Processing Sci_Obj...[/green]"):
        row["Tray ID"] = row["Tray ID"] + "vitesse"#test
        ScObj_Src = ScObj_Api.search_scientific_objects(name=row["Tray ID"])["result"] # on vérifie si l'objet scientifique existe
        if ScObj_Src:
            ScObj_uri.update({row["Tray ID"]: ScObj_Src[0].uri})
        else:
            Relations_ScObj = []
            #ici on à la logique de vérification des germplasmes dans les objets scientifiques, on vérifie si il est dans la liste des germplasmes connus, et si oui on prends son uri
            if row["Germplasm"]:
                if row["Germplasm"] not in dico_germplasm.keys():
                    Germ_Src = silex.GermplasmApi(silex_API_Client).search_germplasm(name=f"^{row["Germplasm"]}$")["result"]
                    if Germ_Src:
                        dico_germplasm[row["Germplasm"]] = Germ_Src[0].uri
                        germplasm_value=dico_germplasm[row["Germplasm"]]
                        relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasGermplasm", value=germplasm_value)
                        Relations_ScObj.append(relation_temp)
                        console.print(f"[bold green]  Germplasm [cyan]{row['Germplasm']}[/cyan] found[/bold green]")
                    else:
                        console.print(f"[bold red] Germplasm [cyan]{row['Germplasm']}[/cyan] cannot be found, please check for typos or if they exist.[/bold red]")
                        console.print("[bold red] Fermeture du client [/bold red]")
                        sys.exit()
                else:
                    germplasm_value=dico_germplasm[row["Germplasm"]]
                    relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasGermplasm", value=germplasm_value)
                    Relations_ScObj.append(relation_temp)
            #on récupère les uri des niveaux de facteur

            if Factors_Levels_uri and row["Factor Level"]:
                if row["Factor Level"] not in Factors_Levels_uri:
                    console.print("[bold red]\n The factor level was not found.\n Starting factor import from the MIAPPE document\n[/bold red]")
                    Factors_Levels_uri, _ = create_factor(document_miappe, silex_API_Client)
                    
                    if row["Factor Level"] not in Factors_Levels_uri:
                        console.print(f"[bold red] This factor level : [cyan]{row['Factor Level']}[/cyan] cannot be found, please check for typos or if they really exist.[/bold red]")
                        console.print("[bold red] Exiting client [/bold red]")
                        sys.exit()
                else:
                    factor_level_value = Factors_Levels_uri.get(row["Factor Level"])
                    relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasFactorLevel", value=factor_level_value)
                    Relations_ScObj.append(relation_temp)

            #on concatène les infos générales et les uri des germplasmes/facteurs puis on envoie le body et on le stock dans un dictionnaire
            Relations = Relations_Gen + Relations_ScObj
            body = silex.ScientificObjectCreationDTO(name=row["Tray ID"], rdf_type=rdf_type, relations=Relations, experiment=NameExp_uri[NameExp])
            ScObj_Api.create_scientific_object(body,)
            ScObj_Src = ScObj_Api.search_scientific_objects(name=row["Tray ID"])["result"]
            ScObj_uri.update({row["Tray ID"]: ScObj_Src[0].uri})

            dtos_to_export.append({
                "studyId": body.experiment,
                "obsUnitType": body.rdf_type,
                "obsUnitId": ScObj_Src[0].uri,
                "externalId": body.name,
                "biologicalMaterialId": germplasm_value if germplasm_value else None,
                "obsUnitFactorValue": factor_level_value if factor_level_value else None,
                "Date Import": datetime.today().strftime('%Y-%m-%d %H:%M'),
            })
            created_sci_obj+=1
    #écriture des metadata des objets scientifiques sur le excel 
    if dtos_to_export:
        fichier_excel = "/home/edelweiss/Documents/JAQOS/exp_database/test_JAQOS/output/miappe_template_filled.xlsx"#A cahnger pour ne pas le hardcode..
        df_export = pd.DataFrame(dtos_to_export)
        df_precedent = pd.read_excel(fichier_excel, sheet_name="scientific object")
        df_final = pd.concat([df_precedent, df_export])
        with pd.ExcelWriter(fichier_excel, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df_final.to_excel(writer, sheet_name="scientific object", index=False)
        console.print("[bold green]The scientific object sheet was sucessfuly created/edited.[/bold green]")
    console.print(f"[bold green]End of import : {len(ScObj_uri)-created_sci_obj} found,{created_sci_obj} created. [/bold green]")
    return ScObj_uri
