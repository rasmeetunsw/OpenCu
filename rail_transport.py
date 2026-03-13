"""Paper-safe backend for copper rail transport model.

Extracted from the original Streamlit rail model to preserve the numerical
backend and default assumptions while removing UI and dashboard logic.
"""

from __future__ import annotations

from copy import deepcopy
from pprint import pprint

# -------------------- Material grades & unit conversion --------------------
MATERIAL_GRADES = {
    "Ore": 0.006,
    "Concentrate": 0.30,
    "Refined Copper": 1.0,
}

# -------------------- Scenario defaults --------------------
DEFAULT_LOCOMOTIVE_DATA = {
    "Diesel": {
        "Locomotive_Cost_USD": 3_940_000,
        "Empty_Weight_tonne": 123.7,
        "Catenary_Cost_USD_per_km": 0.0,
        "Maintenance_USD_per_km": 7.08,
        "Fuel_Consumption_kWh_per_tkm": 0.117,
        "Fuel_Price_USD_per_kWh": 0.123,
        "Emissions_kgCO2_per_kWh": 0.253,
    },
    "Electric": {
        "Locomotive_Cost_USD": 5_470_000,
        "Empty_Weight_tonne": 138.0,
        "Catenary_Cost_USD_per_km": 2_350_000,
        "Maintenance_USD_per_km": 4.04,
        "Fuel_Consumption_kWh_per_tkm": 0.052,
        "Fuel_Price_USD_per_kWh": 0.119,
        "Emissions_kgCO2_per_kWh": 0.56,
    },
    "Battery Electric 2024": {
        "Locomotive_Cost_USD": 9_660_500,
        "Empty_Weight_tonne": 138.0,
        "Catenary_Cost_USD_per_km": 0.0,
        "Maintenance_USD_per_km": 4.04,
        "Fuel_Consumption_kWh_per_tkm": 0.052,
        "Fuel_Price_USD_per_kWh": 0.06,
        "Emissions_kgCO2_per_kWh": 0.05,
    },
    "Battery Electric 2030": {
        "Locomotive_Cost_USD": 8_819_500,
        "Empty_Weight_tonne": 138.0,
        "Catenary_Cost_USD_per_km": 0.0,
        "Maintenance_USD_per_km": 4.04,
        "Fuel_Consumption_kWh_per_tkm": 0.052,
        "Fuel_Price_USD_per_kWh": 0.119,
        "Emissions_kgCO2_per_kWh": 0.50,
    },
    "Battery Electric 2040": {
        "Locomotive_Cost_USD": 7_630_500,
        "Empty_Weight_tonne": 138.0,
        "Catenary_Cost_USD_per_km": 0.0,
        "Maintenance_USD_per_km": 4.04,
        "Fuel_Consumption_kWh_per_tkm": 0.052,
        "Fuel_Price_USD_per_kWh": 0.119,
        "Emissions_kgCO2_per_kWh": 0.25,
    },
    "Battery Electric 2050": {
        "Locomotive_Cost_USD": 7_369_500,
        "Empty_Weight_tonne": 138.0,
        "Catenary_Cost_USD_per_km": 0.0,
        "Maintenance_USD_per_km": 4.04,
        "Fuel_Consumption_kWh_per_tkm": 0.052,
        "Fuel_Price_USD_per_kWh": 0.119,
        "Emissions_kgCO2_per_kWh": 0.05,
    },
    "Hydrogen 2024": {
        "Locomotive_Cost_USD": 24_604_178,
        "Empty_Weight_tonne": 138.0,
        "Catenary_Cost_USD_per_km": 0.0,
        "Maintenance_USD_per_km": 4.04,
        "Fuel_Consumption_kWh_per_tkm": 0.095,
        "Fuel_Price_USD_per_kWh": 0.300,
        "Emissions_kgCO2_per_kWh": 0.0,
    },
    "Hydrogen 2030": {
        "Locomotive_Cost_USD": 17_899_742,
        "Empty_Weight_tonne": 138.0,
        "Catenary_Cost_USD_per_km": 0.0,
        "Maintenance_USD_per_km": 4.04,
        "Fuel_Consumption_kWh_per_tkm": 0.087,
        "Fuel_Price_USD_per_kWh": 0.180,
        "Emissions_kgCO2_per_kWh": 0.0,
    },
    "Hydrogen 2040": {
        "Locomotive_Cost_USD": 14_393_258,
        "Empty_Weight_tonne": 138.0,
        "Catenary_Cost_USD_per_km": 0.0,
        "Maintenance_USD_per_km": 4.04,
        "Fuel_Consumption_kWh_per_tkm": 0.084,
        "Fuel_Price_USD_per_kWh": 0.120,
        "Emissions_kgCO2_per_kWh": 0.0,
    },
    "Hydrogen 2050": {
        "Locomotive_Cost_USD": 13_881_542,
        "Empty_Weight_tonne": 138.0,
        "Catenary_Cost_USD_per_km": 0.0,
        "Maintenance_USD_per_km": 4.04,
        "Fuel_Consumption_kWh_per_tkm": 0.081,
        "Fuel_Price_USD_per_kWh": 0.060,
        "Emissions_kgCO2_per_kWh": 0.0,
    },
}

DEFAULT_SCENARIO = "Diesel"
DEFAULT_MATERIAL = "Concentrate"
DEFAULT_GRADE = MATERIAL_GRADES[DEFAULT_MATERIAL]

DEFAULT_INPUTS = {
    "one_way_km": 250,
    "load_h": 3.0,
    "unload_h": 3.0,
    "speed_kmh": 70.0,
    "operating_days": 350,
    "wagon_cap_t": 110.0,
    "wagon_len_m": 16.1,
    "wagons_per_train": 230,
    "wagon_cost_usd": 150_000.0,
    "wagon_tare_t": 22.0,
    "loco_len_m": 15.0,
    "locos_per_train": 4,
    "flag_fall_usd_per_km": 2.80,
    "var_fee_usd_per_tkm": 0.0054,
    "wagon_mr_usd_per_km_per_wagon": 0.06,
    "rail_mr_usd_per_tkm": 0.002,
    "cargo_ins_usd_per_ntkm": 0.001,
    "add_opex_usd_yr": 0.0,
    "add_capex_usd": 0.0,
    "use_cepci": True,
    "cepci_base": 600.0,
    "cepci_current": 700.0,
    "discount_rate_pct": 7.0,
    "economic_life_yr": 20,
    "capex_markup": 2.0,
    "include_return": True,
    "return_energy_factor": 0.5,
    "return_has_cargo": False,
    "shift_positions": 2,
    "shift_mult": 4.8,
    "hours_per_worker": 1920,
    "wage_per_hour": 45.0,
    "Carbon_Price": 21.9,
    "Infra_Economic_Life": 20,
    "Infra_OM_pct": 2.0,
    "Infra_Electricity_Price_USD_per_kWh": 0.11,
    "Infra_Electricity_EF_kg_per_kWh": 0.50,
    "Charger_Power_kW": 1000.0,
    "Charger_Efficiency": 0.95,
    "Charger_Capex_USD_per_kW": 800.0,
    "Charging_Demand_Charge_USD_per_kW_month": 15.0,
    "Battery_Usable_Energy_kWh_per_Loco": 5000.0,
    "Battery_Replace_Cost_USD_per_kWh": 150.0,
    "Battery_Cycle_Life_full": 3000,
    "Battery_Calendar_Life_years": 10,
    "H2_Refuel_Rate_kg_per_min": 6.0,
    "H2_Station_Capacity_kg_per_day": 2000.0,
    "H2_Station_Capex_USD_per_kg_day": 2000.0,
    "H2_Station_Energy_kWh_per_kg": 2.2,
    "Onsite_Electrolyser": False,
    "Electrolyser_kWh_per_kg": 50.0,
    "Electrolyser_Capex_USD_per_kW": 900.0,
    "Electrolyser_Utilisation": 0.50,
}


def capital_recovery_factor(rate_pct: float, life_years: int) -> float:
    r = rate_pct / 100.0
    n = int(life_years)
    return (r * (1 + r) ** n) / ((1 + r) ** n - 1) if r > 0 else 1.0 / n


def get_tonnes_per_tcu(material_choice: str = DEFAULT_MATERIAL, grade: float | None = None) -> float:
    if grade is None:
        grade = MATERIAL_GRADES[material_choice]
    return 1.0 / max(float(grade), 1e-12)


def compute_results(
    loco_table,
    one_way_km,
    load_h,
    unload_h,
    speed_kmh,
    operating_days,
    wagon_cap_t,
    wagon_len_m,
    wagons_per_train,
    wagon_cost_usd,
    wagon_tare_t,
    loco_len_m,
    locos_per_train,
    flag_fall_usd_per_km,
    var_fee_usd_per_tkm,
    wagon_mr_usd_per_km_per_wagon,
    rail_mr_usd_per_tkm,
    cargo_ins_usd_per_ntkm,
    add_opex_usd_yr,
    add_capex_usd,
    use_cepci,
    cepci_base,
    cepci_current,
    discount_rate_pct,
    economic_life_yr,
    capex_markup,
    include_return=True,
    return_energy_factor=0.5,
    return_has_cargo=False,
    shift_positions=2,
    shift_mult=3.5,
    hours_per_worker=1920,
    wage_per_hour=45.0,
    Carbon_Price=21.9,
    Infra_Economic_Life=20,
    Infra_OM_pct=2.0,
    Infra_Electricity_Price_USD_per_kWh=0.11,
    Infra_Electricity_EF_kg_per_kWh=0.50,
    Charger_Power_kW=1000,
    Charger_Efficiency=0.95,
    Charger_Capex_USD_per_kW=800.0,
    Charging_Demand_Charge_USD_per_kW_month=15.0,
    Battery_Usable_Energy_kWh_per_Loco=5000,
    Battery_Replace_Cost_USD_per_kWh=150.0,
    Battery_Cycle_Life_full=3000,
    Battery_Calendar_Life_years=10,
    H2_Refuel_Rate_kg_per_min=6.0,
    H2_Station_Capacity_kg_per_day=2000,
    H2_Station_Capex_USD_per_kg_day=2000.0,
    H2_Station_Energy_kWh_per_kg=2.2,
    Onsite_Electrolyser=False,
    Electrolyser_kWh_per_kg=50.0,
    Electrolyser_Capex_USD_per_kW=900.0,
    Electrolyser_Utilisation=0.50,
    tonnes_per_tcu: float | None = None,
):
    results = {}
    cepci_mult = (cepci_current / max(cepci_base, 1e-9)) if use_cepci else 1.0
    if tonnes_per_tcu is None:
        tonnes_per_tcu = get_tonnes_per_tcu()

    for scn, data in loco_table.items():
        Locomotive_Cost = float(data["Locomotive_Cost_USD"]) * cepci_mult
        Locomotive_Empty_Weight = float(data["Empty_Weight_tonne"])
        Catenary_Cost_per_km = float(data["Catenary_Cost_USD_per_km"]) * cepci_mult
        Locomotive_Maintenance_Cost = float(data["Maintenance_USD_per_km"])
        Emissions_Factor = float(data["Emissions_kgCO2_per_kWh"])
        Fuel_Price = float(data["Fuel_Price_USD_per_kWh"])
        Cons_kWh_per_tkm = float(data["Fuel_Consumption_kWh_per_tkm"])

        CRF = capital_recovery_factor(discount_rate_pct, economic_life_yr)

        Total_Wagon_Capital_Cost = wagon_cost_usd * wagons_per_train * cepci_mult * capex_markup
        Total_Locomotive_Capital_Cost = Locomotive_Cost * locos_per_train * capex_markup
        Catenary_Line_Installation_Cost = Catenary_Cost_per_km * one_way_km

        Total_Train_Capacity = wagon_cap_t * wagons_per_train
        Total_Train_Tare_Weight = (wagon_tare_t * wagons_per_train) + (Locomotive_Empty_Weight * locos_per_train)
        Total_Train_Gross_Weight = Total_Train_Capacity + Total_Train_Tare_Weight
        Total_Train_Length = ((wagon_len_m * wagons_per_train) + (loco_len_m * locos_per_train)) / 1000.0

        Travel_Time_One_Way = one_way_km / max(speed_kmh, 1e-6)
        Round_Trip_Time = (2 if include_return else 1) * Travel_Time_One_Way + load_h + unload_h
        Total_Round_Trips_Per_Year = (operating_days * 24.0) / max(Round_Trip_Time, 1e-9)

        Gross_Tonne_Kilometres_loaded = Total_Train_Gross_Weight * one_way_km
        Gross_Tonne_Kilometres_return = 0.0

        trailing_loaded_t = (wagon_tare_t * wagons_per_train) + Total_Train_Capacity
        trailing_return_t = (wagon_tare_t * wagons_per_train) if not return_has_cargo else (wagon_tare_t * wagons_per_train + Total_Train_Capacity)
        GTK_loaded = trailing_loaded_t * one_way_km
        GTK_return = (trailing_return_t * one_way_km) if include_return else 0.0
        if include_return:
            Gross_Tonne_Kilometres_return = (Total_Train_Tare_Weight if not return_has_cargo else Total_Train_Gross_Weight) * one_way_km

        Loaded_Energy = GTK_loaded * Cons_kWh_per_tkm
        Return_Energy = GTK_return * Cons_kWh_per_tkm * (return_energy_factor if include_return else 0.0)
        Fuel_Consumption_Per_Trip = Loaded_Energy + Return_Energy
        Fuel_Required_Per_Year = Fuel_Consumption_Per_Trip * Total_Round_Trips_Per_Year

        is_battery = "Battery" in scn
        is_h2 = "Hydrogen" in scn
        CRF_INFRA = capital_recovery_factor(discount_rate_pct, int(Infra_Economic_Life))

        Annual_Charger_CAPEX = 0.0
        Annual_Battery_Replacement = 0.0
        Annual_Demand_Charges = 0.0
        Annual_H2_Station_CAPEX = 0.0
        Annual_Electrolyser_CAPEX = 0.0
        Annual_Infra_Elec_kWh = 0.0
        Annual_Infra_Elec_Cost = 0.0
        Annual_Infra_Elec_Emis_kg = 0.0

        Effective_Fuel_kWh = Fuel_Required_Per_Year
        if is_battery:
            site_energy_kWh = Fuel_Required_Per_Year / max(Charger_Efficiency, 1e-6)
            Effective_Fuel_kWh = site_energy_kWh
            cycles_per_year_per_loco = site_energy_kWh / max(Battery_Usable_Energy_kWh_per_Loco * locos_per_train, 1e-6)
            years_to_replace = min(float(Battery_Calendar_Life_years), float(Battery_Cycle_Life_full) / max(cycles_per_year_per_loco, 1e-9))
            pack_cost_per_loco = Battery_Usable_Energy_kWh_per_Loco * Battery_Replace_Cost_USD_per_kWh
            Annual_Battery_Replacement = (pack_cost_per_loco * locos_per_train) / max(years_to_replace, 1e-9)
            chargers_needed = max(1, int(locos_per_train))
            site_peak_kW = Charger_Power_kW * chargers_needed
            Total_Charger_CAPEX = site_peak_kW * Charger_Capex_USD_per_kW
            Annual_Charger_CAPEX = Total_Charger_CAPEX * CRF_INFRA + Total_Charger_CAPEX * (Infra_OM_pct / 100.0)
            Annual_Demand_Charges = Charging_Demand_Charge_USD_per_kW_month * site_peak_kW * 12.0

        Annual_H2_kg = 0.0
        if is_h2:
            Annual_H2_kg = Fuel_Required_Per_Year / 33.3
            station_kWh = Annual_H2_kg * H2_Station_Energy_kWh_per_kg
            Annual_Infra_Elec_kWh += station_kWh
            daily_h2_need = Annual_H2_kg / max(operating_days, 1)
            stations_required = max(1.0, daily_h2_need / max(H2_Station_Capacity_kg_per_day, 1e-9))
            Total_Station_CAPEX = (H2_Station_Capex_USD_per_kg_day * H2_Station_Capacity_kg_per_day) * stations_required
            Annual_H2_Station_CAPEX = Total_Station_CAPEX * CRF_INFRA + Total_Station_CAPEX * (Infra_OM_pct / 100.0)
            if Onsite_Electrolyser:
                electrolyser_kWh = Annual_H2_kg * Electrolyser_kWh_per_kg
                Annual_Infra_Elec_kWh += electrolyser_kWh
                required_kW = (daily_h2_need * Electrolyser_kWh_per_kg) / max(24.0 * Electrolyser_Utilisation, 1e-6)
                Total_Electrolyser_CAPEX = required_kW * Electrolyser_Capex_USD_per_kW
                Annual_Electrolyser_CAPEX = Total_Electrolyser_CAPEX * CRF_INFRA + Total_Electrolyser_CAPEX * (Infra_OM_pct / 100.0)
            Annual_Infra_Elec_Cost = Annual_Infra_Elec_kWh * Infra_Electricity_Price_USD_per_kWh
            Annual_Infra_Elec_Emis_kg = Annual_Infra_Elec_kWh * Infra_Electricity_EF_kg_per_kWh

        Locomotive_Fuel_Emissions_per_Year_kg = (Effective_Fuel_kWh if is_battery else Fuel_Required_Per_Year) * Emissions_Factor
        Delivered_Quantity = Total_Train_Capacity * Total_Round_Trips_Per_Year
        Emission_per_t_material = Locomotive_Fuel_Emissions_per_Year_kg / max(Delivered_Quantity, 1e-9)

        Total_Wagon_Capex = Total_Wagon_Capital_Cost * CRF
        Total_Locomotive_Capex = Total_Locomotive_Capital_Cost * CRF
        Catenary_Line_Capex = Catenary_Line_Installation_Cost * CRF
        Additional_Capex_Annualised = add_capex_usd * CRF

        Annual_CAPEX_Infra = Annual_Charger_CAPEX + Annual_H2_Station_CAPEX + Annual_Electrolyser_CAPEX
        Annual_OM_Infra = Annual_Battery_Replacement + Annual_Demand_Charges + Annual_Infra_Elec_Cost
        Total_Annual_Emissions_kg = Locomotive_Fuel_Emissions_per_Year_kg + Annual_Infra_Elec_Emis_kg

        km_factor = 2 if include_return else 1
        GTK_total = Gross_Tonne_Kilometres_loaded + (Gross_Tonne_Kilometres_return if include_return else 0.0)
        Flag_Fall_Rail_Access_Fee_Cost = 2 * flag_fall_usd_per_km * one_way_km * Total_Round_Trips_Per_Year
        Variable_Rail_Access_Fee_Cost = var_fee_usd_per_tkm * GTK_total * Total_Round_Trips_Per_Year
        Locomotive_Maintenance_and_Repair_Cost = km_factor * Locomotive_Maintenance_Cost * one_way_km * Total_Round_Trips_Per_Year
        Wagon_Maintenance_and_Repair_Cost = km_factor * wagon_mr_usd_per_km_per_wagon * wagons_per_train * one_way_km * Total_Round_Trips_Per_Year
        Rail_Network_Maintenance_and_Repair_Cost = rail_mr_usd_per_tkm * GTK_total * Total_Round_Trips_Per_Year
        Cargo_Insurance_Cost = cargo_ins_usd_per_ntkm * Total_Train_Capacity * one_way_km * Total_Round_Trips_Per_Year * (1 + int(include_return and return_has_cargo))
        Fuel_Cost_USD_per_year = Fuel_Required_Per_Year * Fuel_Price
        staffing_positions_total = shift_positions * shift_mult
        Staffing_Cost = staffing_positions_total * hours_per_worker * wage_per_hour
        Annual_Carbon_Cost = (Total_Annual_Emissions_kg / 1000.0) * Carbon_Price

        denom = max(Delivered_Quantity, 1e-9)
        L_CAPEX = (Total_Wagon_Capex + Total_Locomotive_Capex + Catenary_Line_Capex + Additional_Capex_Annualised + Annual_CAPEX_Infra) / denom
        L_OM = (
            Flag_Fall_Rail_Access_Fee_Cost + Variable_Rail_Access_Fee_Cost + Locomotive_Maintenance_and_Repair_Cost +
            Wagon_Maintenance_and_Repair_Cost + Rail_Network_Maintenance_and_Repair_Cost + Cargo_Insurance_Cost +
            Staffing_Cost + add_opex_usd_yr + Annual_OM_Infra
        ) / denom
        L_Fuel = Fuel_Cost_USD_per_year / denom
        L_Carbon = Annual_Carbon_Cost / denom
        L_Total = L_CAPEX + L_OM + L_Fuel + L_Carbon

        results[scn] = {
            "Scenario": scn,
            "Total Train Capacity (tonne/train)": Total_Train_Capacity,
            "Total Train Tare Weight (tonne/train)": Total_Train_Tare_Weight,
            "Total Train Gross Weight (tonne/train)": Total_Train_Gross_Weight,
            "Total Train Length (km/train)": Total_Train_Length,
            "Round Trip Time (hours/round-trip)": Round_Trip_Time,
            "Yearly Round Trips (trips/year)": Total_Round_Trips_Per_Year,
            "Delivered Quantity (t-material/year)": Delivered_Quantity,
            "Fuel Required (kWh/yr)": Fuel_Required_Per_Year,
            "Locomotive Fuel Emission (kgCO2/t-material)": Emission_per_t_material,
            "Total Annual Emissions (kgCO2/year)": Total_Annual_Emissions_kg,
            "Total Annual Emissions (tCO2/year)": Total_Annual_Emissions_kg / 1000.0,
            "Wagon CAPEX (USD/year)": Total_Wagon_Capex,
            "Locomotive CAPEX (USD/year)": Total_Locomotive_Capex,
            "Catenary CAPEX (USD/year)": Catenary_Line_Capex,
            "Additional CAPEX (USD/year)": Additional_Capex_Annualised,
            "Charging CAPEX (USD/year)": Annual_Charger_CAPEX,
            "H2 Station CAPEX (USD/year)": Annual_H2_Station_CAPEX,
            "Electrolyser CAPEX (USD/year)": Annual_Electrolyser_CAPEX,
            "Flag Fall Rail Access Fee Cost (USD/year)": Flag_Fall_Rail_Access_Fee_Cost,
            "Variable Rail Access Fee Cost (USD/year)": Variable_Rail_Access_Fee_Cost,
            "Locomotive Maintenance and Repair Cost (USD/year)": Locomotive_Maintenance_and_Repair_Cost,
            "Wagon Maintenance and Repair Cost (USD/year)": Wagon_Maintenance_and_Repair_Cost,
            "Rail Network Maintenance and Repair Cost (USD/year)": Rail_Network_Maintenance_and_Repair_Cost,
            "Cargo Insurance Cost (USD/year)": Cargo_Insurance_Cost,
            "Fuel Cost (USD/year)": Fuel_Cost_USD_per_year,
            "Staffing Cost (USD/year)": Staffing_Cost,
            "Additional Operating Cost (USD/year)": add_opex_usd_yr,
            "Battery Replacement (USD/year)": Annual_Battery_Replacement,
            "Demand Charges (USD/year)": Annual_Demand_Charges,
            "Infra Electricity Cost (USD/year)": Annual_Infra_Elec_Cost,
            "Annual Carbon Cost (USD/year)": Annual_Carbon_Cost,
            "Infra Electricity Emissions (kgCO2/year)": Annual_Infra_Elec_Emis_kg,
            "Levelised Cost of CAPEX (USD/t-material)": L_CAPEX,
            "Levelised Cost of O&M (USD/t-material)": L_OM,
            "Levelised Cost of Fuel Requirement (USD/t-material)": L_Fuel,
            "Levelised Cost of Carbon Price (USD/t-material)": L_Carbon,
            "Total Levelised Cost of Rail (USD/t-material)": L_Total,
            "_loaded_energy_trip_kWh": Loaded_Energy,
            "_return_energy_trip_kWh": Return_Energy,
            "_round_trips_per_year": Total_Round_Trips_Per_Year,
            "_ef_kg_per_kWh": Emissions_Factor,
            "tonnes_per_tCu": tonnes_per_tcu,
        }

    return results


def _safe_div(a, b):
    return a / b if b not in (0, 0.0, None) else 0.0


def _augment_result_units(result):
    t_material = float(result.get("Delivered Quantity (t-material/year)", 0.0) or 0.0)
    tonnes_per_tcu = float(result.get("tonnes_per_tCu", 1.0) or 1.0)
    t_cu = _safe_div(t_material, tonnes_per_tcu)
    total_cost_year = (
        result.get("Wagon CAPEX (USD/year)", 0.0)
        + result.get("Locomotive CAPEX (USD/year)", 0.0)
        + result.get("Catenary CAPEX (USD/year)", 0.0)
        + result.get("Additional CAPEX (USD/year)", 0.0)
        + result.get("Charging CAPEX (USD/year)", 0.0)
        + result.get("H2 Station CAPEX (USD/year)", 0.0)
        + result.get("Electrolyser CAPEX (USD/year)", 0.0)
        + result.get("Flag Fall Rail Access Fee Cost (USD/year)", 0.0)
        + result.get("Variable Rail Access Fee Cost (USD/year)", 0.0)
        + result.get("Locomotive Maintenance and Repair Cost (USD/year)", 0.0)
        + result.get("Wagon Maintenance and Repair Cost (USD/year)", 0.0)
        + result.get("Rail Network Maintenance and Repair Cost (USD/year)", 0.0)
        + result.get("Cargo Insurance Cost (USD/year)", 0.0)
        + result.get("Fuel Cost (USD/year)", 0.0)
        + result.get("Staffing Cost (USD/year)", 0.0)
        + result.get("Additional Operating Cost (USD/year)", 0.0)
        + result.get("Battery Replacement (USD/year)", 0.0)
        + result.get("Demand Charges (USD/year)", 0.0)
        + result.get("Infra Electricity Cost (USD/year)", 0.0)
        + result.get("Annual Carbon Cost (USD/year)", 0.0)
    )

    annual_costs = {
        "Wagon CAPEX": float(result.get("Wagon CAPEX (USD/year)", 0.0)),
        "Locomotive CAPEX": float(result.get("Locomotive CAPEX (USD/year)", 0.0)),
        "Catenary CAPEX": float(result.get("Catenary CAPEX (USD/year)", 0.0)),
        "Additional CAPEX": float(result.get("Additional CAPEX (USD/year)", 0.0)),
        "Charging CAPEX": float(result.get("Charging CAPEX (USD/year)", 0.0)),
        "H2 Station CAPEX": float(result.get("H2 Station CAPEX (USD/year)", 0.0)),
        "Electrolyser CAPEX": float(result.get("Electrolyser CAPEX (USD/year)", 0.0)),
        "Flag Fall Access": float(result.get("Flag Fall Rail Access Fee Cost (USD/year)", 0.0)),
        "Variable Access": float(result.get("Variable Rail Access Fee Cost (USD/year)", 0.0)),
        "Locomotive M&R": float(result.get("Locomotive Maintenance and Repair Cost (USD/year)", 0.0)),
        "Wagon M&R": float(result.get("Wagon Maintenance and Repair Cost (USD/year)", 0.0)),
        "Rail Network M&R": float(result.get("Rail Network Maintenance and Repair Cost (USD/year)", 0.0)),
        "Cargo Insurance": float(result.get("Cargo Insurance Cost (USD/year)", 0.0)),
        "Fuel": float(result.get("Fuel Cost (USD/year)", 0.0)),
        "Staffing": float(result.get("Staffing Cost (USD/year)", 0.0)),
        "Additional OPEX": float(result.get("Additional Operating Cost (USD/year)", 0.0)),
        "Battery Replacement": float(result.get("Battery Replacement (USD/year)", 0.0)),
        "Demand Charges": float(result.get("Demand Charges (USD/year)", 0.0)),
        "Infra Electricity": float(result.get("Infra Electricity Cost (USD/year)", 0.0)),
        "Carbon Pricing": float(result.get("Annual Carbon Cost (USD/year)", 0.0)),
    }
    annual_emissions = {
        "Traction energy": float(result.get("Total Annual Emissions (kgCO2/year)", 0.0)) - float(result.get("Infra Electricity Emissions (kgCO2/year)", 0.0)),
        "Infra electricity": float(result.get("Infra Electricity Emissions (kgCO2/year)", 0.0)),
    }

    result["Total Levelised Cost of Rail (USD/t-Cu)"] = _safe_div(total_cost_year, t_cu)
    result["Total Annual Emissions (kgCO2/t-material)"] = _safe_div(result.get("Total Annual Emissions (kgCO2/year)", 0.0), t_material)
    result["Total Annual Emissions (kgCO2/t-Cu)"] = _safe_div(result.get("Total Annual Emissions (kgCO2/year)", 0.0), t_cu)
    result["Cost_Breakdown_Summary"] = {
        "USD/year": annual_costs,
        "USD/t-material": {k: _safe_div(v, t_material) for k, v in annual_costs.items()},
        "USD/t-Cu": {k: _safe_div(v, t_cu) for k, v in annual_costs.items()},
    }
    result["Emissions_Breakdown_Summary"] = {
        "kgCO2/year": annual_emissions,
        "kgCO2/t-material": {k: _safe_div(v, t_material) for k, v in annual_emissions.items()},
        "kgCO2/t-Cu": {k: _safe_div(v, t_cu) for k, v in annual_emissions.items()},
    }
    return result


def run_model(
    locomotive_data=None,
    material_choice: str = DEFAULT_MATERIAL,
    grade: float | None = None,
    **kwargs,
):
    loco_table = deepcopy(locomotive_data or DEFAULT_LOCOMOTIVE_DATA)
    if grade is None:
        grade = MATERIAL_GRADES[material_choice]
    tonnes_per_tcu = get_tonnes_per_tcu(material_choice, grade)
    inputs = deepcopy(DEFAULT_INPUTS)
    inputs.update(kwargs)
    raw = compute_results(loco_table=loco_table, tonnes_per_tcu=tonnes_per_tcu, **inputs)
    return {k: _augment_result_units(v) for k, v in raw.items()}


from pprint import pprint

def rounded_dict(d, ndigits=2):
    return {k: round(float(v), ndigits) for k, v in d.items()}

def _print_summary(result):
    print(f"Scenario: {result.get('Scenario', 'N/A')}")
    print(f"Total Levelised Cost of Rail (USD/t-material): {result.get('Total Levelised Cost of Rail (USD/t-material)', 0.0):.2f}")
    print(f"Total Levelised Cost of Rail (USD/t-Cu): {result.get('Total Levelised Cost of Rail (USD/t-Cu)', 0.0):.2f}")
    print(f"Total Annual Emissions (kgCO2/t-material): {result.get('Total Annual Emissions (kgCO2/t-material)', 0.0):.2f}")
    print(f"Total Annual Emissions (kgCO2/t-Cu): {result.get('Total Annual Emissions (kgCO2/t-Cu)', 0.0):.2f}")

    cost_summary = result["Cost_Breakdown_Summary"]
    emissions_summary = result["Emissions_Breakdown_Summary"]

    print("\n=== COST BREAKDOWN (USD/t-material) ===")
    pprint(rounded_dict(cost_summary["USD/t-material"]))

    print("\n=== COST BREAKDOWN (USD/t-Cu) ===")
    pprint(rounded_dict(cost_summary["USD/t-Cu"]))

    print("\n=== COST BREAKDOWN (USD/year) ===")
    pprint(rounded_dict(cost_summary["USD/year"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/t-material) ===")
    pprint(rounded_dict(emissions_summary["kgCO2/t-material"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/t-Cu) ===")
    pprint(rounded_dict(emissions_summary["kgCO2/t-Cu"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/year) ===")
    pprint(rounded_dict(emissions_summary["kgCO2/year"]))

if __name__ == "__main__":
    baseline_all = run_model(material_choice=DEFAULT_MATERIAL)
    baseline = baseline_all[DEFAULT_SCENARIO]
    print("Baseline rail backend run completed.")
    _print_summary(baseline)
