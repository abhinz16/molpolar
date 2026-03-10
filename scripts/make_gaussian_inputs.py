# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 17:46:16 2026
Last Updated: 03/01/2026

@author: Abhinav Abraham

"""

from pathlib import Path
from .common import compute_resources

def write_gjf(path: Path, lines: list[str]):
    # Ensure Gaussian terminator blank line:
    path.write_text("\n".join(lines).rstrip() + "\n\n")

def geom_lines_from_xyz(xyz_path: Path) -> list[str]:
    lines = xyz_path.read_text(errors="ignore").splitlines()
    return [ln.strip() for ln in lines[2:] if ln.strip()]

def run(cfg, dirs, logger):
    method = cfg["chemistry"]["method"].strip()
    charge_mult = cfg["chemistry"]["charge_mult"].strip()
    temps = [t.strip() for t in cfg["chemistry"]["temps"].split(",")]

    gjf_dir = dirs["gjf"]
    chk_dir = dirs["chk"]
    out_dir = dirs["out"]
    results = dirs["results"]
    gjf_dir.mkdir(parents=True, exist_ok=True)
    chk_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)

    # resources
    opt_r = compute_resources(cfg, "opt")
    freq_r = compute_resources(cfg, "freq")
    thermo_r = compute_resources(cfg, "thermo")
    polar_r = compute_resources(cfg, "polar")
    
    opt_nproc, opt_mem = opt_r["nproc"], opt_r["mem"]
    freq_nproc, freq_mem = freq_r["nproc"], freq_r["mem"]
    thermo_nproc, thermo_mem = thermo_r["nproc"], thermo_r["mem"]
    polar_nproc, polar_mem = polar_r["nproc"], polar_r["mem"]
    
    logger.info("[resources] OPT   nproc=%s mem=%s", opt_nproc, opt_mem)
    logger.info("[resources] FREQ  nproc=%s mem=%s", freq_nproc, freq_mem)
    logger.info("[resources] THERMO nproc=%s mem=%s", thermo_nproc, thermo_mem)
    logger.info("[resources] POLAR nproc=%s mem=%s", polar_nproc, polar_mem)

    confs = sorted(dirs["confs"].glob("c*.xyz"))
    if not confs:
        raise RuntimeError(f"No conformers found in {dirs['confs']}")

    for xyz in confs:
        conf = xyz.stem
        chk = f"../chk/{conf}.chk"

        # OPT includes coordinates
        opt_route = f"#p opt {method} scf=xqc integral=ultrafine nosymm"
        opt_gjf = gjf_dir / f"{conf}_opt.gjf"
        if not opt_gjf.exists():
            lines = [
                f"%chk={chk}",
                f"%mem={opt_mem}",
                f"%nprocshared={opt_nproc}",
                opt_route,
                "",
                f"{cfg['general']['molecule_name']} {conf} OPT",
                "",
                charge_mult,
                *geom_lines_from_xyz(xyz),
                ""
            ]
            write_gjf(opt_gjf, lines)

        # FREQ reads geometry from chk
        freq_route = f"#p freq {method} geom=check guess=read scf=xqc integral=ultrafine nosymm"
        freq_gjf = gjf_dir / f"{conf}_freq.gjf"
        if not freq_gjf.exists():
            lines = [
                f"%chk={chk}",
                f"%mem={freq_mem}",
                f"%nprocshared={freq_nproc}",
                freq_route,
                "",
                f"{cfg['general']['molecule_name']} {conf} FREQ",
                "",
                charge_mult,
                ""
            ]
            write_gjf(freq_gjf, lines)

        # THERMO (ReadFC) per temperature
        for T in temps:
            thermo_route = f"#p freq=readfc {method} geom=check guess=read Temperature={T} scf=xqc integral=ultrafine nosymm"
            thermo_gjf = gjf_dir / f"{conf}_thermo_{T}.gjf"
            if not thermo_gjf.exists():
                lines = [
                    f"%chk={chk}",
                    f"%mem={thermo_mem}",
                    f"%nprocshared={thermo_nproc}",
                    thermo_route,
                    "",
                    f"{cfg['general']['molecule_name']} {conf} THERMO {T}K",
                    "",
                    charge_mult,
                    ""
                ]
                write_gjf(thermo_gjf, lines)

        # POLAR reads geometry from chk
        polar_route = f"#p polar {method} geom=check guess=read scf=xqc integral=ultrafine nosymm"
        polar_gjf = gjf_dir / f"{conf}_polar.gjf"
        if not polar_gjf.exists():
            lines = [
                f"%chk={chk}",
                f"%mem={polar_mem}",
                f"%nprocshared={polar_nproc}",
                polar_route,
                "",
                f"{cfg['general']['molecule_name']} {conf} POLAR",
                "",
                charge_mult,
                ""
            ]
            write_gjf(polar_gjf, lines)
    
    # --- counts for progress reporting ---
    confs = sorted(dirs["confs"].glob("c*.xyz"))
    n_confs = len(confs)
    
    gjf_dir = dirs["gjf"]
    n_opt = len(list(gjf_dir.glob("*_opt.gjf")))
    n_freq = len(list(gjf_dir.glob("*_freq.gjf")))
    n_polar = len(list(gjf_dir.glob("*_polar.gjf")))
    n_thermo = len(list(gjf_dir.glob("*_thermo_*.gjf")))
    
    logger.info("[gjf] Counts: confs=%d opt=%d freq=%d thermo=%d polar=%d",
                n_confs, n_opt, n_freq, n_thermo, n_polar)
    
    return n_confs, n_opt, n_freq, n_thermo, n_polar