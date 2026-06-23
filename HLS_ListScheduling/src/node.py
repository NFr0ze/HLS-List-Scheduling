# node.py - DFG节点定义
# 表示数据流图中的一个运算节点，包含类型、延迟、依赖关系及调度结果
# 陈润锴 23362012

from typing import List, Optional, Set


class Node:
    """DFG中的运算节点"""

    def __init__(
        self,
        node_id: str,
        op_type: str,
        delay: int = 1,
        predecessors: Optional[List[str]] = None,
        successors: Optional[List[str]] = None,
    ):
        # 简单校验一下输入
        if not isinstance(node_id, str) or not node_id:
            raise ValueError(f"node_id must be a non-empty string, got {node_id!r}")
        if not isinstance(op_type, str) or not op_type:
            raise ValueError(f"op_type must be a non-empty string, got {op_type!r}")
        if not isinstance(delay, int) or delay < 0:
            raise ValueError(f"delay must be a non-negative integer, got {delay!r}")

        self.node_id = node_id
        self.op_type = op_type.upper()
        self.delay = delay
        self.predecessors: List[str] = predecessors or []
        self.successors: List[str] = successors or []

        # 调度相关属性，后面计算
        self.asap: Optional[int] = None
        self.alap: Optional[int] = None
        self.mobility: Optional[int] = None
        self.start_time: Optional[int] = None
        self.finish_time: Optional[int] = None
        self.resource_id: Optional[int] = None

    def is_ready(self, scheduled_nodes: Set[str]) -> bool:
        """前驱节点是否都已调度完成"""
        return all(pred in scheduled_nodes for pred in self.predecessors)

    def compute_mobility(self) -> None:
        """计算mobility = ALAP - ASAP，需要先算好ASAP和ALAP"""
        if self.asap is not None and self.alap is not None:
            self.mobility = self.alap - self.asap
        else:
            self.mobility = None

    def reset_schedule(self) -> None:
        """清空调度结果，方便重新跑实验"""
        self.start_time = None
        self.finish_time = None
        self.resource_id = None

    def __repr__(self) -> str:
        return (
            f"Node({self.node_id}, {self.op_type}, delay={self.delay}, "
            f"ASAP={self.asap}, ALAP={self.alap}, Mobility={self.mobility}, "
            f"Start={self.start_time})"
        )

    def to_dict(self) -> dict:
        """Serialize node to dictionary for JSON export."""
        return {
            "id": self.node_id,
            "type": self.op_type,
            "delay": self.delay,
            "deps": self.predecessors,
            "asap": self.asap,
            "alap": self.alap,
            "mobility": self.mobility,
            "start_time": self.start_time,
            "finish_time": self.finish_time,
        }
