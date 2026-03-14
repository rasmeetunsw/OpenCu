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

## Software archive
The archived release of this reproducibility package is available on Zenodo.

**DOI:** 10.5281/zenodo.19017043 
**Zenodo record:** (https://doi.org/10.5281/zenodo.19017042)

**Authors:** Rasmeet Singh<sup>a,b</sup>, Gabi Burge<sup>c</sup>, Muhammad Haider Ali Khan<sup>a,b</sup>, Serkan Saydam<sup>a</sup>, Ismet Canbulat<sup>a</sup>, Iain MacGill<sup>d,e</sup>, Rahman Daiyan<sup>a,b</sup>

<sup>a</sup> School of Minerals and Energy Resources Engineering, UNSW Sydney  
<sup>b</sup> ARC Training Centre for the Global Hydrogen Economy, Sydney, 2052, Australia  
<sup>c</sup> School of Chemical Engineering, University of New South Wales (UNSW), Sydney, 2052, Australia  
<sup>d</sup> School of Electrical Engineering and Telecommunications, University of New South Wales (UNSW), Sydney, 2052, Australia  
<sup>e</sup> Collaboration on Energy and Environmental Markets, University of New South Wales (UNSW), Sydney, 2052, Australia

## Citation
If you use this code, please cite:
1. the associated journal article  
2. the archived software release on Zenodo

Software DOI: **10.5281/zenodo.19017043**

## License
This repository is released under the **MIT License**.

## Contact
For questions regarding the reproducibility release, contact:
r.daiyan@unsw.edu.au, M.H.A.K: muhammadhaiderali.khan@unsw.edu.au
