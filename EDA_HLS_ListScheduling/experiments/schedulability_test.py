# schedulability_test.py - 可调度性分析
# 逐步收紧延迟约束，观察调度器何时失败，找出调度边界
# 陈润锴

import os
import sys
import argparse
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.dfg_parser import parse_dfg
from src.list_scheduler import ListScheduler, default_priority
from src.asap_alap import compute_asap
from src.visualizer import plot_sensitivity_analysis


def run_schedulability_test(dfg_path: str, output_dir: str, max_steps: int = 15,
                            resource_override: dict = None) -> dict:
    """
    Run schedulability test by tightening latency constraints.

    Args:
        dfg_path: Path to the DFG JSON file.
        output_dir: Directory to save output figure.
        max_steps: Maximum number of constraint steps to test.

    Returns:
        Dictionary with test results.
    """
    dfg, resources = parse_dfg(dfg_path)
    if resource_override:
        resources = resource_override
    dfg_name = os.path.splitext(os.path.basename(dfg_path))[0]

    # Compute critical path (minimum possible latency under unlimited resources)
    critical_path = compute_asap(dfg)
    print(f"\n{'='*60}")
    print(f"Schedulability Test: {dfg_name}")
    print(f"Critical Path (unlimited resources): {critical_path}")
    print(f"Resources: {resources}")
    print(f"{'='*60}")

    labels = []
    latencies = []
    schedulable = []

    # Test from critical_path down to max(0, critical_path - max_steps)
    for constraint in range(critical_path, max(0, critical_path - max_steps), -1):
        labels.append(str(constraint))
        scheduler = ListScheduler(dfg, resources, priority_fn=default_priority,
                                   latency_constraint=constraint)
        try:
            scheduler.schedule()
            actual_latency = scheduler.get_total_latency()
            # 必须同时满足：调度合法 且 实际延迟不超过约束
            valid = scheduler.verify_schedule() and (actual_latency <= constraint)
            latencies.append(actual_latency)
            schedulable.append(1 if valid else 0)
            status = "OK" if valid else "INVALID"
        except RuntimeError as e:
            # 调度失败，用constraint作为柱高让红柱可见（表示在该约束下无法完成）
            latencies.append(constraint)
            schedulable.append(0)
            status = f"FAIL ({str(e)[:40]})"

        print(f"  Constraint={constraint:2d}: Actual Latency={latencies[-1]:2d}, Status={status}")

    # Plot: actual latency vs constraint
    plot_path = os.path.join(output_dir, f"{dfg_name}_schedulability.png")
    fig, ax = plt.subplots(figsize=(10, 6))

    x_vals = range(len(labels))
    # Use different colors for schedulable vs unschedulable
    sched_colors = ['#2ecc71' if s else '#e74c3c' for s in schedulable]

    ax.bar(x_vals, latencies, color=sched_colors, edgecolor='black', linewidth=0.5)
    ax.set_xticks(x_vals)
    ax.set_xticklabels(labels)
    ax.set_xlabel("Latency Constraint (cycles)", fontsize=12)
    ax.set_ylabel("Actual Scheduled Latency (cycles)", fontsize=12)
    ax.set_title(f"Schedulability Test: {dfg_name}", fontsize=14, fontweight='bold')
    ax.grid(axis='y', alpha=0.3)

    # Add legend
    ok_patch = mpatches.Patch(color='#2ecc71', label='Schedulable')
    fail_patch = mpatches.Patch(color='#e74c3c', label='Unschedulable')
    ax.legend(handles=[ok_patch, fail_patch], loc='upper right')

    plt.tight_layout()
    os.makedirs(output_dir, exist_ok=True)
    fig.savefig(plot_path, dpi=300, bbox_inches='tight')
    print(f"[Visualizer] Schedulability plot saved to: {plot_path}")

    return {
        "dfg_name": dfg_name,
        "critical_path": critical_path,
        "labels": labels,
        "latencies": latencies,
        "schedulable": schedulable,
    }


def main():
    parser = argparse.ArgumentParser(description="Schedulability Test")
    parser.add_argument("--output-dir", "-o", type=str, default=None,
                        help="Directory to save output figures")
    parser.add_argument("--max-steps", "-s", type=int, default=15,
                        help="Maximum number of constraint steps to test (default: 15)")
    args = parser.parse_args()

    base_dir = os.path.dirname(__file__)
    if args.output_dir:
        results_dir = args.output_dir
    else:
        results_dir = os.path.join(base_dir, "results", "comparison_plots")
    os.makedirs(results_dir, exist_ok=True)

    test_cases = [
        # fir_filter 原资源配置，通常全部可调度
        (os.path.join(base_dir, "..", "data", "medium", "fir_filter.json"), None),
        # diffeq_solver 紧缩资源，约束收紧后会出现不可调度的情况
        (os.path.join(base_dir, "..", "data", "medium", "diffeq_solver.json"),
         {"ADD": 1, "MUL": 1, "SUB": 1}),
    ]

    for case_path, res_override in test_cases:
        if os.path.exists(case_path):
            result = run_schedulability_test(case_path, results_dir,
                                              max_steps=args.max_steps,
                                              resource_override=res_override)

            # Save summary
            summary_path = os.path.join(results_dir, f"{result['dfg_name']}_schedulability.txt")
            with open(summary_path, 'w', encoding='utf-8') as f:
                f.write(f"SCHEDULABILITY TEST SUMMARY: {result['dfg_name']}\n")
                f.write("=" * 60 + "\n")
                f.write(f"Critical Path: {result['critical_path']}\n\n")
                f.write(f"{'Constraint':<12} {'Actual':<10} {'Status':<15}\n")
                f.write("-" * 60 + "\n")
                for label, lat, sched in zip(result["labels"], result["latencies"], result["schedulable"]):
                    status = "Schedulable" if sched else "UNschedulable"
                    f.write(f"{label:<12} {lat:<10} {status:<15}\n")
            print(f"Summary saved to: {summary_path}\n")
        else:
            print(f"Warning: {case} not found, skipping.")


if __name__ == "__main__":
    main()
