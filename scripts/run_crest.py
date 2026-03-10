# -*- coding: utf-8 -*-
"""

@author: Abhinav Abraham

"""

from pathlib import Path
from .common import which_or_fail, run_cmd

def run(cfg, dirs, logger, input_xyz: Path):
    if cfg["crest"].get("use_crest", "yes").lower() != "yes":
        logger.info("[crest] SKIP: use_crest=no")
        # If you skip crest, treat input_xyz as the single conformer set
        return input_xyz

    crest = cfg["tools"].get("crest", "crest")
    which_or_fail(crest)

    threads = cfg["crest"].getint("threads", 8)
    ewin = cfg["crest"].get("ewin", "15")
    do_gff = cfg["crest"].get("gff", "yes").lower() == "yes"
    do_ref = cfg["crest"].get("gfn2_refine", "yes").lower() == "yes"

    # CREST outputs (names can vary); these are typical
    conformers = dirs["crest"] / "crest_conformers.xyz"
    sorted_conf = dirs["crest"] / "crest_conformers.xyz.sorted"

    # If sorted exists, assume crest+cregen already done
    if sorted_conf.exists() and sorted_conf.stat().st_size > 0:
        logger.info("[crest] SKIP: %s exists", sorted_conf)
        return sorted_conf

    # Run GFN-FF stage
    if do_gff:
        cmd = [crest, str(input_xyz), "-gff", "-ewin", str(ewin), "-T", str(threads)]
        rc = run_cmd(cmd, cwd=dirs["crest"], logger=logger)
        if rc != 0:
            raise RuntimeError("CREST GFN-FF stage failed.")
    else:
        # Direct gfn2 sampling (slower)
        cmd = [crest, str(input_xyz), "-gfn2", "-ewin", str(ewin), "-T", str(threads)]
        rc = run_cmd(cmd, cwd=dirs["crest"], logger=logger)
        if rc != 0:
            raise RuntimeError("CREST GFN2 stage failed.")

    if not conformers.exists():
        raise RuntimeError("CREST did not produce crest_conformers.xyz (check crest output names).")

    # Optional refine with GFN2
    if do_ref:
        cmd = [crest, str(conformers), "-gfn2", "-ewin", str(ewin), "-T", str(threads)]
        rc = run_cmd(cmd, cwd=dirs["crest"], logger=logger)
        if rc != 0:
            raise RuntimeError("CREST refine stage failed.")

    # Cluster/deduplicate
    cmd = [crest, "--cregen", str(conformers)]
    rc = run_cmd(cmd, cwd=dirs["crest"], logger=logger)
    if rc != 0:
        raise RuntimeError("CREGEN clustering failed.")

    # Many CREST versions create crest_conformers.xyz.sorted
    if sorted_conf.exists() and sorted_conf.stat().st_size > 0:
        logger.info("[crest] WROTE: %s", sorted_conf)
        return sorted_conf

    # Fallback: if not sorted, use crest_conformers.xyz
    logger.info("[crest] Using: %s", conformers)
    return conformers