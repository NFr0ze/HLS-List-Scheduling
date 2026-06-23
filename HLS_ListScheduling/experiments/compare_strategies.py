# compare_strategies.py - 策略对比实验
# 比较Mobility-First、CP-First、LDF-First和Random四种优先级策略的效果
# 陈润锴

import os
import sys
import time
import argparse
import random
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.dfg_parser import parse_dfg
from src.list_scheduler import ListScheduler, default_priority, cp_first_priority, ldf_priority
from src.metrics import schedule_summary, print_summary
from src.visualizer import plot_strategy_comparison


def run_strategy(dfg, resources, priority_fn, name):
    """Run a single strategy and return summary."""
    scheduler = ListScheduler(dfg, resources, priority_fn=priority_fn)
    t0 = time.time()
    scheduler.schedule()
    t1 = time.time()
    assert scheduler.verify_schedule(), f"Schedule verification failed for {name}"
    summary = schedule_summary(scheduler)
    summary["runtime"] = t1 - t0
    return summary


def run_random_average(dfg, resources, n_runs=20):
    """Run Random strategy N times and return averaged statistics."""
    latencies = []
    utilizations = []
    runtimes = []

    for i in range(n_runs):
        # Use a different seed per run for true randomness
        rand_fn = lambda node: random.random()
        scheduler = ListScheduler(dfg, resources, priority_fn=rand_fn)
        t0 = time.time()
        scheduler.schedule()
        t1 = time.time()
        assert scheduler.verify_schedule()
        summary = schedule_summary(scheduler)
        latencies.append(summary["total_latency"])
        utilizations.append(summary["overall_utilization"])
        runtimes.append(t1 - t0)

    return {
        "total_latency": float(np.mean(latencies)),
        "latency_std": float(np.std(latencies)),
        "latency_min": int(np.min(latencies)),
        "latency_max": int(np.max(latencies)),
        "overall_utilization": float(np.mean(utilizations)),
        "util_std": float(np.std(utilizations)),
        "runtime": float(np.mean(runtimes)),
        "num_nodes": len(dfg.nodes()),
        "resource_limits": resources,
    }


def run_comparison(dfg_path: str, output_dir: str) -> dict:
    """
    Run strategy comparison on a single DFG.
    """
    dfg, resources = parse_dfg(dfg_path)
    dfg_name = os.path.splitext(os.path.basename(dfg_path))[0]
    print(f"\n{'='*60}")
    print(f"Strategy Comparison: {dfg_name}")
    print(f"Resources: {resources}")
    print(f"{'='*60}")

    results = {}

    # Strategy 1: Mobility-minimum-first
    summary1 = run_strategy(dfg, resources, default_priority, "Mobility-First")
    results["Mobility-First"] = summary1
    print("\n[Strategy 1: Mobility-First]")
    print_summary(summary1)

    # Strategy 2: Critical-Path-First
    summary2 = run_strategy(dfg, resources, cp_first_priority, "CP-First")
    results["CP-First"] = summary2
    print("\n[Strategy 2: CP-First]")
    print_summary(summary2)

    # Strategy 3: Longest-Delay-First
    summary3 = run_strategy(dfg, resources, ldf_priority, "LDF-First")
    results["LDF-First"] = summary3
    print("\n[Strategy 3: LDF-First]")
    print_summary(summary3)

    # Strategy 4: Random (averaged over 20 runs)
    print(f"\n[Strategy 4: Random (averaging 20 runs)...]")
    summary4 = run_random_average(dfg, resources, n_runs=20)
    results["Random (avg)"] = summary4
    print(f"  Latency: {summary4['total_latency']:.1f} ± {summary4['latency_std']:.1f} "
          f"(min={summary4['latency_min']}, max={summary4['latency_max']})")
    print(f"  Utilization: {summary4['overall_utilization']*100:.2f}%")

    # Plot comparison
    plot_path = os.path.join(output_dir, f"{dfg_name}_strategy_comparison.png")
    plot_strategy_comparison(results, output_path=plot_path,
                             title=f"Strategy Comparison: {dfg_name}")

    return {
        "dfg_name": dfg_name,
        "resources": resources,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Strategy Comparison Experiment")
    parser.add_argument("--output-dir", "-o", type=str, default=None,
                        help="Directory to save output figures (default: experiments/results/comparison_plots)")
    args = parser.parse_args()

    base_dir = os.path.dirname(__file__)
    if args.output_dir:
        results_dir = args.output_dir
    else:
        results_dir = os.path.join(base_dir, "results", "comparison_plots")
    os.makedirs(results_dir, exist_ok=True)

    test_cases = [
        os.path.join(base_dir, "..", "data", "small", "simple_expr.json"),
        os.path.join(base_dir, "..", "data", "small", "basic_dag.json"),
        os.path.join(base_dir, "..", "data", "medium", "fir_filter.json"),
        os.path.join(base_dir, "..", "data", "medium", "diffeq_solver.json"),
    ]

    all_results = []
    for case in test_cases:
        if os.path.exists(case):
            result = run_comparison(case, results_dir)
            all_results.append(result)
        else:
            print(f"Warning: {case} not found, skipping.")

    # Print summary table
    print("\n" + "=" * 100)
    print("STRATEGY COMPARISON SUMMARY TABLE")
    print("=" * 100)
    print(f"{'DFG Name':<20} {'Strategy':<15} {'Latency':<20} {'Utilization':<12} {'Runtime(ms)':<12}")
    print("-" * 100)
    for r in all_results:
        for strat_name, summary in r["results"].items():
            if "latency_std" in summary:
                lat_str = f"{summary['total_latency']:.1f}±{summary['latency_std']:.1f}"
            else:
                lat_str = str(summary['total_latency'])
            print(f"{r['dfg_name']:<20} {strat_name:<15} {lat_str:<20} "
                  f"{summary['overall_utilization']*100:>6.2f}%      {summary['runtime']*1000:>8.2f}")
    print("=" * 100)

    # Save summary to text file
    summary_path = os.path.join(results_dir, "comparison_summary.txt")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("STRATEGY COMPARISON SUMMARY\n")
        f.write("=" * 100 + "\n")
        for r in all_results:
            f.write(f"\nDFG: {r['dfg_name']}\n")
            f.write(f"Resources: {r['resources']}\n")
            for strat_name, summary in r["results"].items():
                if "latency_std" in summary:
                    f.write(f"  {strat_name}: Latency={summary['total_latency']:.1f}±{summary['latency_std']:.1f} "
                            f"(range: {summary['latency_min']}-{summary['latency_max']}), "
                            f"Utilization={summary['overall_utilization']*100:.2f}%, "
                            f"Runtime={summary['runtime']*1000:.2f}ms\n")
                else:
                    f.write(f"  {strat_name}: Latency={summary['total_latency']}, "
                            f"Utilization={summary['overall_utilization']*100:.2f}%, "
                            f"Runtime={summary['runtime']*1000:.2f}ms\n")
    print(f"\nSummary saved to: {summary_path}")


if __name__ == "__main__":
    main()
