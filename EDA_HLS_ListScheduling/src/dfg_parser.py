# dfg_parser.py - DFG解析与随机生成
# 从JSON读取数据流图，或生成随机DAG用于大规模测试
# 陈润锴

import json
import random
from typing import Dict, List, Tuple, Optional
import networkx as nx

from .node import Node


# Default operation delays mapping
DEFAULT_OP_DELAYS = {
    "ADD": 1,
    "SUB": 1,
    "MUL": 2,
    "DIV": 3,
    "AND": 1,
    "OR": 1,
    "XOR": 1,
    "SHL": 1,
    "CMP": 1,
}


def parse_dfg(json_path: str) -> Tuple[nx.DiGraph, Dict[str, int]]:
    """从JSON文件解析DFG，返回(DiGraph, resource_limits)"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    nodes_data = data.get("nodes", [])
    resources = data.get("resources", {})

    if not nodes_data:
        raise ValueError(f"No nodes defined in {json_path}. DFG must contain at least one node.")
    if not resources:
        raise ValueError(f"No resource limits defined in {json_path}. Please provide 'resources' field.")

    dfg = nx.DiGraph()
    node_map: Dict[str, Node] = {}

    # 第一遍：创建所有节点
    for nd in nodes_data:
        node_id = nd["id"]
        op_type = nd.get("type", "ADD").upper()
        delay = nd.get("delay", DEFAULT_OP_DELAYS.get(op_type, 1))
        deps = nd.get("deps", [])

        node = Node(node_id=node_id, op_type=op_type, delay=delay, predecessors=deps)
        node_map[node_id] = node
        dfg.add_node(node_id, node=node)

    # 第二遍：加边并填充后继
    for nd in nodes_data:
        node_id = nd["id"]
        deps = nd.get("deps", [])
        for pred_id in deps:
            if pred_id not in node_map:
                # 未定义的前驱自动当成INPUT节点
                input_node = Node(node_id=pred_id, op_type="INPUT", delay=0)
                node_map[pred_id] = input_node
                dfg.add_node(pred_id, node=input_node)
            dfg.add_edge(pred_id, node_id)
            if node_id not in node_map[pred_id].successors:
                node_map[pred_id].successors.append(node_id)

    # 验证无环
    if not nx.is_directed_acyclic_graph(dfg):
        raise ValueError("The parsed graph contains cycles. DFG must be a DAG.")

    return dfg, resources


def dfg_to_nodes_dict(dfg: nx.DiGraph) -> Dict[str, Node]:
    """从DiGraph中提取 node_id -> Node 的映射"""
    return {nid: dfg.nodes[nid]["node"] for nid in dfg.nodes()}


def save_dfg(dfg: nx.DiGraph, resources: Dict[str, int], output_path: str) -> None:
    """把DFG和资源限制保存到JSON文件"""
    nodes_data = []
    for nid in nx.topological_sort(dfg):
        if "node" not in dfg.nodes[nid]:
            continue  # 跳过没有Node对象的占位节点
        node = dfg.nodes[nid]["node"]
        nodes_data.append({
            "id": node.node_id,
            "type": node.op_type,
            "delay": node.delay,
            "deps": node.predecessors,
        })

    data = {
        "nodes": nodes_data,
        "resources": resources,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def generate_random_dag(
    num_nodes: int,
    edge_prob: float = 0.3,
    op_types: Optional[List[str]] = None,
    seed: Optional[int] = None,
) -> Tuple[nx.DiGraph, Dict[str, int]]:
    """生成随机DAG用于测试。边从低index指向高index以保证无环。"""
    if num_nodes <= 0:
        raise ValueError(f"num_nodes must be positive, got {num_nodes}")
    if seed is not None:
        random.seed(seed)

    if op_types is None:
        op_types = ["ADD", "MUL"]

    dfg = nx.DiGraph()
    node_map: Dict[str, Node] = {}

    # 创建节点
    for i in range(num_nodes):
        node_id = f"n{i}"
        op_type = random.choice(op_types)
        # ADD出现概率比MUL高
        if len(op_types) == 2 and op_types == ["ADD", "MUL"]:
            op_type = random.choices(["ADD", "MUL"], weights=[3, 1])[0]
        delay = DEFAULT_OP_DELAYS.get(op_type, 1)
        node = Node(node_id=node_id, op_type=op_type, delay=delay)
        node_map[node_id] = node
        dfg.add_node(node_id, node=node)

    # 创建边（只允许从小编号指向大编号，确保DAG）
    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            if random.random() < edge_prob:
                src = f"n{i}"
                dst = f"n{j}"
                dfg.add_edge(src, dst)
                node_map[dst].predecessors.append(src)
                node_map[src].successors.append(dst)

    # 保证每个非源节点至少有一个前驱
    for i in range(1, num_nodes):
        node_id = f"n{i}"
        if not node_map[node_id].predecessors:
            # 连到一个随机的前面的节点
            pred_idx = random.randint(0, i - 1)
            pred_id = f"n{pred_idx}"
            if not dfg.has_edge(pred_id, node_id):
                dfg.add_edge(pred_id, node_id)
                node_map[node_id].predecessors.append(pred_id)
                node_map[pred_id].successors.append(node_id)

    # 多源节点在DAG里是合法的，不强制全连通，保留并行结构
    sources = [n for n in dfg.nodes() if dfg.in_degree(n) == 0]
    sinks = [n for n in dfg.nodes() if dfg.out_degree(n) == 0]
    if not sinks:
        # 至少保证有一个汇点
        pass

    # 资源限额：按节点数的1/4估算，最少1个，最多8个
    type_counts: Dict[str, int] = {}
    for nid in dfg.nodes():
        op = node_map[nid].op_type
        type_counts[op] = type_counts.get(op, 0) + 1

    resources = {}
    for op, count in type_counts.items():
        limit = max(1, count // 4)
        limit = min(limit, 8)
        resources[op] = limit

    return dfg, resources
