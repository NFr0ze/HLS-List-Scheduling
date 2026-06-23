"""Generate test datasets for EDA HLS List Scheduling project."""
import random
import json
import os
import sys

# Determine project root relative to this file
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

from src.dfg_parser import save_dfg, generate_random_dag
from src.node import Node
import networkx as nx

base_dir = script_dir

# ========================
# Small Scale: simple_expr (9 nodes)
# ========================
dfg = nx.DiGraph()
nodes = [
    Node("n0", "ADD", 1, ["in0", "in1"]),
    Node("n1", "MUL", 2, ["in2", "in3"]),
    Node("n2", "ADD", 1, ["n0", "in4"]),
    Node("n3", "SUB", 1, ["in5", "n1"]),
    Node("n4", "MUL", 2, ["n2", "n3"]),
    Node("n5", "ADD", 1, ["n4", "in6"]),
    Node("n6", "DIV", 3, ["n5", "in7"]),
    Node("n7", "SUB", 1, ["n6", "in8"]),
    Node("n8", "MUL", 2, ["n7", "in9"]),
]
for n in nodes:
    dfg.add_node(n.node_id, node=n)
    for pred in n.predecessors:
        dfg.add_edge(pred, n.node_id)

save_dfg(dfg, {"ADD": 2, "MUL": 2, "SUB": 1, "DIV": 1}, os.path.join(base_dir, "small", "simple_expr.json"))

# ========================
# Small Scale: basic_dag (12 nodes)
# ========================
dfg = nx.DiGraph()
nodes = [
    Node("n0", "ADD", 1, ["in0", "in1"]),
    Node("n1", "MUL", 2, ["in2", "in3"]),
    Node("n2", "ADD", 1, ["n0", "in4"]),
    Node("n3", "MUL", 2, ["n1", "in5"]),
    Node("n4", "SUB", 1, ["n2", "n3"]),
    Node("n5", "ADD", 1, ["n4", "in6"]),
    Node("n6", "MUL", 2, ["n5", "in7"]),
    Node("n7", "ADD", 1, ["n6", "in8"]),
    Node("n8", "DIV", 3, ["n7", "in9"]),
    Node("n9", "SUB", 1, ["n8", "in10"]),
    Node("n10", "ADD", 1, ["n9", "in11"]),
    Node("n11", "MUL", 2, ["n10", "in12"]),
]
for n in nodes:
    dfg.add_node(n.node_id, node=n)
    for pred in n.predecessors:
        dfg.add_edge(pred, n.node_id)

save_dfg(dfg, {"ADD": 2, "MUL": 2, "SUB": 1, "DIV": 1}, os.path.join(base_dir, "small", "basic_dag.json"))

# ========================
# Medium Scale: fir_filter (48 nodes, 8-tap FIR with pipelined structure)
# y = sum(b[i] * x[n-i]) for i=0..7
# ========================
dfg = nx.DiGraph()
nodes = []
# 8 multiplications: m0..m7
for i in range(8):
    nodes.append(Node(f"m{i}", "MUL", 2, [f"b{i}", f"x{i}"]))
# 7 additions: a0 = m0+m1, a1 = a0+m2, ...
nodes.append(Node("a0", "ADD", 1, ["m0", "m1"]))
for i in range(1, 7):
    nodes.append(Node(f"a{i}", "ADD", 1, [f"a{i-1}", f"m{i+1}"]))
# Additional operations to reach ~48 nodes
# Add some scaling and shifting operations
for i in range(16):
    op = "ADD" if i % 3 != 0 else "MUL"
    deps = []
    if i < 7:
        deps = [f"a{i}"]
    elif i < 14:
        deps = [f"aux{i-7}"]
    else:
        deps = [f"aux{i-8}", f"aux{i-13}"]
    if len(deps) == 1:
        deps.append(f"const{i}")
    nodes.append(Node(f"aux{i}", op, 1 if op == "ADD" else 2, deps))
# Final output accumulation
nodes.append(Node("out", "ADD", 1, ["a6", "aux15"]))

for n in nodes:
    dfg.add_node(n.node_id, node=n)
    for pred in n.predecessors:
        if pred.startswith("in") or pred.startswith("b") or pred.startswith("x") or pred.startswith("const"):
            # Inputs are implicit, still add edges for graph consistency
            if pred not in dfg:
                dfg.add_node(pred, node=Node(pred, "INPUT", 0))
        dfg.add_edge(pred, n.node_id)

save_dfg(dfg, {"ADD": 4, "MUL": 3}, os.path.join(base_dir, "medium", "fir_filter.json"))

# ========================
# Medium Scale: diffeq_solver (45 nodes)
# Differential equation solver benchmark (Diffeq)
# ========================
dfg = nx.DiGraph()
nodes = []
# Build a more complex DAG manually
ops = []
# Level 1
ops.extend([("n0", "MUL", ["in0", "in1"]), ("n1", "MUL", ["in2", "in3"]), ("n2", "ADD", ["in4", "in5"])])
# Level 2
ops.extend([("n3", "SUB", ["n0", "n1"]), ("n4", "MUL", ["n2", "in6"]), ("n5", "ADD", ["n0", "in7"])])
# Level 3
ops.extend([("n6", "MUL", ["n3", "n4"]), ("n7", "ADD", ["n4", "n5"]), ("n8", "SUB", ["n5", "in8"])])
# Level 4
ops.extend([("n9", "ADD", ["n6", "n7"]), ("n10", "MUL", ["n7", "n8"])])
# Level 5
ops.extend([("n11", "SUB", ["n9", "n10"])])
# Expand to ~45 nodes by adding parallel branches
idx = 12
for level in range(6, 16):
    for branch in range(3):
        op_type = "ADD" if (level + branch) % 3 != 0 else "MUL"
        delay = 2 if op_type == "MUL" else 1
        # Pick 1-2 random predecessors from previous level
        preds = [f"n{random.choice(range(idx - 6, idx))}" for _ in range(random.choice([1, 2]))]
        preds = list(set(preds))
        ops.append((f"n{idx}", op_type, preds))
        idx += 1

for nid, op_type, deps in ops:
    nodes.append(Node(nid, op_type, 2 if op_type == "MUL" else 1, deps))

for n in nodes:
    dfg.add_node(n.node_id, node=n)
    for pred in n.predecessors:
        if pred not in dfg:
            dfg.add_node(pred, node=Node(pred, "INPUT", 0))
        dfg.add_edge(pred, n.node_id)

save_dfg(dfg, {"ADD": 4, "MUL": 2, "SUB": 2}, os.path.join(base_dir, "medium", "diffeq_solver.json"))

# ========================
# Large Scale: Random DAGs (200 and 300 nodes)
# ========================
import random
random.seed(42)
dfg200, res200 = generate_random_dag(200, edge_prob=0.15, seed=42)
save_dfg(dfg200, res200, os.path.join(base_dir, "large", "random_dag_200.json"))

dfg300, res300 = generate_random_dag(300, edge_prob=0.12, seed=123)
save_dfg(dfg300, res300, os.path.join(base_dir, "large", "random_dag_300.json"))

print("All datasets generated successfully!")
print(f"  Small:  simple_expr ({len([n for n in dfg.nodes() if not n.startswith('in')])} ops), basic_dag")
print(f"  Medium: fir_filter, diffeq_solver")
print(f"  Large:  random_dag_200, random_dag_300")
