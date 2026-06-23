# sensitivity_analysis.py - 灵敏度分析实验
# 固定DFG，逐步改变资源配额，观察Latency的变化趋势
# 陈润锴

import os
import sys
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.dfg_parser import parse_dfg
from src.list_scheduler import ListScheduler, default_priority
from src.metrics import schedule_summary
from src.visualizer import plot_sensitivity_analysis


def run_sensitivity(dfg_path: str, resource_configs: list, output_dir: str) -> dict:
    """
    Run sensitivity analysis by varying resource limits.

    Args:
        dfg_path: Path to the DFG JSON file.
        resource_configs: List of (label, resource_dict) tuples.
        output_dir: Directory to save output figures.

    Returns:
        Dictionary with sensitivity results.
    """
    dfg, base_resources = parse_dfg(dfg_path)
    dfg_name = os.path.splitext(os.path.basename(dfg_path))[0]

    print(f"\n{'='*60}")
    print(f"Sensitivity Analysis: {dfg_name}")
    print(f"Base Resources: {base_resources}")
    print(f"{'='*60}")

    labels = []
    latencies = []
    utilizations = []

    for label, resources in resource_configs:
        scheduler = ListScheduler(dfg, resources, priority_fn=default_priority)
        scheduler.schedule()
        assert scheduler.verify_schedule()
        summary = schedule_summary(scheduler)

        labels.append(label)
        latencies.append(summary["total_latency"])
        utilizations.append(summary["overall_utilization"])

        print(f"  Config {label}: Latency={summary['total_latency']}, "
              f"Utilization={summary['overall_utilization']*100:.2f}%")

    # Plot sensitivity curve
    plot_path = os.path.join(output_dir, f"{dfg_name}_sensitivity.png")
    plot_sensitivity_analysis(labels, latencies, output_path=plot_path,
                              title=f"Sensitivity Analysis: {dfg_name}")

    return {
        "dfg_name": dfg_name,
        "labels": labels,
        "latencies": latencies,
        "utilizations": utilizations,
    }


def main():
    parser = argparse.ArgumentParser(description="Sensitivity Analysis Experiment")
    parser.add_argument("--output-dir", "-o", type=str, default=None,
                        help="Directory to save output figures")
    args = parser.parse_args()

    base_dir = os.path.dirname(__file__)
    if args.output_dir:
        results_dir = args.output_dir
    else:
        results_dir = os.path.join(base_dir, "results", "comparison_plots")
    os.makedirs(results_dir, exist_ok=True)

    # Use FIR filter for sensitivity analysis
    dfg_path = os.path.join(base_dir, "..", "data", "medium", "fir_filter.json")

    if not os.path.exists(dfg_path):
        print(f"Error: {dfg_path} not found.")
        return

    # Define resource configurations: (label, resources_dict)
    # Varying ADD and MUL units
    configs = [
        ("ADD1_MUL1", {"ADD": 1, "MUL": 1}),
        ("ADD2_MUL1", {"ADD": 2, "MUL": 1}),
        ("ADD2_MUL2", {"ADD": 2, "MUL": 2}),
        ("ADD3_MUL2", {"ADD": 3, "MUL": 2}),
        ("ADD4_MUL2", {"ADD": 4, "MUL": 2}),
        ("ADD4_MUL3", {"ADD": 4, "MUL": 3}),
        ("ADD5_MUL3", {"ADD": 5, "MUL": 3}),
        ("ADD6_MUL4", {"ADD": 6, "MUL": 4}),
    ]

    result = run_sensitivity(dfg_path, configs, results_dir)

    # Also run on diffeq_solver
    dfg_path2 = os.path.join(base_dir, "..", "data", "medium", "diffeq_solver.json")
    if os.path.exists(dfg_path2):
        configs2 = [
            ("ADD2_MUL1_SUB1", {"ADD": 2, "MUL": 1, "SUB": 1}),
            ("ADD3_MUL2_SUB1", {"ADD": 3, "MUL": 2, "SUB": 1}),
            ("ADD4_MUL2_SUB2", {"ADD": 4, "MUL": 2, "SUB": 2}),
            ("ADD5_MUL3_SUB2", {"ADD": 5, "MUL": 3, "SUB": 2}),
            ("ADD6_MUL4_SUB3", {"ADD": 6, "MUL": 4, "SUB": 3}),
            ("ADD8_MUL4_SUB3", {"ADD": 8, "MUL": 4, "SUB": 3}),
        ]
        result2 = run_sensitivity(dfg_path2, configs2, results_dir)

    # Save summary
    summary_path = os.path.join(results_dir, "sensitivity_summary.txt")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("SENSITIVITY ANALYSIS SUMMARY\n")
        f.write("=" * 80 + "\n")
        f.write(f"\nDFG: {result['dfg_name']}\n")
        for label, lat, util in zip(result['labels'], result['latencies'], result['utilizations']):
            f.write(f"  {label}: Latency={lat}, Utilization={util*100:.2f}%\n")
    print(f"\nSummary saved to: {summary_path}")


if __name__ == "__main__":
    main()
