# test_extended.py - 扩展单元测试
# 覆盖边界检查、资源池、可视化冒烟测试、集成测试等
# 陈润锴 23362012

import unittest
import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import networkx as nx
from src.node import Node
from src.dfg_parser import parse_dfg, generate_random_dag, save_dfg
from src.asap_alap import compute_asap, compute_alap, compute_mobility, extract_critical_path
from src.list_scheduler import (
    ListScheduler, ResourcePool, PipelinedResourcePool,
    default_priority, cp_first_priority, ldf_priority, random_priority, make_random_priority
)
from src.metrics import schedule_summary, overall_utilization
from src.binding import BindingEngine, BoundUnit
from src.visualizer import (
    plot_gantt_chart, plot_utilization_curve, plot_strategy_comparison,
    plot_sensitivity_analysis, export_schedule_table, plot_pareto_frontier,
    plot_dfg_topology, plot_pipeline_analysis
)


class TestNodeValidation(unittest.TestCase):

    def test_empty_node_id_raises(self):
        with self.assertRaises(ValueError):
            Node("", "ADD", 1)

    def test_invalid_op_type_raises(self):
        with self.assertRaises(ValueError):
            Node("n0", "", 1)

    def test_negative_delay_raises(self):
        with self.assertRaises(ValueError):
            Node("n0", "ADD", -1)

    def test_non_integer_delay_raises(self):
        with self.assertRaises(ValueError):
            Node("n0", "ADD", 1.5)

    def test_valid_node_creation(self):
        n = Node("n0", "add", 2, ["in0"])
        self.assertEqual(n.node_id, "n0")
        self.assertEqual(n.op_type, "ADD")
        self.assertEqual(n.delay, 2)

    def test_is_ready(self):
        n = Node("n1", "ADD", 1, ["n0"])
        self.assertTrue(n.is_ready({"n0"}))
        self.assertFalse(n.is_ready(set()))

    def test_reset_schedule(self):
        n = Node("n0", "ADD", 1)
        n.start_time = 5
        n.finish_time = 6
        n.resource_id = 0
        n.reset_schedule()
        self.assertIsNone(n.start_time)
        self.assertIsNone(n.finish_time)
        self.assertIsNone(n.resource_id)


class TestResourcePool(unittest.TestCase):

    def test_allocate_and_availability(self):
        pool = ResourcePool({"ADD": 2})
        self.assertTrue(pool.is_available("ADD", 0))
        idx = pool.allocate("ADD", 0, 2)
        self.assertEqual(idx, 0)
        # 2个资源，分配1个后还剩1个
        self.assertTrue(pool.is_available("ADD", 0))
        idx2 = pool.allocate("ADD", 0, 2)
        self.assertEqual(idx2, 1)
        # 2个都分了，没了
        self.assertFalse(pool.is_available("ADD", 0))
        self.assertTrue(pool.is_available("ADD", 2))

    def test_multiple_resources(self):
        pool = ResourcePool({"ADD": 2})
        idx1 = pool.allocate("ADD", 0, 1)
        idx2 = pool.allocate("ADD", 0, 1)
        self.assertNotEqual(idx1, idx2)
        with self.assertRaises(RuntimeError):
            pool.allocate("ADD", 0, 1)

    def test_utilization_at_cycle(self):
        pool = ResourcePool({"ADD": 2})
        pool.allocate("ADD", 0, 3)
        self.assertEqual(pool.get_utilization_at_cycle("ADD", 0), 1)
        self.assertEqual(pool.get_utilization_at_cycle("ADD", 2), 1)
        self.assertEqual(pool.get_utilization_at_cycle("ADD", 3), 0)

    def test_reset(self):
        pool = ResourcePool({"ADD": 1})
        pool.allocate("ADD", 0, 5)
        pool.reset()
        self.assertTrue(pool.is_available("ADD", 0))

    def test_unknown_op_type(self):
        pool = ResourcePool({"ADD": 1})
        self.assertFalse(pool.is_available("MUL", 0))
        with self.assertRaises(RuntimeError):
            pool.allocate("MUL", 0, 1)


class TestPipelinedResourcePool(unittest.TestCase):

    def test_basic_allocation(self):
        pool = PipelinedResourcePool({"ADD": 1}, ii=2)
        self.assertTrue(pool.is_available("ADD", 0, 1))
        pool.allocate("ADD", 0, 1)
        self.assertFalse(pool.is_available("ADD", 0, 1))
        self.assertFalse(pool.is_available("ADD", 2, 1))  # 同phase

    def test_multicycle_affected_phases(self):
        pool = PipelinedResourcePool({"ADD": 1}, ii=3)
        # 操作[0,2)影响phase 0和1
        phases = pool._affected_phases(0, 2)
        self.assertEqual(sorted(phases), [0, 1])

    def test_different_phases_available(self):
        pool = PipelinedResourcePool({"ADD": 1}, ii=3)
        pool.allocate("ADD", 0, 1)  # 占用phase 0
        self.assertFalse(pool.is_available("ADD", 3, 1))  # 又是phase 0
        self.assertTrue(pool.is_available("ADD", 1, 1))   # phase 1空闲

    def test_ii_one_fallback(self):
        pool = PipelinedResourcePool({"ADD": 2}, ii=1)
        self.assertTrue(pool.is_available("ADD", 0, 1))
        pool.allocate("ADD", 0, 1)
        self.assertTrue(pool.is_available("ADD", 0, 1))  # 还剩1个
        pool.allocate("ADD", 0, 1)
        self.assertFalse(pool.is_available("ADD", 0, 1))


class TestPriorityFunctions(unittest.TestCase):

    def test_default_priority(self):
        n = Node("n0", "ADD", 1)
        n.mobility = 2
        n.asap = 1
        self.assertEqual(default_priority(n), (2, 1))

    def test_default_priority_none_mobility(self):
        n = Node("n0", "ADD", 1)
        self.assertEqual(default_priority(n), (float('inf'), float('inf')))

    def test_cp_first_priority(self):
        n = Node("n0", "ADD", 2)
        n.mobility = 0
        n.asap = 1
        self.assertEqual(cp_first_priority(n), (0, -2, 1))

    def test_cp_first_priority_off_cp(self):
        n = Node("n0", "ADD", 2)
        n.mobility = 1
        n.asap = 1
        self.assertEqual(cp_first_priority(n), (1, -2, 1))

    def test_ldf_priority(self):
        n = Node("n0", "ADD", 3)
        n.mobility = 1
        n.asap = 0
        self.assertEqual(ldf_priority(n), (-3, 1, 0))

    def test_random_priority_range(self):
        n = Node("n0", "ADD", 1)
        val = random_priority(n)
        self.assertTrue(0.0 <= val <= 1.0)

    def test_make_random_priority_reproducible(self):
        n1 = Node("n0", "ADD", 1)
        n2 = Node("n1", "ADD", 1)
        fn = make_random_priority(seed=42)
        v1 = fn(n1)
        v2 = fn(n2)
        self.assertNotEqual(v1, v2)  # 每次调用不同
        # 但序列可复现
        fn2 = make_random_priority(seed=42)
        self.assertEqual(v1, fn2(n1))
        self.assertEqual(v2, fn2(n2))


class TestVisualizerSmoke(unittest.TestCase):
    """Smoke tests for visualizer functions."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_simple_dfg(self):
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        n1 = Node("n1", "MUL", 2, ["n0"])
        n2 = Node("n2", "ADD", 1, ["n1"])
        for n in [n0, n1, n2]:
            dfg.add_node(n.node_id, node=n)
        dfg.add_edge("n0", "n1")
        dfg.add_edge("n1", "n2")
        return dfg, {"ADD": 2, "MUL": 1}

    def test_plot_gantt_chart(self):
        dfg, resources = self._create_simple_dfg()
        scheduler = ListScheduler(dfg, resources)
        scheduler.schedule()
        path = os.path.join(self.temp_dir, "gantt.png")
        fig = plot_gantt_chart(scheduler.nodes, resources, output_path=path)
        self.assertIsNotNone(fig)
        self.assertTrue(os.path.exists(path))

    def test_plot_utilization_curve(self):
        dfg, resources = self._create_simple_dfg()
        scheduler = ListScheduler(dfg, resources)
        scheduler.schedule()
        summary = schedule_summary(scheduler)
        path = os.path.join(self.temp_dir, "util.png")
        fig = plot_utilization_curve(summary["cycle_usage"], resources, output_path=path)
        self.assertIsNotNone(fig)
        self.assertTrue(os.path.exists(path))

    def test_plot_utilization_empty(self):
        path = os.path.join(self.temp_dir, "util_empty.png")
        fig = plot_utilization_curve({}, {"ADD": 1}, output_path=path)
        self.assertIsNotNone(fig)

    def test_export_schedule_table(self):
        dfg, resources = self._create_simple_dfg()
        scheduler = ListScheduler(dfg, resources)
        scheduler.schedule()
        path = os.path.join(self.temp_dir, "schedule.txt")
        table = export_schedule_table(scheduler.nodes, output_path=path)
        self.assertIn("n0", table)
        self.assertTrue(os.path.exists(path))

    def test_plot_strategy_comparison(self):
        results = {
            "A": {"total_latency": 10, "overall_utilization": 0.5, "latency_std": 0},
            "B": {"total_latency": 12, "overall_utilization": 0.6, "latency_std": 1.0},
        }
        path = os.path.join(self.temp_dir, "comparison.png")
        fig = plot_strategy_comparison(results, output_path=path)
        self.assertIsNotNone(fig)
        self.assertTrue(os.path.exists(path))

    def test_plot_sensitivity_analysis(self):
        path = os.path.join(self.temp_dir, "sensitivity.png")
        fig = plot_sensitivity_analysis(["C1", "C2"], [10, 8], output_path=path)
        self.assertIsNotNone(fig)
        self.assertTrue(os.path.exists(path))

    def test_plot_pareto_frontier(self):
        points = [(10, 500, "A"), (8, 600, "B"), (12, 400, "C")]
        pareto = [(10, 500, "A"), (12, 400, "C")]
        path = os.path.join(self.temp_dir, "pareto.png")
        fig = plot_pareto_frontier(points, pareto, output_path=path)
        self.assertIsNotNone(fig)
        self.assertTrue(os.path.exists(path))

    def test_plot_dfg_topology(self):
        dfg, _ = self._create_simple_dfg()
        path = os.path.join(self.temp_dir, "topology.png")
        fig = plot_dfg_topology(dfg, output_path=path)
        self.assertIsNotNone(fig)
        self.assertTrue(os.path.exists(path))

    def test_plot_pipeline_analysis(self):
        results = [
            {"ii": 1, "throughput": 0.5, "latency": 10, "feasible": True},
            {"ii": 2, "throughput": 0.3, "latency": 10, "feasible": True},
            {"ii": 3, "throughput": None, "latency": None, "feasible": False},
        ]
        path = os.path.join(self.temp_dir, "pipeline.png")
        fig = plot_pipeline_analysis(results, baseline_latency=10, output_path=path)
        self.assertIsNotNone(fig)
        self.assertTrue(os.path.exists(path))


class TestBindingEdgeCases(unittest.TestCase):

    def test_boundunit_is_compatible(self):
        unit = BoundUnit("ADD_0", "ADD")
        self.assertTrue(unit.is_compatible(0, 1))
        unit.bind_node("n0", 0, 1)
        self.assertFalse(unit.is_compatible(0, 2))  # 重叠
        self.assertTrue(unit.is_compatible(1, 2))   # 不重叠

    def test_boundunit_exact_overlap(self):
        unit = BoundUnit("ADD_0", "ADD")
        unit.bind_node("n0", 0, 2)
        self.assertFalse(unit.is_compatible(0, 2))
        self.assertFalse(unit.is_compatible(1, 3))

    def test_binding_with_multiple_types(self):
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
        binder = BindingEngine(scheduler.nodes)
        binder.bind()
        summary = binder.get_binding_summary()
        self.assertIn("ADD", summary["actual_resources"])
        self.assertIn("MUL", summary["actual_resources"])


class TestIntegration(unittest.TestCase):

    def test_full_pipeline(self):
        # 端到端：解析 -> ASAP/ALAP -> 调度 -> 绑定 -> 指标 -> 验证
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        n1 = Node("n1", "MUL", 2, ["n0"])
        n2 = Node("n2", "ADD", 1, ["n1"])
        for n in [n0, n1, n2]:
            dfg.add_node(n.node_id, node=n)
        dfg.add_edge("n0", "n1")
        dfg.add_edge("n1", "n2")

        resources = {"ADD": 2, "MUL": 1}

        # ASAP/ALAP
        cp = compute_asap(dfg)
        compute_alap(dfg, cp)
        compute_mobility(dfg)

        # 调度
        scheduler = ListScheduler(dfg, resources)
        scheduler.schedule()
        self.assertTrue(scheduler.verify_schedule())

        # 指标
        summary = schedule_summary(scheduler)
        self.assertGreater(summary["total_latency"], 0)
        self.assertGreater(summary["overall_utilization"], 0)

        # 绑定
        binder = BindingEngine(scheduler.nodes)
        binder.bind()
        bind_summary = binder.get_binding_summary()
        self.assertGreater(bind_summary["total_units"], 0)

    def test_single_node_dfg(self):
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        dfg.add_node("n0", node=n0)
        scheduler = ListScheduler(dfg, {"ADD": 1})
        scheduler.schedule()
        self.assertTrue(scheduler.verify_schedule())
        self.assertEqual(scheduler.get_total_latency(), 1)

    def test_parallel_branches(self):
        # 并行分支，2个ADD可以并行
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        n1 = Node("n1", "ADD", 1, ["n0"])
        n2 = Node("n2", "ADD", 1, ["n0"])
        n3 = Node("n3", "ADD", 1, ["n1", "n2"])
        for n in [n0, n1, n2, n3]:
            dfg.add_node(n.node_id, node=n)
        dfg.add_edges_from([("n0", "n1"), ("n0", "n2"), ("n1", "n3"), ("n2", "n3")])

        scheduler = ListScheduler(dfg, {"ADD": 2})
        scheduler.schedule()
        self.assertTrue(scheduler.verify_schedule())
        # 2个ADD并行时latency应为3
        self.assertEqual(scheduler.get_total_latency(), 3)

    def test_overall_utilization(self):
        n0 = Node("n0", "ADD", 1)
        n0.start_time = 0
        n0.finish_time = 1
        n1 = Node("n1", "MUL", 2)
        n1.start_time = 1
        n1.finish_time = 3
        nodes = {"n0": n0, "n1": n1}
        util = overall_utilization(nodes, {"ADD": 1, "MUL": 1}, 3)
        # ADD: 1 / (3*1) = 1/3
        # MUL: 2 / (3*1) = 2/3
        # 总: 3/6 = 0.5
        self.assertAlmostEqual(util, 0.5)

    def test_save_and_parse_roundtrip(self):
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        n1 = Node("n1", "MUL", 2, ["n0"])
        for n in [n0, n1]:
            dfg.add_node(n.node_id, node=n)
        dfg.add_edge("n0", "n1")

        resources = {"ADD": 1, "MUL": 1}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            path = f.name

        try:
            save_dfg(dfg, resources, path)
            dfg2, res2 = parse_dfg(path)
            self.assertEqual(len(dfg2), 2)
            self.assertEqual(res2["ADD"], 1)
            self.assertEqual(res2["MUL"], 1)
        finally:
            os.unlink(path)


class TestSchedulerWithCustomPriority(unittest.TestCase):

    def _create_diamond_dfg(self):
        dfg = nx.DiGraph()
        n0 = Node("n0", "ADD", 1)
        n1 = Node("n1", "MUL", 2, ["n0"])
        n2 = Node("n2", "ADD", 1, ["n0"])
        n3 = Node("n3", "ADD", 1, ["n1", "n2"])
        for n in [n0, n1, n2, n3]:
            dfg.add_node(n.node_id, node=n)
        dfg.add_edges_from([("n0", "n1"), ("n0", "n2"), ("n1", "n3"), ("n2", "n3")])
        return dfg

    def test_cp_first_strategy(self):
        dfg = self._create_diamond_dfg()
        scheduler = ListScheduler(dfg, {"ADD": 2, "MUL": 1}, priority_fn=cp_first_priority)
        scheduler.schedule()
        self.assertTrue(scheduler.verify_schedule())

    def test_ldf_strategy(self):
        dfg = self._create_diamond_dfg()
        scheduler = ListScheduler(dfg, {"ADD": 2, "MUL": 1}, priority_fn=ldf_priority)
        scheduler.schedule()
        self.assertTrue(scheduler.verify_schedule())

    def test_random_strategy(self):
        dfg = self._create_diamond_dfg()
        rand_fn = make_random_priority(seed=123)
        scheduler = ListScheduler(dfg, {"ADD": 2, "MUL": 1}, priority_fn=rand_fn)
        scheduler.schedule()
        self.assertTrue(scheduler.verify_schedule())


if __name__ == "__main__":
    unittest.main()
