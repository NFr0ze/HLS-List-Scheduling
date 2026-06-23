# run_all_experiments.py - 一键运行全部实验
# 顺序调用main.py和6个对照实验脚本，输出汇总结果
# 陈润锴

import os
import sys
import argparse
import subprocess
import time
from pathlib import Path


def run_script(script_path: str, description: str, verbose: bool = False) -> bool:
    """运行一个Python脚本并报告状态"""
    print(f"\n{'='*70}")
    print(f"Running: {description}")
    print(f"Script:  {script_path}")
    print(f"{'='*70}")

    t0 = time.time()
    try:
        if verbose:
            result = subprocess.run(
                [sys.executable, script_path],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                check=True,
            )
        else:
            result = subprocess.run(
                [sys.executable, script_path],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        elapsed = time.time() - t0
        print(f"[OK] Completed in {elapsed:.2f}s")
        return True
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - t0
        print(f"[FAILED] After {elapsed:.2f}s")
        if not verbose and e.stdout:
            print("Output:")
            print(e.stdout[-2000:])  # 只显示最后2000字符，避免刷屏
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run all EDA HLS experiments with one command.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_all_experiments.py              # Run everything
  python run_all_experiments.py --skip-main  # Skip main.py (already run)
  python run_all_experiments.py --verbose    # Show full output from each script
        """
    )
    parser.add_argument(
        "--skip-main",
        action="store_true",
        help="Skip main.py scheduling workflow",
    )
    parser.add_argument(
        "--skip-strategies",
        action="store_true",
        help="Skip strategy comparison experiment",
    )
    parser.add_argument(
        "--skip-sensitivity",
        action="store_true",
        help="Skip sensitivity analysis",
    )
    parser.add_argument(
        "--skip-pareto",
        action="store_true",
        help="Skip Pareto frontier analysis",
    )
    parser.add_argument(
        "--skip-pipeline",
        action="store_true",
        help="Skip pipeline scheduling experiment",
    )
    parser.add_argument(
        "--skip-scalability",
        action="store_true",
        help="Skip scalability test",
    )
    parser.add_argument(
        "--skip-schedulability",
        action="store_true",
        help="Skip schedulability test",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show real-time output from each experiment",
    )

    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    experiments_dir = os.path.join(base_dir, "experiments")

    experiments = []
    if not args.skip_main:
        experiments.append((os.path.join(base_dir, "main.py"), "Main Scheduling Workflow"))
    if not args.skip_strategies:
        experiments.append((os.path.join(experiments_dir, "compare_strategies.py"), "Strategy Comparison"))
    if not args.skip_sensitivity:
        experiments.append((os.path.join(experiments_dir, "sensitivity_analysis.py"), "Sensitivity Analysis"))
    if not args.skip_pareto:
        experiments.append((os.path.join(experiments_dir, "pareto_analysis.py"), "Pareto Frontier Analysis"))
    if not args.skip_pipeline:
        experiments.append((os.path.join(experiments_dir, "pipeline_test.py"), "Pipeline Scheduling"))
    if not args.skip_scalability:
        experiments.append((os.path.join(experiments_dir, "scalability_test.py"), "Scalability Test"))
    if not args.skip_schedulability:
        experiments.append((os.path.join(experiments_dir, "schedulability_test.py"), "Schedulability Test"))

    print("\n" + "=" * 70)
    print("EDA HLS List Scheduling - Unified Experiment Runner")
    print("=" * 70)
    print(f"Total experiments to run: {len(experiments)}")
    print(f"Base directory: {base_dir}")
    print("=" * 70)

    results = []
    total_t0 = time.time()
    for script_path, description in experiments:
        success = run_script(script_path, description, verbose=args.verbose)
        results.append((description, success))

    total_elapsed = time.time() - total_t0

    # Print final summary
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"{'Experiment':<40} {'Status':<10}")
    print("-" * 70)
    for desc, success in results:
        status = "OK" if success else "FAILED"
        print(f"{desc:<40} {status:<10}")
    print("-" * 70)
    print(f"Total time: {total_elapsed:.2f}s")
    all_ok = all(success for _, success in results)
    print(f"Overall: {'ALL PASSED' if all_ok else 'SOME FAILED'}")
    print("=" * 70)

    # Save summary to file
    results_dir = os.path.join(base_dir, "experiments", "results")
    os.makedirs(results_dir, exist_ok=True)
    summary_path = os.path.join(results_dir, "run_all_summary.txt")
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("UNIFIED EXPERIMENT RUNNER SUMMARY\n")
        f.write("=" * 70 + "\n")
        f.write(f"Total time: {total_elapsed:.2f}s\n\n")
        for desc, success in results:
            f.write(f"  [{('OK' if success else 'FAIL'):4s}] {desc}\n")
        f.write("\n" + "=" * 70 + "\n")
    print(f"\nSummary saved to: {summary_path}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
