# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 17:46:16 2026
Last Updated: 02/28/2026

@author: Abhinav Abraham

"""

import configparser
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

NORMAL_TERM = "Normal termination"

def load_config(config_path: Path) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read(config_path)
    return cfg

def make_run_dirs(cfg) -> dict:
    name = cfg["general"]["molecule_name"]
    root = Path(cfg["general"].get("work_root", "runs")) / name
    d = {
        "root": root,
        "obabel": root / "01_obabel",
        "crest": root / "02_crest",
        "confs": root / "03_confs",
        "gauss": root / "04_gaussian",
        "gjf":  root / "04_gaussian" / "gjf",
        "chk":  root / "04_gaussian" / "chk",
        "out":  root / "04_gaussian" / "out",
        "results": root / "04_gaussian" / "results",
        "log": root / f"{name}.pipeline.log",
    }
    for k, p in d.items():
        if k != "log":
            p.mkdir(parents=True, exist_ok=True)
    return d


class OnlyWarningsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.WARNING

class GaussianLikeFormatter(logging.Formatter):
    """
    A slightly Gaussian-flavored log style for the FILE log.
    - No ' | INFO | ' on every line.
    - Section headers stand out.
    """
    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()

        # Make warnings/errors stand out a bit in file too
        if record.levelno >= logging.ERROR:
            return f" Error: {msg}"
        if record.levelno >= logging.WARNING:
            return f" Warning: {msg}"

        # For normal info, keep it clean
        return msg

def setup_logger(log_path: Path, cfg) -> logging.Logger:
    logger = logging.getLogger("pipeline")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # ---- FILE HANDLER: detailed but Gaussian-like ----
    fh = logging.FileHandler(log_path, mode="a")
    fh.setLevel(logging.INFO)
    fh.setFormatter(GaussianLikeFormatter())
    logger.addHandler(fh)

    # ---- CONSOLE HANDLER: only warnings/errors ----
    sh = logging.StreamHandler()
    sh.setLevel(logging.WARNING)
    sh.addFilter(OnlyWarningsFilter())
    sh.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(sh)

    return logger

def which_or_fail(exe: str) -> str:
    p = shutil.which(exe)
    if not p:
        raise FileNotFoundError(f"Executable not found in PATH: {exe}")
    return p

def run_cmd(cmd: list[str], cwd: Path, logger: logging.Logger, env=None) -> int:
    logger.info("RUN: %s (cwd=%s)", " ".join(cmd), cwd)
    p = subprocess.run(cmd, cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    logger.info("OUTPUT (tail): %s", " | ".join(p.stdout.splitlines()[-20:]))
    return p.returncode

def gaussian_env(cfg) -> dict:
    env = os.environ.copy()
    prof = cfg["tools"].get("gaussian_profile", "").strip()
    if prof:
        # When profile is needed, we run via bash -lc in step runner, not env.
        # Keep env unchanged here.
        pass
    return env

def out_has_normal_termination(out_path: Path) -> bool:
    if not out_path.exists():
        return False
    txt = out_path.read_text(errors="ignore")
    return NORMAL_TERM in txt

def parse_route_method_basis(gjf_path: Path) -> tuple[str, str]:
    # Simple method/basis extraction from route line: token containing method/basis
    lines = gjf_path.read_text(errors="ignore").splitlines()
    route = []
    in_route = False
    for ln in lines:
        s = ln.strip()
        if s.startswith("#"):
            in_route = True
        if in_route:
            if s == "":
                break
            route.append(s)
    route_s = " ".join(route)
    m = re.search(r"([A-Za-z0-9\-\+]+)\/([A-Za-z0-9\-\+\(\),]+)", route_s)
    if m:
        return m.group(1), m.group(2)
    return "unknown", "unknown"

def compute_resources(cfg, stage: str) -> dict:
    """
    Compute max_workers, nprocshared, mem for a given stage.
    Stages: opt, freq, polar, thermo
    """
    auto = cfg["resources"].get("auto_resources", "no").lower() == "yes"
    if not auto:
        # fall back to explicit config values
        return {
            "max_workers": cfg["resources"].getint("max_workers", 4),
            "nproc": int(cfg["resources"].get(f"{stage}_nproc", "6")),
            "mem": cfg["resources"].get(f"{stage}_mem", "4GB"),
        }

    cores_total = cfg["hardware"].getint("cores_total")
    mem_total_gb = cfg["hardware"].getfloat("mem_total_gb")
    headroom = cfg["hardware"].getfloat("mem_headroom", fallback=0.90)

    cores_per_job = cfg["resources"].getint(f"{stage}_cores_per_job", fallback=6)
    min_mem_gb = cfg["resources"].getint(f"{stage}_min_mem_gb", fallback=2)
    
    max_workers = max(1, cores_total // cores_per_job)
    cap = cfg["resources"].getint(f"{stage}_max_workers_cap", fallback=0)
    if cap > 0:
        max_workers = min(max_workers, cap)
    
    mem_per_job_gb = int((mem_total_gb * headroom) // max_workers)
    mem_per_job_gb = max(min_mem_gb, mem_per_job_gb)

    return {
        "max_workers": max_workers,
        "nproc": cores_per_job,
        "mem": f"{mem_per_job_gb}GB",
    }

def log_section(logger, title: str):
    # Gaussian-ish block header
    logger.info(" ------------------------------------------------------------")
    logger.info(" %s", title)
    logger.info(" ------------------------------------------------------------")

def log_kv(logger, key: str, value: str):
    logger.info(" %-24s %s", key + ":", value)