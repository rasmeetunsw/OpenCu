"""
Smelting and Anode Casting Model 

HOW TO USE THIS FILE
1. Start at the section marked 'USER INPUTS: EDIT HERE FIRST' or change assumptions in any input blocks.
2. Run the file directly to see the baseline output printed at the bottom.
3. If you are unsure, keep the defaults and only change product / route / fuel / scenario selections.

GENERAL NOTES
- Units are shown in variable names or comments where possible.
- Monetary values are in USD unless stated otherwise.
- Energy is usually in kWh, MJ, or GJ depending on the stage.
- Printed outputs are rounded for readability only; internal calculations are not rounded.
"""

import numpy as np
import pandas as pd

# ==================== USER INPUTS: EDIT HERE FIRST ====================
# Core constants and default assumptions.
CEPCI_2024_DEFAULT = 798.8
CEPCI_2011_DEFAULT = 585.7
CEPCI_2011_BASE = CEPCI_2011_DEFAULT

DEFAULT_MINE_CAPACITY = 10_000_000  # t-ore/yr
DEFAULT_ORE_GRADE = 0.006
scope1_baseline = 0.0
project_life = 30

REDUCTANT_CARBON_FRACTION = {"Coke": 0.90, "Graphite": 0.99}
CO2_PER_KG_C = 44.0 / 12.0

fuel_data = {
    "Natural Gas": {
        "Energy_Per_Mass": 13.7,
        "Fuel_Price": 0.036, #10 (USD/GJ)/277.78=0.036 USD/kWh
        "Emissions_Factor": 0.2,
        "Efficiency": 0.90,
        "Needs_Reducing_Agent": True,
        "Reducing_Agent_Type": "Coke",
    },
    "Coal": {
        "Energy_Per_Mass": 8.14,
        "Fuel_Price": 0.013,
        "Emissions_Factor": 0.33,
        "Efficiency": 0.85,
        "Needs_Reducing_Agent": False,
        "Reducing_Agent_Type": None,
    },
    "Hydrogen": {
        "Energy_Per_Mass": 33.33,
        "Fuel_Price": 0.108,
        "Emissions_Factor": 0.0,
        "Efficiency": 0.90,
        "Needs_Reducing_Agent": False,
        "Reducing_Agent_Type": None,
    },
    "Coke": {
        "Energy_Per_Mass": 8.14,
        "Fuel_Price": 0.03,
        "Emissions_Factor": 0.39,
        "Efficiency": 0.85,
        "Needs_Reducing_Agent": False,
        "Reducing_Agent_Type": None,
    },
}

# --- 2. Helper: flows computed per run from Step-1 style inputs ---
def compute_flows(
    mine_capacity,
    ore_grade,
    conc_grade,
    copper_recovery,
    plant_availability,
    smelter_rec=0.97,
    converter_rec=0.97,
    anode_rec=0.97,
    anode_grade=0.999,
    anode_availability=1.0,
    matte_grade=0.65,
    blister_grade=0.99,
    slag_ratio=2.2,
):
    concentrate_produced = (mine_capacity * ore_grade * copper_recovery / conc_grade) * plant_availability
    contained_cu_in_conc = concentrate_produced * conc_grade
    contained_cu_in_matte = contained_cu_in_conc * smelter_rec
    matte_produced = contained_cu_in_matte / matte_grade
    cu_after_converter = contained_cu_in_matte * converter_rec
    blister_produced = cu_after_converter / blister_grade
    slag_produced = cu_after_converter * slag_ratio

    cu_into_anode_furnace = cu_after_converter
    cu_after_anode_furnace = cu_into_anode_furnace * anode_rec
    anode_production_capacity = cu_after_anode_furnace / anode_grade
    copper_anode_production = anode_production_capacity * anode_availability

    t_Cu_total = copper_anode_production * anode_grade
    t_Cu_per_t_conc = t_Cu_total / max(concentrate_produced, 1e-9)

    return {
        "Concentrate_Produced": concentrate_produced,
        "Contained_Cu_in_Conc": contained_cu_in_conc,
        "Contained_Cu_in_Matte": contained_cu_in_matte,
        "Matte_Produced": matte_produced,
        "Cu_After_Converter": cu_after_converter,
        "Blister_Produced": blister_produced,
        "Slag_Produced": slag_produced,
        "Cu_into_Anode_Furnace": cu_into_anode_furnace,
        "Cu_after_Anode_Furnace": cu_after_anode_furnace,
        "Anode_Production_Capacity": anode_production_capacity,
        "Copper_Anode_Production": copper_anode_production,
        "t_Cu_per_t_conc": t_Cu_per_t_conc,
        "t_Cu_total": t_Cu_total,
    }


# --- 3. Core scenario runner ---
def _run_scenario_raw(
    fuel_config: dict,
    scenario_name: str,
    *,
    # Plant & finance (Step-1 style)
    project_life=30,
    discount_rate=7.0,
    plant_availability=0.90,
    concentrate_grade=0.30,
    copper_recovery=0.875,
    ore_grade=DEFAULT_ORE_GRADE,
    mine_capacity=DEFAULT_MINE_CAPACITY,
    # Electricity & emissions
    ppa_emission_factor=0.56,
    electricity_price=0.06,
    # Policy & baseline
    carbon_price_usd_per_t=0,
    scope1_baseline_kg_per_t_anode=0.0,
    # Custom fuel prices (USD/kWh)
    custom_fuel_prices=None,
    # Reductants (mass-based, independent of heat)
    slag_reductant_type="Coke",
    slag_reductant_rate_kg_per_t_slag=15.0,
    anode_reductant_type="None",
    anode_reductant_rate_kg_per_t_anode=0.0,
    reductant_prices_per_kg=None,  # {"Coke": USD/kg, "Graphite": USD/kg}
    # CEPCI scaling (user-editable)
    cepci_current=CEPCI_2024_DEFAULT,
    cepci_ref=CEPCI_2011_DEFAULT,
    # O&M and staffing (user-editable)
    maintenance_pct_of_installed=0.05,  # 5% of installed CAPEX per year (typical 3–6%)
    staff_count=110,
    salary_base_per_person_AUD=53885, #USD
    fx_USD_per_AUD=0.7, #This is AUD:USD factor; Change is salary input is in AUD
    # Optional extras
    additional_capital_cost_usd=0.0,
    # 🔹 NEW: optional aggregate plant-load overrides (Aurubis/Fritz-style)
    advanced_calibration=None,  # dict with keys below, or None
    drying_kWh_per_t_conc=None,
):
    """
    Computes CAPEX, OPEX, total emissions, and breakdowns for a given fuel configuration.
    Returns a dictionary of results.

    References for energy/emissions numbers are preserved throughout the code comments.
    """
    # --- 0. APPLY CUSTOM FUEL PRICES (if any) ---
    FD = {k: v.copy() for k, v in fuel_data.items()}
    if custom_fuel_prices:
        for f, p in custom_fuel_prices.items():
            if f in FD and p is not None:
                FD[f]["Fuel_Price"] = float(p)

    if reductant_prices_per_kg is None:
        reductant_prices_per_kg = {"Coke": 0.20, "Graphite": 1.00}  # fallback defaults

    # --- helper: reductant CO2 & cost from mass and carbon purity ---
    def _reductant_emissions_and_cost(r_type, rate_kg_per_t, throughput_t):
        if r_type == "None" or rate_kg_per_t <= 0.0 or throughput_t <= 0.0:
            return 0.0, 0.0  # kgCO2/yr, USD/yr
        kg_per_year = rate_kg_per_t * throughput_t
        carbon_fraction = REDUCTANT_CARBON_FRACTION.get(r_type, 1.0)
        co2_kg = kg_per_year * carbon_fraction * CO2_PER_KG_C  # (kg-C)×(44/12)
        cost_usd = kg_per_year * float(reductant_prices_per_kg.get(r_type, 0.0))
        return co2_kg, cost_usd

    # --- extra helpers for advanced mode ---
    HRS = 8760.0
    ADV_DEFAULTS = {
        "process_heat_MW": 22.0,   # fossil process heat (avg, reconstructed from annual NG ≈417.9 GWh/y)
        "af_reducing_MW": 12.0,    # AF reducing-agent burner (avg when ON); 9 h cycle, 3 h reduction @ 120 Nm³/h NG
        "af_duty": 1/3,            # on-fraction (3 h ON / 9 h cycle)
        "scf_reductant_MW": 5.5,   # chemical reductant energy-equivalent in SCF (treated as coke)
        "scf_electric_MW": 3.0,    # SCF resistive/aux power (electric settling furnace)
        "other_electric_MW": 60.0, # other plant electricity (lumped “other”)
        "o2_t_per_h": 7.2,        # oxygen demand (t/h) – back-calculated from plant in ref. study
        "asu_kWh_per_tO2": 285.0,  # specific ASU electricity (kWh/t-O2); literature ranges 200–300+
    }
    def _adv(key):
        if advanced_calibration is None:
            return None
        return float(advanced_calibration.get(key, ADV_DEFAULTS[key]))

    # --- A. Recompute plant flows from inputs ---
    flows = compute_flows(
        mine_capacity=mine_capacity,
        ore_grade=ore_grade,
        conc_grade=concentrate_grade,
        copper_recovery=copper_recovery,
        plant_availability=plant_availability,
    )
    Concentrate_Produced = flows["Concentrate_Produced"]
    Contained_Cu_in_Conc = flows["Contained_Cu_in_Conc"]
    Contained_Cu_in_Matte = flows["Contained_Cu_in_Matte"]
    Matte_Produced = flows["Matte_Produced"]
    Cu_After_Converter = flows["Cu_After_Converter"]
    Blister_Produced = flows["Blister_Produced"]
    Slag_Produced = flows["Slag_Produced"]
    Anode_Production_Capacity = flows["Anode_Production_Capacity"]
    Copper_Anode_Production = flows["Copper_Anode_Production"]
    t_Cu_per_t_conc = flows["t_Cu_per_t_conc"]
    t_Cu_total = flows["t_Cu_total"]

    # --- B. Capital recovery factor from Step-1 inputs ---
    CRF_local = ((discount_rate / 100) * (1 + discount_rate / 100) ** project_life) / (
        (1 + discount_rate / 100) ** project_life - 1
    )

    # --- CEPCI ratio (user-editable current vs 2011 ref) ---
    CEPCI_RATIO = float(cepci_current) / float(cepci_ref)  # ref remains fixed to 2011 base

    # --- 1. CAPITAL COST ESTIMATES (installed, before CRF) ---
    # Per-tonne-anode capital costs scaled by CEPCI ratio (2024 vs 2011). Base 4500 USD/t-anode split.
    BASE_CAPEX_PER_T_ANODE = 4500
    Capex_Concentrate_Handling_And_Drying_per_t_anode = 0.10 * BASE_CAPEX_PER_T_ANODE * CEPCI_RATIO
    Capex_Smelting_Furnace_per_t_anode = 0.15 * BASE_CAPEX_PER_T_ANODE * CEPCI_RATIO
    Capex_Converter_per_t_anode = 0.15 * BASE_CAPEX_PER_T_ANODE * CEPCI_RATIO
    Capex_Slag_Cleaning_per_t_anode = 0.10 * BASE_CAPEX_PER_T_ANODE * CEPCI_RATIO
    Capex_Anode_Furnace_per_t_anode = 0.10 * BASE_CAPEX_PER_T_ANODE * CEPCI_RATIO
    Capex_Oxygen_Plant_per_t_anode = 0.10 * BASE_CAPEX_PER_T_ANODE * CEPCI_RATIO
    Capex_Gas_Handling_System_per_t_anode = 0.30 * BASE_CAPEX_PER_T_ANODE * CEPCI_RATIO

    # Scale to annual capacity (t-anode/yr)
    Capex_Concentrate_USD = Capex_Concentrate_Handling_And_Drying_per_t_anode * Anode_Production_Capacity
    Capex_Smelting_USD = Capex_Smelting_Furnace_per_t_anode * Anode_Production_Capacity
    Capex_Converter_USD = Capex_Converter_per_t_anode * Anode_Production_Capacity
    Capex_Slag_Cleaning_USD = Capex_Slag_Cleaning_per_t_anode * Anode_Production_Capacity
    Capex_Anode_USD = Capex_Anode_Furnace_per_t_anode * Anode_Production_Capacity
    Capex_Oxygen_USD = Capex_Oxygen_Plant_per_t_anode * Anode_Production_Capacity
    Capex_Gas_Handling_USD = Capex_Gas_Handling_System_per_t_anode * Anode_Production_Capacity

    # If hydrogen is used in certain units, bump that unit’s CAPEX by 20% (installed basis)
    hydrogen_multiplier = 1.2
    if fuel_config["Smelting Furnace"] == "Hydrogen":
        Capex_Smelting_USD *= hydrogen_multiplier
    if fuel_config["Converter"] == "Hydrogen":
        Capex_Converter_USD *= hydrogen_multiplier
    if fuel_config["Anode Furnace"] == "Hydrogen":
        Capex_Anode_USD *= hydrogen_multiplier

    Installed_CAPEX = (
        Capex_Concentrate_USD
        + Capex_Smelting_USD
        + Capex_Converter_USD
        + Capex_Slag_Cleaning_USD
        + Capex_Anode_USD
        + Capex_Oxygen_USD
        + Capex_Gas_Handling_USD
        + float(additional_capital_cost_usd)
    )

    # Annualised CAPEX using CRF
    Annualised_CAPEX = Installed_CAPEX * CRF_local

    # --- 2. MAINTENANCE & STAFFING COSTS (OPEX) ---
    # Maintenance as % of installed CAPEX (not annualised)
    Annual_Maintenance_Cost = Installed_CAPEX * float(maintenance_pct_of_installed)

    # Staffing with explicit currency handling
    Smelting_Staff = int(staff_count)
    salary_base_per_person_AUD = float(salary_base_per_person_AUD)
    fx_USD_per_AUD = float(fx_USD_per_AUD)
    Smelter_Personnel_Salary_USD = salary_base_per_person_AUD * fx_USD_per_AUD
    Annual_Staffing_Cost = Smelting_Staff * Smelter_Personnel_Salary_USD

    # --- 3. PROCESS ENERGY & EMISSIONS CALCULATIONS ---

    # Choose fuels for each “bucket”
    Fuel_Drying = FD[fuel_config["Concentrate Handling"]]
    Fuel_Smelter = FD[fuel_config["Smelting Furnace"]]      # used for process-heat bucket in advanced mode
    Fuel_Converter = FD[fuel_config["Converter"]]
    Fuel_Slag = FD[fuel_config["Slag Cleaning"]]
    Fuel_Anode = FD[fuel_config["Anode Furnace"]]           # used for AF-reducing bucket in advanced mode

    # 3.1 Concentrate Handling & Drying (unit-based always)
    # 12,389 kWh to dry 160 t of wet conc → 77.43 kWh/t (Kumera dryer ref)
    # https://www.saimm.co.za/Conferences/Pyro2006/265_Kumera.pdf
    Drying_kWh_per_t_conc = (12_389 / 160.0) if (drying_kWh_per_t_conc is None) else float(drying_kWh_per_t_conc)
    Drying_kWh_annual = Drying_kWh_per_t_conc * Concentrate_Produced
    # Apply fuel efficiency (convert useful kWh to input kWh)
    Drying_Fuel_kWh_input = Drying_kWh_annual / max(Fuel_Drying["Efficiency"], 1e-9)
    Emissions_From_Concentrate_Handling_And_Drying = Drying_Fuel_kWh_input * Fuel_Drying["Emissions_Factor"]
    Cost_Concentrate_Handling_Fuel = Drying_Fuel_kWh_input * Fuel_Drying["Fuel_Price"]

    # Initialize all outputs (we’ll fill from either standard path or advanced path)
    Emissions_From_Smelting_Furnace_Fuel = 0.0
    Cost_Smelting_Fuel = 0.0
    Emissions_From_Converter_Fuel = 0.0
    Cost_Converter_Fuel = 0.0
    Emissions_From_Slag_Cleaning_Furnace_Fuel = 0.0
    Cost_Slag_Cleaning_Fuel = 0.0
    Emissions_From_Slag_Cleaning_Reducing_Agent = 0.0
    Cost_Slag_Cleaning_Reducing_Agent = 0.0
    Emissions_From_Slag_Cleaning_Elec = 0.0
    Cost_Slag_Cleaning_Elec = 0.0
    Emissions_From_Anode_Furnace_Fuel = 0.0
    Cost_Anode_Fuel = 0.0
    Emissions_From_Anode_Reducing_Agent = 0.0
    Cost_Anode_Reducing_Agent = 0.0
    Emissions_From_Anode_Casting_Elec = 0.0
    Cost_Anode_Casting_Elec = 0.0
    Emissions_From_Gas_Handling_Elec = 0.0
    Cost_Gas_Handling_Elec = 0.0

    # 3.2 Oxygen demand & ASU power (supports override)
    if advanced_calibration is not None:
        Oxygen_Required_t = _adv("o2_t_per_h") * 24.0 * 365.0
        Oxygen_Plant_kWh_per_t_O2 = _adv("asu_kWh_per_tO2")
    else:
        # Smelter: 486 t O2 per 2 040 t conc (Extractive Metallurgy of Copper - ch.6, Grupo Mexico Outotec smelter)
        Smelter_O2_t_per_year = (486.0 / 2040.0) * Concentrate_Produced
        # Converter: 730 Nm³/min @22% O₂ for 3.3 h per 205 t matte
        # → (730×60×3.3×0.22×0.00143)/205 ≈ 0.222 t O₂/t matte
        Converter_Cu_Blow_Cycle_Time = 3.3  # hr/cycle
        Converter_Volume_Percent = 0.22  # O₂ fraction
        tO2_per_t_matte = (730 * 60 * Converter_Cu_Blow_Cycle_Time * Converter_Volume_Percent * 0.00143) / 205.0
        Converter_O2_t_per_year = tO2_per_t_matte * Matte_Produced
        Oxygen_Required_t = Smelter_O2_t_per_year + Converter_O2_t_per_year
        # ASU specific energy (kWh/t-O2). Literature range ~200–300; you previously used 285 (Energy 2022.124303).
        Oxygen_Plant_kWh_per_t_O2 = 285.0

    Oxygen_Plant_kWh_annual = Oxygen_Required_t * Oxygen_Plant_kWh_per_t_O2
    # Electric load only; no separate combustion fuel here.
    Emissions_From_Oxygen_Plant = 0.0 # no Scope 1; O2 plant considrered electric 
    Cost_Oxygen_Plant_Fuel = 0.0
    Emissions_From_Oxygen_Elec = Oxygen_Plant_kWh_annual * ppa_emission_factor # scope 2
    Cost_Oxygen_Plant_Elec = Oxygen_Plant_kWh_annual * electricity_price

    if advanced_calibration is None:
        # ==============
        # STANDARD PATH
        # ==============
        # 3.2 Smelting Furnace
        Fuel_Type = fuel_config["Smelting Furnace"]
        SF_E = FD[Fuel_Type]
        # 3 GJ/t matte → 3 × 277.78 = 833 kWh/t matte
        Smelting_kWh_per_t_matte = 3.0 * 277.78
        Smelting_kWh_annual = Smelting_kWh_per_t_matte * Matte_Produced
        Smelting_Fuel_kWh_input = Smelting_kWh_annual / max(SF_E["Efficiency"], 1e-9)
        Emissions_From_Smelting_Furnace_Fuel = Smelting_Fuel_kWh_input * SF_E["Emissions_Factor"]
        Cost_Smelting_Fuel = Smelting_Fuel_kWh_input * SF_E["Fuel_Price"]

        # 3.3 Converter
        Fuel_Type = fuel_config["Converter"]
        C_E = FD[Fuel_Type]
        # 107 kWh/t matte (coursol-type reference)
        Converter_kWh_per_t_matte = 107.0
        Converter_kWh_annual = Converter_kWh_per_t_matte * Matte_Produced
        Converter_Fuel_kWh_input = Converter_kWh_annual / max(C_E["Efficiency"], 1e-9)
        Emissions_From_Converter_Fuel = Converter_Fuel_kWh_input * C_E["Emissions_Factor"]
        Cost_Converter_Fuel = Converter_Fuel_kWh_input * C_E["Fuel_Price"]

        # 3.5 Slag Cleaning Furnace (fuel heat)
        Fuel_Type = fuel_config["Slag Cleaning"]
        SC_E = FD[Fuel_Type]
        # 15.8 Nm3/t-slag @ 37.7 MJ/Nm3 → 595.66 MJ/t → 165.46 kWh/t (Coursol)
        # https://www.pyrometallurgy.co.za/pjmackey/Files/2010-Coursol.
        Slag_Cleaning_kWh_per_t_slag = (15.8 * 37.7) / 3.6
        Slag_Cleaning_kWh_annual = Slag_Cleaning_kWh_per_t_slag * Slag_Produced
        Slag_Cleaning_Fuel_kWh_input = Slag_Cleaning_kWh_annual / max(SC_E["Efficiency"], 1e-9)
        Emissions_From_Slag_Cleaning_Furnace_Fuel = Slag_Cleaning_Fuel_kWh_input * SC_E["Emissions_Factor"]
        Cost_Slag_Cleaning_Fuel = Slag_Cleaning_Fuel_kWh_input * SC_E["Fuel_Price"]

        # 3.6 Electricity for Slag Cleaning (RHF power)
        # QLD Tariff 50 ref retained in comments
        Slag_Cleaning_Elec_kWh_per_t_slag = 6.0 + 45.0  # 6 kWh/t aux + 45 kWh/t electric settling furnace
        Slag_Cleaning_Elec_annual = Slag_Cleaning_Elec_kWh_per_t_slag * Slag_Produced
        Cost_Slag_Cleaning_Elec = Slag_Cleaning_Elec_annual * electricity_price
        Emissions_From_Slag_Cleaning_Elec = Slag_Cleaning_Elec_annual * ppa_emission_factor

        # 3.8 Anode Furnace (Refining & Casting)
        Fuel_Type = fuel_config["Anode Furnace"]
        AF_E = FD[Fuel_Type]
        # 247 kWh/t-anode for heating + 27.4 kWh/t-anode casting power (Coursol)
        Anode_Heating_kWh_per_t_anode = 247.0
        Anode_Casting_kWh_per_t_anode = 27.4
        Anode_Heating_kWh_annual = Anode_Heating_kWh_per_t_anode * Copper_Anode_Production
        Anode_Casting_KWh_annual = Anode_Casting_kWh_per_t_anode * Copper_Anode_Production

        # Apply fuel efficiency for heating
        Anode_Heating_kWh_fuel_input = Anode_Heating_kWh_annual
        Emissions_From_Anode_Furnace_Fuel = Anode_Heating_kWh_fuel_input * AF_E["Emissions_Factor"]
        Cost_Anode_Fuel = Anode_Heating_kWh_fuel_input * AF_E["Fuel_Price"]

        Emissions_From_Anode_Casting_Elec = Anode_Casting_KWh_annual * ppa_emission_factor
        Cost_Anode_Casting_Elec = Anode_Casting_KWh_annual * electricity_price

        # 3.9 Reductants (mass-based, independent of heat fuel)
        Emissions_From_Slag_Cleaning_Reducing_Agent, Cost_Slag_Cleaning_Reducing_Agent = _reductant_emissions_and_cost(
            slag_reductant_type, slag_reductant_rate_kg_per_t_slag, Slag_Produced
        )
        Emissions_From_Anode_Reducing_Agent, Cost_Anode_Reducing_Agent = _reductant_emissions_and_cost(
            anode_reductant_type, anode_reductant_rate_kg_per_t_anode, Copper_Anode_Production
        )

        # 3.10 Gas Handling / Misc Electricity
        # 59 kWh/t-anode (breakdown refs in your comments)
        Gas_Handling_System_Elec_per_t_anode = 59.0
        Gas_Handling_System_Elec_annual = Gas_Handling_System_Elec_per_t_anode * Copper_Anode_Production
        Cost_Gas_Handling_Elec = Gas_Handling_System_Elec_annual * electricity_price
        Emissions_From_Gas_Handling_Elec = Gas_Handling_System_Elec_annual * ppa_emission_factor

    else:
        # =================
        # ADVANCED PATH 
        # =================

        # (i) Fossil process heat as a single bucket (uses Smelting Furnace fuel choice)
        ProcessHeat_kWh = _adv("process_heat_MW") * HRS * 1000.0
        ProcessHeat_kWh_input = ProcessHeat_kWh / max(Fuel_Smelter["Efficiency"], 1e-9)
        Emissions_From_Smelting_Furnace_Fuel = ProcessHeat_kWh_input * Fuel_Smelter["Emissions_Factor"]
        Cost_Smelting_Fuel = ProcessHeat_kWh_input * Fuel_Smelter["Fuel_Price"]

        # (ii) AF reducing-agent burner (uses Anode Furnace fuel choice), with duty
        AF_kWh = _adv("af_reducing_MW") * _adv("af_duty") * HRS * 1000.0
        AF_kWh_input = AF_kWh / max(Fuel_Anode["Efficiency"], 1e-9)
        Emissions_From_Anode_Furnace_Fuel = AF_kWh_input * Fuel_Anode["Emissions_Factor"]
        Cost_Anode_Fuel = AF_kWh_input * Fuel_Anode["Fuel_Price"]

        # mass-based SCF reductant (align with "slag_reductant_*" inputs)
        Emissions_From_Slag_Cleaning_Reducing_Agent, Cost_Slag_Cleaning_Reducing_Agent = \
            _reductant_emissions_and_cost(
                slag_reductant_type,                           # "Coke" or "Graphite"
                slag_reductant_rate_kg_per_t_slag,             # e.g., 10–20 kg per t-slag
                Slag_Produced                                  # t-slag/yr from compute_flows
            )

        # (iv) SCF resistive/electric heating
        Slag_Cleaning_Elec_annual = _adv("scf_electric_MW") * HRS * 1000.0
        Emissions_From_Slag_Cleaning_Elec = Slag_Cleaning_Elec_annual * ppa_emission_factor
        Cost_Slag_Cleaning_Elec = Slag_Cleaning_Elec_annual * electricity_price

        # (v) Other plant electricity (lumped 60 MW)
        Gas_Handling_System_Elec_annual = _adv("other_electric_MW") * HRS * 1000.0
        Emissions_From_Gas_Handling_Elec = Gas_Handling_System_Elec_annual * ppa_emission_factor
        Cost_Gas_Handling_Elec = Gas_Handling_System_Elec_annual * electricity_price

        # (vi) Converter & unit-specific per-ton energy buckets are not used here
        #      (already represented by the process-heat & lumps above). Keep them at 0.
        Converter_kWh_annual = 0.0
        Anode_Casting_KWh_annual = 0.0
        Slag_Cleaning_Fuel_kWh_input = 0.0

    # 3.12 Electricity Costs (combined)
    Annual_Electricity_Consumption = (
        Slag_Cleaning_Elec_annual
        + Anode_Casting_KWh_annual
        + Oxygen_Plant_kWh_annual
        + Gas_Handling_System_Elec_annual
    )
    Annual_Electricity_Cost = (
        Cost_Slag_Cleaning_Elec
        + Cost_Anode_Casting_Elec
        + Cost_Oxygen_Plant_Elec
        + Cost_Gas_Handling_Elec
    )
    Emissions_From_Electricity = (
        Emissions_From_Slag_Cleaning_Elec
        + Emissions_From_Anode_Casting_Elec
        + Emissions_From_Oxygen_Elec
        + Emissions_From_Gas_Handling_Elec
    )

    # 3.13 Fuel & Reductant Costs (separated)
    Annual_Heat_Fuel_Costs = (
        Cost_Concentrate_Handling_Fuel
        + Cost_Smelting_Fuel
        + Cost_Converter_Fuel
        + Cost_Slag_Cleaning_Fuel
        + Cost_Anode_Fuel
    )
    Annual_Reductant_Costs = (
        Cost_Slag_Cleaning_Reducing_Agent + Cost_Anode_Reducing_Agent
    )

    # 3.14 Other + Additional OPEX
    Additional_Operating_Cost = 0.0

    # 3.15 Total OPEX
    Total_OPEX = (
        Annual_Staffing_Cost
        + Annual_Heat_Fuel_Costs
        + Annual_Reductant_Costs
        + Annual_Electricity_Cost
        + Annual_Maintenance_Cost
        + Additional_Operating_Cost
    )

    # 3.16 TOTAL EMISSIONS (kg CO2/yr)
    Total_Emissions_kg_per_yr = (
        Emissions_From_Concentrate_Handling_And_Drying
        + Emissions_From_Smelting_Furnace_Fuel
        + Emissions_From_Converter_Fuel
        + Emissions_From_Slag_Cleaning_Furnace_Fuel
        + Emissions_From_Slag_Cleaning_Reducing_Agent
        + Emissions_From_Slag_Cleaning_Elec
        + Emissions_From_Oxygen_Plant
        + Emissions_From_Oxygen_Elec
        + Emissions_From_Anode_Furnace_Fuel
        + Emissions_From_Anode_Reducing_Agent
        + Emissions_From_Anode_Casting_Elec
        + Emissions_From_Gas_Handling_Elec
    )
    Total_Emissions_t_per_year = Total_Emissions_kg_per_yr / 1000.0

    # 3.17 Emissions Intensity: t CO2 per t ore (legacy KPI, kept)
    Emissions_Intensity_tCO2_per_t_ore = Total_Emissions_t_per_year / max(mine_capacity, 1e-9)

    # 3.18 Carbon Cost (Safeguard-style: Scope 1 only, above baseline)
    Scope1_kg_per_year = (
        Emissions_From_Concentrate_Handling_And_Drying
        + Emissions_From_Smelting_Furnace_Fuel
        + Emissions_From_Converter_Fuel
        + Emissions_From_Slag_Cleaning_Furnace_Fuel
        + Emissions_From_Slag_Cleaning_Reducing_Agent
        + Emissions_From_Anode_Furnace_Fuel
        + Emissions_From_Anode_Reducing_Agent
    )
    Scope2_kg_per_year = (
        Emissions_From_Slag_Cleaning_Elec
        + Emissions_From_Oxygen_Elec
        + Emissions_From_Anode_Casting_Elec
        + Emissions_From_Gas_Handling_Elec
    )
    scope1_kg_per_t_anode = Scope1_kg_per_year / max(Copper_Anode_Production, 1e-9)
    excess_scope1_kg_per_t_anode = max(0.0, scope1_kg_per_t_anode - scope1_baseline_kg_per_t_anode)
    Total_Carbon_Cost = (excess_scope1_kg_per_t_anode / 1000.0) * carbon_price_usd_per_t * Copper_Anode_Production

    # 3.11 Flux Consumption (kept from your original; declare before use if not already executed)
    # If you want flux to be independent of advanced/standard switch, keep it here:
    Effective_Flux_Usage = 0.90
    Flux_Price = 57.0  # actual USD/t-flux price (not inflated)

    # Smelting flux: 273 t per 2040 t conc
    Smelting_Flux_annual = (273 / 2040.0) * Concentrate_Produced / Effective_Flux_Usage

    # Converter flux: 0.19 t/t-blister
    Converter_Flux_annual = 0.19 * Blister_Produced / Effective_Flux_Usage

    Annual_Flux_Cost = Flux_Price * (Smelting_Flux_annual + Converter_Flux_annual)

    # Recompute Total_OPEX to ensure Flux is included (in case locals guard above skipped earlier)
    Total_OPEX = (
        Annual_Staffing_Cost
        + Annual_Heat_Fuel_Costs
        + Annual_Reductant_Costs
        + Annual_Electricity_Cost
        + Annual_Flux_Cost
        + Annual_Maintenance_Cost
        + Additional_Operating_Cost
    )

    # --- 4. LEVELISED COST & KPIs ---
    levelised_cost_per_tconc = (Annualised_CAPEX + Total_OPEX + Total_Carbon_Cost) / max(Concentrate_Produced, 1e-9)
    levelised_cost_per_tcu = (Annualised_CAPEX + Total_OPEX + Total_Carbon_Cost) / max(t_Cu_total, 1e-9)
    emission_intensity_per_tanode = (Total_Emissions_t_per_year * 1000.0) / max(Copper_Anode_Production, 1e-9)
    emission_intensity_per_tcu    = (Total_Emissions_t_per_year * 1000.0) / max(t_Cu_total, 1e-9)

    # --- 5. ORGANIZE RESULTS ---
    results = {
        "Scenario": scenario_name,
        "Levelised Cost (USD/t-conc)": levelised_cost_per_tconc,
        "Levelised Cost (USD/t-Cu)": levelised_cost_per_tcu,  # explicit for UI clarity
        "Emission Intensity (kgCO2/t-anode)": emission_intensity_per_tanode,
        "Emission Intensity (kgCO2/t-Cu)": emission_intensity_per_tcu,
        "Annual CAPEX (USD/yr)": Annualised_CAPEX,
        "Annual OPEX (USD/yr)": Total_OPEX,
        "Annual Carbon Cost (USD/yr)": Total_Carbon_Cost,
        "Total Emissions (kgCO2/yr)": Total_Emissions_kg_per_yr,
        "Total Emissions (tCO2/yr)": Total_Emissions_t_per_year,
        "Concentrate Produced (t-conc/yr)": Concentrate_Produced,
        "Anode Production (t-anode/yr)": Copper_Anode_Production,
        # Emissions breakdown (kg CO2/yr):
        "Emissions From Concentrate Handling And Drying (kg-CO2/yr)": Emissions_From_Concentrate_Handling_And_Drying,
        "Emissions From Smelting Furnace Fuel (kg-CO2/yr)": Emissions_From_Smelting_Furnace_Fuel,
        "Emissions From Converter Fuel (kg-CO2/yr)": Emissions_From_Converter_Fuel,
        "Emissions From Slag Cleaning Furnace Fuel (kg-CO2/yr)": Emissions_From_Slag_Cleaning_Furnace_Fuel,
        "Emissions From Slag Cleaning Reducing Agent (kg-CO2/yr)": Emissions_From_Slag_Cleaning_Reducing_Agent,
        "Emissions From Slag Cleaning Electricity (kg-CO2/yr)": Emissions_From_Slag_Cleaning_Elec,
        "Emissions From Oxygen Plant Fuel (kg-CO2/yr)": Emissions_From_Oxygen_Plant,
        "Emissions From Oxygen Plant Electricity (kg-CO2/yr)": Emissions_From_Oxygen_Elec,
        "Emissions From Anode Furnace Fuel (kg-CO2/yr)": Emissions_From_Anode_Furnace_Fuel,
        "Emissions From Anode Furnace Reducing Agent (kg-CO2/yr)": Emissions_From_Anode_Reducing_Agent,
        "Emissions From Anode Casting Electricity (kg-CO2/yr)": Emissions_From_Anode_Casting_Elec,
        "Emissions From Gas Handling Electricity (kg-CO2/yr)": Emissions_From_Gas_Handling_Elec,
        "Emissions From Grid Electricity (kg-CO2/yr)": Emissions_From_Electricity,  # aggregate (kept for QA)
        # Costs breakdown
        "Annual Fuel Cost (USD/yr)": Annual_Heat_Fuel_Costs,
        "Annual Reductant Cost (USD/yr)": Annual_Reductant_Costs,
        "Annual Electricity Cost (USD/yr)": Annual_Electricity_Cost,
        "Annual Staffing Cost (USD/yr)": Annual_Staffing_Cost,
        "Annual Maintenance Cost (USD/yr)": Annual_Maintenance_Cost,
        "Annual Flux Cost (USD/yr)": Annual_Flux_Cost,
        # Scope info
        "Scope 1 Emissions (kgCO2/yr)": Scope1_kg_per_year,
        "Scope 2 Emissions (kgCO2/yr)": Scope2_kg_per_year,
        "Scope 1 Intensity (kgCO2/t-anode)": scope1_kg_per_t_anode,
        "Scope 1 Baseline (kgCO2/t-anode)": scope1_baseline_kg_per_t_anode,
        "Scope 1 Excess (kgCO2/t-anode)": excess_scope1_kg_per_t_anode,
        # Copper factor for UI
        "t_Cu_per_t_conc": t_Cu_per_t_conc,
        "t_Cu_total": t_Cu_total,
        # Installed CAPEX for info
        "Installed CAPEX (USD)": Installed_CAPEX,
        # Electricity bucket echoes (optional for debugging)
        "Annual Electricity (kWh/y)": Annual_Electricity_Consumption,
    }

    results["Total Annualised Cost (USD/yr)"] = (
        results["Annual CAPEX (USD/yr)"]
        + results["Annual OPEX (USD/yr)"]
        + results["Annual Carbon Cost (USD/yr)"]
    )
    return results




# -------------------- Main default user inputs --------------------
DEFAULT_FUEL_CONFIG = {
    "Concentrate Handling": "Natural Gas",
    "Smelting Furnace": "Natural Gas",
    "Converter": "Natural Gas",
    "Slag Cleaning": "Natural Gas",
    "Anode Furnace": "Natural Gas",
}

DEFAULT_CUSTOM_FUEL_PRICES = None
DEFAULT_ADVANCED_CALIBRATION = None


def _safe_div(a, b):
    return a / b if b not in (0, 0.0, None) else 0.0


def _build_breakdown_summaries(results):
    anode = float(results.get("Anode Production (t-anode/yr)", 0.0) or 0.0)
    conc = float(results.get("Concentrate Produced (t-conc/yr)", 0.0) or 0.0)
    t_cu = float(results.get("t_Cu_total", 0.0) or 0.0)

    annual_costs = {
        "CAPEX": float(results.get("Annual CAPEX (USD/yr)", 0.0)),
        "Fuel": float(results.get("Annual Fuel Cost (USD/yr)", 0.0)),
        "Reductant": float(results.get("Annual Reductant Cost (USD/yr)", 0.0)),
        "Electricity": float(results.get("Annual Electricity Cost (USD/yr)", 0.0)),
        "Staffing": float(results.get("Annual Staffing Cost (USD/yr)", 0.0)),
        "Maintenance": float(results.get("Annual Maintenance Cost (USD/yr)", 0.0)),
        "Flux": float(results.get("Annual Flux Cost (USD/yr)", 0.0)),
        "Carbon Pricing": float(results.get("Annual Carbon Cost (USD/yr)", 0.0)),
    }

    annual_emissions = {
        "Concentrate handling and drying": float(results.get("Emissions From Concentrate Handling And Drying (kg-CO2/yr)", 0.0)),
        "Smelting furnace fuel": float(results.get("Emissions From Smelting Furnace Fuel (kg-CO2/yr)", 0.0)),
        "Converter fuel": float(results.get("Emissions From Converter Fuel (kg-CO2/yr)", 0.0)),
        "Slag cleaning furnace fuel": float(results.get("Emissions From Slag Cleaning Furnace Fuel (kg-CO2/yr)", 0.0)),
        "Slag cleaning reducing agent": float(results.get("Emissions From Slag Cleaning Reducing Agent (kg-CO2/yr)", 0.0)),
        "Slag cleaning electricity": float(results.get("Emissions From Slag Cleaning Electricity (kg-CO2/yr)", 0.0)),
        "Oxygen plant fuel": float(results.get("Emissions From Oxygen Plant Fuel (kg-CO2/yr)", 0.0)),
        "Oxygen plant electricity": float(results.get("Emissions From Oxygen Plant Electricity (kg-CO2/yr)", 0.0)),
        "Anode furnace fuel": float(results.get("Emissions From Anode Furnace Fuel (kg-CO2/yr)", 0.0)),
        "Anode furnace reducing agent": float(results.get("Emissions From Anode Furnace Reducing Agent (kg-CO2/yr)", 0.0)),
        "Anode casting electricity": float(results.get("Emissions From Anode Casting Electricity (kg-CO2/yr)", 0.0)),
        "Gas handling electricity": float(results.get("Emissions From Gas Handling Electricity (kg-CO2/yr)", 0.0)),
    }

    return {
        "Cost_Breakdown_Summary": {
            "USD/yr": annual_costs,
            "USD/t-anode": {k: _safe_div(v, anode) for k, v in annual_costs.items()},
            "USD/t-conc": {k: _safe_div(v, conc) for k, v in annual_costs.items()},
            "USD/t-Cu": {k: _safe_div(v, t_cu) for k, v in annual_costs.items()},
        },
        "Emissions_Breakdown_Summary": {
            "kgCO2/yr": annual_emissions,
            "kgCO2/t-anode": {k: _safe_div(v, anode) for k, v in annual_emissions.items()},
            "kgCO2/t-conc": {k: _safe_div(v, conc) for k, v in annual_emissions.items()},
            "kgCO2/t-Cu": {k: _safe_div(v, t_cu) for k, v in annual_emissions.items()},
        },
    }


# ==================== CORE MODEL FUNCTIONS ====================

def run_scenario(*args, **kwargs):
    """Paper-ready wrapper around the original smelting backend."""
    results = _run_scenario_raw(*args, **kwargs)

    anode = float(results.get("Anode Production (t-anode/yr)", 0.0) or 0.0)
    conc = float(results.get("Concentrate Produced (t-conc/yr)", 0.0) or 0.0)
    t_cu = float(results.get("t_Cu_total", 0.0) or 0.0)
    total_cost_yr = float(results.get("Total Annualised Cost (USD/yr)", 0.0) or 0.0)
    total_emis_yr = float(results.get("Total Emissions (kgCO2/yr)", 0.0) or 0.0)

    results["Levelised Cost (USD/t-anode)"] = _safe_div(total_cost_yr, anode)
    results["Emission Intensity (kgCO2/t-conc)"] = _safe_div(total_emis_yr, conc)

    results.update(_build_breakdown_summaries(results))
    return results

def _round_nested(d, ndigits=2):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = _round_nested(v, ndigits)
        else:
            try:
                out[k] = round(float(v), ndigits)
            except:
                out[k] = v
    return out

# ==================== OUTPUT HELPERS ====================

def _print_summary(results):
    from pprint import pprint

    print(f"Scenario: {results.get('Scenario', 'N/A')}")
    print(f"Levelised Cost (USD/t-anode): {results.get('Levelised Cost (USD/t-anode)', 0.0):.2f}")
    print(f"Levelised Cost (USD/t-conc): {results.get('Levelised Cost (USD/t-conc)', 0.0):.2f}")
    print(f"Levelised Cost (USD/t-Cu): {results.get('Levelised Cost (USD/t-Cu)', 0.0):.2f}")
    print(f"Emission Intensity (kgCO2/t-anode): {results.get('Emission Intensity (kgCO2/t-anode)', 0.0):.2f}")
    print(f"Emission Intensity (kgCO2/t-conc): {results.get('Emission Intensity (kgCO2/t-conc)', 0.0):.2f}")
    print(f"Emission Intensity (kgCO2/t-Cu): {results.get('Emission Intensity (kgCO2/t-Cu)', 0.0):.2f}")
    print(f"Scope 1 Intensity (kgCO2/t-anode): {results.get('Scope 1 Intensity (kgCO2/t-anode)', 0.0):.2f}")

    print("\n=== COST BREAKDOWN (USD/t-anode) ===")
    pprint(_round_nested(results["Cost_Breakdown_Summary"]["USD/t-anode"]))

    print("\n=== COST BREAKDOWN (USD/t-conc) ===")
    pprint(_round_nested(results["Cost_Breakdown_Summary"]["USD/t-conc"]))

    print("\n=== COST BREAKDOWN (USD/t-Cu) ===")
    pprint(_round_nested(results["Cost_Breakdown_Summary"]["USD/t-Cu"]))

    print("\n=== COST BREAKDOWN (USD/yr) ===")
    pprint(_round_nested(results["Cost_Breakdown_Summary"]["USD/yr"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/t-anode) ===")
    pprint(_round_nested(results["Emissions_Breakdown_Summary"]["kgCO2/t-anode"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/t-conc) ===")
    pprint(_round_nested(results["Emissions_Breakdown_Summary"]["kgCO2/t-conc"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/t-Cu) ===")
    pprint(_round_nested(results["Emissions_Breakdown_Summary"]["kgCO2/t-Cu"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/yr) ===")
    pprint(_round_nested(results["Emissions_Breakdown_Summary"]["kgCO2/yr"]))

# ==================== EXAMPLE BASELINE RUN ====================

if __name__ == "__main__":
    baseline = run_scenario(
        DEFAULT_FUEL_CONFIG,
        scenario_name="Baseline",
        project_life=30,
        discount_rate=7.0,
        plant_availability=0.90,
        concentrate_grade=0.30,
        copper_recovery=0.875,
        ore_grade=0.006,
        mine_capacity=10_000_000,
        ppa_emission_factor=0.56,
        electricity_price=0.06,
        carbon_price_usd_per_t=0.0,
        scope1_baseline_kg_per_t_anode=0.0,
        custom_fuel_prices={"Natural Gas": 10 / 277.78},
        cepci_current=798.8,
        cepci_ref=585.7,
        maintenance_pct_of_installed=0.05,
        staff_count=110,
        salary_base_per_person_AUD=53885.0,
        fx_USD_per_AUD=0.7, #This is AUD:USD factor; Change is salary input is in AUD
        slag_reductant_type="Coke",
        slag_reductant_rate_kg_per_t_slag=15.0,
        anode_reductant_type="None",
        anode_reductant_rate_kg_per_t_anode=0.0,
        reductant_prices_per_kg={"Coke": 0.43, "Graphite": 1.2},
        advanced_calibration=None,
    )
    print("Baseline smelting backend run completed.")
    _print_summary(baseline)
