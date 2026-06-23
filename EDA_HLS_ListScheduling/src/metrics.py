# metrics.py - 评价指标计算
# Latency、Utilization、Throughput等调度结果评估
# 陈润锴

from typing import Dict, List

from .node import Node
from .list_scheduler import ListScheduler


def total_latency(scheduled_nodes: Dict[str, Node]) -> int:
    """计算总延迟（makespan），空输入返回0"""
    if not scheduled_nodes:
        return 0
    finish_times = [node.finish_time for node in scheduled_nodes.values() if node.finish_time is not None]
    return max(finish_times) if finish_times else 0


def resource_utilization(
    scheduled_nodes: Dict[str, Node],
    resource_limits: Dict[str, int],
    total_latency_val: int,
) -> Dict[str, float]:
    """计算每类资源的利用率 = 总活跃周期 / (latency * 资源限额)"""
    utilizations = {}
    for op_type, limit in resource_limits.items():
        if limit <= 0 or total_latency_val <= 0:
            utilizations[op_type] = 0.0
            continue

        total_active_cycles = sum(
            node.delay
            for node in scheduled_nodes.values()
            if node.op_type == op_type and node.delay is not None
        )

        total_available_cycles = total_latency_val * limit
        utilizations[op_type] = total_active_cycles / total_available_cycles

    return utilizations


def overall_utilization(
    scheduled_nodes: Dict[str, Node],
    resource_limits: Dict[str, int],
    total_latency_val: int,
) -> float:
    """整体资源利用率，按资源数量加权"""
    total_active = 0
    total_available = 0
    for op_type, limit in resource_limits.items():
        active = sum(
            node.delay
            for node in scheduled_nodes.values()
            if node.op_type == op_type
        )
        total_active += active
        total_available += total_latency_val * limit

    return total_active / total_available if total_available > 0 else 0.0


def throughput(scheduled_nodes: Dict[str, Node], total_latency_val: int) -> float:
    """吞吐率 = 节点数 / latency"""
    if not scheduled_nodes or total_latency_val <= 0:
        return 0.0
    return len(scheduled_nodes) / total_latency_val


def schedule_summary(scheduler: ListScheduler) -> Dict:
    """生成调度结果的汇总字典，包含latency、utilization、throughput等"""
    nodes = scheduler.nodes
    limits = scheduler.resource_limits
    lat = total_latency(nodes)
    util = resource_utilization(nodes, limits, lat)
    overall_util = overall_utilization(nodes, limits, lat)
    tp = throughput(nodes, lat)

    # 每cycle的资源占用数，用于画图
    cycle_usage: Dict[int, Dict[str, int]] = {}
    for cycle in range(lat):
        cycle_usage[cycle] = {}
        for op_type in limits:
            count = 0
            for node in nodes.values():
                if node.op_type == op_type and node.start_time is not None:
                    if node.start_time <= cycle < node.finish_time:
                        count += 1
            cycle_usage[cycle][op_type] = count

    return {
        "total_latency": lat,
        "resource_utilization": util,
        "overall_utilization": overall_util,
        "throughput": tp,
        "num_nodes": len(nodes),
        "resource_limits": limits,
        "cycle_usage": cycle_usage,
        "schedule_log": scheduler.schedule_log,
    }


def print_summary(summary: Dict) -> None:
    """把调度结果打印到控制台"""
    print("=" * 60)
    print("SCHEDULING RESULT SUMMARY")
    print("=" * 60)
    print(f"Total Nodes:        {summary['num_nodes']}")
    print(f"Total Latency:      {summary['total_latency']} cycles")
    print(f"Throughput:         {summary['throughput']:.4f} ops/cycle")
    print(f"Overall Utilization:{summary['overall_utilization']*100:.2f}%")
    print("-" * 60)
    print("Per-Resource Utilization:")
    for op_type, util in summary['resource_utilization'].items():
        limit = summary['resource_limits'].get(op_type, 0)
        print(f"  {op_type:6s} (limit={limit}): {util*100:.2f}%")
    print("=" * 60)
