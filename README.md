# MolPolar Pipeline (SMILES → CREST → Gaussian16 → Boltzmann-averaged polarizability)

This repository provides a restartable, config-driven workflow to compute temperature-dependent, Boltzmann-averaged static isotropic polarizability for molecules by chaining SMILES → Open Babel 3D structure generation → CREST/xTB conformer sampling and clustering → Gaussian 16 OPT/FREQ/THERMO/POLAR calculations, with parallel execution, automatic resume via “Normal termination” detection, detailed pipeline logging, and CSV outputs for per-job status and final αiso(T) in Bohr³ and Å³.


Pipeline overview:

1. Build an initial 3D structure from **SMILES** using **Open Babel** (`obabel`)
2. Generate and cluster conformers using **CREST/xTB**
3. Split the clustered conformer ensemble into individual `.xyz` files
4. Generate Gaussian16 input files for each conformer:
   - `OPT` (geometry optimization)
   - `FREQ` (minimum check + force constants)
   - `THERMO` at multiple temperatures using `freq=readfc`
   - `POLAR` (static polarizability)
5. Run Gaussian stages in parallel with automatic resume:
   - Completed jobs are detected by `Normal termination` in `.out` files and skipped on reruns
6. Parse Gaussian outputs and compute **Boltzmann-weighted αiso(T)** (in Bohr³ and Å³)

Temperatures supported are configured in `config.ini` (default: 650, 660, 670, 680, 700, 750 K).

---

## Requirements

### System tools (must be installed)
- **Open Babel** (`obabel`)
- **CREST** and **xTB**
- **Gaussian 16** (`g16`) properly installed and runnable from your shell

> Note: Gaussian 16 is proprietary software and is not installed via pip/conda here.

### Python
- Python 3.9+ recommended
- This project uses only Python standard library modules (no pip dependencies)

---

## Installation

### 1) Clone repo
```bash
git clone <your_repo_url>
cd molpolar_pipeline