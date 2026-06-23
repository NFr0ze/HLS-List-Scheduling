# binding.py - 资源绑定模块
# 调度之后决定每个操作映射到哪个物理运算单元，支持共享与MUX开销估算
# 陈润锴

from typing import Dict, List, Tuple
from collections import defaultdict

from .node import Node


class BoundUnit:
    """绑定后的一个物理运算单元实例"""

    def __init__(self, unit_id: str, op_type: str):
        self.unit_id = unit_id
        self.op_type = op_type
        self.bound_nodes: List[str] = []
        self.schedule_intervals: List[Tuple[int, int]] = []

    def is_compatible(self, start_time: int, finish_time: int) -> bool:
        """检查新操作[start_time, finish_time)是否与当前单元已绑定的操作不重叠"""
        for s, f in self.schedule_intervals:
            # 有重叠除非新操作在旧操作开始前结束，或在旧操作开始后开始
            if not (finish_time <= s or start_time >= f):
                return False
        return True

    def bind_node(self, node_id: str, start_time: int, finish_time: int):
        """把节点绑定到这个单元上"""
        self.bound_nodes.append(node_id)
        self.schedule_intervals.append((start_time, finish_time))
        # 保持区间有序，看起来整齐点
        self.schedule_intervals.sort(key=lambda x: x[0])

    @property
    def mux_inputs(self) -> int:
        """MUX输入数 = 共享这个单元的不同操作数"""
        return len(self.bound_nodes)

    def __repr__(self) -> str:
        return f"BoundUnit({self.unit_id}, nodes={self.bound_nodes}, intervals={self.schedule_intervals})"


class BindingEngine:
    """资源绑定引擎，用贪心区间划分把调度结果映射到物理单元"""

    # 面积估算用的相对单位（随便定的，能比较就行）
    UNIT_AREA = {
        "ADD": 100,
        "SUB": 100,
        "MUL": 400,
        "DIV": 800,
        "AND": 50,
        "OR": 50,
        "XOR": 50,
        "SHL": 50,
        "CMP": 60,
    }
    MUX_AREA_PER_INPUT = 30  # 每个MUX输入的额外面积

    def __init__(self, scheduled_nodes: Dict[str, Node]):
        """scheduled_nodes: 已经调度好的节点字典"""
        self.scheduled_nodes = scheduled_nodes
        self.units: Dict[str, List[BoundUnit]] = defaultdict(list)
        self.node_to_unit: Dict[str, str] = {}

    def bind(self) -> Dict[str, List[BoundUnit]]:
        """执行贪心绑定，返回 op_type -> BoundUnit列表 的映射"""
        # 按操作类型分组
        type_groups: Dict[str, List[Node]] = defaultdict(list)
        for node in self.scheduled_nodes.values():
            if node.delay > 0:  # 跳过INPUT节点
                type_groups[node.op_type].append(node)

        # 每类按开始时间排序
        for op_type in type_groups:
            type_groups[op_type].sort(key=lambda n: (n.start_time or 0, n.node_id))

        # 贪心分配
        for op_type, nodes in type_groups.items():
            for node in nodes:
                assigned = False
                for unit in self.units[op_type]:
                    if unit.is_compatible(node.start_time, node.finish_time):
                        unit.bind_node(node.node_id, node.start_time, node.finish_time)
                        self.node_to_unit[node.node_id] = unit.unit_id
                        assigned = True
                        break
                if not assigned:
                    unit_id = f"{op_type}_{len(self.units[op_type])}"
                    new_unit = BoundUnit(unit_id, op_type)
                    new_unit.bind_node(node.node_id, node.start_time, node.finish_time)
                    self.units[op_type].append(new_unit)
                    self.node_to_unit[node.node_id] = unit_id

        return dict(self.units)

    def get_actual_resource_count(self) -> Dict[str, int]:
        """返回每类操作实际分配的物理单元数"""
        return {op_type: len(units) for op_type, units in self.units.items()}

    def get_mux_overhead(self) -> Dict[str, int]:
        """计算每类操作的MUX总输入数"""
        overhead = {}
        for op_type, units in self.units.items():
            total_inputs = sum(u.mux_inputs for u in units)
            overhead[op_type] = total_inputs
        return overhead

    def get_binding_summary(self) -> Dict:
        """生成绑定的汇总信息，包括面积估算"""
        actual_counts = self.get_actual_resource_count()
        mux_overhead = self.get_mux_overhead()

        total_area = 0
        total_mux_area = 0
        for op_type, units in self.units.items():
            unit_area = self.UNIT_AREA.get(op_type, 100)
            for u in units:
                total_area += unit_area
                if u.mux_inputs > 1:
                    # 只有共享时才需要MUX
                    mux_area = (u.mux_inputs - 1) * self.MUX_AREA_PER_INPUT
                    total_mux_area += mux_area
                    total_area += mux_area

        return {
            "actual_resources": actual_counts,
            "mux_overhead": mux_overhead,
            "total_units": sum(actual_counts.values()),
            "total_area_estimate": total_area,
            "functional_area": total_area - total_mux_area,
            "mux_area": total_mux_area,
            "units_detail": {
                op_type: [
                    {
                        "unit_id": u.unit_id,
                        "bound_nodes": u.bound_nodes,
                        "mux_inputs": u.mux_inputs,
                    }
                    for u in units
                ]
                for op_type, units in self.units.items()
            },
        }


def print_binding_summary(summary: Dict) -> None:
    """打印绑定结果到控制台"""
    print("=" * 60)
    print("BINDING RESULT SUMMARY")
    print("=" * 60)
    print(f"Total Physical Units: {summary['total_units']}")
    print(f"Functional Area:      {summary['functional_area']}")
    print(f"MUX Area:             {summary['mux_area']}")
    print(f"Total Estimated Area: {summary['total_area_estimate']}")
    print("-" * 60)
    print("Per-Type Resource Binding:")
    for op_type, count in summary["actual_resources"].items():
        mux = summary["mux_overhead"].get(op_type, 0)
        print(f"  {op_type:6s}: {count} units, {mux} total MUX inputs")
    print("=" * 60)
