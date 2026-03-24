# toy-zkVM

A hands-on walkthrough of the Jolt zkVM pipeline, from program execution to Groth16 proof. Every exercise uses **F_97** so all numbers are small and hand-checkable.

## Exercises

| # | File | Topic |
|---|------|-------|
| 1 | `01_trace_to_polynomial.py` | Program -> execution trace -> MLE polynomials |
| 2 | `02_sumcheck.py` | Sumcheck: verify a sum without touching each row |
| 3 | `03_fiat_shamir.py` | Fiat-Shamir: make it non-interactive with hashing |
| 4 | `04_symbolic_execution.py` | Symbolic execution: record ops instead of computing |
| 5 | `05_circuit_generation.py` | From AST to circuit constraints |
| 6 | `06_full_pipeline.py` | End-to-end: trace -> proof -> verify -> circuit |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install marimo
```

## Run

```bash
source .venv/bin/activate
marimo edit 01_trace_to_polynomial.py
```

This opens the notebook in your browser. You can also `marimo run` for read-only mode.
