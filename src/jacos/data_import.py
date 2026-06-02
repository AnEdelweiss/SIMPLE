import os
import sys
import yaml
import pandas as pd
import opensilexClientToolsPython as silex
from rich.progress import track
from rich.table import Table
from jacos.ui import console

def create_factor(document_miappe, silex_API_Client):
    #getting experiment name
    dataframe = pd.read_excel(document_miappe, sheet_name=2, header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    for index, row in dataframe.iterrows():
        row_dict = row.dropna().to_dict()
        NameExp = row_dict.get('name')

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

    for index, row in track(list(dataframe.iterrows()), description="[green]Importation des facteurs...[/green]"):
        row_dict = row.dropna().to_dict()
        factor = str(row_dict.get('name', '')).strip()
        levels = list(str(row_dict.get('levels')).strip().split(","))
        description = row_dict.get('description') 

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
            
    for factor in Factors_uri:
        console.print(f"[bold cyan]{factor}[/bold cyan] URI: {Factors_uri[factor]}")
    for lvl in Factors_Levels_uri:
        console.print(f"[bold yellow]{lvl}[/bold yellow] URI: {Factors_Levels_uri[lvl]}")
    return Factors_Levels_uri, Factors_uri

def create_germplasm(document_miappe, silex_API_Client):
    console.print(f"[cyan]Fichier :[/cyan] {document_miappe}")
    dataframe = pd.read_excel(document_miappe, sheet_name=4, header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    Germ_Api = silex.GermplasmApi(silex_API_Client)
    Species_uri = {}
    Germplasms_uri = {}

    for index, row in track(list(dataframe.iterrows()), description="[green]Importation des germplasmes...[/green]"):
        row_dict = row.dropna().to_dict()
        germ_name = row_dict.get('name') 
        germ_species = row_dict.get('species') 
        germ_type_species = row_dict.get('RDF_Type_Species') 
        germ_type_germplasm = row_dict.get('rdf_type')
        public = bool(row_dict.get('is_public'))

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
                row_dict.pop('RDF_Type_Species', None)
                row_dict.pop('Species', None)
                row_dict['species'] = Species_uri[germ_species]
                body = silex.GermplasmCreationDTO(**row_dict)
                Germ_Api.create_germplasm(body=body, check_only=False)
                Germ_Src = Germ_Api.search_germplasm(name=f"^{germ_name}$", rdf_type=germ_type_germplasm)["result"]
            Germplasms_uri[germ_name] = Germ_Src[0].uri

    # for germplasm in Germplasms_uri:
    #     console.print(f"[bold cyan]{germplasm}[/bold cyan] URI: {Germplasms_uri[germplasm]}")
    # for species in Species_uri:
    #     console.print(f"[bold yellow]{species}[/bold yellow] URI: {Species_uri[species]}")


    table = Table(title="Espèces", show_header=False)
    table.add_column("Index", style="cyan")
    table.add_column("Nom", style="green")
    for germplasm in Germplasms_uri:
        table.add_row(str(germplasm), str(Germplasms_uri[germplasm]))
    console.print(table)

    table = Table(title="Variétés", show_header=False)
    table.add_column("Index", style="cyan")
    table.add_column("Nom", style="green")
    for species in Species_uri:
        table.add_row(str(species),str(Species_uri[species]))
    console.print(table)

    return Germplasms_uri, Species_uri

def create_sci_obj(Factors_Levels_uri, Germplasms_uri, document_data,document_miappe,silex_API_Client):
    # EXCEL
    dataframe = pd.read_excel(document_miappe, sheet_name=2, header=1)
    dataframe.drop(dataframe.columns[dataframe.columns.str.contains('unnamed', case=False)], axis=1, inplace=True)
    
    for index, row in dataframe.iterrows():
        row_dict = row.dropna().to_dict()
        NameExp_uri = {}

        def to_list(key):
            val = row_dict.get(key)
            return list(map(str.strip, val.split(","))) if val else []

        NameExp = row_dict.get('name')
        StartExp = row_dict.get('start_date')
        EndExp = row_dict.get('end_date')
        BioMat_Type=to_list('scientifc_object_type')
    # EXCEL

    desired_format = "%Y-%m-%dT%H:%M:%S%z"

    df_data = pd.read_excel(os.path.join(NameExp, document_data))
    df_data['Measuring Date'] = df_data['Measuring Date'].dt.date
    df_data['Measuring Time'] = df_data['Measuring Time'].dt.tz_localize('UTC').dt.tz_convert('Europe/Helsinki').dt.strftime(desired_format)
    
    PID = df_data['PID'].unique()[0]
    console.print(f'[bold cyan]PID found:[/bold cyan] {PID}')

    df_ScObj = df_data.loc[:, "Tray ID":"PID"].drop_duplicates()
    Relations_Gen = []

    Exp_Src = silex.ExperimentsApi(silex_API_Client).search_experiments(name=NameExp)
    NameExp_uri = {NameExp: Exp_Src["result"][0].uri}

    if StartExp is not None:
        relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasCreationDate", value=StartExp)
        Relations_Gen.append(relation_temp)
    else:
        console.print('[bold yellow]Start Date Missing[/bold yellow]')

    if EndExp is not None:
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

    ScObj_Api = silex.ScientificObjectsApi(silex_API_Client)
    ScObj_uri = {}
    dtos_to_export = []
    
    for index, row in track(list(df_ScObj.iterrows()), description="[green]ScObj processing...[/green]"):
        row["Tray ID"] = row["Tray ID"] + "test_3"
        ScObj_Src = ScObj_Api.search_scientific_objects(name=row["Tray ID"])["result"]
        if ScObj_Src:
            ScObj_uri.update({row["Tray ID"]: ScObj_Src[0].uri})
        else:
            Relations_ScObj = []
            if Germplasms_uri:
                relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasGermplasm", value=Germplasms_uri.get(row["Germplasm"]))
                Relations_ScObj.append(relation_temp)

            if Factors_Levels_uri:
                relation_temp = silex.RDFObjectRelationDTO(_property="vocabulary:hasFactorLevel", value=Factors_Levels_uri.get(row["Factor Level"]))
                Relations_ScObj.append(relation_temp)
                
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
                "biologicalMaterialId": Relations_ScObj[0] if len(Relations_ScObj) > 0 else None,
                "obsUnitFactorValue": Relations_ScObj[1] if len(Relations_ScObj) > 1 else None,
            })

    if dtos_to_export:
        fichier_excel = "exp_database/test_JACOS/output/Test_OSC_x_MIAPPE.xlsx"
        df_export = pd.DataFrame(dtos_to_export)
        df_precedent = pd.read_excel(fichier_excel, sheet_name="scientific object")
        df_final = pd.concat([df_precedent, df_export])

        with pd.ExcelWriter(fichier_excel, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
            df_final.to_excel(writer, sheet_name="scientific object", index=False)
            
        console.print("[bold green]Excel mis à jour/créé avec succès.[/bold green]")

    console.print("[bold green]Opération terminée.[/bold green]")