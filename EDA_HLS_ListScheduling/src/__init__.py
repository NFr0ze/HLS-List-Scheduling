"""
EDA HLS List Scheduling
=========================
Resource-Constrained List Scheduling Algorithm Implementation for
High-Level Synthesis (HLS).

Modules:
    node            - Node class for DFG operations
    dfg_parser      - DFG JSON parser and random DAG generator
    asap_alap       - Static timing analysis (ASAP/ALAP/Mobility)
    list_scheduler  - List Scheduling core engine
    metrics         - Evaluation metrics (latency, utilization, throughput)
    visualizer      - Gantt charts, utilization curves, comparison plots

Author: 陈润锴 (23362012)
Course: 电子设计自动化 (EDA)
"""

__version__ = "1.0.0"
