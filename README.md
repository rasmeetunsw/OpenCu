# CuSCORE Paper Reproducibility Release

## Overview
This repository contains the paper-focused reproducibility release of the CuSCORE modelling framework used to evaluate cost and emissions across selected stages of the copper value chain.

The repository includes backend scripts for:
- ore extraction and concentration (mining)
- smelting and anode casting
- electrorefining
- rail transport
- marine shipping

This release is intended to reproduce the results reported in the associated manuscript. 

## Repository contents
```text
.
├── mining_paper_backend.py
├── smelting_paper_backend.py
├── electrorefining_paper_backend.py
├── rail_paper_backend.py
├── shipping_paper_backend.py
├── requirements.txt
└── README.md
```

## What is included
Included in this reproducibility release:
- backend calculation scripts required to reproduce the paper results
- embedded default assumptions used in the publication-ready baseline cases
- detailed cost and emissions breakdown outputs for each stage

## Software requirements
This codebase was prepared for Python 3.10+.

Install dependencies with:
```bash
pip install -r requirements.txt
```

## Running the scripts
Each stage can be run independently from the command line.

### Mining
```bash
python ore_extraction_and_concentration.py
```

### Smelting
```bash
python smelting_and_anode_casting_.py
```

### Electrorefining
```bash
python electrorefining.py
```

### Rail
```bash
python rail_transport.py
```

### Shipping
```bash
python marine_shipping.py
```

Each script prints:
- headline cost and emissions metrics
- detailed cost breakdowns
- detailed emissions breakdowns

## Reproducibility scope
This repository is a reproducibility release prepared for academic publication. It is designed to reproduce the results reported in the manuscript and provide transparency around the underlying calculations used in the published analysis.

## Manuscript
Associated manuscript:
**OpenCu: An Open-Source Framework for Evaluating Renewables Integration in the Copper Value Chain**

Authors:
**(
    r"Rasmeet Singh$^{a,b}$, "
    r"Gabi Burge$^{c}$, "
    r"Muhammad Haider Ali Khan$^{a,b*}$, "
    r"Serkan Saydam$^{a}$, "
    r"Ismet Canbulat$^{a}$, "
    r"Iain MacGill$^{d,e}$, "
    r"Rahman Daiyan$^{a,b*}$"
)**

## Citation
If you use this code, please cite:
1. the associated journal article
2. the archived software release DOI

A `CITATION.cff` file and Zenodo DOI can be added once the repository is archived.

## License
Choose and insert an appropriate software license before public release.

## Contact
For questions regarding the reproducibility release, contact:
**r.daiyan@unsw.edu.au, M.H.A.K: muhammadhaiderali.khan@unsw.edu.au  **
