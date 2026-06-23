# main.py - 主入口
# 加载DFG → ASAP/ALAP → List Scheduling → 验证 → 指标 → 可视化
# 支持命令行参数指定数据集、策略、输出目录等
# 陈润锴 23362012

import os
import sys
import time
import argparse
import logging

from src.dfg_parser import parse_dfg
from src.asap_alap import run_static_timing_analysis, extract_critical_path
from src.list_scheduler import (
    ListScheduler, default_priority, cp_first_priority, ldf_priority
)
from src.metrics import schedule_summary, print_summary
from src.binding import BindingEngine, print_binding_summary
from src.visualizer import (
    plot_gantt_chart,
    plot_utilization_curve,
    export_schedule_table,
)


# Setup logging
logger = logging.getLogger("EDA_HLS")


def setup_logging(verbose: bool = False):
    """设置日志级别"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def get_strategy(name: str):
    """策略名称映射到优先级函数"""
    strategies = {
        "mobility": default_priority,
        "cp_first": cp_first_priority,
        "ldf": ldf_priority,
    }
    if name not in strategies:
        raise ValueError(f"Unknown strategy '{name}'. Choose from: {list(strategies.keys())}")
    return strategies[name]


def run_single_test(dfg_path: str, resources: dict = None, output_dir: str = None,
                    priority_fn=None, verbose: bool = False) -> dict:
    """跑单个DFG的完整调度流程，返回汇总字典"""
    dfg_name = os.path.splitext(os.path.basename(dfg_path))[0]
    logger.info(f"{'='*70}")
    logger.info(f"Testing: {dfg_name}")
    logger.info(f"{'='*70}")

    # Step 1: 解析DFG
    dfg, default_resources = parse_dfg(dfg_path)
    if resources is None:
        resources = default_resources
    logger.info(f"Loaded DFG: {len(dfg)} nodes")
    logger.info(f"Resource Limits: {resources}")

    # Step 2: ASAP/ALAP + 关键路径
    critical_path = run_static_timing_analysis(dfg)
    cp_nodes = extract_critical_path(dfg)
    logger.info(f"Critical Path Length (ASAP): {critical_path}")
    logger.info(f"Critical Path Nodes ({len(cp_nodes)}): {cp_nodes}")

    # Step 3: List Scheduling
    scheduler = ListScheduler(dfg, resources, priority_fn=priority_fn)
    t0 = time.time()
    scheduler.schedule()
    t1 = time.time()
    runtime = t1 - t0
    logger.info(f"Scheduling completed in {runtime*1000:.2f} ms")

    # Step 4: 验证
    valid = scheduler.verify_schedule()
    logger.info(f"Schedule Valid: {valid}")

    # Step 5: 指标
    summary = schedule_summary(scheduler)
    summary["runtime"] = runtime
    summary["critical_path"] = critical_path
    print_summary(summary)

    # Step 6: 资源绑定
    logger.info(f"{'='*60}")
    logger.info("RESOURCE BINDING")
    logger.info(f"{'='*60}")
    binder = BindingEngine(scheduler.nodes)
    binder.bind()
    bind_summary = binder.get_binding_summary()
    print_binding_summary(bind_summary)
    summary["binding"] = bind_summary

    # Step 7: 可视化输出
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        gantt_path = os.path.join(output_dir, f"{dfg_name}_gantt.png")
        util_path = os.path.join(output_dir, f"{dfg_name}_utilization.png")
        table_path = os.path.join(output_dir, f"{dfg_name}_schedule.txt")

        plot_gantt_chart(scheduler.nodes, resources, output_path=gantt_path,
                         title=f"Gantt Chart: {dfg_name}", critical_path=cp_nodes)
        plot_utilization_curve(summary["cycle_usage"], resources, output_path=util_path,
                               title=f"Utilization: {dfg_name}")
        export_schedule_table(scheduler.nodes, output_path=table_path)

    return summary


def main():
    parser = argparse.ArgumentParser(
        description="EDA HLS List Scheduling - Main Entry Point",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                                    # Run all default tests
  python main.py --dataset data/medium/fir_filter.json
  python main.py --strategy cp_first --verbose
  python main.py --output-dir ./my_results
        """
    )
    parser.add_argument(
        "--dataset", "-d",
        type=str,
        default=None,
        help="Path to a specific DFG JSON file to run. If omitted, runs all default test cases."
    )
    parser.add_argument(
        "--strategy", "-s",
        type=str,
        default="mobility",
        choices=["mobility", "cp_first", "ldf"],
        help="Scheduling priority strategy (default: mobility)"
    )
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default=None,
        help="Directory to save output figures (default: experiments/results/gantt_charts)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging"
    )
    parser.add_argument(
        "--resources", "-r",
        type=str,
        default=None,
        help="Override resource limits as JSON string, e.g., '{\"ADD\":2,\"MUL\":1}'"
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    priority_fn = get_strategy(args.strategy)
    logger.info(f"Using strategy: {args.strategy}")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    if args.output_dir:
        results_dir = args.output_dir
    else:
        results_dir = os.path.join(base_dir, "experiments", "results", "gantt_charts")
    os.makedirs(results_dir, exist_ok=True)

    # Parse override resources if provided
    override_resources = None
    if args.resources:
        import json
        override_resources = json.loads(args.resources)
        logger.info(f"Override resources: {override_resources}")

    # Build test case list
    if args.dataset:
        test_cases = [(args.dataset, results_dir)]
    else:
        test_cases = [
            (os.path.join(base_dir, "data", "small", "simple_expr.json"), results_dir),
            (os.path.join(base_dir, "data", "small", "basic_dag.json"), results_dir),
            (os.path.join(base_dir, "data", "medium", "fir_filter.json"), results_dir),
            (os.path.join(base_dir, "data", "medium", "diffeq_solver.json"), results_dir),
            (os.path.join(base_dir, "data", "large", "random_dag_200.json"), results_dir),
            (os.path.join(base_dir, "data", "large", "random_dag_300.json"), results_dir),
        ]

    all_summaries = []
    for dfg_path, subdir in test_cases:
        if os.path.exists(dfg_path):
            summary = run_single_test(
                dfg_path,
                resources=override_resources,
                output_dir=subdir,
                priority_fn=priority_fn,
                verbose=args.verbose,
            )
            summary["name"] = os.path.splitext(os.path.basename(dfg_path))[0]
            all_summaries.append(summary)
        else:
            logger.warning(f"Warning: {dfg_path} not found, skipping.")

    # Print overall summary table
    print("\n" + "=" * 80)
    print("OVERALL TEST SUMMARY")
    print("=" * 80)
    print(f"{'Test Case':<20} {'Nodes':<8} {'Latency':<10} {'Utilization':<12} {'Runtime(ms)':<12}")
    print("-" * 80)
    for s in all_summaries:
        print(f"{s['name']:<20} {s['num_nodes']:<8} {s['total_latency']:<10} "
              f"{s['overall_utilization']*100:>6.2f}%      {s['runtime']*1000:>8.2f}")
    print("=" * 80)

    logger.info("All tests completed. Results saved to %s", results_dir)


if __name__ == "__main__":
    main()
