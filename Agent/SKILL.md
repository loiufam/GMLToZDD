---
name: build-dxd-exact-cover-benchmarks
description: Build reproducible GraphML-to-exact-cover benchmark suites for comparing single-thread DXZ with 8-thread DynDXD. Use when selecting Rome graphs by edge count, converting graphs with GMLParser.py, generating balanced multi-block exact-cover matrices with many solutions, screening instances where DXZ times out while DynDXD succeeds, or running formal Algorithm_DXD experiments and reporting results.
---

# Build DXZ/DynDXD Exact-Cover Benchmarks

## Objective

Produce a reproducible benchmark suite that is complex enough to expose the
parallel decomposition advantage:

- DXZ runs with 1 thread and reaches the outer wall-clock timeout.
- DynDXD runs with 8 threads, `--cc-ett-max-calls 1`, and completes before
  the same intended time budget.
- Every generated matrix is built from a seeded, multi-block graph partition.
- The compiler reports at least 51 distinct exact-cover solutions per
  successful block, and each partition block differs in node count by at most
  one.

Use `GMLToMat` as the working directory. The generator and experiment runner
are relative to it, and its defaults resolve the ZDD engine from the script
location.

```bash
cd /home/lyh/projects/lyh/Alg_DXD/GMLToMat
```

## Execution Contract

1. Preserve a fixed solver binary, graph seed, block count, time budget, and
   thread configuration for every run in one experiment.
2. Compare DXZ at 1 thread with DynDXD at 8 threads. Pass
   `--cc-ett-max-calls 1` to DynDXD unless the experiment explicitly studies
   a different decomposition budget.
3. Treat the source and runtime behavior as authoritative when the solver help
   text is stale. The DynDXD algorithm name accepted by the solver is `ddxd`.
4. Pass `--time-limit T` to DynDXD. DXZ does not apply that internal limit;
   enforce its cutoff with `--dxz-process-timeout`.
5. Keep screening, accepted target instances, and the final formal input set
   in separate directories. Do not silently mix candidates with rejects.
6. Record the exact commands, seed, edge interval, candidate count, time
   budget, and result CSV in the experiment notes.

Check prerequisites before generating data:

```bash
test -x build_zdd_bin/main
test -x ec_solver/main
python3 -c 'import networkx'
ec_solver/main --help
```

If the solver binary is missing, build the Release target according to
`Algorithm_DXD/README.md`:

```bash
cd ../Algorithm_DXD
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
cd ../GMLToMat
```

Then point `--solver` at the resulting binary or install it as
`GMLToMat/ec_solver/main`. Record which binary was used.

## Calibrated Topology Standard

The 2026-11-06 ten-round calibration showed that edge count alone is not
predictive. Use these graph and matrix gates together:

- Select Rome graphs with 131-134 edges and 90-100 nodes.
- Require min-fill edges at least 125 and elimination width at least 8.
- Require degree standard deviation at least 1.25.
- Require articulation vertices to be at most 30% of nodes.
- Generate with 10 blocks and 2400-3000 extra solutions per block.
- Keep matrices with 25000-45000 rows and 8-10 valid components.
- Require the largest component area share to be between 13.5% and 23%.
- Require unique matrix rows and no ZDD or total-row safety-limit warning.

The range excludes the 12.6% case that finished DXZ in 380 seconds and the
44.7% case that caused OOM, while retaining the 14.1% case that reached 813
seconds. Rank graph candidates with:

```text
0.45 * min_fill_edges
+ 3.00 * elimination_width
+ 15.0 * degree_standard_deviation
+ 20.0 * articulation_ratio
```

Run the integrated topology-aware generator from `GMLToMat`:

```bash
python3 generate_exact_cover.py \
  --select-rome-dir graphs_graphml/rome_3 \
  --output experiments/topology_standard_20261106 \
  --seed 20261114 \
  --search-seeds 3 \
  --select-count 10
```

This writes selected matrices to `matrices/`, one-seed candidates to
`candidates/`, normalized graphs to `inputs/`, and the auditable
`selection_report.csv` plus `selection_manifest.json`. The structural gates
raise the probability of the target; they do not prove it. Screen the selected
matrices with the 1500-second command below.

The generator passes each Python seed to the ZDD engine as `ZDD_SEED`. The
rebuilt `build_zdd_bin/main` must support this variable; without it, the
engine's randomized fallback makes byte-identical regeneration impossible.
`selection_manifest.json` records the engine SHA-256. Verify a repeated
generation by comparing every file in `matrices/` with `sha256sum`.

## Workflow

### 1. Analyze and Sample Graphs

Build the Rome inventory once, then sample by an edge interval. The selector
uses `min_edges < edges <= max_edges`; its lower bound is strict.

```bash
cd origin_gml
python3 select_rome_graphml.py \
  --source rome \
  --csv rome_analysis.csv \
  --analysis-only \
  --refresh-analysis
```

Use an initial sweep around the observed difficulty band rather than starting
with the largest graphs. Rome edge counts in the current inventory range from
9 to 158, with the upper quartile near 98. Start with 110-140 edges, then widen
or shift the interval based on screening outcomes.

```bash
python3 select_rome_graphml.py \
  --source rome \
  --csv rome_analysis.csv \
  --dest ../graphs_graphml/screen_edges_110_140 \
  --min-edges 109 \
  --max-edges 140 \
  --top-n 12 \
  --exclude ../graphs_graphml/rome_1 \
  --exclude ../graphs_graphml/rome_2 \
  --exclude ../graphs_graphml/rome_3 \
  --seed 20261106
```

Keep the same seed while changing one variable. If DXZ finishes too quickly,
move upward in edge count or change the seed. If both solvers time out, first
try a lower edge interval or a larger time budget chosen before the run; do not
call a double-timeout a success.

Repeat `--exclude` for every prior sample directory to avoid duplicate
candidates. Copy the selected GraphML names into the experiment notes.

### 2. Convert GraphML to `.in`

Run the batch conversion into a fresh folder:

```bash
cd ..
python3 GMLParser.py \
  --batch \
  graphs_graphml/screen_edges_110_140 \
  graphs_in/screen_edges_110_140
```

For one malformed graph, inspect it separately:

```bash
python3 GMLParser.py --debug path/to/graph.graphml
```

Batch conversion stops after 500 files and reports failures without making the
process fail. Count the output files and compare them with the selected folder.
Remove or investigate any graph that failed conversion.

### 3. Generate Balanced Multi-Block Matrices

Generate from the whole converted folder with a fixed seed:

```bash
python3 generate_exact_cover.py \
  --directory graphs_in/screen_edges_110_140 \
  --output output/screen_edges_110_140 \
  --seed 20261106 \
  --min-blocks 6 \
  --max-blocks 10 \
  --min-extra-solutions 51 \
  --max-extra-solutions 100
```

The generator uses a min-fill order and contiguous balanced partitions, whose
node counts differ by at most one. It injects distinct exact-cover solution
rows into every block and removes duplicate rows before writing the matrix.

Save the generator output for each batch. Retain a matrix only when all of
these conditions hold:

- At least 6 blocks generate valid ZDD rows.
- Every successful block reports at least 51 constructed exact-cover
  solutions; there is no `未达到 >50` warning.
- The reported block sizes have `max - min <= 1`.
- The final matrix has at least 600 rows, at least 120 columns, and more than
  one initial independent component.
- No block reaches the ZDD safety limit or causes the total-row early-exit.

These are structural gates, not proof of the runtime target. Continue to
solver screening after generation. If most blocks are too small to reach 51
solutions, reduce the maximum block count or select a larger graph. If the
matrix is too easy, increase graph edge density before increasing the number
of blocks.

### 4. Screen with a Fixed Time Budget

First use a short budget to classify candidates, then repeat the accepted
configuration with the intended formal budget. Use a common intended budget
`T`; give only the outer process monitors a small cleanup grace period.

For a manual smoke test, use the same algorithm names and thread counts:

```bash
timeout 155s ec_solver/main -a dxz -i path/to/matrix.txt -t 1
ec_solver/main -a ddxd -i path/to/matrix.txt -t 8 \
  --cc-ett-max-calls 1 --time-limit 150
```

```bash
python3 run_ec_solver_experiment.py \
  --solver ec_solver/main \
  --input-dir output/screen_edges_110_140 \
  --result-dir results/screening \
  --dxz-threads 1 \
  --dyndxd-threads 8 \
  --cc-ett-max-calls 1 \
  --solver-time-limit 150 \
  --dxz-process-timeout 155 \
  --dyndxd-process-timeout 160 \
  --target-policy any
```

The runner writes `results.csv` after every instance and logs each solver
under the run directory. It returns exit code 3 when `--target-policy` is not
satisfied, so a zero exit code is evidence of the requested screening result.

Apply this acceptance rule to `results.csv`:

| Field | Required value |
| --- | --- |
| `dxz_status` | `timeout` |
| `dyndxd_status` | `success` |
| `dxz_threads` | `1` |
| `dyndxd_threads` | `8` |
| `dyndxd_cc_ett_max_calls` | `1` |
| `target_met` | `True` |

Require DynDXD's reported solver time to be below the frozen budget. Prefer a
borderline margin over a timeout caused by process startup or cleanup. For a
formal target, reproduce the result with at least two independent runs of the
same matrix and configuration, or explicitly mark it as unstable.

Use the diagnostics to choose the next adjustment:

| Observation | Next action |
| --- | --- |
| DXZ succeeds | Select a denser or larger graph, or increase generated rows while keeping the same 51-solution rule |
| DXZ and DynDXD both time out | Lower the edge interval or increase the frozen budget before rerunning |
| DXZ times out and DynDXD times out on one dominant block | Reduce the maximum block area or choose a graph that produces more balanced independent components |
| DynDXD crashes or reports `unknown` | Reject the matrix and inspect its log; do not tune around a corrupt instance |
| DynDXD succeeds and DXZ times out | Candidate accepted; repeat with the frozen budget |

Do not use `solutions_match` alone for a timed-out DXZ row because DXZ has no
reported solution count. Validate correctness separately with easier control
instances where both solvers finish, and verify that the matrix header and row
column indices satisfy the generator format.

### 5. Freeze the Calibration

Once screening succeeds, freeze:

- graph edge interval and node interval,
- selection seed and exact selected-file list,
- conversion output directory,
- generation seed, block range, extra-solution range, and row/column limits,
- solver binary path and build identity,
- DXZ and DynDXD thread counts, ETT call budget, and time budget.

Do not alter the matrix generator while running the formal suite. If any
parameter changes, start a new calibration and result directory.

### 6. Generate the Formal Batch

Sample a new batch from the frozen interval, excluding every screening and
prior formal folder:

```bash
cd origin_gml
python3 select_rome_graphml.py \
  --source rome \
  --csv rome_analysis.csv \
  --dest ../graphs_graphml/formal_edges_frozen \
  --min-edges 109 \
  --max-edges 140 \
  --top-n 40 \
  --exclude ../graphs_graphml/screen_edges_110_140 \
  --seed 20261107
```

Convert and generate the new batch with fresh directories and a new recorded
seed. Preserve the generation block and extra-solution configuration that
passed calibration.

Before the formal solver run, subset the generated matrices to instances that
pass the structural gates. If the experiment studies only accepted hard
instances, run the same frozen-budget screening on the batch and create a
curated input directory containing only `target_met=True` matrices.

### 7. Run the Formal Experiment

Run the same frozen configuration without `--debug`; reserve debug collection
for a separate diagnostic run because it changes output volume and can perturb
timing.

```bash
python3 run_ec_solver_experiment.py \
  --solver ec_solver/main \
  --input-dir output/formal_edges_frozen \
  --result-dir results/formal \
  --dxz-threads 1 \
  --dyndxd-threads 8 \
  --cc-ett-max-calls 1 \
  --solver-time-limit 150 \
  --dxz-process-timeout 155 \
  --dyndxd-process-timeout 160 \
  --target-policy all
```

Use `--target-policy all` only when every file in the input directory is
supposed to meet the target. If the formal suite intentionally includes
controls, use `none` and report target and control results separately.

Report at least:

- accepted target count divided by attempted count,
- DXZ timeout rate,
- DynDXD success rate and solver-time distribution,
- DynDXD speedup where both solvers complete,
- solution agreement on completed controls,
- exact configuration, seeds, and paths to `results.csv` and logs.

## Common Failure Checks

- If `ec_solver/main` rejects the algorithm, use `ddxd`, not the stale help-text
  alias `mdxd`.
- If DXZ never stops at `--time-limit`, set the DXZ outer timeout. The DXZ
  entry point does not install the internal timer.
- If DynDXD is killed while printing cleanup statistics, increase only
  `--dyndxd-process-timeout`, not `--solver-time-limit`.
- If the generator says a block has too few exact-cover solutions, reduce the
  block count before weakening the 51-solution requirement.
- If shared `temp` output creates cross-run artifacts, pass a unique
  `--temp-dir` per generation process and keep generation serial unless the
  generator is changed to isolate every block.
- If a result has `target_met=False`, read `target_reason` and the corresponding
  solver log before changing graph-selection parameters.
