# list_scheduler.py - 列表调度主引擎
# 实现资源约束下的List Scheduling，支持多种优先级策略和流水线调度
# 陈润锴

import random
from typing import Dict, List, Callable, Optional, Set, Tuple
import networkx as nx

from .node import Node
from .dfg_parser import dfg_to_nodes_dict
from .asap_alap import run_static_timing_analysis


class ResourcePool:
    """维护各类型运算单元在时间轴上的占用状态"""

    def __init__(self, resource_limits: Dict[str, int]):
        """resource_limits: {'ADD': 2, 'MUL': 1} 这样的字典"""
        self.limits = resource_limits
        # 每类资源记录各自空闲时间，例如 {'ADD': [0, 0]} 表示2个ADD都在cycle 0空闲
        self.resources: Dict[str, List[int]] = {
            op: [0] * count for op, count in resource_limits.items()
        }

    def is_available(self, op_type: str, cycle: int) -> bool:
        """检查某类资源在指定cycle是否还有空闲的"""
        if op_type not in self.resources:
            return False
        return any(free_time <= cycle for free_time in self.resources[op_type])

    def allocate(self, op_type: str, cycle: int, delay: int) -> int:
        """分配一个资源，返回资源编号。找不到就报错"""
        if op_type not in self.resources:
            raise RuntimeError(f"No resource defined for operation type '{op_type}'")

        # 找最早空闲的资源
        best_idx = -1
        best_free = float('inf')
        for idx, free_time in enumerate(self.resources[op_type]):
            if free_time <= cycle and free_time < best_free:
                best_free = free_time
                best_idx = idx

        if best_idx == -1:
            raise RuntimeError(
                f"No available '{op_type}' resource at cycle {cycle}. "
                f"Limit: {self.limits.get(op_type, 0)}"
            )

        # 标记资源忙到 cycle + delay
        self.resources[op_type][best_idx] = cycle + delay
        return best_idx

    def get_utilization_at_cycle(self, op_type: str, cycle: int) -> int:
        """返回某类资源在指定cycle的占用数量"""
        if op_type not in self.resources:
            return 0
        busy = 0
        for free_time in self.resources[op_type]:
            # free_time > cycle 说明还在忙
            if free_time > cycle:
                busy += 1
        return busy

    def reset(self) -> None:
        """重置所有资源为空闲状态"""
        self.resources = {
            op: [0] * count for op, count in self.limits.items()
        }


def default_priority(node: Node) -> Tuple:
    """默认优先级：mobility小的优先，相同则ASAP小的优先"""
    mobility = node.mobility if node.mobility is not None else float('inf')
    asap = node.asap if node.asap is not None else float('inf')
    return (mobility, asap)


def cp_first_priority(node: Node) -> Tuple:
    """关键路径优先：mobility=0的节点排在前面，相同则delay大的优先"""
    on_cp = 0 if (node.mobility == 0) else 1
    asap = node.asap if node.asap is not None else float('inf')
    delay = -node.delay  # delay大的排前面，所以取负
    return (on_cp, delay, asap)


def ldf_priority(node: Node) -> Tuple:
    """长延迟优先：delay大的排前面，相同则mobility小的优先"""
    delay = -node.delay
    mobility = node.mobility if node.mobility is not None else float('inf')
    asap = node.asap if node.asap is not None else float('inf')
    return (delay, mobility, asap)


def random_priority(node: Node) -> float:
    """随机优先级，作为baseline对比用"""
    return random.random()


def make_random_priority(seed: Optional[int] = None) -> Callable[[Node], float]:
    """生成一个带独立随机状态的优先级函数，方便复现实验"""
    rng = random.Random(seed)
    def priority(node: Node) -> float:
        return rng.random()
    return priority


class ListScheduler:
    """资源约束列表调度引擎"""

    def __init__(
        self,
        dfg: nx.DiGraph,
        resource_limits: Dict[str, int],
        priority_fn: Optional[Callable[[Node], Tuple]] = None,
        latency_constraint: Optional[int] = None,
    ):
        """初始化调度器，priority_fn默认为mobility最小优先"""
        if not resource_limits:
            raise ValueError("Resource limits cannot be empty.")
        for op, limit in resource_limits.items():
            if limit < 0:
                raise ValueError(f"Resource limit for '{op}' cannot be negative ({limit}).")

        self.dfg = dfg
        self.nodes = dfg_to_nodes_dict(dfg)
        self.resource_limits = resource_limits
        self.priority_fn = priority_fn or default_priority
        self.latency_constraint = latency_constraint
        self.resource_pool = ResourcePool(resource_limits)
        self.schedule_log: List[Dict] = []

    def schedule(self) -> Dict[str, Node]:
        """执行List Scheduling，返回调度后的节点字典"""
        # 重置状态
        for node in self.nodes.values():
            node.reset_schedule()
        self.resource_pool.reset()
        self.schedule_log = []

        # 先跑ASAP/ALAP，算优先级要用
        run_static_timing_analysis(self.dfg, self.latency_constraint)

        # 预检查：每个非INPUT节点类型都必须有正的资源限额
        for node in self.nodes.values():
            if node.delay > 0:
                limit = self.resource_limits.get(node.op_type, 0)
                if limit <= 0:
                    raise RuntimeError(
                        f"Cannot schedule node '{node.node_id}' (type={node.op_type}) "
                        f"because resource limit for {node.op_type} is {limit}."
                    )

        scheduled: Set[str] = set()
        cycle = 0
        max_cycles = len(self.nodes) * 100  # 防止死循环的安全上限

        # INPUT节点delay=0，不需要资源，直接放在cycle 0
        for node in self.nodes.values():
            if node.delay == 0:
                node.start_time = 0
                node.finish_time = 0
                node.resource_id = -1
                scheduled.add(node.node_id)

        while len(scheduled) < len(self.nodes) and cycle < max_cycles:
            # 找就绪节点：所有前驱都已完成
            ready_list: List[Node] = []
            for node in self.nodes.values():
                if node.node_id in scheduled:
                    continue
                all_preds_done = True
                for pred_id in node.predecessors:
                    pred = self.nodes[pred_id]
                    if pred.finish_time is None or pred.finish_time > cycle:
                        all_preds_done = False
                        break
                if all_preds_done:
                    ready_list.append(node)

            # 按优先级排序
            ready_list.sort(key=self.priority_fn)

            # 尝试分配资源
            scheduled_this_cycle: List[str] = []
            for node in ready_list:
                op_type = node.op_type
                if self.resource_pool.is_available(op_type, cycle):
                    res_id = self.resource_pool.allocate(op_type, cycle, node.delay)
                    node.start_time = cycle
                    node.finish_time = cycle + node.delay
                    node.resource_id = res_id
                    scheduled_this_cycle.append(node.node_id)

            # 标记本轮调度的节点
            for nid in scheduled_this_cycle:
                scheduled.add(nid)

            # 记录本轮状态
            self.schedule_log.append({
                "cycle": cycle,
                "scheduled_nodes": scheduled_this_cycle,
                "ready_count": len(ready_list),
            })

            cycle += 1

        if len(scheduled) < len(self.nodes):
            unscheduled = [nid for nid in self.nodes if nid not in scheduled]
            raise RuntimeError(f"Scheduling failed. Unscheduled nodes: {unscheduled}")

        return self.nodes

    def get_total_latency(self) -> int:
        """返回调度总延迟（makespan）"""
        return max(node.finish_time for node in self.nodes.values() if node.finish_time is not None)

    def verify_schedule(self) -> bool:
        """验证调度结果是否满足数据依赖和资源约束"""
        # 检查数据依赖
        for node in self.nodes.values():
            for pred_id in node.predecessors:
                pred = self.nodes[pred_id]
                if pred.finish_time is None or node.start_time is None:
                    return False
                if pred.finish_time > node.start_time:
                    print(f"Dependency violation: {pred_id} finishes at {pred.finish_time}, "
                          f"but {node.node_id} starts at {node.start_time}")
                    return False

        # 检查每cycle的资源使用是否超限
        total_latency = self.get_total_latency()
        for cycle in range(total_latency):
            usage: Dict[str, int] = {}
            for node in self.nodes.values():
                if node.start_time is not None and node.start_time <= cycle < node.finish_time:
                    usage[node.op_type] = usage.get(node.op_type, 0) + 1
            for op_type, used in usage.items():
                limit = self.resource_limits.get(op_type, 0)
                if used > limit:
                    print(f"Resource violation: {op_type} usage {used} > limit {limit} at cycle {cycle}")
                    return False

        return True


class PipelinedResourcePool:
    """流水线调度的资源池，按模II的phase来检查资源冲突"""

    def __init__(self, resource_limits: Dict[str, int], ii: int):
        """ii: Initiation Interval，必须 >= 1"""
        if ii < 1:
            raise ValueError("Initiation Interval (II) must be >= 1.")
        self.limits = resource_limits
        self.ii = ii
        # usage[op_type][p] 记录phase p上的占用数
        self.usage: Dict[str, List[int]] = {
            op: [0] * ii for op in resource_limits
        }

    def _affected_phases(self, cycle: int, delay: int) -> List[int]:
        """一个操作[cycle, cycle+delay)会影响哪些phase"""
        phases = []
        for c in range(cycle, cycle + delay):
            p = c % self.ii
            if p not in phases:
                phases.append(p)
        return phases

    def is_available(self, op_type: str, cycle: int, delay: int) -> bool:
        """在流水线上下文中检查资源是否可用"""
        if op_type not in self.usage:
            return False
        limit = self.limits.get(op_type, 0)
        for p in self._affected_phases(cycle, delay):
            if self.usage[op_type][p] >= limit:
                return False
        return True

    def allocate(self, op_type: str, cycle: int, delay: int) -> int:
        """分配资源，返回phase编号（cycle % II）作为资源ID"""
        if op_type not in self.usage:
            raise RuntimeError(f"No resource defined for operation type '{op_type}'")
        for p in self._affected_phases(cycle, delay):
            self.usage[op_type][p] += 1
        return cycle % self.ii

    def reset(self) -> None:
        """清空占用计数"""
        self.usage = {
            op: [0] * self.ii for op in self.limits
        }


class PipelinedListScheduler(ListScheduler):
    """带启动间隔(II)约束的流水线列表调度器"""

    def __init__(
        self,
        dfg: nx.DiGraph,
        resource_limits: Dict[str, int],
        ii: int,
        priority_fn: Optional[Callable[[Node], Tuple]] = None,
        latency_constraint: Optional[int] = None,
    ):
        """ii: Initiation Interval， successive iterations之间的间隔"""
        super().__init__(dfg, resource_limits, priority_fn, latency_constraint)
        if ii < 1:
            raise ValueError("Initiation Interval (II) must be >= 1.")
        self.ii = ii
        self.resource_pool = PipelinedResourcePool(resource_limits, ii)

    def schedule(self) -> Dict[str, Node]:
        """执行流水线列表调度"""
        # 重置状态
        for node in self.nodes.values():
            node.reset_schedule()
        self.resource_pool.reset()
        self.schedule_log = []

        # 先跑ASAP/ALAP算优先级
        run_static_timing_analysis(self.dfg, self.latency_constraint)

        # 预检查
        for node in self.nodes.values():
            if node.delay > 0:
                limit = self.resource_limits.get(node.op_type, 0)
                if limit <= 0:
                    raise RuntimeError(
                        f"Cannot schedule node '{node.node_id}' (type={node.op_type}) "
                        f"because resource limit for {node.op_type} is {limit}."
                    )

        scheduled: Set[str] = set()
        cycle = 0
        max_cycles = len(self.nodes) * 100

        # INPUT节点自动调度
        for node in self.nodes.values():
            if node.delay == 0:
                node.start_time = 0
                node.finish_time = 0
                node.resource_id = -1
                scheduled.add(node.node_id)

        while len(scheduled) < len(self.nodes) and cycle < max_cycles:
            # 找就绪节点
            ready_list: List[Node] = []
            for node in self.nodes.values():
                if node.node_id in scheduled:
                    continue
                all_preds_done = True
                for pred_id in node.predecessors:
                    pred = self.nodes[pred_id]
                    if pred.finish_time is None or pred.finish_time > cycle:
                        all_preds_done = False
                        break
                if all_preds_done:
                    ready_list.append(node)

            # 按优先级排序
            ready_list.sort(key=self.priority_fn)

            # 用PipelinedResourcePool分配资源
            scheduled_this_cycle: List[str] = []
            for node in ready_list:
                op_type = node.op_type
                if self.resource_pool.is_available(op_type, cycle, node.delay):
                    res_id = self.resource_pool.allocate(op_type, cycle, node.delay)
                    node.start_time = cycle
                    node.finish_time = cycle + node.delay
                    node.resource_id = res_id
                    scheduled_this_cycle.append(node.node_id)

            for nid in scheduled_this_cycle:
                scheduled.add(nid)

            self.schedule_log.append({
                "cycle": cycle,
                "scheduled_nodes": scheduled_this_cycle,
                "ready_count": len(ready_list),
            })

            cycle += 1

        if len(scheduled) < len(self.nodes):
            unscheduled = [nid for nid in self.nodes if nid not in scheduled]
            raise RuntimeError(f"Pipelined scheduling failed (II={self.ii}). Unscheduled: {unscheduled}")

        return self.nodes

    def get_effective_throughput(self, num_iterations: int = 100) -> float:
        """计算流水线有效吞吐率。总时间 = latency + (num_iterations-1)*II"""
        latency = self.get_total_latency()
        total_time = latency + (num_iterations - 1) * self.ii
        total_ops = len(self.nodes) * num_iterations
        return total_ops / total_time if total_time > 0 else 0.0

    def verify_schedule(self) -> bool:
        """验证流水线调度是否满足数据依赖和模II资源约束"""
        # 检查数据依赖（和基类一样）
        for node in self.nodes.values():
            for pred_id in node.predecessors:
                pred = self.nodes[pred_id]
                if pred.finish_time is None or node.start_time is None:
                    return False
                if pred.finish_time > node.start_time:
                    print(f"Dependency violation: {pred_id} finishes at {pred.finish_time}, "
                          f"but {node.node_id} starts at {node.start_time}")
                    return False

        # 检查模II资源约束
        for op_type, limit in self.resource_limits.items():
            for phase in range(self.ii):
                usage = 0
                for node in self.nodes.values():
                    if node.op_type != op_type or node.start_time is None:
                        continue
                    # 检查该操作是否占用了这个phase
                    for c in range(node.start_time, node.finish_time):
                        if c % self.ii == phase:
                            usage += 1
                            break  # 每个操作每个phase只算一次
                if usage > limit:
                    print(f"Modulo-II resource violation: {op_type} usage {usage} > limit {limit} "
                          f"at phase {phase} (II={self.ii})")
                    return False

        return True
