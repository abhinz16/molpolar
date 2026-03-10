# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 17:46:16 2026
Last Updated: 02/28/2026

@author: Abhinav Abraham

"""

from pathlib import Path
from scripts.common import load_config, make_run_dirs, setup_logger, log_section, log_kv
from scripts import build_xyz_obabel as s1
from scripts import run_crest as s2
from scripts import split_conformers as s3
from scripts import make_gaussian_inputs as s4
from scripts.run_gaussian_stage import run_stage
from scripts import compute_boltzmann_alpha as s6

def stage_summary(cfg, dirs, suffix: str, stage_name: str):
    gjf_dir = dirs["gjf"]
    out_dir = dirs["out"]

    gjfs = sorted(gjf_dir.glob(f"*{suffix}"))
    total = len(gjfs)

    done = 0
    for gjf in gjfs:
        outp = out_dir / f"{gjf.stem}.out"
        if outp.exists():
            txt = outp.read_text(errors="ignore")
            if "Normal termination" in txt:
                done += 1

    todo = total - done
    max_workers = cfg["resources"].getint("max_workers", 4)

    print(f"[{stage_name}] jobs found: {total} | already done: {done} | to run: {todo} | max_workers: {max_workers}")

def main():
    cfg = load_config(Path("config.ini"))
    dirs = make_run_dirs(cfg)
    logger = setup_logger(dirs["log"], cfg)
    
    log_section(logger, "PIPELINE START")
    log_kv(logger, "Molecule", cfg["general"]["molecule_name"])
    log_kv(logger, "SMILES", cfg["general"]["smiles"])
    log_kv(logger, "Method", cfg["chemistry"]["method"])
    log_kv(logger, "Temperatures (K)", cfg["chemistry"]["temps"])

    print("\n[Step 1/6] Build initial XYZ with Open Babel...")
    xyz = s1.run(cfg, dirs, logger)
    print(f"[Step 1/6] Done. XYZ: {xyz}")
    
    print("[Step 2/6] Running CREST... this may take a while.")
    multi_xyz = s2.run(cfg, dirs, logger, xyz)
    print(f"[Step 2/6] Done. Using: {multi_xyz}")
    
    print("\n[Step 3/6] Split multi-XYZ into individual conformers...")
    n_confs = s3.run(cfg, dirs, logger, multi_xyz)
    # If s3 returns the dir; if not, just print dirs["confs"]
    print(f"[Step 3/6] Done. Conformers created: {n_confs}")
    
    print("\n[Step 4/6] Generate Gaussian input files (gjf)...")
    n_confs, n_opt, n_freq, n_thermo, n_polar = s4.run(cfg, dirs, logger)
    print(f"[Step 4/6] Done. confs={n_confs}, opt={n_opt}, freq={n_freq}, thermo={n_thermo}, polar={n_polar}")

    if cfg["gaussian"].get("run_opt","yes").lower()=="yes":
        print("\n=== OPT stage ===")
        stage_summary(cfg, dirs, suffix="_opt.gjf", stage_name="opt")
        run_stage(cfg, dirs, logger, suffix="_opt.gjf", stage_name="opt")

    if cfg["gaussian"].get("run_freq","yes").lower()=="yes":
        print("\n=== FREQ stage ===")
        stage_summary(cfg, dirs, suffix="_freq.gjf", stage_name="freq")
        run_stage(cfg, dirs, logger, suffix="_freq.gjf", stage_name="freq")

    if cfg["gaussian"].get("run_thermo","yes").lower()=="yes":
        print("\n=== THERMO stage ===")
        for T in ["650","660","670","680","700","750"]:
            suffix = f"_thermo_{T}.gjf"
            stage_name = f"thermo_{T}"
            stage_summary(cfg, dirs, suffix=suffix, stage_name=stage_name)
            run_stage(cfg, dirs, logger, suffix=suffix, stage_name=stage_name)

    if cfg["gaussian"].get("run_polar","yes").lower()=="yes":
        print("\n=== POLAR stage ===")
        stage_summary(cfg, dirs, suffix="_polar.gjf", stage_name="polar")
        run_stage(cfg, dirs, logger, suffix="_polar.gjf", stage_name="polar")

    s6.run(cfg, dirs, logger)
    
    log_section(logger, "PIPELINE END")

if __name__ == "__main__":
    main()