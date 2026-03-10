# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 17:46:16 2026
Last Updated: 02/23/2026

@author: Abhinav Abraham

"""

import csv
import math
import re
from datetime import datetime
from pathlib import Path

HARTREE_TO_KCAL = 627.509474
R_KCAL = 1.987204e-3
BOHR3_TO_A3 = 0.148184711  # 1 Bohr^3 in Å^3

def parse_alpha_iso(polar_out: Path) -> float:
    txt = polar_out.read_text(errors="ignore")
    # Matches: "Isotropic polarizability for W= 0.000000      101.00 Bohr**3."
    m = re.search(r"Isotropic\s+polarizability\s+for\s+W=\s*[-+]?\d+\.\d+\s+([-+]?\d+\.\d+)", txt, re.IGNORECASE)
    if m:
        return float(m.group(1))
    raise RuntimeError(f"Cannot find isotropic polarizability in {polar_out}")

def parse_gibbs(thermo_out: Path) -> float:
    txt = thermo_out.read_text(errors="ignore")
    m = re.search(r"Sum of electronic and thermal Free Energies=\s*([-+]?\d+\.\d+)", txt)
    if not m:
        raise RuntimeError(f"Cannot find Gibbs free energy in {thermo_out}")
    return float(m.group(1))

def run(cfg, dirs, logger):
    temps = [t.strip() for t in cfg["chemistry"]["temps"].split(",")]
    out_dir = dirs["out"]
    results_dir = dirs["results"]
    results_dir.mkdir(parents=True, exist_ok=True)

    confs = sorted({p.name.replace("_polar.out","") for p in out_dir.glob("c*_polar.out")})
    if not confs:
        raise RuntimeError("No polar outputs found; run POLAR stage first.")

    # Parse alpha for each conformer
    alpha = {c: parse_alpha_iso(out_dir / f"{c}_polar.out") for c in confs}

    rows = []
    for T in temps:
        T_int = int(T)
        G = {c: parse_gibbs(out_dir / f"{c}_thermo_{T}.out") for c in confs}
        gmin = min(G.values())

        weights = {}
        Z = 0.0
        for c in confs:
            dG_kcal = (G[c] - gmin) * HARTREE_TO_KCAL
            w = math.exp(-dG_kcal / (R_KCAL * T_int))
            weights[c] = w
            Z += w
        for c in confs:
            weights[c] /= Z

        alpha_avg = sum(weights[c] * alpha[c] for c in confs)

        for c in confs:
            rows.append({
                "molecule": cfg["general"]["molecule_name"],
                "T_K": T_int,
                "conformer": c,
                "weight": weights[c],
                "alpha_iso_bohr3": alpha[c],
                "alpha_iso_A3": alpha[c] * BOHR3_TO_A3,
                "G_hartree": G[c],
            })
        rows.append({
            "molecule": cfg["general"]["molecule_name"],
            "T_K": T_int,
            "conformer": "BOLTZMANN_AVG",
            "weight": 1.0,
            "alpha_iso_bohr3": alpha_avg,
            "alpha_iso_A3": alpha_avg * BOHR3_TO_A3,
            "G_hartree": ""
        })

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = results_dir / f"boltzmann_alpha_{cfg['general']['molecule_name']}_{ts}.csv"

    with out_csv.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames=["molecule","T_K","conformer","weight","alpha_iso_bohr3","alpha_iso_A3","G_hartree"])
        w.writeheader()
        w.writerows(rows)

    logger.info("[boltzmann] WROTE: %s", out_csv)

            
    # Print + log averages in both units
    print("\nBoltzmann-averaged isotropic polarizability:")
    for T in temps:
        T_int = int(T)
        avg_bohr3 = next(r["alpha_iso_bohr3"] for r in rows if r["T_K"] == T_int and r["conformer"] == "BOLTZMANN_AVG")
        avg_a3 = avg_bohr3 * BOHR3_TO_A3
    
        # To file log
        logger.info("[boltzmann] %s K: %.6f Bohr^3 | %.6f Å^3", T, avg_bohr3, avg_a3)
    
        # To screen (no timestamps)
        print(f"  {T_int} K: {avg_bohr3:.6f} Bohr^3 | {avg_a3:.6f} Å^3")

    return out_csv