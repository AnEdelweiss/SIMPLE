# JAQOS A Quick Opensilex script

This is a work in progress, feedbacks are welcome.

![picture of jaqos](jaqos.png)

## Description.

In the context of my internship, I am working on JAQOS, a Command Line Interface coded in python with a focus on ease of use, rapidity and flexibility. This tool will ( I hope ) help researchers uppload MIAPPE compliant phenotyping data on OpenSilex instances without any efforts. Allowing them to keep germplasm banks up to date, to create experiments, create or add scientific objects to an experiment, add pictures, DATA and more.

## Before the first run :

As of now, the file structure for using the script properly is the following :

```
exp_database/
├── experiment_1/
│   ├── tabular_data_file.xlsx
│   ├── Miappe_template.xlsx
│   ├── 00-RoundProtocol/
│   │   └── Round_protocol_files.txt
│   ├── output/
│   │   └── miappe_template_filled.xlsx
│   └── RGB1/
│       ├── FEC/
│       │   └── FEC_images.png
│       └── FEM/
│           └── FEM_images.png
├── experiment_2/
├── experiment_3/
└── experiment_4/
```

## The miappe file

as this is a work in progress, it currently only works with the current MIAPPE table provided in /exp_database/test_JAQOS/Miappe_Template.xlsx

## The tabular data

as this is a work in progress, it currently only works with the current tabular data provided in exp_database/test_JAQOS/RGB1_Morpho_Manual.xlsx

## Instructions for running (as of now) :

- git clone https://github.com/AnEdelweiss/JAQOS.git
- cd JAQOS
- uv pip install -r pyproject.toml
- uv run jaqos.

You can then use the provided dummy experiment in test_JAQOS, you can also modify the content of the miappe_template to try and create different experiments, germpasms etc...
Everything should work !

## Project roadmap :

- ~~Using the rich library.~~
- ~~English translation.~~
- ~~Photo upploadng.~~
- Data upploading.
- Generalization.
- Automatization(?)
