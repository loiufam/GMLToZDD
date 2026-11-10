# Topology-Aware Experiment Runbook

All commands run from `GMLToMat`.

## Generated Inputs

- Selected matrices: `matrices/`
- Normalized `.in` graphs: `inputs/`
- Three seed candidates per graph: `candidates/`
- Selection metrics: `selection_report.csv`
- Frozen generator criteria: `selection_manifest.json`

## 1. Regenerate Deterministically

```bash
cd /home/lyh/projects/lyh/Alg_DXD/GMLToMat

python3 generate_exact_cover.py \
  --select-rome-dir graphs_graphml/rome_3 \
  --output experiments/rome_graphs_to_matrices_1108 \
  --seed 20261118 \
  --search-seeds 1 \
  --select-count 10 \
  --randomize-candidates \
  --min-edges 125 --max-edges 160 \
  --min-nodes 90 --max-nodes 100 \
  --min-fill-edges 126 --min-elimination-width 8 \
  --min-degree-std 1.2 --max-articulation-ratio 0.30 \
  --min-blocks 10 --max-blocks 10 \
  --min-extra-solutions 4500 --max-extra-solutions 5000 \
  --matrix-rows-min 37001 --matrix-rows-max 250000 \
  --matrix-cols-min 641 --matrix-cols-max 2000 \
  --min-components 1 --max-components 50 \
  --min-largest-area-share 0 --max-largest-area-share 1 \
  --min-solution-log10 95 \
  --target-matrix-rows 180000 --target-matrix-cols 800 \
  --target-area-share 0.04 \
  --min-replications 5
  --max-replications 6
  --base-matrix-cols-min 150

  --exclude-matrix-dir experiments/rome_graphs_to_matrices/matrices \
```

The generator sets `ZDD_SEED` for the C++ engine. A repeated run must produce identical matrix hashes. The expected ZDD engine SHA-256 for this generated suite is recorded in `selection_manifest.json`.

## 2. Recheck the Selection

```bash
python3 - <<'PY'
import csv
rows = list(csv.DictReader(open(
    "experiments/topology_standard_20261106/selection_report.csv"
)))
print("selected:", len(rows))
print("profile_pass:", sum(r["within_profile"] == "True" for r in rows))
for row in rows:
    print(
        row["topology_rank"],
        row["name"],
        f'rows={row["matrix_rows"]}',
        f'cols={row["matrix_cols"]}',
        f'components={row["valid_components"]}',
        f'largest_share={float(row["largest_component_area_share"]):.4f}',
        f'seed={row["selected_seed"]}',
    )
PY
```

## 3. Test One Matrix First

```bash
python3 run_ec_solver_experiment.py \
  --solver ec_solver/main \
  --input-dir experiments/rome_graphs_to_matrices/matrices \
  --pattern grafo10527.93.txt \
  --result-dir experiments/rome_results \
  --dxz-threads 1 \
  --dyndxd-threads 8 \
  --cc-ett-max-calls 1 \
  --solver-time-limit 1500 \
  --dxz-process-timeout 1500 \
  --dyndxd-process-timeout 1500 \
  --target-policy none
```

Inspect `target_met` and `target_reason` in the generated `results.csv` before starting the full suite.

## 4. Run the Ten-Matrix Experiment

```bash
cd /home/lyh/projects/lyh/Alg_DXD/GMLToMat

python3 run_ec_solver_experiment.py \
  --solver ec_solver/main \
  --input-dir experiments/rome_graphs_to_matrices_1108/matrices \
  --graph-dir experiments/rome_graphs_to_matrices_1108/inputs \
  --result-dir experiments/rome_results \
  --dxz-threads 1 \
  --dxd-threads 8 \
  --dyndxd-threads 8 \
  --solver-time-limit 1500 \
  --dxz-process-timeout 1500 \
  --dxd-process-timeout 1500 \
  --dyndxd-process-timeout 1500 \
  --target-policy none

  --cc-ett-max-calls 1 \
```

The runner flushes `results.csv` after every matrix. Use `none` for a batch
that may contain non-target cases; use `all` only after curating a directory
that contains target matrices exclusively.

## 5. Audit Results

```bash
python3 - <<'PY'
import csv
from pathlib import Path

run_dirs = sorted(
    Path("experiments/topology_standard_results").glob("*/results.csv")
)
if not run_dirs:
    raise SystemExit("no results.csv found")

path = run_dirs[-1]
rows = list(csv.DictReader(path.open()))
targets = [row for row in rows if row["target_met"] == "True"]
print("result:", path)
print("targets:", len(targets), "/", len(rows))
for row in rows:
    print(
        row["instance"],
        row["dxz_status"],
        row["dxz_solver_time_sec"],
        row["dyndxd_status"],
        row["dyndxd_solver_time_sec"],
        row["target_met"],
        row["target_reason"],
    )
PY
```

Accept a target only when:

- `dxz_status` is `timeout`
- `dyndxd_status` is `success`
- both budgets are 1500 seconds
- `dyndxd_threads` is 8 and `dyndxd_cc_ett_max_calls` is 1

Repeat any target instance at least once before treating it as stable.

## Adjustment Rules

- DXZ succeeds below 1500 seconds: increase rows or choose a higher
  topology-ranked candidate, but keep largest area share at or below 23%.
- DXZ is OOM-killed: reject the matrix and reduce rows/component concentration.
- DXZ and DynDXD both time out: reject the matrix or revisit the time budget.
- DynDXD crashes or reports `unknown`: inspect the log and reject the matrix.
- DXZ times out and DynDXD succeeds: retain the matrix and repeat it.

## 2026-11-07 Hard-Profile Replacement

The nine matrices that did not meet the runtime target were replaced. The
successful `grafo3482.98.txt` matrix was retained unchanged.

Every replacement was generated with 10-node target blocks and checked against
these hard gates:

- more than 37,000 rows,
- more than 160 columns,
- at least `1e95` exact-cover solutions,
- unique rows and valid matrix headers.

The current selection and hashes are recorded in
`replacement_report_20261107.csv` and `selection_manifest.json`. Old matrices
and their metadata are preserved under `replaced_20261107/`.

The topology batch was generated with:

```bash
python3 generate_exact_cover.py \
  --select-rome-dir graphs_graphml/topo \
  --output experiments/topology_standard_20261107_replace9_v3 \
  --seed 20261117 \
  --search-seeds 1 \
  --select-count 9 \
  --exclude-name Cogentco \
  --exclude-matrix-dir experiments/topology_standard_20261106/matrices \
  --min-nodes 100 --max-nodes 250 \
  --min-edges 100 --max-edges 250 \
  --min-fill-edges 0 --min-elimination-width 0 \
  --min-degree-std 0 --max-articulation-ratio 1 \
  --target-block-size 10 \
  --min-extra-solutions 3600 --max-extra-solutions 4000 \
  --matrix-rows-min 37001 --matrix-rows-max 120000 \
  --matrix-cols-min 161 --matrix-cols-max 400 \
  --min-components 8 --max-components 25 \
  --min-solution-log10 95
```

`Cogentco` was generated with the same seed and hard profile in
`topology_standard_20261107_replace9_v2`; its `seed_20261118` candidate was
added as the ninth replacement.

## Random Rome-3 Hard-Profile Mode

For a random sample from `graphs_graphml/rome_3`, use the automatic selector
with an explicit node range. The selector parses only selected graphs into
`inputs/`, and writes only matrices that satisfy every hard gate into
`matrices/`.

The generator first builds a normal 10-block matrix. If the row count, column
count, or exact solution count is below the target, it repeats the complete
base matrix in new, column-disjoint space. If the base matrix has `r` rows,
`c` columns, and `s` solutions, repeating it `k` times produces `k*r` rows,
`k*c` columns, and `s^k` solutions. Component row patterns and per-component
block sizes are unchanged.

Validated command:

```bash
cd /home/lyh/projects/lyh/Alg_DXD/GMLToMat

python3 generate_exact_cover.py \
  --select-rome-dir graphs_graphml/rome_3 \
  --output experiments/topology_standard_20261106 \
  --seed 20261117 \
  --search-seeds 1 \
  --select-count 9 \
  --randomize-candidates \
  --exclude-matrix-dir experiments/topology_standard_20261106/matrices \
  --min-edges 0 --max-edges 100000 \
  --min-nodes 90 --max-nodes 100 \
  --min-fill-edges 0 --min-elimination-width 0 \
  --min-degree-std 0 --max-articulation-ratio 1 \
  --min-blocks 10 --max-blocks 10 \
  --min-extra-solutions 3600 --max-extra-solutions 4000 \
  --matrix-rows-min 37001 --matrix-rows-max 180000 \
  --matrix-cols-min 161 --matrix-cols-max 2000 \
  --min-components 1 --max-components 50 \
  --min-largest-area-share 0 --max-largest-area-share 1 \
  --min-solution-log10 95 \
  --target-matrix-rows 60000 --target-matrix-cols 320 \
  --target-area-share 0.18 \
  --max-replications 5
```

With seed `20261117`, this command selected nine graphs, used exactly two
copies for each base matrix, and produced matrices with 51,940-73,630 rows,
272-320 columns, and `1.55e154`-`1.92e191` solutions.
