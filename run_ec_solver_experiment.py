#!/usr/bin/env python3
"""Batch-run DXZ, DXD, and DynDXD on generated exact-cover instances.

The default setup compares single-thread DXZ with 8-thread DXD and 8-thread
DynDXD, restricting DynDXD to one ETT connectivity query. Results are flushed
to CSV after every instance so a long-running experiment can be resumed by
inspection.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_SOLVER = ROOT / "ec_solver" / "main"
DEFAULT_INPUT_DIR = ROOT / "output" / "rome_3_sample"
DEFAULT_RESULT_DIR = ROOT / "results" / "ec_solver_experiments"

TIME_RE = re.compile(r"^Time:\s*([0-9.eE+-]+)\s*s\s*$", re.MULTILINE)
SOLUTIONS_RE = re.compile(r"^Solutions(?: \(scientific\))?:\s*(\S+)\s*$", re.MULTILINE)
ROWS_RE = re.compile(r"^rows:\s*(\d+)\s*$", re.MULTILINE)
COLS_RE = re.compile(r"^cols:\s*(\d+)\s*$", re.MULTILINE)
MAX_BLOCKS_RE = re.compile(r"^Max Blocks:\s*(\d+)\s*$", re.MULTILINE)
DNNF_SIZE_RE = re.compile(r"^DNNF Size:\s*(\d+)\s*$", re.MULTILINE)
ZDD_SIZE_RE = re.compile(r"^ZDD Size:\s*(\d+)\s*$", re.MULTILINE)


@dataclass
class RunResult:
    algorithm: str
    status: str
    exit_code: int | None
    solver_time_sec: float | None
    wall_time_sec: float
    solutions: str
    rows: int | None
    cols: int | None
    max_blocks: int | None
    graph_size: int | None
    log_path: str
    output: str
    thread_stats: list[dict[str, str]]
    search_stats: list[dict[str, str]]


class DisjointSet:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, value: int) -> int:
        parent = self.parent
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return
        if self.rank[root_left] < self.rank[root_right]:
            root_left, root_right = root_right, root_left
        self.parent[root_right] = root_left
        if self.rank[root_left] == self.rank[root_right]:
            self.rank[root_left] += 1


def parse_number(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


def parse_first_int(pattern: re.Pattern[str], output: str) -> int | None:
    match = pattern.search(output)
    return int(match.group(1)) if match else None


def parse_output(
    algorithm: str,
    output: str,
    wall_time_sec: float,
    exit_code: int | None,
    log_path: Path,
) -> RunResult:
    time_match = TIME_RE.search(output)
    solutions_match = SOLUTIONS_RE.search(output)
    internal_timeout = (
        "Time bound broken" in output
        or "搜索超时" in output
        or "time out" in output.lower()
    )
    process_timeout = exit_code is None
    completed = f"{algorithm}算法求解结束" in output

    if process_timeout or (exit_code == 0 and internal_timeout):
        status = "timeout"
    elif exit_code not in (None, 0):
        status = "crashed"
    elif solutions_match and completed:
        status = "success"
    elif solutions_match:
        status = "incomplete"
    else:
        status = "unknown"

    graph_size_pattern = ZDD_SIZE_RE if algorithm == "DXZ" else DNNF_SIZE_RE
    thread_stats = []
    search_stats = []
    if algorithm == "DynDXD":
        for line in output.splitlines():
            if not line.startswith("[thread-task] "):
                continue
            values = dict(re.findall(r"(\w+)=([^\s]+)", line))
            if values:
                values["task_index"] = values.pop("task", "")
                thread_stats.append(values)
    for line in output.splitlines():
        if line.startswith("[search-summary] "):
            values = dict(re.findall(r"(\w+)=([^\s]+)", line))
            if values:
                search_stats.append(values)

    return RunResult(
        algorithm=algorithm,
        status=status,
        exit_code=exit_code,
        solver_time_sec=parse_number(time_match.group(1)) if time_match else None,
        wall_time_sec=wall_time_sec,
        solutions=solutions_match.group(1) if solutions_match else "",
        rows=parse_first_int(ROWS_RE, output),
        cols=parse_first_int(COLS_RE, output),
        max_blocks=parse_first_int(MAX_BLOCKS_RE, output),
        graph_size=parse_first_int(graph_size_pattern, output),
        log_path=str(log_path),
        output=output,
        thread_stats=thread_stats,
        search_stats=search_stats,
    )


def read_matrix_components(path: Path) -> tuple[int, int, list[int], list[int], list[int]]:
    """Return matrix dimensions and initial row-projection components.

    Generated matrices use: first line ``cols rows``, then one line per row as
    ``count col1 col2 ...``.
    """
    with path.open("r", encoding="utf-8") as stream:
        header = stream.readline().split()
        if len(header) < 2:
            raise ValueError(f"{path}: invalid matrix header")
        cols, rows = int(header[0]), int(header[1])

        row_cols: list[list[int]] = []
        column_rows: dict[int, list[int]] = {}
        for row_id, line in enumerate(stream):
            tokens = [int(token) for token in line.split()]
            if not tokens:
                row_cols.append([])
                continue
            count = tokens[0]
            values = tokens[1:]
            if len(values) != count:
                raise ValueError(
                    f"{path}:{row_id + 2}: expected {count} columns, got {len(values)}"
                )
            row_cols.append(values)
            for col in values:
                column_rows.setdefault(col, []).append(row_id)

    if len(row_cols) < rows:
        row_cols.extend([] for _ in range(rows - len(row_cols)))
    row_cols = row_cols[:rows]

    dsu = DisjointSet(rows)
    for row_ids in column_rows.values():
        if len(row_ids) < 2:
            continue
        first = row_ids[0]
        for row_id in row_ids[1:]:
            dsu.union(first, row_id)

    component_rows: dict[int, int] = {}
    component_cols: dict[int, set[int]] = {}
    for row_id, values in enumerate(row_cols):
        if not values:
            continue
        root = dsu.find(row_id)
        component_rows[root] = component_rows.get(root, 0) + 1
        component_cols.setdefault(root, set()).update(values)

    rows_per_component = sorted(component_rows.values(), reverse=True)
    cols_per_component = sorted(
        (len(values) for values in component_cols.values()), reverse=True
    )
    areas = sorted(
        (
            component_rows[root] * len(values)
            for root, values in component_cols.items()
        ),
        reverse=True,
    )
    return rows, cols, rows_per_component, cols_per_component, areas


def read_graph_size(path: Path) -> tuple[int, int]:
    """Return the vertex and edge counts from a normalized graph ``.in`` file."""
    with path.open("r", encoding="utf-8") as stream:
        header = stream.readline().split()
    if len(header) < 2:
        raise ValueError(f"{path}: invalid graph header")
    vertices, edges = int(header[0]), int(header[1])
    if vertices < 0 or edges < 0:
        raise ValueError(f"{path}: negative graph size")
    return vertices, edges


def run_solver(
    solver: Path,
    instance: Path,
    algorithm: str,
    threads: int,
    cc_ett_max_calls: int,
    cc_bfs_max_calls: int,
    solver_time_limit: int,
    process_timeout: int,
    log_path: Path,
    debug: bool = False,
    report_dnnf_size: bool = False,
) -> RunResult:
    command = [
        str(solver),
        "-a",
        algorithm,
        "-i",
        str(instance),
        "-t",
        str(threads),
        "--time-limit",
        str(solver_time_limit),
    ]
    if algorithm in ("dxd", "ddxd") and not report_dnnf_size:
        command.append("--skip-dnnf-size")
    if algorithm == "ddxd":
        command.extend(
            [
                "--cc-ett-max-calls",
                str(cc_ett_max_calls),
                "--cc-bfs-max-calls",
                str(cc_bfs_max_calls),
            ]
        )
        if debug:
            command.append("--debug")

    environment = os.environ.copy()
    environment.setdefault("ASAN_OPTIONS", "detect_leaks=0")

    started = time.perf_counter()
    exit_code: int | None = None
    try:
        completed = subprocess.run(
            command,
            cwd=solver.parent,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=process_timeout,
            check=False,
        )
        output = completed.stdout
        exit_code = completed.returncode
    except subprocess.TimeoutExpired as exc:
        if isinstance(exc.stdout, bytes):
            output = exc.stdout.decode("utf-8", errors="replace")
        else:
            output = exc.stdout or ""
        output += f"\n[experiment] process timeout after {process_timeout}s\n"
    except OSError as exc:
        output = f"[experiment] failed to launch solver: {exc}\n"
        exit_code = -1

    wall_time_sec = time.perf_counter() - started
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(output, encoding="utf-8")

    display_name = {
        "dxz": "DXZ",
        "dxd": "DXD",
        "ddxd": "DynDXD",
    }[algorithm]
    return parse_output(display_name, output, wall_time_sec, exit_code, log_path)


CSV_FIELDS = [
    "experiment_id",
    "instance",
    "rows",
    "cols",
    "graph_vertices",
    "graph_edges",
    "dxz_status",
    "dxz_solver_time_sec",
    "dxd_threads",
    "dxd_status",
    "dxd_solver_time_sec",
    "dxd_solutions",
    "dxd_max_blocks",
    "dyndxd_threads",
    "dyndxd_status",
    "dyndxd_solver_time_sec",
    "dyndxd_solutions",
    "dyndxd_max_blocks",
    "target",
]

THREAD_STATS_FIELDS = [
    "experiment_id",
    "instance",
    "task_index",
    "omp_thread",
    "rows",
    "cols",
    "area",
    "solve_sec",
    "cache_reads",
    "cache_hits",
    "cache_hit_rate",
    "cache_writes",
    "nodes_allocated",
    "cache_read_sec",
    "cache_write_sec",
    "node_lookup_sec",
    "node_insert_sec",
    "state_hash_sec",
    "choose_col_sec",
    "probe_sec",
    "state_hash_calls",
    "choose_col_calls",
    "probe_calls",
    "cache_key_columns",
    "cover_sec",
    "uncover_sec",
    "cover_set_sec",
    "uncover_set_sec",
    "removed_rows_clear_sec",
    "cover_calls",
    "uncover_calls",
    "cover_set_ops",
    "uncover_set_ops",
    "removed_rows_clear_calls",
    "lock_wait_sec",
]

SEARCH_STATS_FIELDS = [
    "experiment_id",
    "instance",
    "label",
    "cache_reads",
    "cache_hits",
    "cache_hit_rate",
    "cache_writes",
    "cache_key_columns",
    "avg_cache_key_columns",
    "state_hash_calls",
    "choose_col_calls",
    "probe_calls",
    "nodes_allocated",
    "state_hash_sec",
    "choose_col_sec",
    "probe_sec",
    "cache_read_sec",
    "cache_write_sec",
    "node_lookup_sec",
    "node_insert_sec",
    "cover_sec",
    "uncover_sec",
    "cover_set_sec",
    "uncover_set_sec",
    "removed_rows_clear_sec",
]


def compact(values: list[int]) -> str:
    return "|".join(str(value) for value in values)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare DXZ, DXD, and DynDXD on exact-cover matrices."
    )
    parser.add_argument("--solver", type=Path, default=DEFAULT_SOLVER)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument(
        "--graph-dir",
        type=Path,
        default=None,
        help=(
            "Directory containing normalized <instance>.in graph files. "
            "Defaults to <input-dir>/../inputs when it exists."
        ),
    )
    parser.add_argument("--pattern", default="*.txt")
    parser.add_argument("--result-dir", type=Path, default=DEFAULT_RESULT_DIR)
    parser.add_argument(
        "--dxd-threads",
        type=int,
        default=8,
        help="OpenMP threads passed to DXD (default: 8).",
    )
    parser.add_argument(
        "--dyndxd-threads",
        type=int,
        default=8,
        help="OpenMP threads passed to DynDXD (default: 8).",
    )
    parser.add_argument(
        "--dxz-threads",
        type=int,
        default=1,
        help="Threads passed to DXZ; its current search is not block-parallel (default: 1).",
    )
    parser.add_argument("--cc-ett-max-calls", type=int, default=1)
    parser.add_argument(
        "--cc-bfs-max-calls",
        type=int,
        default=10,
        help="Stop DynDXD BFS decomposition after N BFS queries (0: unlimited).",
    )
    parser.add_argument(
        "--report-dnnf-size",
        action="store_true",
        help=(
            "Ask DXD/DynDXD to print DNNF Size. Performance runs skip this "
            "output by default."
        ),
    )
    parser.add_argument("--solver-time-limit", type=int, default=1500)
    parser.add_argument(
        "--process-timeout",
        type=int,
        default=1800,
        help=(
            "Fallback hard wall-clock timeout for a solver run. Prefer the "
            "per-algorithm timeout options during screening."
        ),
    )
    parser.add_argument(
        "--dxz-process-timeout",
        type=int,
        default=None,
        help=(
            "Hard wall-clock timeout for DXZ. DXZ does not honor "
            "--time-limit internally, so this is the effective cutoff."
        ),
    )
    parser.add_argument(
        "--dxd-process-timeout",
        type=int,
        default=None,
        help="Hard wall-clock timeout for DXD.",
    )
    parser.add_argument(
        "--dyndxd-process-timeout",
        type=int,
        default=None,
        help=(
            "Hard wall-clock timeout for DynDXD. Leave a small grace period "
            "over --solver-time-limit for cleanup."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Run only the first N sorted instances; 0 means all.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Pass -d so DynDXD emits per-task cache and timing diagnostics.",
    )
    parser.add_argument(
        "--target-policy",
        choices=("none", "any", "all"),
        default="none",
        help=(
            "Exit non-zero unless the target (DXZ timeout and DynDXD success) "
            "is met by any or all instances (default: none)."
        ),
    )
    args = parser.parse_args()
    args.dxz_process_timeout = (
        args.dxz_process_timeout
        if args.dxz_process_timeout is not None
        else args.process_timeout
    )
    args.dxd_process_timeout = (
        args.dxd_process_timeout
        if args.dxd_process_timeout is not None
        else args.process_timeout
    )
    args.dyndxd_process_timeout = (
        args.dyndxd_process_timeout
        if args.dyndxd_process_timeout is not None
        else args.process_timeout
    )
    if (
        args.dxz_process_timeout < 1
        or args.dxd_process_timeout < 1
        or args.dyndxd_process_timeout < 1
    ):
        parser.error("process timeouts must be >= 1 second")
    return args


def main() -> int:
    args = parse_args()
    solver = args.solver.resolve()
    input_dir = args.input_dir.resolve()
    if not solver.is_file():
        print(f"[error] solver not found: {solver}", file=sys.stderr)
        return 2
    if not input_dir.is_dir():
        print(f"[error] input directory not found: {input_dir}", file=sys.stderr)
        return 2

    inferred_graph_dir = input_dir.parent / "inputs"
    graph_dir = (
        args.graph_dir.resolve()
        if args.graph_dir is not None
        else inferred_graph_dir if inferred_graph_dir.is_dir() else None
    )
    if graph_dir is not None and not graph_dir.is_dir():
        print(f"[error] graph directory not found: {graph_dir}", file=sys.stderr)
        return 2

    instances = sorted(input_dir.glob(args.pattern))
    if args.limit > 0:
        instances = instances[: args.limit]
    if not instances:
        print(f"[error] no instances matched {input_dir / args.pattern}", file=sys.stderr)
        return 2

    experiment_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = args.result_dir.resolve() / experiment_id
    log_dir = run_dir / "logs"
    run_dir.mkdir(parents=True, exist_ok=True)
    csv_path = run_dir / "results.csv"
    thread_stats_path = run_dir / "thread_stats.csv"
    search_stats_path = run_dir / "search_stats.csv"

    print(f"Experiment: {experiment_id}")
    print(f"Solver:     {solver}")
    print(f"Instances:  {len(instances)} from {input_dir}")
    print(f"Graphs:     {graph_dir if graph_dir is not None else 'not found'}")
    print(f"CSV:        {csv_path}")

    target_results: list[bool] = []
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        stream.flush()

        for index, instance in enumerate(instances, start=1):
            print(f"[{index}/{len(instances)}] {instance.name}", flush=True)
            try:
                matrix_rows, matrix_cols, component_rows, component_cols, areas = (
                    read_matrix_components(instance)
                )
            except (OSError, ValueError) as exc:
                print(f"  component scan failed: {exc}", file=sys.stderr, flush=True)
                matrix_rows = matrix_cols = None
                component_rows = component_cols = areas = []

            graph_vertices = graph_edges = None
            if graph_dir is not None:
                graph_path = graph_dir / f"{instance.stem}.in"
                try:
                    graph_vertices, graph_edges = read_graph_size(graph_path)
                except (OSError, ValueError) as exc:
                    print(f"  graph scan failed: {exc}", file=sys.stderr, flush=True)

            dxz_log = log_dir / f"{instance.stem}.dxz.log"
            dxd_log = log_dir / f"{instance.stem}.dxd.log"
            ddxd_log = log_dir / f"{instance.stem}.dyndxd.log"

            print(f"  DXZ ({args.dxz_threads} thread)", flush=True)
            dxz = run_solver(
                solver=solver,
                instance=instance,
                algorithm="dxz",
                threads=args.dxz_threads,
                cc_ett_max_calls=args.cc_ett_max_calls,
                cc_bfs_max_calls=args.cc_bfs_max_calls,
                solver_time_limit=args.solver_time_limit,
                process_timeout=args.dxz_process_timeout,
                log_path=dxz_log,
                report_dnnf_size=args.report_dnnf_size,
            )

            print(f"  DXD ({args.dxd_threads} threads)", flush=True)
            dxd = run_solver(
                solver=solver,
                instance=instance,
                algorithm="dxd",
                threads=args.dxd_threads,
                cc_ett_max_calls=args.cc_ett_max_calls,
                cc_bfs_max_calls=args.cc_bfs_max_calls,
                solver_time_limit=args.solver_time_limit,
                process_timeout=args.dxd_process_timeout,
                log_path=dxd_log,
                report_dnnf_size=args.report_dnnf_size,
            )

            print(f"  DynDXD ({args.dyndxd_threads} threads)", flush=True)
            dyndxd = run_solver(
                solver=solver,
                instance=instance,
                algorithm="ddxd",
                threads=args.dyndxd_threads,
                cc_ett_max_calls=args.cc_ett_max_calls,
                cc_bfs_max_calls=args.cc_bfs_max_calls,
                solver_time_limit=args.solver_time_limit,
                process_timeout=args.dyndxd_process_timeout,
                log_path=ddxd_log,
                debug=args.debug,
                report_dnnf_size=args.report_dnnf_size,
            )

            speedup = None
            if (
                dxz.status == "success"
                and dyndxd.status == "success"
                and dxz.solver_time_sec
                and dyndxd.solver_time_sec
            ):
                speedup = dxz.solver_time_sec / dyndxd.solver_time_sec

            solutions_match = ""
            if dxz.solutions and dyndxd.solutions:
                solutions_match = str(dxz.solutions == dyndxd.solutions)
            dxd_solutions_match = ""
            if dxz.solutions and dxd.solutions:
                dxd_solutions_match = str(dxz.solutions == dxd.solutions)
            dyndxd_solutions_match = ""
            if dxz.solutions and dyndxd.solutions:
                dyndxd_solutions_match = str(dxz.solutions == dyndxd.solutions)
            all_solutions_match = ""
            if dxz.solutions and dxd.solutions and dyndxd.solutions:
                all_solutions_match = str(
                    dxz.solutions == dxd.solutions == dyndxd.solutions
                )

            target_met = (
                dxz.status == "timeout" and dyndxd.status == "success"
            )
            target_results.append(target_met)
            if target_met:
                target_reason = "DXZ timeout; DynDXD success"
            elif dxz.status != "timeout":
                target_reason = f"DXZ status is {dxz.status}, not timeout"
            else:
                target_reason = (
                    f"DynDXD status is {dyndxd.status}, not success"
                )

            writer.writerow(
                {
                    "experiment_id": experiment_id,
                    "instance": instance.name,
                    "rows": matrix_rows if matrix_rows is not None else dxz.rows,
                    "cols": matrix_cols if matrix_cols is not None else dxz.cols,
                    "graph_vertices": graph_vertices,
                    "graph_edges": graph_edges,
                    "dxz_status": dxz.status,
                    "dxz_solver_time_sec": dxz.solver_time_sec,
                    "dxd_threads": args.dxd_threads,
                    "dxd_status": dxd.status,
                    "dxd_solver_time_sec": dxd.solver_time_sec,
                    "dxd_solutions": dxd.solutions,
                    "dxd_max_blocks": dxd.max_blocks,
                    "dyndxd_threads": args.dyndxd_threads,
                    "dyndxd_status": dyndxd.status,
                    "dyndxd_solver_time_sec": dyndxd.solver_time_sec,
                    "dyndxd_solutions": dyndxd.solutions,
                    "dyndxd_max_blocks": dyndxd.max_blocks,
                    "target": target_met,
                }
            )
            stream.flush()

            if dyndxd.thread_stats:
                write_header = not thread_stats_path.exists()
                with thread_stats_path.open(
                    "a", newline="", encoding="utf-8"
                ) as thread_stream:
                    thread_writer = csv.DictWriter(
                        thread_stream, fieldnames=THREAD_STATS_FIELDS
                    )
                    if write_header:
                        thread_writer.writeheader()
                    for stats in dyndxd.thread_stats:
                        thread_writer.writerow(
                            {
                                "experiment_id": experiment_id,
                                "instance": instance.name,
                                **stats,
                            }
                        )
                    thread_stream.flush()

            search_rows = [
                {
                    "experiment_id": experiment_id,
                    "instance": instance.name,
                    "algorithm": "DXZ",
                    **stats,
                }
                for stats in dxz.search_stats
            ]
            search_rows.extend(
                {
                    "experiment_id": experiment_id,
                    "instance": instance.name,
                    "algorithm": "DXD",
                    **stats,
                }
                for stats in dxd.search_stats
            )
            search_rows.extend(
                {
                    "experiment_id": experiment_id,
                    "instance": instance.name,
                    "algorithm": "DynDXD",
                    **stats,
                }
                for stats in dyndxd.search_stats
            )
            if search_rows:
                write_header = not search_stats_path.exists()
                with search_stats_path.open(
                    "a", newline="", encoding="utf-8"
                ) as search_stream:
                    search_writer = csv.DictWriter(
                        search_stream,
                        fieldnames=["algorithm", *SEARCH_STATS_FIELDS],
                        extrasaction="ignore",
                    )
                    if write_header:
                        search_writer.writeheader()
                    search_writer.writerows(search_rows)
                    search_stream.flush()

            print(
                "  "
                f"DXZ={dxz.status}/{dxz.solver_time_sec}s, "
                f"DXD={dxd.status}/{dxd.solver_time_sec}s, "
                f"DynDXD={dyndxd.status}/{dyndxd.solver_time_sec}s, "
                f"speedup={speedup if speedup is not None else 'n/a'}, "
                f"target={'yes' if target_met else 'no'}",
                flush=True,
            )

    print(f"Completed. CSV: {csv_path}")
    print(f"Target instances: {sum(target_results)}/{len(target_results)}")
    if thread_stats_path.exists():
        print(f"Thread diagnostics: {thread_stats_path}")
    if search_stats_path.exists():
        print(f"Search diagnostics: {search_stats_path}")
    if args.target_policy == "any" and not any(target_results):
        print("[error] no instance met the DXZ-timeout/DynDXD-success target", file=sys.stderr)
        return 3
    if args.target_policy == "all" and not all(target_results):
        print(
            "[error] at least one instance did not meet the target",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
