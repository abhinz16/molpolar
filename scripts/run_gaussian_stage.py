# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 17:46:16 2026
Last Updated: 02/28/2026

@author: Abhinav Abraham

"""

import csv
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from .common import out_has_normal_termination, parse_route_method_basis, compute_resources

@dataclass
class Job:
    gjf: Path
    out: Path
    stage: str

def run_one(job: Job, gjf_dir: Path, out_dir: Path, g16: str, profile: str | None):
    # Skip if already done
    if out_has_normal_termination(job.out):
        return (job.gjf.name, "SKIP", 0)

    # Run from within gjf_dir so %chk=../chk works
    cwd0 = os.getcwd()
    try:
        os.chdir(gjf_dir)
        if profile:
            cmd = f"bash -lc 'source {profile} && {g16} < {job.gjf.name} > ../out/{job.out.name} 2>&1'"
        else:
            cmd = f"{g16} < {job.gjf.name} > ../out/{job.out.name} 2>&1"
        rc = os.system(cmd)
        # Normalize return code on POSIX
        if os.name == "posix":
            try:
                rc = os.WEXITSTATUS(rc)
            except Exception:
                pass
        status = "SUCCESS" if out_has_normal_termination(job.out) else "FAIL"
        return (job.gjf.name, status, rc)
    finally:
        os.chdir(cwd0)

def run_stage(cfg, dirs, logger, suffix: str, stage_name: str):
    g16 = cfg["tools"].get("g16", "g16")
    profile = cfg["tools"].get("gaussian_profile", "").strip() or None
    
    stage_key = stage_name.split("_")[0]  # opt, freq, thermo, polar
    max_workers = compute_resources(cfg, stage_key)["max_workers"]

    gjf_dir = dirs["gjf"]
    out_dir = dirs["out"]

    gjfs = sorted(gjf_dir.glob(f"*{suffix}"))
    if not gjfs:
        logger.info("[%s] No inputs found for %s", stage_name, suffix)
        return None

    jobs = []
    for gjf in gjfs:
        out = out_dir / f"{gjf.stem}.out"
        jobs.append(Job(gjf=gjf, out=out, stage=stage_name))

    method, basis = parse_route_method_basis(gjfs[0])
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = dirs["gauss"] / f"status_{cfg['general']['molecule_name']}_{stage_name}_{method}_{basis}_{ts}.csv"

    logger.info("[%s] Running %d jobs with max_workers=%d", stage_name, len(jobs), max_workers)
    ok = fail = skip = 0
    rows = []

    total = len(jobs)
    print(f"[{stage_name}] starting: total={total}, max_workers={max_workers}")
    
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(run_one, j, gjf_dir, out_dir, g16, profile): j for j in jobs}
        done = 0
        for fut in as_completed(futs):
            done += 1
            name, status, rc = fut.result()
    
            if status == "SUCCESS":
                ok += 1
            elif status == "SKIP":
                skip += 1
            else:
                fail += 1
    
            # --- Clean progress on screen (no timestamps) ---
            # Print every job, or throttle (see below)
            print(f"[{stage_name}] {done}/{total}  ok={ok}  fail={fail}  skip={skip}  last={name}:{status}")
    
            # --- Detailed to file log ---
            logger.info("[%s] %d/%d %s -> %s", stage_name, done, total, name, status)
    
            rows.append({"gjf": name, "status": status, "returncode": rc})
    
    print(f"[{stage_name}] finished: ok={ok}, fail={fail}, skip={skip}")

    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["gjf","status","returncode"])
        w.writeheader()
        w.writerows(rows)

    logger.info("[%s] Done. SUCCESS=%d SKIP=%d FAIL=%d. CSV=%s", stage_name, ok, skip, fail, csv_path)
    return csv_path