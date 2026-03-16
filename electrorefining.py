# Copper Electrolytic Refining Model


import numpy as np
import pandas as pd

# -------------------- Constants --------------------
DEFAULT_PROJECT_LIFE = 30
DEFAULT_DISCOUNT_RATE = 7.0
CEPCI_2011_BASE = 585.7
CEPCI_CURRENT_DEFAULT = 798.8
CEPCI_2018_DEFAULT = 603.1

DEFAULT_MINE_CAPACITY = 10_000_000
DEFAULT_ORE_GRADE = 0.0079

FUEL_DEFAULTS = {
    "Electricity (PPA)": {
        "Fuel_Price": 0.06,
        "Emissions_Factor": 0.50,
        "Efficiency": 1.0,
        "Scope": "Scope 2",
    },
    "Natural Gas": {
        "Fuel_Price": 0.118,
        "Emissions_Factor": 0.202,
        "Efficiency": 0.90,
        "Scope": "Scope 1",
    },
    "Coal": {
        "Fuel_Price": 0.013,
        "Emissions_Factor": 0.34,
        "Efficiency": 0.85,
        "Scope": "Scope 1",
    },
    "Hydrogen": {
        "Fuel_Price": 0.108,
        "Emissions_Factor": 0.00,
        "Efficiency": 0.90,
        "Scope": "Scope 1 (upstream eq.)",
    },
}

CAPEX_PER_T_CU_BASE = 1000
CAPEX_SPLIT = {
    "Anode reception & prep": 0.17,
    "Electrorefining equipment": 0.39,
    "Electrolyte & purification": 0.18,
    "Cathode handling": 0.11,
    "Scrap melt & anode casting": 0.14,
    "Additional": 0.00,
}

REFINERY_WEEKLY_AUD = 1326.59
USD_PER_AUD = 0.7
HOURS_PER_WEEK = 40
MAINTENANCE_FRAC_OF_CAPEX_DEFAULT = 0.05

# -------------------- Paper-friendly defaults --------------------
DEFAULT_SIMPLE_MIX = {
    "Electricity (PPA) %": 49.0,
    "Natural Gas %": 51.0,
    "Coal %": 0.0,
    "Hydrogen %": 0.0,
}

DEFAULT_ADVANCED_CALIBRATION = {
    "cell_dc_kWh_per_t": 400.0,
    "rectifier_efficiency": 0.92,
    "aux_elec_kWh_per_t": 15.0,
    "cathode_handling_kWh_per_t": 12.0,
    "gas_handling_kWh_per_t": 6.0,
    "thermal_useful_kWh_per_t": 416.0,
    "thermal_fuel_input_kWh_per_t": 0.0,
    "thermal_fuel": "Natural Gas",
    "reagent_makeup_kg_per_t": 2.0,
    "reagent_emission_factor": 2.0,
}

DEFAULT_MODEL_INPUTS = {
    "mine_capacity_t_ore_yr": DEFAULT_MINE_CAPACITY,
    "ore_grade_frac": DEFAULT_ORE_GRADE,
    "conc_grade_frac": 0.30,
    "copper_recovery_frac": 0.85,
    "process_availability_frac": 0.90,
    "project_life_years": DEFAULT_PROJECT_LIFE,
    "discount_rate_pct": DEFAULT_DISCOUNT_RATE,
    "carbon_price_usd_per_t": 21.9,
    "scope1_baseline_kg_per_t_cu": 0.0,
    "fte_count": 120,
    "avg_salary_usd": 80_000.0,
    "capex_current_usd_per_t_capacity": 1000.0,
    "cepci_tankhouse": CEPCI_CURRENT_DEFAULT,
    "maintenance_frac": MAINTENANCE_FRAC_OF_CAPEX_DEFAULT,
    "ppa_price_usd_per_kwh": 0.111,
    "ppa_emission_factor": 0.70,
    "ng_price_usd_per_gj": FUEL_DEFAULTS["Natural Gas"]["Fuel_Price"] * 277.78,
    "ng_emission_factor": FUEL_DEFAULTS["Natural Gas"]["Emissions_Factor"],
    "coal_price_usd_per_t": FUEL_DEFAULTS["Coal"]["Fuel_Price"] * (8.14 * 1000),
    "coal_emission_factor": FUEL_DEFAULTS["Coal"]["Emissions_Factor"],
    "h2_price_usd_per_kg": FUEL_DEFAULTS["Hydrogen"]["Fuel_Price"] * 33.33,
    "h2_emission_factor": FUEL_DEFAULTS["Hydrogen"]["Emissions_Factor"],
}


def capital_recovery_factor(discount_rate_pct, project_life_yr):
    r = discount_rate_pct / 100.0
    n = int(project_life_yr)
    return (r * (1 + r) ** n) / ((1 + r) ** n - 1)


def compute_refining_flows(
    mine_capacity_t_ore_yr,
    ore_grade_frac,
    conc_grade_frac,
    copper_recovery_frac,
    process_availability_frac,
    smelter_rec=0.97,
    converter_rec=0.97,
    anode_rec=0.97,
    anode_grade=0.999,
    anode_availability=0.90,
    matte_grade=0.65,
    blister_grade=0.99,
    slag_ratio=2.2,
    cathode_grade=0.99,
    cathode_recovery=0.99,
):
    concentrate_produced = (mine_capacity_t_ore_yr * ore_grade_frac * copper_recovery_frac / conc_grade_frac)
    contained_cu_in_conc = concentrate_produced * conc_grade_frac
    contained_cu_in_matte = contained_cu_in_conc * smelter_rec
    matte_produced = contained_cu_in_matte / matte_grade
    cu_after_converter = contained_cu_in_matte * converter_rec
    blister_produced = cu_after_converter / blister_grade

    cu_into_anode_furnace = cu_after_converter
    cu_after_anode = cu_into_anode_furnace * anode_rec
    anode_capacity = cu_after_anode / anode_grade
    t_anode = anode_capacity * anode_availability

    cathode_capacity = t_anode * anode_grade * cathode_recovery / cathode_grade
    t_cathode = cathode_capacity * process_availability_frac
    t_cu_total = t_cathode * cathode_grade
    t_cu_per_t_conc = t_cu_total / max(concentrate_produced, 1e-9)

    return {
        "Concentrate_Produced": concentrate_produced,
        "Contained_Cu_in_Conc": contained_cu_in_conc,
        "Matte_Produced": matte_produced,
        "Blister_Produced": blister_produced,
        "Copper_Anode_Production": t_anode,
        "Copper_Cathode_Production": t_cathode,
        "t_Cu_total": t_cu_total,
        "t_Cu_per_t_conc": t_cu_per_t_conc,
    }


def compute_capex_per_year(
    t_cu_per_year,
    discount_rate_pct,
    project_life_years,
    cepci_current,
    capex_per_t_cu_base=CAPEX_PER_T_CU_BASE,
):
    ratio = float(cepci_current) / CEPCI_2011_BASE
    capex_per_t_cu_scaled = capex_per_t_cu_base * ratio
    total_installed_capex = capex_per_t_cu_scaled * t_cu_per_year
    crf = capital_recovery_factor(discount_rate_pct, project_life_years)
    annualised = total_installed_capex * crf
    return annualised, capex_per_t_cu_scaled, ratio, total_installed_capex


def compute_scope_capex(
    t_cu_per_year,
    *,
    er_capex_base_2011,
    cepci_current,
    discount_rate_pct=DEFAULT_DISCOUNT_RATE,
    project_life_years=DEFAULT_PROJECT_LIFE,
):
    er_intensity_current = float(er_capex_base_2011) * (float(cepci_current) / CEPCI_2011_BASE)
    installed_intensity = er_intensity_current
    total_installed_capex = installed_intensity * float(t_cu_per_year)
    crf = capital_recovery_factor(discount_rate_pct, project_life_years)
    annualised_capex = total_installed_capex * crf
    return {
        "er_intensity_current": er_intensity_current,
        "installed_intensity": installed_intensity,
        "total_installed_capex": total_installed_capex,
        "annualised_capex": annualised_capex,
        "crf": crf,
    }


def staffing_cost_per_year(t_cu_per_year_unused, fte_count, avg_salary_usd):
    return float(fte_count) * float(avg_salary_usd)


def maintenance_cost_per_year(total_installed_capex_usd, maintenance_frac=MAINTENANCE_FRAC_OF_CAPEX_DEFAULT):
    return float(maintenance_frac) * float(total_installed_capex_usd)


def advanced_costs_and_emissions(
    t_cu_per_year,
    *,
    cell_dc_kWh_per_t=400.0,
    rectifier_efficiency=0.92,
    aux_elec_kWh_per_t=15.0,
    cathode_handling_kWh_per_t=12.0,
    gas_handling_kWh_per_t=6.0,
    thermal_useful_kWh_per_t=416.0,
    thermal_fuel_input_kWh_per_t=0.0,
    thermal_fuel="Natural Gas",
    thermal_blend=None,
    fuels=None,
    ppa_price_usd_per_kwh=0.111,
    ppa_emission_factor=0.70,
    reagent_makeup_kg_per_t=2.0,
    reagent_emission_factor=2.0,
):
    cell_ac_kWh_per_t = cell_dc_kWh_per_t / max(rectifier_efficiency, 1e-9)
    rectifier_losses_kWh_per_t = cell_ac_kWh_per_t - cell_dc_kWh_per_t

    elec_breakdown_kWh_per_t = {
        "Cell Load": cell_dc_kWh_per_t,
        "Rectifier Losses": rectifier_losses_kWh_per_t,
        "Auxiliary Systems": aux_elec_kWh_per_t,
        "Cathode Handling": cathode_handling_kWh_per_t,
        "Gas Handling": gas_handling_kWh_per_t,
    }
    elec_total_kWh_per_t = sum(elec_breakdown_kWh_per_t.values())
    elec_total_kWh_y = elec_total_kWh_per_t * t_cu_per_year

    elec_cost_y = elec_total_kWh_y * ppa_price_usd_per_kwh
    elec_em_y = elec_total_kWh_y * ppa_emission_factor
    elec_breakdown_em_y = {k: (v * t_cu_per_year * ppa_emission_factor) for k, v in elec_breakdown_kWh_per_t.items()}

    if thermal_blend and isinstance(thermal_blend, dict) and sum(thermal_blend.values()) > 1e-12:
        input_per_t = 0.0
        cost_per_t = 0.0
        em_per_t = 0.0
        for f, sh in thermal_blend.items():
            eta = max(fuels[f]["Efficiency"], 1e-9)
            price = fuels[f]["Fuel_Price"]
            ef = fuels[f]["Emissions_Factor"]
            inp_i = thermal_useful_kWh_per_t / eta * sh
            input_per_t += inp_i
            cost_per_t += inp_i * price
            em_per_t += inp_i * ef
        thermal_total_kWh_y = input_per_t * t_cu_per_year
        fuel_cost_y = cost_per_t * t_cu_per_year
        fuel_em_y = em_per_t * t_cu_per_year
    else:
        tf = fuels[thermal_fuel]
        if thermal_fuel_input_kWh_per_t and thermal_fuel_input_kWh_per_t > 0:
            thermal_input_kWh_per_t = float(thermal_fuel_input_kWh_per_t)
        else:
            thermal_input_kWh_per_t = thermal_useful_kWh_per_t / max(tf["Efficiency"], 1e-9)
        thermal_total_kWh_y = thermal_input_kWh_per_t * t_cu_per_year
        fuel_cost_y = thermal_total_kWh_y * tf["Fuel_Price"]
        fuel_em_y = thermal_total_kWh_y * tf["Emissions_Factor"]

    reagent_em_y = reagent_makeup_kg_per_t * reagent_emission_factor * t_cu_per_year
    total_em_y = elec_em_y + fuel_em_y + reagent_em_y
    scope1_em_y = fuel_em_y

    return {
        "fuel_cost_y": fuel_cost_y,
        "elec_cost_y": elec_cost_y,
        "total_em_y": total_em_y,
        "scope1_em_y": scope1_em_y,
        "elec_total_kWh_per_t": elec_total_kWh_per_t,
        "thermal_input_kWh_per_t": thermal_total_kWh_y / max(t_cu_per_year, 1e-9),
        "elec_em_breakdown_y": elec_breakdown_em_y,
        "fuel_em_y": fuel_em_y,
        "reagent_em_y": reagent_em_y,
    }


def lcoa_vs_baseline(user_levelised, base_levelised, user_em_intensity, base_em_intensity):
    avoided = base_em_intensity - user_em_intensity
    if abs(avoided) < 1e-9:
        return None, 0.0
    return (user_levelised - base_levelised) / avoided, avoided


def _thermal_blend_from_shares(ng, coal, h2):
    raw = {"Natural Gas": ng, "Coal": coal, "Hydrogen": h2}
    s = sum(raw.values())
    if s <= 0:
        return None
    return {k: v / s for k, v in raw.items() if v > 0}


def _build_fuels(ppa_price_usd_per_kwh, ppa_emission_factor, ng_price_usd_per_gj, ng_emission_factor,
                 coal_price_usd_per_t, coal_emission_factor, h2_price_usd_per_kg, h2_emission_factor):
    fuels = {k: v.copy() for k, v in FUEL_DEFAULTS.items()}
    fuels["Electricity (PPA)"]["Fuel_Price"] = float(ppa_price_usd_per_kwh)
    fuels["Electricity (PPA)"]["Emissions_Factor"] = float(ppa_emission_factor)
    fuels["Natural Gas"]["Fuel_Price"] = float(ng_price_usd_per_gj) / 277.78
    fuels["Natural Gas"]["Emissions_Factor"] = float(ng_emission_factor)
    fuels["Coal"]["Fuel_Price"] = float(coal_price_usd_per_t) / (8.14 * 1000.0)
    fuels["Coal"]["Emissions_Factor"] = float(coal_emission_factor)
    fuels["Hydrogen"]["Fuel_Price"] = float(h2_price_usd_per_kg) / 33.33
    fuels["Hydrogen"]["Emissions_Factor"] = float(h2_emission_factor)
    return fuels


def _safe_div(a, b):
    return a / b if b not in (0, 0.0, None) else 0.0


def run_scenario(
    scenario_name="Baseline",
    simple_mix=None,
    advanced_calibration=None,
    **kwargs,
):
    inputs = DEFAULT_MODEL_INPUTS.copy()
    inputs.update(kwargs)
    simple_mix = DEFAULT_SIMPLE_MIX.copy() if simple_mix is None else simple_mix.copy()
    adv = DEFAULT_ADVANCED_CALIBRATION.copy()
    if advanced_calibration:
        adv.update(advanced_calibration)

    flows = compute_refining_flows(
        inputs["mine_capacity_t_ore_yr"],
        inputs["ore_grade_frac"],
        inputs["conc_grade_frac"],
        inputs["copper_recovery_frac"],
        inputs["process_availability_frac"],
    )
    t_cathode = float(flows["Copper_Cathode_Production"])
    t_cu_total = float(flows["t_Cu_total"])
    concentrate_produced = float(flows["Concentrate_Produced"])
    t_anode = float(flows["Copper_Anode_Production"])

    fuels = _build_fuels(
        inputs["ppa_price_usd_per_kwh"],
        inputs["ppa_emission_factor"],
        inputs["ng_price_usd_per_gj"],
        inputs["ng_emission_factor"],
        inputs["coal_price_usd_per_t"],
        inputs["coal_emission_factor"],
        inputs["h2_price_usd_per_kg"],
        inputs["h2_emission_factor"],
    )

    thermal_blend = _thermal_blend_from_shares(
        simple_mix.get("Natural Gas %", 0.0),
        simple_mix.get("Coal %", 0.0),
        simple_mix.get("Hydrogen %", 0.0),
    )

    scope_capex = compute_scope_capex(
        t_cu_total,
        er_capex_base_2011=float(inputs["capex_current_usd_per_t_capacity"]) * (CEPCI_2011_BASE / max(float(inputs["cepci_tankhouse"]), 1e-9)),
        cepci_current=inputs["cepci_tankhouse"],
        discount_rate_pct=inputs["discount_rate_pct"],
        project_life_years=inputs["project_life_years"],
    )

    annual_capex = scope_capex["annualised_capex"]
    installed_capex = scope_capex["total_installed_capex"]
    annual_staffing = staffing_cost_per_year(t_cu_total, inputs["fte_count"], inputs["avg_salary_usd"])
    annual_maintenance = maintenance_cost_per_year(installed_capex, inputs["maintenance_frac"])

    ae = advanced_costs_and_emissions(
        t_cu_total,
        cell_dc_kWh_per_t=adv["cell_dc_kWh_per_t"],
        rectifier_efficiency=adv["rectifier_efficiency"],
        aux_elec_kWh_per_t=adv["aux_elec_kWh_per_t"],
        cathode_handling_kWh_per_t=adv["cathode_handling_kWh_per_t"],
        gas_handling_kWh_per_t=adv["gas_handling_kWh_per_t"],
        thermal_useful_kWh_per_t=adv["thermal_useful_kWh_per_t"],
        thermal_fuel_input_kWh_per_t=adv["thermal_fuel_input_kWh_per_t"],
        thermal_fuel=adv["thermal_fuel"],
        thermal_blend=thermal_blend,
        fuels=fuels,
        ppa_price_usd_per_kwh=inputs["ppa_price_usd_per_kwh"],
        ppa_emission_factor=inputs["ppa_emission_factor"],
        reagent_makeup_kg_per_t=adv["reagent_makeup_kg_per_t"],
        reagent_emission_factor=adv["reagent_emission_factor"],
    )

    annual_fuel_cost = ae["fuel_cost_y"]
    annual_electricity_cost = ae["elec_cost_y"]
    annual_reagent_cost = 0.0
    total_opex = annual_staffing + annual_maintenance + annual_fuel_cost + annual_electricity_cost + annual_reagent_cost

    scope1_kg_per_year = ae["scope1_em_y"]
    scope2_kg_per_year = sum(ae["elec_em_breakdown_y"].values())
    reagent_kg_per_year = ae["reagent_em_y"]
    total_emissions_kg_per_year = ae["total_em_y"]

    scope1_intensity_kg_per_t_cu = _safe_div(scope1_kg_per_year, t_cu_total)
    excess_scope1_kg_per_t_cu = max(0.0, scope1_intensity_kg_per_t_cu - float(inputs["scope1_baseline_kg_per_t_cu"]))
    annual_carbon_cost = (excess_scope1_kg_per_t_cu / 1000.0) * float(inputs["carbon_price_usd_per_t"]) * t_cu_total

    total_annualised_cost = annual_capex + total_opex + annual_carbon_cost

    cost_annual = {
        "CAPEX": annual_capex,
        "Fuel": annual_fuel_cost,
        "Electricity": annual_electricity_cost,
        "Staffing": annual_staffing,
        "Maintenance": annual_maintenance,
        "Reagents": annual_reagent_cost,
        "Carbon Pricing": annual_carbon_cost,
    }

    emissions_annual = {
        "Cell Load electricity": ae["elec_em_breakdown_y"].get("Cell Load", 0.0),
        "Rectifier losses": ae["elec_em_breakdown_y"].get("Rectifier Losses", 0.0),
        "Auxiliary systems": ae["elec_em_breakdown_y"].get("Auxiliary Systems", 0.0),
        "Cathode handling": ae["elec_em_breakdown_y"].get("Cathode Handling", 0.0),
        "Gas handling": ae["elec_em_breakdown_y"].get("Gas Handling", 0.0),
        "Thermal fuel": ae["fuel_em_y"],
        "Reagents": ae["reagent_em_y"],
    }

    results = {
        "Scenario": scenario_name,
        "Concentrate Produced (t-conc/yr)": concentrate_produced,
        "Anode Production (t-anode/yr)": t_anode,
        "Cathode Production (t-cathode/yr)": t_cathode,
        "t_Cu_total": t_cu_total,
        "t_Cu_per_t_conc": flows["t_Cu_per_t_conc"],
        "Installed CAPEX (USD)": installed_capex,
        "Annual CAPEX (USD/yr)": annual_capex,
        "Annual OPEX (USD/yr)": total_opex,
        "Annual Fuel Cost (USD/yr)": annual_fuel_cost,
        "Annual Electricity Cost (USD/yr)": annual_electricity_cost,
        "Annual Staffing Cost (USD/yr)": annual_staffing,
        "Annual Maintenance Cost (USD/yr)": annual_maintenance,
        "Annual Reagent Cost (USD/yr)": annual_reagent_cost,
        "Annual Carbon Cost (USD/yr)": annual_carbon_cost,
        "Total Annualised Cost (USD/yr)": total_annualised_cost,
        "Total Emissions (kgCO2/yr)": total_emissions_kg_per_year,
        "Scope 1 Emissions (kgCO2/yr)": scope1_kg_per_year,
        "Scope 2 Emissions (kgCO2/yr)": scope2_kg_per_year,
        "Reagent Emissions (kgCO2/yr)": reagent_kg_per_year,
        "Scope 1 Baseline (kgCO2/t-Cu)": float(inputs["scope1_baseline_kg_per_t_cu"]),
        "Scope 1 Excess (kgCO2/t-Cu)": excess_scope1_kg_per_t_cu,
        "Scope 1 Intensity (kgCO2/t-Cu)": scope1_intensity_kg_per_t_cu,
        "Levelised Cost (USD/t-cathode)": _safe_div(total_annualised_cost, t_cathode),
        "Levelised Cost (USD/t-Cu)": _safe_div(total_annualised_cost, t_cu_total),
        "Levelised Cost (USD/t-conc)": _safe_div(total_annualised_cost, concentrate_produced),
        "Emission Intensity (kgCO2/t-cathode)": _safe_div(total_emissions_kg_per_year, t_cathode),
        "Emission Intensity (kgCO2/t-Cu)": _safe_div(total_emissions_kg_per_year, t_cu_total),
        "Emission Intensity (kgCO2/t-conc)": _safe_div(total_emissions_kg_per_year, concentrate_produced),
        "Electricity Total (kWh/t-Cu)": ae["elec_total_kWh_per_t"],
        "Thermal Input (kWh/t-Cu)": ae["thermal_input_kWh_per_t"],
        "Cost_Breakdown_Summary": {
            "USD/yr": cost_annual,
            "USD/t-cathode": {k: _safe_div(v, t_cathode) for k, v in cost_annual.items()},
            "USD/t-Cu": {k: _safe_div(v, t_cu_total) for k, v in cost_annual.items()},
            "USD/t-conc": {k: _safe_div(v, concentrate_produced) for k, v in cost_annual.items()},
        },
        "Emissions_Breakdown_Summary": {
            "kgCO2/yr": emissions_annual,
            "kgCO2/t-cathode": {k: _safe_div(v, t_cathode) for k, v in emissions_annual.items()},
            "kgCO2/t-Cu": {k: _safe_div(v, t_cu_total) for k, v in emissions_annual.items()},
            "kgCO2/t-conc": {k: _safe_div(v, concentrate_produced) for k, v in emissions_annual.items()},
        },
    }
    return results


from pprint import pprint

def rounded_dict(d, ndigits=2):
    return {k: round(float(v), ndigits) for k, v in d.items()}

def _print_summary(results):
    print(f"Scenario: {results.get('Scenario', 'N/A')}")
    print(f"Levelised Cost (USD/t-cathode): {results.get('Levelised Cost (USD/t-cathode)', 0.0):.2f}")
    print(f"Levelised Cost (USD/t-Cu): {results.get('Levelised Cost (USD/t-Cu)', 0.0):.2f}")
    print(f"Levelised Cost (USD/t-conc): {results.get('Levelised Cost (USD/t-conc)', 0.0):.2f}")
    print(f"Emission Intensity (kgCO2/t-cathode): {results.get('Emission Intensity (kgCO2/t-cathode)', 0.0):.2f}")
    print(f"Emission Intensity (kgCO2/t-Cu): {results.get('Emission Intensity (kgCO2/t-Cu)', 0.0):.2f}")
    print(f"Emission Intensity (kgCO2/t-conc): {results.get('Emission Intensity (kgCO2/t-conc)', 0.0):.2f}")
    print(f"Scope 1 Intensity (kgCO2/t-Cu): {results.get('Scope 1 Intensity (kgCO2/t-Cu)', 0.0):.2f}")

    cost_summary = results["Cost_Breakdown_Summary"]
    emissions_summary = results["Emissions_Breakdown_Summary"]

    print("\n=== COST BREAKDOWN (USD/t-cathode) ===")
    pprint(rounded_dict(cost_summary["USD/t-cathode"]))

    print("\n=== COST BREAKDOWN (USD/t-Cu) ===")
    pprint(rounded_dict(cost_summary["USD/t-Cu"]))

    print("\n=== COST BREAKDOWN (USD/t-conc) ===")
    pprint(rounded_dict(cost_summary["USD/t-conc"]))

    print("\n=== COST BREAKDOWN (USD/yr) ===")
    pprint(rounded_dict(cost_summary["USD/yr"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/t-cathode) ===")
    pprint(rounded_dict(emissions_summary["kgCO2/t-cathode"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/t-Cu) ===")
    pprint(rounded_dict(emissions_summary["kgCO2/t-Cu"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/t-conc) ===")
    pprint(rounded_dict(emissions_summary["kgCO2/t-conc"]))

    print("\n=== EMISSIONS BREAKDOWN (kgCO2/yr) ===")
    pprint(rounded_dict(emissions_summary["kgCO2/yr"]))

if __name__ == "__main__":
    baseline = run_scenario(scenario_name="Baseline")
    print("Baseline electrorefining backend run completed.")
    _print_summary(baseline)
