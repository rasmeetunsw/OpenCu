
# Shipping TEA Model — paper-safe backend
# Extracted from Streamlit app; retains calculation core and default assumptions,
# while removing UI, plotting, and dashboard logic.

import copy
import math
from pprint import pprint

# ----------------- Static route data -----------------
distances_nm = {
    "Townsville Port (AUS)": {"New Orleans": 9758, "Rotterdam": 11346, "Qingdao": 3954},
    "Antofagasta (Chile)":   {"New Orleans": 3567, "Rotterdam": 6965,  "Qingdao": 10095},
    "Callao (Peru)":         {"New Orleans": 2782, "Rotterdam": 5652,  "Qingdao": 8812},
}

canal_passage = {
    "Suez Canal": {
        "Townsville Port (AUS)": {"New Orleans": "NO",  "Rotterdam": "YES", "Qingdao": "NO"},
        "Antofagasta (Chile)":   {"New Orleans": "NO",  "Rotterdam": "NO",  "Qingdao": "NO"},
        "Callao (Peru)":         {"New Orleans": "NO",  "Rotterdam": "NO",  "Qingdao": "NO"},
    },
    "Panama Canal": {
        "Townsville Port (AUS)": {"New Orleans": "YES", "Rotterdam": "NO",  "Qingdao": "NO"},
        "Antofagasta (Chile)":   {"New Orleans": "YES", "Rotterdam": "YES", "Qingdao": "NO"},
        "Callao (Peru)":         {"New Orleans": "YES", "Rotterdam": "YES", "Qingdao": "NO"},
    },
}

port_types = {
    "Townsville Port (AUS)": "Concentrate",
    "Antofagasta (Chile)":   "Concentrate",
    "Callao (Peru)":         "Concentrate",
    "New Orleans":           "Refined",
    "Rotterdam":             "Refined",
    "Qingdao":               "Refined",
}

vessel_defaults = {"Concentrate": "Supramax", "Refined": "Panamax"}

Ship_Data = [
    {"Ship Type":"Handysize", "Length":155, "Beam":23, "Draft":10,
     "Displacement":31000, "Dead Weight":25000, "Installed Power":5.5, "Speed":14,
     "Newbuild Cost":27_613_262, "Suez Canal":"YES", "Panama Canal":"YES"},
    {"Ship Type":"Supramax", "Length":190, "Beam":32, "Draft":13,
     "Displacement":70000, "Dead Weight":60000, "Installed Power":9.0, "Speed":15,
     "Newbuild Cost":37_277_903, "Suez Canal":"YES", "Panama Canal":"YES"},
    {"Ship Type":"Panamax", "Length":220, "Beam":32, "Draft":15,
     "Displacement":92000, "Dead Weight":80000, "Installed Power":10.5, "Speed":15,
     "Newbuild Cost":41_419_892, "Suez Canal":"YES", "Panama Canal":"YES"},
    {"Ship Type":"HandyCape", "Length":240, "Beam":43, "Draft":15,
     "Displacement":135000, "Dead Weight":120000, "Installed Power":13.5, "Speed":15,
     "Newbuild Cost":55_226_523, "Suez Canal":"YES", "Panama Canal":"NO"},
]

Fuel_Assumptions = [
    {"Fuel":"Heavy Fuel Oil (HFO)", "Engine Efficiency":40.00, "Fuel Energy Content":40.40,
     "Carbon Emissions":2.98, "Shipping Fuel Cost":650.00,
     "New Build Diesel Engine Cost":449.00, "New Build Converter Engine Cost":449.00, "New Build Tank Scrubber Cost":0.00},
    {"Fuel":"Marine Gas Oil (MGO)", "Engine Efficiency":40.00, "Fuel Energy Content":42.70,
     "Carbon Emissions":3.21, "Shipping Fuel Cost":999.00,
     "New Build Diesel Engine Cost":449.00, "New Build Converter Engine Cost":449.00, "New Build Tank Scrubber Cost":0.00},
    {"Fuel":"Very Low Sulfur Fuel Oil (VLSFO)", "Engine Efficiency":40.00, "Fuel Energy Content":41.00,
     "Carbon Emissions":3.18, "Shipping Fuel Cost":650.00,
     "New Build Diesel Engine Cost":449.00, "New Build Converter Engine Cost":449.00, "New Build Tank Scrubber Cost":0.00},
    {"Fuel":"Ammonia", "Engine Efficiency":35.00, "Fuel Energy Content":18.80,
     "Carbon Emissions":0.008, "Shipping Fuel Cost":1400.00,
     "New Build Diesel Engine Cost":449.00, "New Build Converter Engine Cost":898.00, "New Build Tank Scrubber Cost":0.00},
    {"Fuel":"Methanol", "Engine Efficiency":40.00, "Fuel Energy Content":19.90,
     "Carbon Emissions":0.003, "Shipping Fuel Cost":1400.00,
     "New Build Diesel Engine Cost":449.00, "New Build Converter Engine Cost":673.00, "New Build Tank Scrubber Cost":0.00},
]

def CRF_from_rate(i, n):
    i = float(i)
    if n <= 0 or i <= -1:
        return 0.0
    return (i * (1 + i) ** n) / ((1 + i) ** n - 1)

def get_shipping_config():
    return (
        copy.deepcopy(distances_nm),
        copy.deepcopy(Ship_Data),
        copy.deepcopy(port_types),
        copy.deepcopy(Fuel_Assumptions),
        copy.deepcopy(canal_passage),
    )

def _warn_power_if_infeasible(p_req_kw, p_inst_kw, op_speed, speed_power_exp, sea_state_power_pct):
    if p_req_kw > p_inst_kw:
        print(
            f"Warning: required propulsion {p_req_kw:,.0f} kW exceeds installed {p_inst_kw:,.0f} kW "
            f"at {op_speed:.1f} kn (n={float(speed_power_exp):.2f}, sea-state={float(sea_state_power_pct):.1f}%)."
        )

def run_leg(
    export_type, ore_grade, concentrate_grade, carbon_price,
    distance_nm_value, use_suez, use_panama, suez_fee, panama_fee,
    suez_wait_days, panama_wait_days, toll_uplift_pct,
    ship_dict, operating_speed_kn, speed_power_exp, sea_state_power_pct,
    crew_workers, crew_hours_per_year, crew_hour_wage,
    backhaul_load_frac, backhaul_credit_usd_per_t,
    use_wacc_for_crf, simple_interest_pct, project_life_years,
    WACC, residual_frac, use_CEPCI, CEPCI_base, CEPCI_current, CPI_multiplier,
    fuels_table,
    days_per_year_in_operation, port_throughput_t_per_hr,
    port_pilotage_usd, port_tonnage_usd_per_t, port_wharfage_usd_per_t, port_berthage_usd_per_hr,
    stores_and_consumables_usd_yr, maintenance_and_repair_usd_yr, insurance_usd_yr,
    general_cost_usd_yr, periodic_maintenance_usd_yr,
    aux_power_kW=0.0,
):
    Port_Days_perhour     = float(port_throughput_t_per_hr)
    Port_Pilotage_Charges = float(port_pilotage_usd) * float(CPI_multiplier)
    Port_Tonnage_Charge   = float(port_tonnage_usd_per_t) * float(CPI_multiplier)
    Port_Wharfage_Charge  = float(port_wharfage_usd_per_t) * float(CPI_multiplier)
    Port_Berthage_Charge  = float(port_berthage_usd_per_hr) * float(CPI_multiplier)

    Stores_And_Consumables = float(stores_and_consumables_usd_yr) * float(CPI_multiplier)
    Maintenance_And_Repair = float(maintenance_and_repair_usd_yr) * float(CPI_multiplier)
    General_Cost           = float(general_cost_usd_yr) * float(CPI_multiplier)
    Periodic_Maintenance   = float(periodic_maintenance_usd_yr) * float(CPI_multiplier)

    Crew_Cost = float(crew_workers) * float(crew_hours_per_year) * float(crew_hour_wage)

    Newbuild_Cost = float(ship_dict["Newbuild Cost"])
    if use_CEPCI and CEPCI_base > 0:
        Newbuild_Cost *= (float(CEPCI_current) / float(CEPCI_base))

    n = int(project_life_years)
    i = float(WACC if use_wacc_for_crf else simple_interest_pct / 100.0)
    CRF = CRF_from_rate(i, n)
    Annualised_CAPEX = Newbuild_Cost * CRF - (Newbuild_Cost * float(residual_frac) / (1 + i) ** n) * CRF

    DWT = float(ship_dict["Dead Weight"])
    Cargo_Fill_Factor = 1.0
    out_cargo_t = DWT * Cargo_Fill_Factor
    backhaul_t  = DWT * Cargo_Fill_Factor * backhaul_load_frac

    Insurance = float(insurance_usd_yr) * float(CPI_multiplier) * (out_cargo_t / max(out_cargo_t + backhaul_t, 1e-9))

    distance = float(distance_nm_value)
    design_speed = float(ship_dict["Speed"])
    op_speed = float(operating_speed_kn)

    port_days_per_call_out = (out_cargo_t / Port_Days_perhour) / 24.0
    port_days_per_call_back = (backhaul_t / Port_Days_perhour) / 24.0 if backhaul_t > 0 else 0.0

    port_days_rt = 2 * port_days_per_call_out
    if backhaul_t > 0:
        port_days_rt += 2 * port_days_per_call_back

    canal_wait_rt_days = 0.0
    if use_suez:
        canal_wait_rt_days += 2 * float(suez_wait_days)
    if use_panama:
        canal_wait_rt_days += 2 * float(panama_wait_days)

    sailing_days_rt = 2.0 * (distance / max(op_speed, 0.1)) / 24.0
    Total_Trip_Days = sailing_days_rt + port_days_rt + canal_wait_rt_days

    days_op = float(days_per_year_in_operation)
    Trips_Per_Year = math.floor(days_op / max(Total_Trip_Days, 1e-9))
    Delivered_Quantity_t = Trips_Per_Year * out_cargo_t

    export_map = {"Refined Copper": "Refined", "Ore": "Ore", "Concentrate": "Concentrate"}
    prod = export_map.get(export_type, "Refined")
    if prod == "Refined":
        Delivered_Quantity_t_Cu = Delivered_Quantity_t
    elif prod == "Ore":
        Delivered_Quantity_t_Cu = Delivered_Quantity_t * float(ore_grade)
    elif prod == "Concentrate":
        Delivered_Quantity_t_Cu = Delivered_Quantity_t * float(concentrate_grade)
    else:
        Delivered_Quantity_t_Cu = Delivered_Quantity_t

    def port_fee_for_tonnage(tonnes, port_days_one_call):
        pilotage = 2 * Port_Pilotage_Charges
        tonnage  = 2 * Port_Tonnage_Charge  * tonnes
        wharfage = 2 * Port_Wharfage_Charge * tonnes
        berthage = 2 * Port_Berthage_Charge * (port_days_one_call * 24.0)
        return pilotage + tonnage + wharfage + berthage

    fee_outbound_rt  = port_fee_for_tonnage(out_cargo_t, port_days_per_call_out)
    fee_backhaul_rt  = port_fee_for_tonnage(backhaul_t, port_days_per_call_back) if backhaul_t > 0 else 0.0
    total_port_fee_per_trip = fee_outbound_rt + fee_backhaul_rt
    total_port_fee_per_year = total_port_fee_per_trip * Trips_Per_Year

    toll_mult = 1.0 + float(toll_uplift_pct) / 100.0
    canal_cost_per_trip = 0.0
    if use_suez:
        canal_cost_per_trip += float(suez_fee) * toll_mult
    if use_panama:
        canal_cost_per_trip += float(panama_fee) * toll_mult
    canal_cost_per_year = canal_cost_per_trip * Trips_Per_Year

    sailing_hours_rt   = sailing_days_rt * 24.0
    portcanal_hours_rt = (port_days_rt + canal_wait_rt_days) * 24.0

    P_inst_kW = float(ship_dict["Installed Power"]) * 1000.0
    coef      = P_inst_kW / (max(design_speed, 0.1) ** float(speed_power_exp))
    P_req_kW  = coef * (max(op_speed, 0.1) ** float(speed_power_exp)) * (1.0 + float(sea_state_power_pct) / 100.0)
    _warn_power_if_infeasible(P_req_kW, P_inst_kW, op_speed, speed_power_exp, sea_state_power_pct)
    P_sail_kW = P_req_kW
    P_aux_kW  = max(float(aux_power_kW), 0.0)

    E_sail_trip_MJ = P_sail_kW * sailing_hours_rt * 3.6
    E_port_trip_MJ = P_aux_kW  * portcanal_hours_rt * 3.6
    E_sail_yr_MJ = E_sail_trip_MJ * Trips_Per_Year
    E_port_yr_MJ = E_port_trip_MJ * Trips_Per_Year

    results = {}
    for fuel in fuels_table:
        name = fuel["Fuel"]
        LHV_MJ_kg = float(fuel["Fuel Energy Content"])
        eff       = float(fuel["Engine Efficiency"]) / 100.0
        ef_CO2    = float(fuel["Carbon Emissions"])
        price_t   = float(fuel["Shipping Fuel Cost"])

        MJ_needed_sail = E_sail_yr_MJ / max(eff, 1e-9)
        MJ_needed_port = E_port_yr_MJ / max(eff, 1e-9)

        fuel_kg_sail = MJ_needed_sail / max(LHV_MJ_kg, 1e-9)
        fuel_kg_port = MJ_needed_port / max(LHV_MJ_kg, 1e-9)
        fuel_kg      = fuel_kg_sail + fuel_kg_port
        fuel_t       = fuel_kg / 1000.0

        fuel_cost_total = fuel_t * price_t
        CO2_kg_sail     = fuel_kg_sail * ef_CO2
        CO2_kg_port     = fuel_kg_port * ef_CO2
        CO2_kg_total    = CO2_kg_sail + CO2_kg_port
        carbon_cost_total = (CO2_kg_total / 1000.0) * float(carbon_price)

        Base_OandM_yr = (
            Stores_And_Consumables + Maintenance_And_Repair +
            Insurance + General_Cost + Periodic_Maintenance + Crew_Cost
        )
        backhaul_credit_year = float(backhaul_credit_usd_per_t) * backhaul_t * Trips_Per_Year

        Fuel_CAPEX = (
            float(fuel["New Build Diesel Engine Cost"]) +
            float(fuel["New Build Converter Engine Cost"]) +
            float(fuel["New Build Tank Scrubber Cost"])
        )
        Annualised_Fuel_CAPEX = Fuel_CAPEX * CRF

        denom_cu = max(Delivered_Quantity_t_Cu, 1e-9)
        denom_material = max(Delivered_Quantity_t, 1e-9)

        capex_yr = Annualised_CAPEX + Annualised_Fuel_CAPEX
        om_yr = Base_OandM_yr + total_port_fee_per_year + canal_cost_per_year - backhaul_credit_year

        results[name] = {
            "Fuel Required (t/yr)": fuel_t,
            "Fuel Cost (USD/yr)": fuel_cost_total,
            "CO2 Emissions (kg/yr)": CO2_kg_total,
            "CO2 Sailing (kg/yr)": CO2_kg_sail,
            "CO2 Port+Canal (kg/yr)": CO2_kg_port,
            "CAPEX (USD/yr)": capex_yr,
            "Base O&M (USD/yr)": Base_OandM_yr,
            "Port Fees (USD/yr)": total_port_fee_per_year,
            "Canal Fees (USD/yr)": canal_cost_per_year,
            "Backhaul Credit (USD/yr)": backhaul_credit_year,
            "O&M (USD/yr)": om_yr,
            "Carbon Cost (USD/yr)": carbon_cost_total,
            "CO2 Intensity (kgCO2/t-Cu)": CO2_kg_total / denom_cu,
            "CO2 Intensity (kgCO2/t-material)": CO2_kg_total / denom_material,
            "CAPEX (USD/t-Cu)": capex_yr / denom_cu,
            "CAPEX (USD/t-material)": capex_yr / denom_material,
            "O&M (USD/t-Cu)": om_yr / denom_cu,
            "O&M (USD/t-material)": om_yr / denom_material,
            "Fuel Cost (USD/t-Cu)": fuel_cost_total / denom_cu,
            "Fuel Cost (USD/t-material)": fuel_cost_total / denom_material,
            "Carbon Cost (USD/t-Cu)": carbon_cost_total / denom_cu,
            "Carbon Cost (USD/t-material)": carbon_cost_total / denom_material,
            "Total Levelised Cost (USD/t-Cu)": (capex_yr + om_yr + fuel_cost_total + carbon_cost_total) / denom_cu,
            "Total Levelised Cost (USD/t-material)": (capex_yr + om_yr + fuel_cost_total + carbon_cost_total) / denom_material,
        }

    diagnostics = {
        "Trips_Per_Year": float(Trips_Per_Year),
        "Delivered_Quantity_t": float(Delivered_Quantity_t),
        "Delivered_Quantity_t_Cu": float(Delivered_Quantity_t_Cu),
        "Total_Trip_Days": float(Total_Trip_Days),
        "Sailing_Days_RT": float(sailing_days_rt),
        "Port_Days_RT": float(port_days_rt),
        "Canal_Wait_RT_Days": float(canal_wait_rt_days),
        "Distance_nm": float(distance_nm_value),
        "Days_Per_Year_In_Operation": float(days_per_year_in_operation),
        "Uses_Suez": bool(use_suez),
        "Uses_Panama": bool(use_panama),
        "Suez_Fee": float(suez_fee),
        "Panama_Fee": float(panama_fee),
        "Toll_Uplift_pct": float(toll_uplift_pct),
        "Annualised_CAPEX_USDyr": float(Annualised_CAPEX),
        "Base_OandM_USDyr": float(Stores_And_Consumables + Maintenance_And_Repair + Insurance + General_Cost + Periodic_Maintenance + Crew_Cost),
        "Port_Fees_USDyr": float(total_port_fee_per_year),
        "Canal_Fees_USDyr": float(canal_cost_per_year),
        "Backhaul_Credit_USDyr": float(backhaul_credit_usd_per_t * backhaul_t * Trips_Per_Year),
        "Sailing_Power_kW": float(P_sail_kW),
        "Aux_Power_kW": float(P_aux_kW),
        "Ship_Length_m": float(ship_dict["Length"]),
        "Ship_Beam_m": float(ship_dict["Beam"]),
        "Ship_Draft_m": float(ship_dict["Draft"]),
        "Ship_Displacement_t": float(ship_dict["Displacement"]),
        "Insurance_USDyr": Insurance,
    }
    return results, diagnostics

def run_route_two_leg(legA_kwargs, legB_kwargs_or_none, selected_fuel):
    resA, dA = run_leg(**legA_kwargs)
    if legB_kwargs_or_none:
        resB, dB = run_leg(**legB_kwargs_or_none)
        denom_cu = max(dA["Delivered_Quantity_t_Cu"], 1e-9)
        denom_material = max(dA["Delivered_Quantity_t"], 1e-9)

        total_fuel_year   = resA[selected_fuel]["Fuel Cost (USD/yr)"] + resB[selected_fuel]["Fuel Cost (USD/yr)"]
        total_CO2_year    = resA[selected_fuel]["CO2 Emissions (kg/yr)"] + resB[selected_fuel]["CO2 Emissions (kg/yr)"]
        total_capex_year  = resA[selected_fuel]["CAPEX (USD/yr)"] + resB[selected_fuel]["CAPEX (USD/yr)"]
        total_om_year     = resA[selected_fuel]["O&M (USD/yr)"] + resB[selected_fuel]["O&M (USD/yr)"]
        total_carbon_year = resA[selected_fuel]["Carbon Cost (USD/yr)"] + resB[selected_fuel]["Carbon Cost (USD/yr)"]

        combined = {
            "CAPEX (USD/yr)": total_capex_year,
            "O&M (USD/yr)": total_om_year,
            "Fuel Cost (USD/yr)": total_fuel_year,
            "Carbon Cost (USD/yr)": total_carbon_year,
            "CO2 Emissions (kg/yr)": total_CO2_year,
            "CAPEX (USD/t-Cu)": total_capex_year / denom_cu,
            "O&M (USD/t-Cu)": total_om_year / denom_cu,
            "Fuel Cost (USD/t-Cu)": total_fuel_year / denom_cu,
            "Carbon Cost (USD/t-Cu)": total_carbon_year / denom_cu,
            "Total Levelised Cost (USD/t-Cu)": (total_capex_year + total_om_year + total_fuel_year + total_carbon_year) / denom_cu,
            "CO2 Intensity (kgCO2/t-Cu)": total_CO2_year / denom_cu,
            "CAPEX (USD/t-material)": total_capex_year / denom_material,
            "O&M (USD/t-material)": total_om_year / denom_material,
            "Fuel Cost (USD/t-material)": total_fuel_year / denom_material,
            "Carbon Cost (USD/t-material)": total_carbon_year / denom_material,
            "Total Levelised Cost (USD/t-material)": (total_capex_year + total_om_year + total_fuel_year + total_carbon_year) / denom_material,
            "CO2 Intensity (kgCO2/t-material)": total_CO2_year / denom_material,
        }
        diags = {"A": dA, "B": dB}
        return combined, diags
    else:
        combined = resA[selected_fuel]
        diags = {"A": dA}
        return combined, diags

def emissions_breakdown_sailing_port(legA_kwargs, legB_kwargs, fuel_name):
    resA, dA = run_leg(**legA_kwargs)
    denom_cu = max(dA["Delivered_Quantity_t_Cu"], 1e-9)
    denom_material = max(dA["Delivered_Quantity_t"], 1e-9)

    def split(res, d):
        s = res[fuel_name].get("CO2 Sailing (kg/yr)", 0.0)
        p = res[fuel_name].get("CO2 Port+Canal (kg/yr)", 0.0)
        return s, p

    sA, pA = split(resA, dA)
    sB = pB = 0.0
    if legB_kwargs:
        resB, dB = run_leg(**legB_kwargs)
        sB, pB = split(resB, dB)

    sailing_year = float(sA + sB)
    port_year = float(pA + pB)
    return {
        "kgCO2/yr": {"Sailing": sailing_year, "Port + Canal": port_year},
        "kgCO2/t-Cu": {"Sailing": sailing_year / denom_cu, "Port + Canal": port_year / denom_cu},
        "kgCO2/t-material": {"Sailing": sailing_year / denom_material, "Port + Canal": port_year / denom_material},
    }

# ----------------- Defaults from the original UI -----------------
def compute_default_wacc(debt_frac_pct=40, cost_debt_pct=6.0, cost_equity_pct=12.0, tax_rate_pct=30.0):
    return (debt_frac_pct/100.0) * (cost_debt_pct/100.0) * (1 - tax_rate_pct/100.0) + (1 - debt_frac_pct/100.0) * (cost_equity_pct/100.0)

DEFAULT_EXPORT_TYPE = "Concentrate"
DEFAULT_ORE_GRADE = 0.60
DEFAULT_CONCENTRATE_GRADE = 0.30
DEFAULT_CARBON_PRICE = 0.0

DEFAULT_DEBT_FRAC_PCT = 40.0
DEFAULT_COST_DEBT_PCT = 6.0
DEFAULT_COST_EQUITY_PCT = 12.0
DEFAULT_TAX_RATE_PCT = 30.0
DEFAULT_WACC = compute_default_wacc(DEFAULT_DEBT_FRAC_PCT, DEFAULT_COST_DEBT_PCT, DEFAULT_COST_EQUITY_PCT, DEFAULT_TAX_RATE_PCT)

DEFAULT_PROJECT_LIFE_YEARS = 30
DEFAULT_SIMPLE_INTEREST_PCT = 8.0
DEFAULT_RESIDUAL_FRAC = 0.10

DEFAULT_CREW_HEADCOUNT = 20
DEFAULT_CREW_HOURS_PER_YEAR = 1920
DEFAULT_CREW_WAGE_USD_PER_HOUR = 36.0
DEFAULT_CPI_MULTIPLIER = 1.00
DEFAULT_USE_CEPCI = True
DEFAULT_CEPCI_BASE = 600.0
DEFAULT_CEPCI_CURRENT = 700.0

DEFAULT_DAYS_PER_YEAR_IN_OPERATION = 350
DEFAULT_PORT_THROUGHPUT_T_PER_HR = 3000.0
DEFAULT_PORT_PILOTAGE_USD = 15291.0
DEFAULT_PORT_TONNAGE_USD_PER_T = 0.35
DEFAULT_PORT_WHARFAGE_USD_PER_T = 1.86
DEFAULT_PORT_BERTHAGE_USD_PER_HR = 315.0

DEFAULT_STORES_AND_CONSUMABLES_USD_YR = 355434.0
DEFAULT_MAINTENANCE_AND_REPAIR_USD_YR = 375625.0
DEFAULT_INSURANCE_USD_YR = 384951.0
DEFAULT_GENERAL_COST_USD_YR = 330836.0
DEFAULT_PERIODIC_MAINTENANCE_USD_YR = 588666.0

DEFAULT_BACKHAUL_LOAD_FRAC = 0.0
DEFAULT_BACKHAUL_CREDIT_USD_PER_T = 0.0
DEFAULT_SPEED_POWER_EXP = 3.0
DEFAULT_SEA_STATE_POWER_PCT = 10.0
DEFAULT_AUX_POWER_KW = 1500.0

DEFAULT_ROUTE_DEPARTURE = "Townsville Port (AUS)"
DEFAULT_ROUTE_ARRIVAL = "New Orleans"
DEFAULT_SELECTED_FUEL = "Heavy Fuel Oil (HFO)"
DEFAULT_USE_LEG_B = False

def _select_default_ship_for_departure(departure_port):
    ship_table = copy.deepcopy(Ship_Data)
    ptype = port_types.get(departure_port, "Refined")
    default_ship_type = vessel_defaults.get(ptype, "Panamax")
    return next(s for s in ship_table if s["Ship Type"] == default_ship_type)

def build_default_legA_kwargs():
    dep = DEFAULT_ROUTE_DEPARTURE
    arr = DEFAULT_ROUTE_ARRIVAL
    ship = _select_default_ship_for_departure(dep)

    return dict(
        export_type=DEFAULT_EXPORT_TYPE,
        ore_grade=DEFAULT_ORE_GRADE,
        concentrate_grade=DEFAULT_CONCENTRATE_GRADE,
        carbon_price=DEFAULT_CARBON_PRICE,
        distance_nm_value=float(distances_nm[dep][arr]),
        use_suez=(canal_passage["Suez Canal"][dep][arr] == "YES"),
        use_panama=(canal_passage["Panama Canal"][dep][arr] == "YES"),
        suez_fee=400000.0,
        panama_fee=350000.0,
        suez_wait_days=0.5,
        panama_wait_days=0.5,
        toll_uplift_pct=0.0,
        ship_dict=copy.deepcopy(ship),
        operating_speed_kn=float(ship["Speed"]),
        speed_power_exp=DEFAULT_SPEED_POWER_EXP,
        sea_state_power_pct=DEFAULT_SEA_STATE_POWER_PCT,
        crew_workers=DEFAULT_CREW_HEADCOUNT,
        crew_hours_per_year=DEFAULT_CREW_HOURS_PER_YEAR,
        crew_hour_wage=DEFAULT_CREW_WAGE_USD_PER_HOUR,
        backhaul_load_frac=DEFAULT_BACKHAUL_LOAD_FRAC,
        backhaul_credit_usd_per_t=DEFAULT_BACKHAUL_CREDIT_USD_PER_T,
        use_wacc_for_crf=True,
        simple_interest_pct=DEFAULT_SIMPLE_INTEREST_PCT,
        project_life_years=DEFAULT_PROJECT_LIFE_YEARS,
        WACC=DEFAULT_WACC,
        residual_frac=DEFAULT_RESIDUAL_FRAC,
        use_CEPCI=DEFAULT_USE_CEPCI,
        CEPCI_base=DEFAULT_CEPCI_BASE,
        CEPCI_current=DEFAULT_CEPCI_CURRENT,
        CPI_multiplier=DEFAULT_CPI_MULTIPLIER,
        fuels_table=copy.deepcopy(Fuel_Assumptions),
        days_per_year_in_operation=DEFAULT_DAYS_PER_YEAR_IN_OPERATION,
        port_throughput_t_per_hr=DEFAULT_PORT_THROUGHPUT_T_PER_HR,
        port_pilotage_usd=DEFAULT_PORT_PILOTAGE_USD,
        port_tonnage_usd_per_t=DEFAULT_PORT_TONNAGE_USD_PER_T,
        port_wharfage_usd_per_t=DEFAULT_PORT_WHARFAGE_USD_PER_T,
        port_berthage_usd_per_hr=DEFAULT_PORT_BERTHAGE_USD_PER_HR,
        stores_and_consumables_usd_yr=DEFAULT_STORES_AND_CONSUMABLES_USD_YR,
        maintenance_and_repair_usd_yr=DEFAULT_MAINTENANCE_AND_REPAIR_USD_YR,
        insurance_usd_yr=DEFAULT_INSURANCE_USD_YR,
        general_cost_usd_yr=DEFAULT_GENERAL_COST_USD_YR,
        periodic_maintenance_usd_yr=DEFAULT_PERIODIC_MAINTENANCE_USD_YR,
        aux_power_kW=DEFAULT_AUX_POWER_KW,
    )

def run_default_scenario(selected_fuel=DEFAULT_SELECTED_FUEL):
    legA_kwargs = build_default_legA_kwargs()
    legB_kwargs = None
    result, diags = run_route_two_leg(legA_kwargs, legB_kwargs, selected_fuel)
    em_break = emissions_breakdown_sailing_port(legA_kwargs, legB_kwargs, selected_fuel)
    return {
        "Scenario": selected_fuel,
        "LegA": legA_kwargs,
        "LegB": legB_kwargs,
        "Results": result,
        "Diagnostics": diags,
        "Emissions_Breakdown_Summary": em_break,
        "Cost_Breakdown_Summary": {
            "USD/yr": {
                "CAPEX": result["CAPEX (USD/yr)"],
                "O&M": result["O&M (USD/yr)"],
                "Fuel": result["Fuel Cost (USD/yr)"],
                "Carbon": result["Carbon Cost (USD/yr)"],
            },
            "USD/t-material": {
                "CAPEX": result["CAPEX (USD/t-material)"],
                "O&M": result["O&M (USD/t-material)"],
                "Fuel": result["Fuel Cost (USD/t-material)"],
                "Carbon": result["Carbon Cost (USD/t-material)"],
            },
            "USD/t-Cu": {
                "CAPEX": result["CAPEX (USD/t-Cu)"],
                "O&M": result["O&M (USD/t-Cu)"],
                "Fuel": result["Fuel Cost (USD/t-Cu)"],
                "Carbon": result["Carbon Cost (USD/t-Cu)"],
            },
        },
    }

from pprint import pprint

def rounded_dict(d, ndigits=2):
    return {k: round(float(v), ndigits) for k, v in d.items()}

def _print_summary(out):
    print("Baseline shipping backend run completed.")
    print(f"Scenario: {out['Scenario']}")
    r = out["Results"]

    print(f"Total Levelised Cost of Shipping (USD/t-material): {r['Total Levelised Cost (USD/t-material)']:.2f}")
    print(f"Total Levelised Cost of Shipping (USD/t-Cu): {r['Total Levelised Cost (USD/t-Cu)']:.2f}")
    print(f"Total Emissions Intensity (kgCO2/t-material): {r['CO2 Intensity (kgCO2/t-material)']:.2f}")
    print(f"Total Emissions Intensity (kgCO2/t-Cu): {r['CO2 Intensity (kgCO2/t-Cu)']:.2f}")

    cost_summary = out["Cost_Breakdown_Summary"]
    emissions_summary = out["Emissions_Breakdown_Summary"]

    print("\n=== COST BREAKDOWN (USD/t-material) ===")
    pprint(rounded_dict(cost_summary["USD/t-material"]))

    print("\n=== COST BREAKDOWN (USD/t-Cu) ===")
    pprint(rounded_dict(cost_summary["USD/t-Cu"]))

    print("\n=== COST BREAKDOWN (USD/yr) ===")
    pprint(rounded_dict(cost_summary["USD/yr"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/t-material) ===")
    pprint(rounded_dict(emissions_summary["kgCO2/t-material"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/t-Cu) ===")
    pprint(rounded_dict(emissions_summary["kgCO2/t-Cu"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/yr) ===")
    pprint(rounded_dict(emissions_summary["kgCO2/yr"]))

if __name__ == "__main__":
    baseline = run_default_scenario()
    _print_summary(baseline)