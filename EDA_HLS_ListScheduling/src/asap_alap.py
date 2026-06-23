# asap_alap.py - 静态时序分析
# 计算ASAP/ALAP和Mobility，为List Scheduling提供优先级依据
# 陈润锴

import networkx as nx
from typing import Dict, List, Optional

from .node import Node
from .dfg_parser import dfg_to_nodes_dict


def compute_asap(dfg: nx.DiGraph) -> int:
    """正向拓扑遍历，计算每个节点的ASAP时间和关键路径长度"""
    nodes = dfg_to_nodes_dict(dfg)

    for node_id in nx.topological_sort(dfg):
        node = nodes[node_id]
        if not node.predecessors:
            node.asap = 0
        else:
            max_pred_finish = 0
            for pred_id in node.predecessors:
                pred = nodes[pred_id]
                if pred.asap is None:
                    raise RuntimeError(f"ASAP of predecessor {pred_id} not computed before {node_id}")
                pred_finish = pred.asap + pred.delay
                if pred_finish > max_pred_finish:
                    max_pred_finish = pred_finish
            node.asap = max_pred_finish

    # 关键路径长度 = 所有节点里 ASAP+delay 的最大值
    critical_path = max(node.asap + node.delay for node in nodes.values())
    return critical_path


def compute_alap(dfg: nx.DiGraph, latency_constraint: int) -> None:
    """反向拓扑遍历，在延迟约束下算ALAP。latency_constraint必须为正整数"""
    if not isinstance(latency_constraint, int) or latency_constraint <= 0:
        raise ValueError(f"latency_constraint must be a positive integer, got {latency_constraint!r}")

    nodes = dfg_to_nodes_dict(dfg)

    for node_id in reversed(list(nx.topological_sort(dfg))):
        node = nodes[node_id]
        succs = list(dfg.successors(node_id))
        if not succs:
            # Sinks: start as late as possible while still finishing in time
            node.alap = latency_constraint - node.delay
        else:
            min_succ_start = float('inf')
            for succ_id in succs:
                succ = nodes[succ_id]
                if succ.alap is None:
                    raise RuntimeError(f"ALAP of successor {succ_id} not computed before {node_id}")
                # Node must finish before successor starts
                latest_finish = succ.alap
                if latest_finish < min_succ_start:
                    min_succ_start = latest_finish
            node.alap = min_succ_start - node.delay


def compute_mobility(dfg: nx.DiGraph) -> None:
    """Mobility = ALAP - ASAP，mobility为0的节点在关键路径上"""
    nodes = dfg_to_nodes_dict(dfg)
    for node in nodes.values():
        node.compute_mobility()


def extract_critical_path(dfg: nx.DiGraph) -> List[str]:
    """
    提取一条关键路径。用networkx的dag_longest_path算带权最长路径，
    如果失败就回退到按mobility=0的节点手动拼一条出来。
    """
    nodes = dfg_to_nodes_dict(dfg)

    # 建一个带权DAG，边权 = 终点节点的delay
    weighted_dfg = nx.DiGraph()
    for nid in dfg.nodes():
        weighted_dfg.add_node(nid)
    for u, v in dfg.edges():
        node_v = nodes.get(v)
        weight = node_v.delay if node_v else 0
        weighted_dfg.add_edge(u, v, weight=weight)

    try:
        path = nx.dag_longest_path(weighted_dfg, weight='weight')
        return path
    except nx.NetworkXUnfeasible:
        # 有环或其他问题，fallback
        return []
    except Exception:
        # 兼容fallback：按mobility找
        cp_nodes = set(nid for nid in nodes if nodes[nid].mobility == 0)
        if not cp_nodes:
            return []
        start_nodes = [nid for nid in cp_nodes
                       if not any(pred in cp_nodes for pred in dfg.predecessors(nid))]
        if not start_nodes:
            start_nodes = [next(iter(cp_nodes))]
        cp_path = []
        visited = set()
        current = start_nodes[0]
        while current is not None:
            cp_path.append(current)
            visited.add(current)
            next_candidates = [succ for succ in dfg.successors(current)
                               if succ in cp_nodes and succ not in visited]
            if not next_candidates:
                break
            current = max(next_candidates, key=lambda nid: nodes[nid].asap)
        return cp_path


def run_static_timing_analysis(dfg: nx.DiGraph, latency_constraint: Optional[int] = None) -> int:
    """跑一遍完整的静态时序分析：ASAP → ALAP → Mobility。返回关键路径长度"""
    critical_path = compute_asap(dfg)
    constraint = latency_constraint if latency_constraint is not None else critical_path
    compute_alap(dfg, constraint)
    compute_mobility(dfg)
    return critical_path
