# test_core.py - 核心算法单元测试
# 覆盖ASAP/ALAP、List Scheduling、Metrics、DFG解析、Binding、流水线调度
# 陈润锴 23362012

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import networkx as nx
from src.node import Node
from src.dfg_parser import parse_dfg, generate_random_dag
from src.asap_alap import compute_asap, compute_alap, compute_mobility, extract_critical_path
from src.list_scheduler import ListScheduler, default_priority, PipelinedListScheduler
from src.metrics import total_latency, resource_utilization, throughput, schedule_summary
from src.binding import BindingEngine


class TestASAPALAP(unittest.TestCase):

    def test_simple_chain(self):
        # 简单3节点链验证ASAP/ALAP
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        n1 = Node("n1", "MUL", 2, ["n0"])
        n2 = Node("n2", "ADD", 1, ["n1"])
        for n in [n0, n1, n2]:
            dfg.add_node(n.node_id, node=n)
        dfg.add_edge("n0", "n1")
        dfg.add_edge("n1", "n2")

        cp = compute_asap(dfg)
        self.assertEqual(cp, 4)  # 1 + 2 + 1
        self.assertEqual(n0.asap, 0)
        self.assertEqual(n1.asap, 1)
        self.assertEqual(n2.asap, 3)

        compute_alap(dfg, cp)
        self.assertEqual(n0.alap, 0)
        self.assertEqual(n1.alap, 1)
        self.assertEqual(n2.alap, 3)

        compute_mobility(dfg)
        self.assertEqual(n0.mobility, 0)
        self.assertEqual(n1.mobility, 0)
        self.assertEqual(n2.mobility, 0)

    def test_parallel_branches(self):
        # 并行分支DAG
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        n1 = Node("n1", "MUL", 2, ["n0"])
        n2 = Node("n2", "ADD", 1, ["n0"])
        n3 = Node("n3", "ADD", 1, ["n1", "n2"])
        for n in [n0, n1, n2, n3]:
            dfg.add_node(n.node_id, node=n)
        dfg.add_edges_from([("n0", "n1"), ("n0", "n2"), ("n1", "n3"), ("n2", "n3")])

        cp = compute_asap(dfg)
        self.assertEqual(cp, 4)
        self.assertEqual(n0.asap, 0)
        self.assertEqual(n1.asap, 1)
        self.assertEqual(n2.asap, 1)
        self.assertEqual(n3.asap, 3)

        compute_alap(dfg, cp)
        compute_mobility(dfg)
        self.assertEqual(n0.mobility, 0)
        self.assertEqual(n1.mobility, 0)
        self.assertEqual(n3.mobility, 0)
        # n2可以推迟1个周期
        self.assertEqual(n2.mobility, 1)

    def test_critical_path_extraction(self):
        # 提取关键路径
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        n1 = Node("n1", "MUL", 2, ["n0"])
        n2 = Node("n2", "ADD", 1, ["n0"])
        n3 = Node("n3", "ADD", 1, ["n1", "n2"])
        for n in [n0, n1, n2, n3]:
            dfg.add_node(n.node_id, node=n)
        dfg.add_edges_from([("n0", "n1"), ("n0", "n2"), ("n1", "n3"), ("n2", "n3")])

        compute_asap(dfg)
        compute_alap(dfg, 4)
        compute_mobility(dfg)
        cp = extract_critical_path(dfg)
        self.assertIn("n0", cp)
        self.assertIn("n1", cp)
        self.assertIn("n3", cp)


class TestListScheduler(unittest.TestCase):

    def test_simple_chain_schedule(self):
        # 简单链式调度，资源充足
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        n1 = Node("n1", "MUL", 2, ["n0"])
        n2 = Node("n2", "ADD", 1, ["n1"])
        for n in [n0, n1, n2]:
            dfg.add_node(n.node_id, node=n)
        dfg.add_edge("n0", "n1")
        dfg.add_edge("n1", "n2")

        scheduler = ListScheduler(dfg, {"ADD": 2, "MUL": 1})
        scheduler.schedule()
        self.assertTrue(scheduler.verify_schedule())
        self.assertEqual(scheduler.get_total_latency(), 4)

    def test_resource_constrained(self):
        # 资源紧张，只有1个ADD
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        n1 = Node("n1", "ADD", 1, ["n0"])
        n2 = Node("n2", "ADD", 1, ["n0"])
        n3 = Node("n3", "ADD", 1, ["n1", "n2"])
        for n in [n0, n1, n2, n3]:
            dfg.add_node(n.node_id, node=n)
        dfg.add_edges_from([("n0", "n1"), ("n0", "n2"), ("n1", "n3"), ("n2", "n3")])

        scheduler = ListScheduler(dfg, {"ADD": 1})
        scheduler.schedule()
        self.assertTrue(scheduler.verify_schedule())
        # 1个ADD时n1和n2必须串行，latency=4
        self.assertEqual(scheduler.get_total_latency(), 4)

    def test_empty_resources_raises(self):
        # 空资源限制应报错
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        dfg.add_node("n0", node=n0)
        with self.assertRaises(ValueError):
            ListScheduler(dfg, {})

    def test_zero_resource_limit_raises(self):
        # 负资源限制应报错
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        dfg.add_node("n0", node=n0)
        with self.assertRaises(ValueError):
            ListScheduler(dfg, {"ADD": -1})


class TestMetrics(unittest.TestCase):

    def test_total_latency(self):
        # latency = 最大完成时间
        n0 = Node("n0", "ADD", 1)
        n0.start_time = 0
        n0.finish_time = 1
        n1 = Node("n1", "MUL", 2)
        n1.start_time = 1
        n1.finish_time = 3
        nodes = {"n0": n0, "n1": n1}
        self.assertEqual(total_latency(nodes), 3)

    def test_total_latency_empty(self):
        self.assertEqual(total_latency({}), 0)

    def test_utilization(self):
        # 2个ADD各跑1周期，总可用 = 3周期 * 2单元 = 6
        n0 = Node("n0", "ADD", 1)
        n0.start_time = 0
        n0.finish_time = 1
        n1 = Node("n1", "ADD", 1)
        n1.start_time = 1
        n1.finish_time = 2
        nodes = {"n0": n0, "n1": n1}
        util = resource_utilization(nodes, {"ADD": 2}, 3)
        self.assertAlmostEqual(util["ADD"], 2 / 6)

    def test_throughput(self):
        n0 = Node("n0", "ADD", 1)
        nodes = {"n0": n0}
        self.assertEqual(throughput(nodes, 5), 0.2)
        self.assertEqual(throughput(nodes, 0), 0.0)


class TestDFGParser(unittest.TestCase):

    def test_parse_valid_dfg(self):
        import tempfile
        import json

        data = {
            "nodes": [
                {"id": "n0", "type": "ADD", "delay": 1, "deps": []},
                {"id": "n1", "type": "MUL", "delay": 2, "deps": ["n0"]},
            ],
            "resources": {"ADD": 1, "MUL": 1}
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(data, f)
            path = f.name

        try:
            dfg, resources = parse_dfg(path)
            self.assertEqual(len(dfg), 2)
            self.assertEqual(resources["ADD"], 1)
        finally:
            os.unlink(path)

    def test_parse_empty_nodes_raises(self):
        import tempfile
        import json

        data = {"nodes": [], "resources": {"ADD": 1}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(data, f)
            path = f.name

        try:
            with self.assertRaises(ValueError):
                parse_dfg(path)
        finally:
            os.unlink(path)

    def test_generate_random_dag(self):
        dfg, resources = generate_random_dag(50, edge_prob=0.2, seed=123)
        self.assertEqual(len(dfg), 50)
        self.assertTrue(nx.is_directed_acyclic_graph(dfg))
        self.assertGreater(len(resources), 0)

    def test_generate_random_dag_zero_nodes_raises(self):
        with self.assertRaises(ValueError):
            generate_random_dag(0)


class TestBinding(unittest.TestCase):

    def test_simple_binding(self):
        # 3个ADD串行，可以共享1个单元
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        n1 = Node("n1", "ADD", 1, ["n0"])
        n2 = Node("n2", "ADD", 1, ["n1"])
        for n in [n0, n1, n2]:
            dfg.add_node(n.node_id, node=n)
        dfg.add_edges_from([("n0", "n1"), ("n1", "n2")])

        scheduler = ListScheduler(dfg, {"ADD": 1})
        scheduler.schedule()

        binder = BindingEngine(scheduler.nodes)
        binder.bind()
        summary = binder.get_binding_summary()

        # 3个ADD不重叠，可以共用1个单元
        self.assertEqual(summary["total_units"], 1)
        self.assertEqual(summary["functional_area"], 100)
        self.assertEqual(summary["mux_area"], 60)  # (3-1)*30
        self.assertEqual(summary["total_area_estimate"], 160)

    def test_binding_no_sharing(self):
        # 3个ADD全部重叠，不能共享
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        n1 = Node("n1", "ADD", 1)
        n2 = Node("n2", "ADD", 1)
        for n in [n0, n1, n2]:
            dfg.add_node(n.node_id, node=n)

        # 手动设置调度时间，全部重叠
        n0.start_time = 0
        n0.finish_time = 1
        n1.start_time = 0
        n1.finish_time = 1
        n2.start_time = 0
        n2.finish_time = 1

        binder = BindingEngine({"n0": n0, "n1": n1, "n2": n2})
        binder.bind()
        summary = binder.get_binding_summary()

        # 全部重叠，需要3个独立单元
        self.assertEqual(summary["total_units"], 3)
        self.assertEqual(summary["mux_area"], 0)  # 无共享，无MUX


class TestPipelinedScheduler(unittest.TestCase):

    def test_pipelined_simple_chain(self):
        # II=2的简单链应该可行
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        n1 = Node("n1", "MUL", 2, ["n0"])
        n2 = Node("n2", "ADD", 1, ["n1"])
        for n in [n0, n1, n2]:
            dfg.add_node(n.node_id, node=n)
        dfg.add_edge("n0", "n1")
        dfg.add_edge("n1", "n2")

        scheduler = PipelinedListScheduler(dfg, {"ADD": 2, "MUL": 1}, ii=2)
        scheduler.schedule()
        self.assertTrue(scheduler.verify_schedule())
        self.assertEqual(scheduler.get_total_latency(), 4)
        self.assertGreater(scheduler.get_effective_throughput(), 0)

    def test_pipelined_ii_one_fails_when_overloaded(self):
        # II=1但资源不够，应该失败
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        n1 = Node("n1", "ADD", 1, ["n0"])
        n2 = Node("n2", "ADD", 1, ["n0"])
        n3 = Node("n3", "ADD", 1, ["n1", "n2"])
        for n in [n0, n1, n2, n3]:
            dfg.add_node(n.node_id, node=n)
        dfg.add_edges_from([("n0", "n1"), ("n0", "n2"), ("n1", "n3"), ("n2", "n3")])

        # 1个ADD，II=1不可能，因为n1和n2在相邻迭代中会重叠
        with self.assertRaises(RuntimeError):
            scheduler = PipelinedListScheduler(dfg, {"ADD": 1}, ii=1)
            scheduler.schedule()

    def test_pipelined_large_ii_fallback(self):
        # II很大时，行为应接近普通调度
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        n1 = Node("n1", "MUL", 2, ["n0"])
        n2 = Node("n2", "ADD", 1, ["n1"])
        for n in [n0, n1, n2]:
            dfg.add_node(n.node_id, node=n)
        dfg.add_edge("n0", "n1")
        dfg.add_edge("n1", "n2")

        scheduler = PipelinedListScheduler(dfg, {"ADD": 2, "MUL": 1}, ii=10)
        scheduler.schedule()
        self.assertTrue(scheduler.verify_schedule())
        self.assertEqual(scheduler.get_total_latency(), 4)


if __name__ == "__main__":
    unittest.main()
