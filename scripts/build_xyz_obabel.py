# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 17:46:16 2026
Last Updated: 02/23/2026

@author: Abhinav Abraham

"""

from pathlib import Path
from .common import which_or_fail, run_cmd

def run(cfg, dirs, logger):
    obabel = cfg["tools"].get("obabel", "obabel")
    which_or_fail(obabel)

    smiles = cfg["general"]["smiles"].strip()
    out_xyz = dirs["obabel"] / f"{cfg['general']['molecule_name']}.xyz"

    if out_xyz.exists() and out_xyz.stat().st_size > 0:
        logger.info("[obabel] SKIP: %s already exists", out_xyz)
        return out_xyz

    # --gen3d is sufficient; minimize is optional (can be helpful)
    cmd = [obabel, f"-:{smiles}", "-O", str(out_xyz), "--gen3d", "--minimize", "--ff", "mmff94", "--steps", "500"]
    rc = run_cmd(cmd, cwd=dirs["obabel"], logger=logger)
    if rc != 0 or not out_xyz.exists():
        raise RuntimeError("Open Babel failed to generate XYZ.")
    logger.info("[obabel] WROTE: %s", out_xyz)
    return out_xyz