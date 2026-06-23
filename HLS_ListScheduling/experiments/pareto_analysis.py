# pareto_analysis.py - 面积-延迟帕累托前沿分析
# 网格搜索不同资源配置，运行调度+绑定，找出帕累托最优点
# 陈润锴

import os
import sys
import argparse
import itertools

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.dfg_parser import parse_dfg
from src.list_scheduler import ListScheduler, default_priority
from src.metrics import schedule_summary
from src.binding import BindingEngine
from src.visualizer import plot_pareto_frontier


def is_pareto_optimal(point: tuple, all_points: list) -> bool:
    """
    Check if a point is Pareto-optimal.
    A point (lat, area) is dominated if there exists another point
    with lat <= lat_i AND area <= area_i, with at least one strict.
    """
    lat_i, area_i = point
    for lat_j, area_j in all_points:
        if lat_j <= lat_i and area_j <= area_i:
            if lat_j < lat_i or area_j < area_i:
                return False
    return True


def run_pareto_analysis(dfg_path: str, resource_configs: list, output_dir: str) -> dict:
    """
    Run area-latency Pareto analysis by varying resource limits.

    Args:
        dfg_path: Path to the DFG JSON file.
        resource_configs: List of (label, resource_dict) tuples.
        output_dir: Directory to save output figures.

    Returns:
        Dictionary with Pareto analysis results.
    """
    dfg, base_resources = parse_dfg(dfg_path)
    dfg_name = os.path.splitext(os.path.basename(dfg_path))[0]

    print(f"\n{'='*60}")
    print(f"Pareto Analysis: {dfg_name}")
    print(f"{'='*60}")

    points = []  # List of (latency, area, label)

    for label, resources in resource_configs:
        scheduler = ListScheduler(dfg, resources, priority_fn=default_priority)
        scheduler.schedule()
        assert scheduler.verify_schedule()
        summary = schedule_summary(scheduler)
        latency = summary["total_latency"]

        # Run binding to get area
        binder = BindingEngine(scheduler.nodes)
        binder.bind()
        bind_summary = binder.get_binding_summary()
        total_area = bind_summary["total_area_estimate"]

        points.append((latency, total_area, label))
        print(f"  Config {label}: Latency={latency}, Total Area={total_area}")

    # Identify Pareto-optimal points
    all_points = [(lat, area) for lat, area, _ in points]
    pareto_points = [(lat, area, lbl) for lat, area, lbl in points
                     if is_pareto_optimal((lat, area), all_points)]

    # Sort Pareto points by latency for line drawing
    pareto_points.sort(key=lambda x: x[0])

    print(f"\n  Pareto-optimal configurations ({len(pareto_points)}/{len(points)}):")
    for lat, area, lbl in pareto_points:
        print(f"    {lbl}: Latency={lat}, Area={area}")

    # Plot
    plot_path = os.path.join(output_dir, f"{dfg_name}_pareto.png")
    plot_pareto_frontier(
        points=points,
        pareto_points=pareto_points,
        output_path=plot_path,
        title=f"Area-Latency Pareto Frontier: {dfg_name}"
    )

    return {
        "dfg_name": dfg_name,
        "points": points,
        "pareto_points": pareto_points,
    }


def generate_resource_configs(base_resources: dict, variations: dict) -> list:
    """
    Generate a grid of resource configurations for Pareto analysis.

    Args:
        base_resources: Base resource dictionary.
        variations: Dict mapping op_type -> list of possible counts.

    Returns:
        List of (label, resources_dict) tuples.
    """
    configs = []
    op_types = list(variations.keys())
    counts_lists = [variations[op] for op in op_types]

    for combo in itertools.product(*counts_lists):
        resources = dict(base_resources)
        label_parts = []
        for op_type, count in zip(op_types, combo):
            resources[op_type] = count
            label_parts.append(f"{op_type}{count}")
        label = "_".join(label_parts)
        configs.append((label, resources))

    return configs


def main():
    parser = argparse.ArgumentParser(description="Experiment")
    parser.add_argument("--output-dir", "-o", type=str, default=None,
                        help="Directory to save output figures")
    args = parser.parse_args()

    base_dir = os.path.dirname(__file__)
    if args.output_dir:
        results_dir = args.output_dir
    else:
        results_dir = os.path.join(base_dir, "results", "comparison_plots")
    os.makedirs(results_dir, exist_ok=True)

    # --- FIR Filter Pareto Analysis ---
    dfg_path = os.path.join(base_dir, "..", "data", "medium", "fir_filter.json")
    if os.path.exists(dfg_path):
        # Grid search over ADD and MUL counts
        variations = {
            "ADD": [1, 2, 3, 4, 5, 6, 8],
            "MUL": [1, 2, 3, 4, 5, 6],
        }
        # We need a base config with all required keys
        base_resources = {"ADD": 4, "MUL": 3}  # values will be overwritten
        configs = generate_resource_configs(base_resources, variations)
        result1 = run_pareto_analysis(dfg_path, configs, results_dir)

    # --- DiffEq Solver Pareto Analysis ---
    dfg_path2 = os.path.join(base_dir, "..", "data", "medium", "diffeq_solver.json")
    if os.path.exists(dfg_path2):
        variations2 = {
            "ADD": [1, 2, 3, 4, 5, 6, 8],
            "MUL": [1, 2, 3, 4],
            "SUB": [1, 2, 3, 4],
        }
        base_resources2 = {"ADD": 4, "MUL": 2, "SUB": 2}
        configs2 = generate_resource_configs(base_resources2, variations2)
        result2 = run_pareto_analysis(dfg_path2, configs2, results_dir)

    # Save summary
    summary_path = os.path.join(results_dir, "pareto_summary.txt")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("AREA-LATENCY PARETO ANALYSIS SUMMARY\n")
        f.write("=" * 80 + "\n")
        if 'result1' in locals():
            f.write(f"\nDFG: {result1['dfg_name']}\n")
            f.write(f"Total configurations tested: {len(result1['points'])}\n")
            f.write(f"Pareto-optimal points: {len(result1['pareto_points'])}\n")
            f.write("\nAll points (Latency, Area, Config):\n")
            for lat, area, lbl in result1['points']:
                marker = " [PARETO]" if (lat, area, lbl) in result1['pareto_points'] else ""
                f.write(f"  ({lat:3d}, {area:5d})  {lbl}{marker}\n")
        if 'result2' in locals():
            f.write(f"\nDFG: {result2['dfg_name']}\n")
            f.write(f"Total configurations tested: {len(result2['points'])}\n")
            f.write(f"Pareto-optimal points: {len(result2['pareto_points'])}\n")
            for lat, area, lbl in result2['points']:
                marker = " [PARETO]" if (lat, area, lbl) in result2['pareto_points'] else ""
                f.write(f"  ({lat:3d}, {area:5d})  {lbl}{marker}\n")
    print(f"\nSummary saved to: {summary_path}")


if __name__ == "__main__":
    main()
