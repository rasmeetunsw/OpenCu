"""
Ore Extraction and Concentration Model

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

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

# ==================== USER INPUTS: EDIT HERE FIRST ====================
# Financial constants and default assumptions.
PROJECT_LIFE = 30  # years
DISCOUNT_RATE = 7  # %
CEPCI_2024 = 798.8
CEPCI_1992 = 358.2
INTEREST_RATE = 7  # % (kept for future modelling)
EOL_CAPACITY_DROP_FRAC = 0.20  # replace when capacity/efficiency has fallen by 20%

# -------------------- Main baseline process inputs --------------------
PROCESS_PLANT_AVAILABILITY = 90  # %
MINE_CAPACITY = 10_000_000  # t-ore/yr
ORE_GRADE = 0.6  # %
CONCENTRATE_GRADE = 30.0  # %
COPPER_RECOVERY = 87.5  # %

# --- Fuel data (defaults) ---
DEFAULT_FUEL_DATA: Dict[str, Dict[str, float]] = {
    "Diesel": {
        "Existing_Cost_per_kW": 0.0,
        "New_Cost_per_kW": 0.0,
        "Efficiency": 40.0,
        "Fuel_Price": 0.124,
        "Emissions_Factor": 0.267,
    },
    "Battery": {
        "Existing_Cost_per_kW": 100.0,
        "New_Cost_per_kW": 450.0,
        "Efficiency": 80.0,
        "Fuel_Price": 0.112,
        "Emissions_Factor": 0.7,
    },
    "Hydrogen": {
        "Existing_Cost_per_kW": 95.0,
        "New_Cost_per_kW": 325.0,
        "Efficiency": 44.0,
        "Fuel_Price": 0.108,
        "Emissions_Factor": 0.0,
    },
    "PPA": {
        "Fuel_Price": 0.06,
        "Emissions_Factor": 0.56,
        "Efficiency": 1.0,
        "Existing_Cost_per_kW": 0.0,
        "New_Cost_per_kW": 0.0,
        "PPA_Capacity_Factor": 1.0,
    },
}

# Effective electricity carrier for stationary loads.
DEFAULT_FUEL_DATA["Grid"] = {
    "Fuel_Price": DEFAULT_FUEL_DATA["PPA"]["Fuel_Price"],
    "Emissions_Factor": DEFAULT_FUEL_DATA["PPA"]["Emissions_Factor"],
    "Efficiency": 1.0,
    "Existing_Cost_per_kW": 0.0,
    "New_Cost_per_kW": 0.0,
}

# --- Unit conversions ---
KWH_PER_L_DIESEL = 10.72
KWH_PER_KG_H2 = 33.33
EXPLOSIVE_EMISSION_FACTOR = 1.4  # kg CO2/kg ANFO
EXPLOSIVE_PRICE = 1950.6  # USD/t-ANFO

# -------------------- Major CAPEX scalers --------------------
CONCENTRATOR_BUILDING_COST_FACTOR = 0.6
CONCENTRATOR_BUILDING_UNIT_COST = 27000 * (CEPCI_2024 / CEPCI_1992)
PRIMARY_CRUSHING_PLANT_COST_FACTOR = 0.7
PRIMARY_CRUSHING_PLANT_UNIT_COST = 15000 * (CEPCI_2024 / CEPCI_1992)
FINE_ORE_CRUSHING_AND_CONVEYORS_COST_FACTOR = 0.7
FINE_ORE_CRUSHING_AND_CONVEYORS_UNIT_COST = 18000 * (CEPCI_2024 / CEPCI_1992)
GRINDING_AND_STORAGE_COST_FACTOR = 0.7
GRINDING_AND_STORAGE_UNIT_COST = 12400 * (CEPCI_2024 / CEPCI_1992)
BENEFICIATION_COST_FACTOR = 0.6
BENEFICIATION_UNIT_COST = 13700 * (CEPCI_2024 / CEPCI_1992)
TAILING_DAM_STORAGE_COST_FACTOR = 0.5
TAILING_DAM_STORAGE_UNIT_COST = 20000 * (CEPCI_2024 / CEPCI_1992)
TOTAL_ORE_REFERENCE = 1.0  # t-ore/day

# Equipment defaults
NUMBER_OF_DRILLS = 2
DRILL_DIAMETER = 12.69  # inches
DRILLING_EQUIPMENT_COST_FACTOR = 1.8
DRILLING_EQUIPMENT_POWER_RATING = 25  # kW/drill
DRILLING_EQUIPMENT_REFERENCE_SIZE = 1
DRILLING_EQUIPMENT_COST_AT_REFERENCE_SIZE = 20000 * (CEPCI_2024 / CEPCI_1992)

SHOVEL_CAPACITY = 8.64  # cubic yards
NUMBER_OF_SHOVELS = 5
LOADING_EQUIPMENT_POWER_RATING = 120  # kW/loader
SHOVEL_EQUIPMENT_COST_FACTOR = 0.8
SHOVEL_EQUIPMENT_REFERENCE_SIZE_FOR_LOADING_EQUIPMENT = 1
SHOVEL_EQUIPMENT_COST_AT_REFERENCE_SIZE = 510000 * (CEPCI_2024 / CEPCI_1992)

TRUCK_CAPACITY = 96  # tonne
NUMBER_OF_TRUCKS = 10
HAULING_EQUIPMENT_POWER_RATING_PER_TONNE = 8  # kW/tonne
TRUCK_EQUIPMENT_COST_FACTOR = 0.9
TRUCK_EQUIPMENT_REFERENCE_CAPACITY = 1
TRUCK_EQUIPMENT_COST_AT_REFERENCE_CAPACITY = 20400 * (CEPCI_2024 / CEPCI_1992)

MINING_VEHICLES_UTILISATION_FACTOR = 92  # %
BATTERY_KWH_PER_KW = 1.3

DEFAULT_STATIONARY_SPLIT = {
    "Crushing": 5.5 / 46.4,
    "Grinding": 11.5 / 46.4,
    "Storage": 1.5 / 46.4,
    "Beneficiation": 27.9 / 46.4,
}

# --------------- Change these for scenario testing -----------------------
DEFAULT_FUEL_PENETRATION = {
    "Drilling": {"Diesel": 1.0, "Battery": 0.0, "Hydrogen": 0.0},
    "Loading": {"Diesel": 1.0, "Battery": 0.0, "Hydrogen": 0.0},
    "Hauling": {"Diesel": 1.0, "Battery": 0.0, "Hydrogen": 0.0},
    "Crushing": {"Grid": 1.0, "Battery": 0.0},
    "Grinding": {"Grid": 1.0, "Battery": 0.0},
}


def diesel_litre_to_kwh_price(usd_per_litre: float) -> float:
    return usd_per_litre / KWH_PER_L_DIESEL



def h2_kg_to_kwh_price(usd_per_kg: float) -> float:
    return usd_per_kg / KWH_PER_KG_H2



def safe_efficiency(percent: float) -> float:
    return max(percent / 100.0, 1e-6)



def scope1_ef(fuel: str, fuel_data: Dict[str, Dict[str, float]]) -> float:
    if fuel == "Diesel":
        return float(fuel_data["Diesel"]["Emissions_Factor"])
    if fuel == "Hydrogen":
        return float(fuel_data["Hydrogen"]["Emissions_Factor"])
    return 0.0



def _blend_price(cf: float, ppa_p: float, res_p: float) -> float:
    return cf * ppa_p + (1.0 - cf) * res_p



def _blend_ef(cf: float, ppa_e: float, res_e: float) -> float:
    return cf * ppa_e + (1.0 - cf) * res_e



def _crf(rate: float, n_years: float) -> float:
    if n_years <= 0:
        return 0.0
    return rate * (1.0 + rate) ** n_years / ((1.0 + rate) ** n_years - 1.0)



def apply_default_stationary_split(total_kwh_t_ore: float) -> Dict[str, float]:
    return {
        key: total_kwh_t_ore * frac for key, frac in DEFAULT_STATIONARY_SPLIT.items()
    }



def _validate_fuel_penetration(fuel_penetration: Dict[str, Dict[str, float]]) -> None:
    for process in ["Crushing", "Grinding"]:
        if fuel_penetration.get(process, {}).get("Diesel", 0.0) > 0:
            raise ValueError(f"{process} cannot use Diesel. Use Grid, Battery, or Hydrogen.")



# ==================== CORE MODEL FUNCTIONS ====================

def run_scenario(
    fuel_penetration: Dict[str, Dict[str, float]],
    scenario_name: str = "Base",
    project_life: float = PROJECT_LIFE,
    discount_rate: float = DISCOUNT_RATE,
    mine_capacity: float = MINE_CAPACITY,
    availability: float = PROCESS_PLANT_AVAILABILITY,
    ore_grade: float = ORE_GRADE,
    conc_grade: float = CONCENTRATE_GRADE,
    copper_recovery: float = COPPER_RECOVERY,
    carbon_price: float = 0,
    scope1_baseline_kg_per_t_conc: float = 0.0,
    cepci_index: float = CEPCI_2024,
    crush_kwh_per_t_ore: float = 5.5,
    grind_kwh_per_t_ore: float = 11.5,
    storage_kwh_per_t_ore: float = 3.0,
    benef_kwh_per_t_ore: float = 12.0,
    explosive_kg_per_t_ore: float = 0.4,
    battery_life_years: float = 7,
    battery_degradation: float = 0.02,
    battery_replacement_cost: float = 150,
    fuel_cell_life_hours: float = 25000,
    fuel_cell_degradation: float = 0.02,
    fuel_cell_replacement_cost: float = 500,
    ppa_price_contract: float | None = None,
    ppa_ef: float | None = None,
    ppa_cf: float | None = None,
    residual_price: float | None = None,
    residual_ef: float | None = None,
    Number_of_Drills_: int = NUMBER_OF_DRILLS,
    Drill_Diameter_: float = DRILL_DIAMETER,
    Drilling_Equipment_Power_Rating_: float = DRILLING_EQUIPMENT_POWER_RATING,
    Shovel_Capacity_: float = SHOVEL_CAPACITY,
    Number_of_Shovels_: int = NUMBER_OF_SHOVELS,
    Loading_Equipment_Power_Rating_: float = LOADING_EQUIPMENT_POWER_RATING,
    Truck_Capacity_: float = TRUCK_CAPACITY,
    Number_of_Trucks_: int = NUMBER_OF_TRUCKS,
    Hauling_Equipment_Power_Rating_per_Tonne_: float = HAULING_EQUIPMENT_POWER_RATING_PER_TONNE,
    include_trolley: bool = False,
    trolley_ohl_km: float = 0.0,
    trolley_cost_per_km: float = 6_000_000.0,
    trolley_substations: int = 0,
    trolley_substation_cost: float = 8_000_000.0,
    trolley_truck_kits: int = 0,
    trolley_truck_kit_cost: float = 400_000.0,
    trolley_om_frac: float = 0.015,
    trolley_life_years: int = 10,
    include_ipcc: bool = False,
    ipcc_overland_km: float = 0.0,
    ipcc_overland_cost_per_km: float = 5_500_000.0,
    ipcc_shiftable_km: float = 0.0,
    ipcc_shiftable_cost_per_km: float = 3_000_000.0,
    ipcc_crusher_stations: int = 0,
    ipcc_crusher_cost: float = 10_000_000.0,
    ipcc_om_frac: float = 0.02,
    ipcc_life_years: int = 20,
    num_mining_staff: int = 200,
    num_mill_staff: int = 500,
    num_service_staff: int = 200,
    num_admin_staff: int = 500,
    salary_mining: float = 60000,
    salary_mill: float = 65000,
    salary_service: float = 70000,
    salary_admin: float = 45000,
    fuel_data_override: Dict[str, Dict[str, float]] | None = None,
) -> Dict[str, Any]:
    
    """Run the mining/concentration scenario.
    """
    _validate_fuel_penetration(fuel_penetration)

    fuel_data = deepcopy(DEFAULT_FUEL_DATA)
    if fuel_data_override is not None:
        for carrier, attrs in fuel_data_override.items():
            fuel_data.setdefault(carrier, {})
            fuel_data[carrier].update(attrs)

    # Staffing
    annual_staffing_cost = (
        (salary_mining * 0.7 * num_mining_staff)
        + (salary_mill * 0.7 * num_mill_staff)
        + (salary_service * 0.7 * num_service_staff)
        + (salary_admin * 0.7 * num_admin_staff)
    )

    r = float(discount_rate) / 100.0
    crf_scn = _crf(r, float(project_life))

    trolley_annualised_capex = 0.0
    trolley_annual_om = 0.0
    if include_trolley:
        c_total_trolley = (
            float(trolley_ohl_km) * float(trolley_cost_per_km)
            + int(trolley_substations) * float(trolley_substation_cost)
            + int(trolley_truck_kits) * float(trolley_truck_kit_cost)
        )
        crf_trolley = _crf(r, float(trolley_life_years))
        trolley_annualised_capex = c_total_trolley * crf_trolley
        trolley_annual_om = c_total_trolley * float(trolley_om_frac)

    ipcc_annualised_capex = 0.0
    ipcc_annual_om = 0.0
    if include_ipcc:
        c_total_ipcc = (
            float(ipcc_overland_km) * float(ipcc_overland_cost_per_km)
            + float(ipcc_shiftable_km) * float(ipcc_shiftable_cost_per_km)
            + int(ipcc_crusher_stations) * float(ipcc_crusher_cost)
        )
        crf_ipcc = _crf(r, float(ipcc_life_years))
        ipcc_annualised_capex = c_total_ipcc * crf_ipcc
        ipcc_annual_om = c_total_ipcc * float(ipcc_om_frac)

    cu_fraction_in_conc = max(conc_grade / 100.0, 1e-6)
    effective_mine_capacity = mine_capacity * availability / 100.0
    copper_contained_in_concentrate = (
        effective_mine_capacity * (ore_grade / 100.0) * (copper_recovery / 100.0)
    )
    concentrate_produced = copper_contained_in_concentrate / cu_fraction_in_conc
    if concentrate_produced <= 1e-9:
        raise ValueError("Concentrate production is ~zero with current inputs.")
    daily_production_of_cu_ore = effective_mine_capacity / 365.0

    # Per-run electricity blending
    if ppa_price_contract is not None:
        fuel_data["PPA"]["Fuel_Price"] = float(ppa_price_contract)
    if ppa_ef is not None:
        fuel_data["PPA"]["Emissions_Factor"] = float(ppa_ef)

    cf = float(ppa_cf) if ppa_cf is not None else float(fuel_data["PPA"].get("PPA_Capacity_Factor", 1.0))
    res_price = float(residual_price) if residual_price is not None else float(fuel_data["PPA"]["Fuel_Price"])
    res_ef_val = float(residual_ef) if residual_ef is not None else float(fuel_data["PPA"]["Emissions_Factor"])

    fuel_data["Grid"] = {
        "Fuel_Price": _blend_price(cf, fuel_data["PPA"]["Fuel_Price"], res_price),
        "Emissions_Factor": _blend_ef(cf, fuel_data["PPA"]["Emissions_Factor"], res_ef_val),
        "Efficiency": 1.0,
        "Existing_Cost_per_kW": 0.0,
        "New_Cost_per_kW": 0.0,
    }

    utilisation = MINING_VEHICLES_UTILISATION_FACTOR / 100.0
    hours_per_year = 24 * 365

    drilling_equipment_power_rating = float(Drilling_Equipment_Power_Rating_)
    number_of_drills = int(Number_of_Drills_)
    drill_diameter = float(Drill_Diameter_)
    loading_equipment_power_rating = float(Loading_Equipment_Power_Rating_)
    number_of_shovels = int(Number_of_Shovels_)
    shovel_capacity = float(Shovel_Capacity_)
    truck_capacity = float(Truck_Capacity_)
    number_of_trucks = int(Number_of_Trucks_)
    hauling_equipment_power_rating_per_tonne = float(Hauling_Equipment_Power_Rating_per_Tonne_)
    hauling_equipment_power_rating = hauling_equipment_power_rating_per_tonne * truck_capacity

    drilling_energy_kwh = drilling_equipment_power_rating * number_of_drills * utilisation * hours_per_year
    loading_energy_kwh = loading_equipment_power_rating * number_of_shovels * utilisation * hours_per_year
    hauling_energy_kwh = hauling_equipment_power_rating * number_of_trucks * utilisation * hours_per_year

    get_eff = lambda fuel: safe_efficiency(fuel_data[fuel]["Efficiency"])
    drilling_fuel_energy = {fuel: drilling_energy_kwh / get_eff(fuel) * frac for fuel, frac in fuel_penetration["Drilling"].items()}
    loading_fuel_energy = {fuel: loading_energy_kwh / get_eff(fuel) * frac for fuel, frac in fuel_penetration["Loading"].items()}
    hauling_fuel_energy = {fuel: hauling_energy_kwh / get_eff(fuel) * frac for fuel, frac in fuel_penetration["Hauling"].items()}

    battery_energy_requirement_kwh = (
        drilling_fuel_energy.get("Battery", 0.0)
        + loading_fuel_energy.get("Battery", 0.0)
        + hauling_fuel_energy.get("Battery", 0.0)
    )
    hydrogen_energy_requirement_kwh = (
        drilling_fuel_energy.get("Hydrogen", 0.0)
        + loading_fuel_energy.get("Hydrogen", 0.0)
        + hauling_fuel_energy.get("Hydrogen", 0.0)
    )
    diesel_energy_requirement_kwh = (
        drilling_fuel_energy.get("Diesel", 0.0)
        + loading_fuel_energy.get("Diesel", 0.0)
        + hauling_fuel_energy.get("Diesel", 0.0)
    )

    fuel_costs = {}
    for fuel in ["Diesel", "Hydrogen"]:
        total_energy_kwh = (
            drilling_fuel_energy.get(fuel, 0.0)
            + loading_fuel_energy.get(fuel, 0.0)
            + hauling_fuel_energy.get(fuel, 0.0)
        )
        fuel_costs[fuel] = total_energy_kwh * fuel_data[fuel]["Fuel_Price"]

    annual_fuel_cost = sum(fuel_costs.values())
    annual_battery_charging_cost = battery_energy_requirement_kwh * fuel_data["Battery"]["Fuel_Price"]

    direct_emissions = (
        diesel_energy_requirement_kwh * fuel_data["Diesel"]["Emissions_Factor"]
        + hydrogen_energy_requirement_kwh * fuel_data["Hydrogen"]["Emissions_Factor"]
    )

    crushing_electricity_requirement = crush_kwh_per_t_ore
    grinding_electricity_requirement = grind_kwh_per_t_ore
    storage_electricity_requirement = storage_kwh_per_t_ore
    beneficiation_electricity_requirement = benef_kwh_per_t_ore

    crushing_kwh = crushing_electricity_requirement * mine_capacity * (availability / 100.0)
    grinding_kwh = grinding_electricity_requirement * mine_capacity * (availability / 100.0)
    storage_kwh = storage_electricity_requirement * mine_capacity * (availability / 100.0)

    annual_crushing_electricity_cost = 0.0
    emissions_from_electricity_crushing_per_year = 0.0
    for fuel, share in fuel_penetration["Crushing"].items():
        kwh = crushing_electricity_requirement * mine_capacity * (availability / 100.0) * share
        if fuel in ["Grid", "Battery"]:
            annual_crushing_electricity_cost += kwh * fuel_data[fuel]["Fuel_Price"]
            emissions_from_electricity_crushing_per_year += kwh * fuel_data[fuel]["Emissions_Factor"]

    annual_grinding_electricity_cost = 0.0
    emissions_from_electricity_grinding_per_year = 0.0
    for fuel, share in fuel_penetration["Grinding"].items():
        kwh = grinding_electricity_requirement * mine_capacity * (availability / 100.0) * share
        if fuel in ["Grid", "Battery"]:
            annual_grinding_electricity_cost += kwh * fuel_data[fuel]["Fuel_Price"]
            emissions_from_electricity_grinding_per_year += kwh * fuel_data[fuel]["Emissions_Factor"]

    annual_storage_electricity_cost = storage_kwh * fuel_data["Grid"]["Fuel_Price"]
    annual_cgs_electricity_cost = (
        annual_crushing_electricity_cost
        + annual_grinding_electricity_cost
        + annual_storage_electricity_cost
    )
    annual_beneficiation_electricity_cost = (
        beneficiation_electricity_requirement * mine_capacity * fuel_data["Grid"]["Fuel_Price"] * (availability / 100.0)
    )

    emissions_from_electricity_storage_per_year = storage_kwh * fuel_data["Grid"]["Emissions_Factor"]
    emissions_from_electricity_beneficiation_per_year = (
        beneficiation_electricity_requirement * mine_capacity * (availability / 100.0) * fuel_data["Grid"]["Emissions_Factor"]
    )
    stationary_emissions = (
        emissions_from_electricity_crushing_per_year
        + emissions_from_electricity_grinding_per_year
        + emissions_from_electricity_storage_per_year
        + emissions_from_electricity_beneficiation_per_year
    )
    battery_grid_emissions = battery_energy_requirement_kwh * fuel_data["Battery"]["Emissions_Factor"]
    indirect_emissions = battery_grid_emissions + stationary_emissions

    annual_explosive_cost = (
        explosive_kg_per_t_ore / 1000.0 * EXPLOSIVE_PRICE * mine_capacity * (availability / 100.0)
    )

    cepci_scale = float(cepci_index) / float(CEPCI_2024)
    concentrator_building_unit_cost_sc = CONCENTRATOR_BUILDING_UNIT_COST * cepci_scale
    primary_crushing_plant_unit_cost_sc = PRIMARY_CRUSHING_PLANT_UNIT_COST * cepci_scale
    fine_ore_crushing_and_conveyors_unit_cost_sc = FINE_ORE_CRUSHING_AND_CONVEYORS_UNIT_COST * cepci_scale
    grinding_and_storage_unit_cost_sc = GRINDING_AND_STORAGE_UNIT_COST * cepci_scale
    beneficiation_unit_cost_sc = BENEFICIATION_UNIT_COST * cepci_scale
    tailing_dam_storage_unit_cost_sc = TAILING_DAM_STORAGE_UNIT_COST * cepci_scale
    drilling_equipment_cost_at_reference_size_sc = DRILLING_EQUIPMENT_COST_AT_REFERENCE_SIZE * cepci_scale
    shovel_equipment_cost_at_reference_size_sc = SHOVEL_EQUIPMENT_COST_AT_REFERENCE_SIZE * cepci_scale
    truck_equipment_cost_at_reference_capacity_sc = TRUCK_EQUIPMENT_COST_AT_REFERENCE_CAPACITY * cepci_scale

    concentrator_building_cost = concentrator_building_unit_cost_sc * ((daily_production_of_cu_ore / TOTAL_ORE_REFERENCE) ** CONCENTRATOR_BUILDING_COST_FACTOR)
    primary_crushing_plant_cost = primary_crushing_plant_unit_cost_sc * ((daily_production_of_cu_ore / TOTAL_ORE_REFERENCE) ** PRIMARY_CRUSHING_PLANT_COST_FACTOR)
    fine_ore_crushing_and_conveyors_cost = fine_ore_crushing_and_conveyors_unit_cost_sc * ((daily_production_of_cu_ore / TOTAL_ORE_REFERENCE) ** FINE_ORE_CRUSHING_AND_CONVEYORS_COST_FACTOR)
    grinding_and_storage_cost = grinding_and_storage_unit_cost_sc * ((daily_production_of_cu_ore / TOTAL_ORE_REFERENCE) ** GRINDING_AND_STORAGE_COST_FACTOR)
    beneficiation_cost = beneficiation_unit_cost_sc * ((daily_production_of_cu_ore / TOTAL_ORE_REFERENCE) ** BENEFICIATION_COST_FACTOR)
    tailing_dam_storage_cost = tailing_dam_storage_unit_cost_sc * ((daily_production_of_cu_ore / TOTAL_ORE_REFERENCE) ** TAILING_DAM_STORAGE_COST_FACTOR)
    tailing_dam_capex = tailing_dam_storage_cost * crf_scn
    annual_tailings_operations_management = 0.05 * tailing_dam_capex

    drilling_equipment_cost = drilling_equipment_cost_at_reference_size_sc * ((drill_diameter / DRILLING_EQUIPMENT_REFERENCE_SIZE) ** DRILLING_EQUIPMENT_COST_FACTOR)
    shovel_equipment_cost = shovel_equipment_cost_at_reference_size_sc * ((shovel_capacity / SHOVEL_EQUIPMENT_REFERENCE_SIZE_FOR_LOADING_EQUIPMENT) ** SHOVEL_EQUIPMENT_COST_FACTOR)
    truck_equipment_cost = truck_equipment_cost_at_reference_capacity_sc * ((truck_capacity / TRUCK_EQUIPMENT_REFERENCE_CAPACITY) ** TRUCK_EQUIPMENT_COST_FACTOR)

    additional_capex_input = 0.0
    additional_opex = 0.0
    additional_capex = additional_capex_input * crf_scn

    explosive_use_kg = explosive_kg_per_t_ore * mine_capacity * (availability / 100.0)
    process_emissions_kgyr = explosive_use_kg * EXPLOSIVE_EMISSION_FACTOR

    direct_co2 = direct_emissions / concentrate_produced
    indirect_co2 = indirect_emissions / concentrate_produced
    process_co2_per_t_conc = process_emissions_kgyr / concentrate_produced

    drilling_conversion_capex = sum(
        (fuel_data[f]["New_Cost_per_kW"] - fuel_data[f]["Existing_Cost_per_kW"])
        * drilling_equipment_power_rating
        * fuel_penetration["Drilling"].get(f, 0.0)
        for f in fuel_data
    )
    loading_conversion_capex = sum(
        (fuel_data[f]["New_Cost_per_kW"] - fuel_data[f]["Existing_Cost_per_kW"])
        * loading_equipment_power_rating
        * fuel_penetration["Loading"].get(f, 0.0)
        for f in fuel_data
    )
    hauling_conversion_capex = sum(
        (fuel_data[f]["New_Cost_per_kW"] - fuel_data[f]["Existing_Cost_per_kW"])
        * hauling_equipment_power_rating
        * fuel_penetration["Hauling"].get(f, 0.0)
        for f in fuel_data
    )

    total_cost_of_drilling_equipment = (drilling_equipment_cost + drilling_conversion_capex) * number_of_drills
    total_cost_of_loading_equipment = (shovel_equipment_cost + loading_conversion_capex) * number_of_shovels
    total_cost_of_hauling_equipment = (truck_equipment_cost + hauling_conversion_capex) * number_of_trucks

    drilling_equipment_capex = total_cost_of_drilling_equipment * crf_scn
    loading_equipment_capex = total_cost_of_loading_equipment * crf_scn
    hauling_equipment_capex = total_cost_of_hauling_equipment * crf_scn
    cgs_capex = (
        concentrator_building_cost
        + primary_crushing_plant_cost
        + fine_ore_crushing_and_conveyors_cost
        + grinding_and_storage_cost
    ) * crf_scn
    beneficiation_capex = beneficiation_cost * crf_scn

    batt_kw = (
        drilling_equipment_power_rating * number_of_drills * fuel_penetration["Drilling"].get("Battery", 0.0)
        + loading_equipment_power_rating * number_of_shovels * fuel_penetration["Loading"].get("Battery", 0.0)
        + hauling_equipment_power_rating * number_of_trucks * fuel_penetration["Hauling"].get("Battery", 0.0)
    )
    fc_kw = (
        drilling_equipment_power_rating * number_of_drills * fuel_penetration["Drilling"].get("Hydrogen", 0.0)
        + loading_equipment_power_rating * number_of_shovels * fuel_penetration["Loading"].get("Hydrogen", 0.0)
        + hauling_equipment_power_rating * number_of_trucks * fuel_penetration["Hauling"].get("Hydrogen", 0.0)
    )

    life_by_fade_batt = EOL_CAPACITY_DROP_FRAC / battery_degradation if battery_degradation > 0 else 1e9
    battery_life_effective = min(float(battery_life_years), life_by_fade_batt)
    battery_pack_kwh = batt_kw * BATTERY_KWH_PER_KW
    battery_crf = _crf(r, battery_life_effective)
    annual_battery_replacement_cost = battery_pack_kwh * float(battery_replacement_cost) * battery_crf

    fc_life_years_from_hours = (float(fuel_cell_life_hours) / (utilisation * hours_per_year)) if fuel_cell_life_hours > 0 else 0.0
    life_by_fade_fc = EOL_CAPACITY_DROP_FRAC / fuel_cell_degradation if fuel_cell_degradation > 0 else 1e9
    fc_life_effective = min(fc_life_years_from_hours, life_by_fade_fc)
    fc_crf = _crf(r, fc_life_effective if fc_life_effective > 0 else 1e9)
    annual_fuel_cell_replacement_cost = fc_kw * float(fuel_cell_replacement_cost) * fc_crf

    scope1_co2_per_t_conc = direct_co2 + process_co2_per_t_conc
    excess_co2_per_t_conc = max(0.0, scope1_co2_per_t_conc - scope1_baseline_kg_per_t_conc)
    annual_carbon_cost_usd = (excess_co2_per_t_conc / 1000.0) * carbon_price * concentrate_produced

    annual_cgs_cost = annual_crushing_electricity_cost + annual_grinding_electricity_cost + annual_storage_electricity_cost
    opex_without_staffing = (
        annual_fuel_cost
        + annual_cgs_cost
        + annual_beneficiation_electricity_cost
        + annual_battery_charging_cost
        + annual_explosive_cost
        + annual_tailings_operations_management
        + additional_opex
        + annual_carbon_cost_usd
    )

    base_opex = (
        annual_staffing_cost
        + annual_fuel_cost
        + annual_battery_charging_cost
        + annual_cgs_electricity_cost
        + annual_beneficiation_electricity_cost
        + annual_explosive_cost
        + annual_tailings_operations_management
        + additional_opex
        + annual_carbon_cost_usd
    )
    annual_maintenance_cost = 0.40 * base_opex
    annual_opex = (
        base_opex
        + annual_maintenance_cost
        + annual_battery_replacement_cost
        + annual_fuel_cell_replacement_cost
        + trolley_annual_om
        + ipcc_annual_om
    )

    annualised_capex = (
        drilling_equipment_capex
        + loading_equipment_capex
        + hauling_equipment_capex
        + cgs_capex
        + beneficiation_capex
        + tailing_dam_capex
        + additional_capex
        + trolley_annualised_capex
        + ipcc_annualised_capex
    )

    total_numerator = (
        drilling_equipment_capex
        + loading_equipment_capex
        + hauling_equipment_capex
        + cgs_capex
        + beneficiation_capex
        + tailing_dam_capex
        + additional_capex
        + annual_opex
    )
    total_levelised_cost_of_concentration = total_numerator / concentrate_produced

    replacement_batt_per_t_conc = annual_battery_replacement_cost / concentrate_produced
    replacement_fc_per_t_conc = annual_fuel_cell_replacement_cost / concentrate_produced
    levelised_cost_attributed_to_capex = (
        drilling_equipment_capex
        + loading_equipment_capex
        + hauling_equipment_capex
        + cgs_capex
        + beneficiation_capex
        + tailing_dam_capex
        + additional_capex
    ) / concentrate_produced
    levelised_cost_attributed_to_operational_and_maintenance = (
        annual_staffing_cost + annual_maintenance_cost + additional_opex
    ) / concentrate_produced
    levelised_cost_attributed_to_fuel_requirements = sum(fuel_costs.values()) / concentrate_produced
    levelised_cost_attributed_to_stationary_electricity = (
        annual_cgs_cost + annual_beneficiation_electricity_cost
    ) / concentrate_produced
    levelised_cost_attributed_to_battery_electricity = annual_battery_charging_cost / concentrate_produced

    annual_cu_production = copper_contained_in_concentrate

    results: Dict[str, Any] = {
        "Scenario": scenario_name,
        "Annual_Cu_Production": annual_cu_production,
        "Concentrate_Produced": concentrate_produced,
        "Annualised_CAPEX": annualised_capex,
        "Annual_OPEX": annual_opex,
        "Base_OPEX": base_opex,
        "Annual_Staffing_Cost": annual_staffing_cost,
        "Annual_Fuel_Cost": annual_fuel_cost,
        "Annual_Battery_Charging_Cost": annual_battery_charging_cost,
        "Annual_CGS_Electricity_Cost": annual_cgs_electricity_cost,
        "Annual_Beneficiation_Electricity_Cost": annual_beneficiation_electricity_cost,
        "Annual_Explosive_Cost": annual_explosive_cost,
        "Annual_Tailings_Operations_Management": annual_tailings_operations_management,
        "Annual_Maintenance_Cost": annual_maintenance_cost,
        "Annual_Carbon_Cost_USD": annual_carbon_cost_usd,
        "Additional_OPEX": additional_opex,
        "Annual_Battery_Replacement_Cost": annual_battery_replacement_cost,
        "Annual_FuelCell_Replacement_Cost": annual_fuel_cell_replacement_cost,
        "Annual_Trolley_OandM": trolley_annual_om,
        "Annual_IPCC_OandM": ipcc_annual_om,
        "Total_Cost (USD/t-conc)": total_levelised_cost_of_concentration,
        "Total_Emissions (kgCO2/t-conc)": direct_co2 + indirect_co2 + process_co2_per_t_conc,
        "CAPEX": annualised_capex,
        "Levelised Cost (USD/t-Cu)": (annualised_capex + annual_opex) / annual_cu_production,
        "Emission Intensity (kgCO2/t-Cu)": (direct_emissions + indirect_emissions + process_emissions_kgyr) / annual_cu_production,
        "Annual_Electricity_Cost": annual_cgs_electricity_cost + annual_beneficiation_electricity_cost,
        "CAPEX (USD/t-Cu)": levelised_cost_attributed_to_capex / cu_fraction_in_conc,
        "O&M excl. Staffing (USD/t-Cu)": opex_without_staffing / annual_cu_production,
        "Fuel Requirements (USD/t-Cu)": levelised_cost_attributed_to_fuel_requirements / cu_fraction_in_conc,
        "Electricity (Stationary) (USD/t-Cu)": levelised_cost_attributed_to_stationary_electricity / cu_fraction_in_conc,
        "Electricity (Battery) (USD/t-Cu)": levelised_cost_attributed_to_battery_electricity / cu_fraction_in_conc,
        "Battery Replacement (USD/t-Cu)": replacement_batt_per_t_conc / cu_fraction_in_conc,
        "Fuel Cell Replacement (USD/t-Cu)": replacement_fc_per_t_conc / cu_fraction_in_conc,
        "Explosives (USD/t-Cu)": (annual_explosive_cost / concentrate_produced) / cu_fraction_in_conc,
        "Carbon Pricing (USD/t-Cu)": (annual_carbon_cost_usd / concentrate_produced) / cu_fraction_in_conc,
        "Scope 1 - Fuel (kgCO2/t-Cu)": direct_co2 / cu_fraction_in_conc,
        "Scope 1 - Explosives (kgCO2/t-Cu)": process_emissions_kgyr / annual_cu_production,
        "Scope 2 - Grid (kgCO2/t-Cu)": indirect_co2 / cu_fraction_in_conc,
        "Total Emissions (kgCO2/t-Cu)": (direct_co2 + indirect_co2 + process_co2_per_t_conc) / cu_fraction_in_conc,
        "Drilling Emissions (kgCO2/t-Cu)": sum(drilling_fuel_energy.get(f, 0.0) * scope1_ef(f, fuel_data) for f in fuel_penetration["Drilling"]) / annual_cu_production,
        "Loading Emissions (kgCO2/t-Cu)": sum(loading_fuel_energy.get(f, 0.0) * scope1_ef(f, fuel_data) for f in fuel_penetration["Loading"]) / annual_cu_production,
        "Hauling Emissions (kgCO2/t-Cu)": sum(hauling_fuel_energy.get(f, 0.0) * scope1_ef(f, fuel_data) for f in fuel_penetration["Hauling"]) / annual_cu_production,
        "Comminution Emissions (kgCO2/t-Cu)": (
            emissions_from_electricity_crushing_per_year
            + emissions_from_electricity_grinding_per_year
            + storage_kwh * fuel_data["Grid"]["Emissions_Factor"]
        ) / annual_cu_production,
        "Beneficiation Emissions (kgCO2/t-Cu)": (
            beneficiation_electricity_requirement * mine_capacity * (availability / 100.0) * fuel_data["Grid"]["Emissions_Factor"]
        ) / annual_cu_production,
        "Explosive Emissions (kgCO2/t-Cu)": process_emissions_kgyr / annual_cu_production,
        "Drilling (kWh/t-conc)": sum(drilling_fuel_energy.values()) / concentrate_produced,
        "Loading  (kWh/t-conc)": sum(loading_fuel_energy.values()) / concentrate_produced,
        "Hauling  (kWh/t-conc)": sum(hauling_fuel_energy.values()) / concentrate_produced,
        "CGS (Comminution) (kWh/t-conc)": (
            (crushing_electricity_requirement + grinding_electricity_requirement + storage_electricity_requirement)
            * mine_capacity * (availability / 100.0)
        ) / concentrate_produced,
        "Beneficiation (kWh/t-conc)": (
            beneficiation_electricity_requirement * mine_capacity * (availability / 100.0)
        ) / concentrate_produced,
        "Battery Charging (USD/t-Cu)": annual_battery_charging_cost / annual_cu_production,
        "Tailings, Water, Reagents (USD/t-Cu)": annual_tailings_operations_management / annual_cu_production,
        "Additional OPEX (USD/t-Cu)": additional_opex / annual_cu_production,
        "Maintenance (USD/t-Cu)": annual_maintenance_cost / annual_cu_production,
        "Staffing (USD/t-Cu)": annual_staffing_cost / annual_cu_production,
        "Trolley Annualised CAPEX (USD/yr)": trolley_annualised_capex,
        "Trolley O&M (USD/yr)": trolley_annual_om,
        "Trolley CAPEX (USD/t-Cu)": trolley_annualised_capex / annual_cu_production,
        "Trolley O&M (USD/t-Cu)": trolley_annual_om / annual_cu_production,
        "IPCC Annualised CAPEX (USD/yr)": ipcc_annualised_capex,
        "IPCC O&M (USD/yr)": ipcc_annual_om,
        "IPCC CAPEX (USD/t-Cu)": ipcc_annualised_capex / annual_cu_production,
        "IPCC O&M (USD/t-Cu)": ipcc_annual_om / annual_cu_production,
    }

    cost_breakdown = [
        {
            "Component": "CAPEX",
            "USD/yr": annualised_capex,
            "USD/t-conc": levelised_cost_attributed_to_capex,
            "USD/t-Cu": results.get("CAPEX (USD/t-Cu)", 0.0),
        },
        {
            "Component": "Trolley CAPEX",
            "USD/yr": trolley_annualised_capex,
            "USD/t-conc": trolley_annualised_capex / concentrate_produced,
            "USD/t-Cu": results.get("Trolley CAPEX (USD/t-Cu)", 0.0),
        },
        {
            "Component": "IPCC CAPEX",
            "USD/yr": ipcc_annualised_capex,
            "USD/t-conc": ipcc_annualised_capex / concentrate_produced,
            "USD/t-Cu": results.get("IPCC CAPEX (USD/t-Cu)", 0.0),
        },
        {
            "Component": "Fuel",
            "USD/yr": annual_fuel_cost,
            "USD/t-conc": levelised_cost_attributed_to_fuel_requirements,
            "USD/t-Cu": results.get("Fuel Requirements (USD/t-Cu)", 0.0),
        },
        {
            "Component": "Electricity (Stationary)",
            "USD/yr": annual_cgs_cost + annual_beneficiation_electricity_cost,
            "USD/t-conc": levelised_cost_attributed_to_stationary_electricity,
            "USD/t-Cu": results.get("Electricity (Stationary) (USD/t-Cu)", 0.0),
        },
        {
            "Component": "Battery Charging",
            "USD/yr": annual_battery_charging_cost,
            "USD/t-conc": annual_battery_charging_cost / concentrate_produced,
            "USD/t-Cu": results.get("Electricity (Battery) (USD/t-Cu)", 0.0),
        },
        {
            "Component": "Battery Replacement",
            "USD/yr": annual_battery_replacement_cost,
            "USD/t-conc": replacement_batt_per_t_conc,
            "USD/t-Cu": results.get("Battery Replacement (USD/t-Cu)", 0.0),
        },
        {
            "Component": "Fuel Cell Replacement",
            "USD/yr": annual_fuel_cell_replacement_cost,
            "USD/t-conc": replacement_fc_per_t_conc,
            "USD/t-Cu": results.get("Fuel Cell Replacement (USD/t-Cu)", 0.0),
        },
        {
            "Component": "Explosives",
            "USD/yr": annual_explosive_cost,
            "USD/t-conc": annual_explosive_cost / concentrate_produced,
            "USD/t-Cu": results.get("Explosives (USD/t-Cu)", 0.0),
        },
        {
            "Component": "Tailings, Water, Reagents",
            "USD/yr": annual_tailings_operations_management,
            "USD/t-conc": annual_tailings_operations_management / concentrate_produced,
            "USD/t-Cu": results.get("Tailings, Water, Reagents (USD/t-Cu)", 0.0),
        },
        {
            "Component": "Carbon Pricing",
            "USD/yr": annual_carbon_cost_usd,
            "USD/t-conc": annual_carbon_cost_usd / concentrate_produced,
            "USD/t-Cu": results.get("Carbon Pricing (USD/t-Cu)", 0.0),
        },
        {
            "Component": "Additional OPEX",
            "USD/yr": additional_opex,
            "USD/t-conc": additional_opex / concentrate_produced,
            "USD/t-Cu": results.get("Additional OPEX (USD/t-Cu)", 0.0),
        },
        {
            "Component": "Trolley O&M",
            "USD/yr": trolley_annual_om,
            "USD/t-conc": trolley_annual_om / concentrate_produced,
            "USD/t-Cu": results.get("Trolley O&M (USD/t-Cu)", 0.0),
        },
        {
            "Component": "IPCC O&M",
            "USD/yr": ipcc_annual_om,
            "USD/t-conc": ipcc_annual_om / concentrate_produced,
            "USD/t-Cu": results.get("IPCC O&M (USD/t-Cu)", 0.0),
        },
        {
            "Component": "Staffing",
            "USD/yr": annual_staffing_cost,
            "USD/t-conc": annual_staffing_cost / concentrate_produced,
            "USD/t-Cu": results.get("Staffing (USD/t-Cu)", 0.0),
        },
        {
            "Component": "Maintenance",
            "USD/yr": annual_maintenance_cost,
            "USD/t-conc": annual_maintenance_cost / concentrate_produced,
            "USD/t-Cu": results.get("Maintenance (USD/t-Cu)", 0.0),
        },
    ]
    results["Cost_Breakdown"] = cost_breakdown
    results["Cost_Breakdown_Summary"] = {
        "USD/yr": {item["Component"]: item["USD/yr"] for item in cost_breakdown},
        "USD/t-conc": {item["Component"]: item["USD/t-conc"] for item in cost_breakdown},
        "USD/t-Cu": {item["Component"]: item["USD/t-Cu"] for item in cost_breakdown},
    }

    scope2_total = results.get("Scope 2 - Grid (kgCO2/t-Cu)", 0.0)
    commin_per_tcu = results.get("Comminution Emissions (kgCO2/t-Cu)", 0.0)
    benef_per_tcu = results.get("Beneficiation Emissions (kgCO2/t-Cu)", 0.0)
    batt_chg = max(0.0, float(scope2_total) - float(commin_per_tcu) - float(benef_per_tcu))
    emissions_breakdown = [
        {
            "Source": "Drilling (mobile, direct)",
            "kgCO2/yr": sum(drilling_fuel_energy.get(f, 0.0) * scope1_ef(f, fuel_data) for f in fuel_penetration["Drilling"]),
            "kgCO2/t-conc": sum(drilling_fuel_energy.get(f, 0.0) * scope1_ef(f, fuel_data) for f in fuel_penetration["Drilling"]) / concentrate_produced,
            "kgCO2/t-Cu": results.get("Drilling Emissions (kgCO2/t-Cu)", 0.0),
        },
        {
            "Source": "Loading (mobile, direct)",
            "kgCO2/yr": sum(loading_fuel_energy.get(f, 0.0) * scope1_ef(f, fuel_data) for f in fuel_penetration["Loading"]),
            "kgCO2/t-conc": sum(loading_fuel_energy.get(f, 0.0) * scope1_ef(f, fuel_data) for f in fuel_penetration["Loading"]) / concentrate_produced,
            "kgCO2/t-Cu": results.get("Loading Emissions (kgCO2/t-Cu)", 0.0),
        },
        {
            "Source": "Hauling (mobile, direct)",
            "kgCO2/yr": sum(hauling_fuel_energy.get(f, 0.0) * scope1_ef(f, fuel_data) for f in fuel_penetration["Hauling"]),
            "kgCO2/t-conc": sum(hauling_fuel_energy.get(f, 0.0) * scope1_ef(f, fuel_data) for f in fuel_penetration["Hauling"]) / concentrate_produced,
            "kgCO2/t-Cu": results.get("Hauling Emissions (kgCO2/t-Cu)", 0.0),
        },
        {
            "Source": "Battery charging (mobile, indirect)",
            "kgCO2/yr": batt_chg * annual_cu_production,
            "kgCO2/t-conc": (batt_chg * annual_cu_production) / concentrate_produced,
            "kgCO2/t-Cu": batt_chg,
        },
        {
            "Source": "Comminution (Crush+Grind+Storage, indirect)",
            "kgCO2/yr": emissions_from_electricity_crushing_per_year + emissions_from_electricity_grinding_per_year + emissions_from_electricity_storage_per_year,
            "kgCO2/t-conc": (emissions_from_electricity_crushing_per_year + emissions_from_electricity_grinding_per_year + emissions_from_electricity_storage_per_year) / concentrate_produced,
            "kgCO2/t-Cu": commin_per_tcu,
        },
        {
            "Source": "Beneficiation (indirect)",
            "kgCO2/yr": emissions_from_electricity_beneficiation_per_year,
            "kgCO2/t-conc": emissions_from_electricity_beneficiation_per_year / concentrate_produced,
            "kgCO2/t-Cu": benef_per_tcu,
        },
        {
            "Source": "Explosives (process)",
            "kgCO2/yr": process_emissions_kgyr,
            "kgCO2/t-conc": process_co2_per_t_conc,
            "kgCO2/t-Cu": results.get("Explosive Emissions (kgCO2/t-Cu)", 0.0),
        },
    ]
    results["Emissions_Breakdown"] = emissions_breakdown
    results["Emissions_Breakdown_Summary"] = {
        "kgCO2/yr": {item["Source"]: item["kgCO2/yr"] for item in emissions_breakdown},
        "kgCO2/t-conc": {item["Source"]: item["kgCO2/t-conc"] for item in emissions_breakdown},
        "kgCO2/t-Cu": {item["Source"]: item["kgCO2/t-Cu"] for item in emissions_breakdown},
    }

    return results

from pprint import pprint

def rounded_dict(d, ndigits=2):
    return {k: round(float(v), ndigits) for k, v in d.items()}

# ==================== OUTPUT HELPERS ====================

def _print_summary(results):
    print("Baseline mining backend run completed.")
    print(f"Levelised Cost (USD/t-Cu): {results['Levelised Cost (USD/t-Cu)']:.2f}")
    print(f"Emission Intensity (kgCO2/t-Cu): {results['Emission Intensity (kgCO2/t-Cu)']:.2f}")

    cost_summary = results["Cost_Breakdown_Summary"]
    emissions_summary = results["Emissions_Breakdown_Summary"]

    print("\n=== COST BREAKDOWN (USD/t-Cu) ===")
    pprint(rounded_dict(cost_summary["USD/t-Cu"]))

    print("\n=== COST BREAKDOWN (USD/t-conc) ===")
    pprint(rounded_dict(cost_summary["USD/t-conc"]))

    print("\n=== COST BREAKDOWN (USD/yr) ===")
    pprint(rounded_dict(cost_summary["USD/yr"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/t-Cu) ===")
    pprint(rounded_dict(emissions_summary["kgCO2/t-Cu"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/t-conc) ===")
    pprint(rounded_dict(emissions_summary["kgCO2/t-conc"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/yr) ===")
    pprint(rounded_dict(emissions_summary["kgCO2/yr"]))

# ==================== EXAMPLE BASELINE RUN ====================

if __name__ == "__main__":
    baseline = run_scenario(
        DEFAULT_FUEL_PENETRATION,
        scenario_name="Baseline",
        project_life=30,
        discount_rate=7,
        mine_capacity=10_000_000,
        availability=90,
        ore_grade=0.6,
        conc_grade=30.0,
        copper_recovery=87.5,
        carbon_price=0.0,
        scope1_baseline_kg_per_t_conc=0.0,
        cepci_index=798.8,
        crush_kwh_per_t_ore=5.5,
        grind_kwh_per_t_ore=11.5,
        storage_kwh_per_t_ore=3.0,
        benef_kwh_per_t_ore=12.0,
        explosive_kg_per_t_ore=0.4,
        ppa_price_contract=0.06,
        ppa_ef=0.56,
    )
    _print_summary(baseline)
