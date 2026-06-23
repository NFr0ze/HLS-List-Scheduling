# pipeline_test.py - 流水线调度实验
# 测试不同启动间隔(II)下的流水线调度可行性与吞吐率
# 陈润锴

import os
import sys
import argparse
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.dfg_parser import parse_dfg
from src.list_scheduler import ListScheduler, default_priority, PipelinedListScheduler
from src.metrics import schedule_summary
from src.visualizer import plot_pipeline_analysis


def run_pipeline_analysis(dfg_path: str, ii_values: list, output_dir: str) -> dict:
    """
    Run pipelined scheduling with varying II values.

    Args:
        dfg_path: Path to the DFG JSON file.
        ii_values: List of II values to test.
        output_dir: Directory to save output figures.

    Returns:
        Dictionary with pipeline analysis results.
    """
    dfg, resources = parse_dfg(dfg_path)
    dfg_name = os.path.splitext(os.path.basename(dfg_path))[0]

    print(f"\n{'='*60}")
    print(f"Pipeline Analysis: {dfg_name}")
    print(f"Resources: {resources}")
    print(f"{'='*60}")

    # Baseline: non-pipelined latency
    baseline_scheduler = ListScheduler(dfg, resources, priority_fn=default_priority)
    baseline_scheduler.schedule()
    baseline_summary = schedule_summary(baseline_scheduler)
    baseline_latency = baseline_summary["total_latency"]
    print(f"Baseline (non-pipelined) Latency: {baseline_latency}")

    results = []
    for ii in ii_values:
        try:
            scheduler = PipelinedListScheduler(dfg, resources, ii=ii, priority_fn=default_priority)
            scheduler.schedule()
            valid = scheduler.verify_schedule()
            if not valid:
                raise RuntimeError("Schedule verification failed")

            latency = scheduler.get_total_latency()
            throughput = scheduler.get_effective_throughput(num_iterations=100)
            summary = schedule_summary(scheduler)

            results.append({
                "ii": ii,
                "latency": latency,
                "throughput": throughput,
                "utilization": summary["overall_utilization"],
                "feasible": True,
            })
            print(f"  II={ii:2d}: Latency={latency:3d}, Throughput={throughput:.4f} ops/cycle, OK")
        except Exception as e:
            results.append({
                "ii": ii,
                "latency": None,
                "throughput": None,
                "utilization": None,
                "feasible": False,
            })
            print(f"  II={ii:2d}: INFEASIBLE ({e})")

    # Plot
    plot_path = os.path.join(output_dir, f"{dfg_name}_pipeline.png")
    plot_pipeline_analysis(
        results=results,
        baseline_latency=baseline_latency,
        output_path=plot_path,
        title=f"Pipelined Scheduling: {dfg_name}"
    )

    return {
        "dfg_name": dfg_name,
        "baseline_latency": baseline_latency,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Pipeline Scheduling Experiment")
    parser.add_argument("--output-dir", "-o", type=str, default=None,
                        help="Directory to save output figures")
    parser.add_argument("--ii-values", "-i", type=str, default=None,
                        help="Comma-separated list of II values to test (default: 1,2,3,4,5,6,8,10,12)")
    args = parser.parse_args()

    base_dir = os.path.dirname(__file__)
    if args.output_dir:
        results_dir = args.output_dir
    else:
        results_dir = os.path.join(base_dir, "results", "comparison_plots")
    os.makedirs(results_dir, exist_ok=True)

    # Parse II values
    if args.ii_values:
        ii_values = [int(x.strip()) for x in args.ii_values.split(",")]
    else:
        ii_values = [1, 2, 3, 4, 5, 6, 8, 10, 12]

    # Test on FIR filter
    dfg_path = os.path.join(base_dir, "..", "data", "medium", "fir_filter.json")
    if os.path.exists(dfg_path):
        result1 = run_pipeline_analysis(dfg_path, ii_values, results_dir)

    # Test on simple_expr
    dfg_path2 = os.path.join(base_dir, "..", "data", "small", "simple_expr.json")
    if os.path.exists(dfg_path2):
        ii_values2 = [1, 2, 3, 4, 5, 6, 8] if not args.ii_values else ii_values
        result2 = run_pipeline_analysis(dfg_path2, ii_values2, results_dir)

    # Save summary
    summary_path = os.path.join(results_dir, "pipeline_summary.txt")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("PIPELINED SCHEDULING ANALYSIS SUMMARY\n")
        f.write("=" * 80 + "\n")
        if 'result1' in locals():
            f.write(f"\nDFG: {result1['dfg_name']}\n")
            f.write(f"Baseline Latency: {result1['baseline_latency']}\n")
            f.write(f"{'II':<5} {'Latency':<10} {'Throughput':<15} {'Status':<10}\n")
            for r in result1['results']:
                status = "FEASIBLE" if r['feasible'] else "INFEASIBLE"
                lat = str(r['latency']) if r['latency'] is not None else "N/A"
                thr = f"{r['throughput']:.4f}" if r['throughput'] is not None else "N/A"
                f.write(f"{r['ii']:<5} {lat:<10} {thr:<15} {status:<10}\n")
        if 'result2' in locals():
            f.write(f"\nDFG: {result2['dfg_name']}\n")
            f.write(f"Baseline Latency: {result2['baseline_latency']}\n")
            f.write(f"{'II':<5} {'Latency':<10} {'Throughput':<15} {'Status':<10}\n")
            for r in result2['results']:
                status = "FEASIBLE" if r['feasible'] else "INFEASIBLE"
                lat = str(r['latency']) if r['latency'] is not None else "N/A"
                thr = f"{r['throughput']:.4f}" if r['throughput'] is not None else "N/A"
                f.write(f"{r['ii']:<5} {lat:<10} {thr:<15} {status:<10}\n")
    print(f"\nSummary saved to: {summary_path}")


if __name__ == "__main__":
    main()
