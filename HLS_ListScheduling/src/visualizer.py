# visualizer.py - 可视化模块
# 甘特图、利用率曲线、对比图、帕累托图等绘图功能
# 陈润锴

import os
from typing import Dict, List, Optional
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from .node import Node


# Default color scheme for operation types
OP_TYPE_COLORS = {
    "ADD": "#3498db",
    "MUL": "#e74c3c",
    "SUB": "#2ecc71",
    "DIV": "#f39c12",
    "AND": "#9b59b6",
    "OR": "#1abc9c",
    "XOR": "#e91e63",
    "SHL": "#00bcd4",
    "CMP": "#ff5722",
    "INPUT": "#95a5a6",
}


def _get_op_color(op_type: str) -> str:
    """Get color for an operation type."""
    return OP_TYPE_COLORS.get(op_type.upper(), "#7f8c8d")


def plot_gantt_chart(
    scheduled_nodes: Dict[str, Node],
    resource_limits: Dict[str, int],
    output_path: Optional[str] = None,
    title: str = "Schedule Gantt Chart",
    critical_path: Optional[List[str]] = None,
) -> plt.Figure:
    """
    Draw a Gantt chart showing the scheduling timeline.

    Each row represents a functional unit instance, grouped by operation type.
    Bars are colored by operation type. Nodes on the critical path are
    highlighted with a red border.

    Args:
        scheduled_nodes: Dictionary of node_id -> Node.
        resource_limits: Resource constraints per operation type.
        output_path: If provided, save figure to this path.
        title: Chart title.
        critical_path: Optional list of node IDs on the critical path.

    Returns:
        Matplotlib Figure object.
    """
    cp_set = set(critical_path or [])

    # Group nodes by (op_type, resource_id)
    assignments: Dict[str, Dict[int, List[Node]]] = {}
    for node in scheduled_nodes.values():
        op = node.op_type
        rid = node.resource_id if node.resource_id is not None else 0
        if op not in assignments:
            assignments[op] = {}
        if rid not in assignments[op]:
            assignments[op][rid] = []
        assignments[op][rid].append(node)

    # Prepare y-axis labels and bars
    y_labels = []
    y_pos = 0
    bars = []

    fig, ax = plt.subplots(figsize=(14, 8))

    for op_type in sorted(assignments.keys()):
        limit = resource_limits.get(op_type, 1)
        base_color = _get_op_color(op_type)
        for rid in range(limit):
            y_labels.append(f"{op_type} #{rid}")
            if rid in assignments.get(op_type, {}):
                for node in assignments[op_type][rid]:
                    is_cp = node.node_id in cp_set
                    bars.append({
                        "y": y_pos,
                        "start": node.start_time,
                        "duration": node.delay,
                        "color": base_color,
                        "label": node.node_id,
                        "is_cp": is_cp,
                    })
            y_pos += 1

    # Draw bars
    for bar in bars:
        edge_color = '#c0392b' if bar["is_cp"] else 'black'
        line_width = 2.5 if bar["is_cp"] else 0.5
        ax.barh(
            bar["y"],
            bar["duration"],
            left=bar["start"],
            height=0.6,
            color=bar["color"],
            edgecolor=edge_color,
            linewidth=line_width,
            alpha=0.85,
        )
        # Add node ID text in the middle of the bar
        text_x = bar["start"] + bar["duration"] / 2
        text_y = bar["y"]
        ax.text(text_x, text_y, bar["label"], ha='center', va='center',
                fontsize=7, color='white' if not bar["is_cp"] else 'yellow',
                fontweight='bold' if bar["is_cp"] else 'normal')

    ax.set_yticks(range(len(y_labels)))
    ax.set_yticklabels(y_labels)
    ax.set_xlabel("Clock Cycle", fontsize=12)
    ax.set_ylabel("Functional Unit", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(axis='x', alpha=0.3)
    ax.invert_yaxis()

    # Add legend for operation types
    patches = []
    for op in sorted(assignments.keys()):
        patches.append(mpatches.Patch(color=_get_op_color(op), label=op))
    if cp_set:
        patches.append(mpatches.Patch(facecolor='none', label='Critical Path',
                                       edgecolor='#c0392b', linewidth=2))
    ax.legend(handles=patches, loc='upper right', title='Legend')

    plt.tight_layout()

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"[Visualizer] Gantt chart saved to: {output_path}")

    return fig


def plot_utilization_curve(
    cycle_usage: Dict[int, Dict[str, int]],
    resource_limits: Dict[str, int],
    output_path: Optional[str] = None,
    title: str = "Resource Utilization Over Time",
) -> plt.Figure:
    """
    Plot resource utilization curves over clock cycles.

    Args:
        cycle_usage: Dictionary mapping cycle -> {op_type: usage_count}.
        resource_limits: Resource limits per operation type.
        output_path: If provided, save figure to this path.
        title: Chart title.

    Returns:
        Matplotlib Figure object.
    """
    cycles = sorted(cycle_usage.keys())
    if not cycles:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No cycle usage data available",
                ha='center', va='center', transform=ax.transAxes, fontsize=12)
        return fig

    fig, axes = plt.subplots(len(resource_limits), 1, figsize=(12, 3 * len(resource_limits)), sharex=True)
    if len(resource_limits) == 1:
        axes = [axes]

    for ax, (op_type, limit) in zip(axes, sorted(resource_limits.items())):
        usages = [cycle_usage[c].get(op_type, 0) for c in cycles]
        utilization_rates = [u / limit * 100 if limit > 0 else 0 for u in usages]

        ax.fill_between(cycles, utilization_rates, alpha=0.3)
        ax.plot(cycles, utilization_rates, marker='o', markersize=3, label=f'{op_type} Utilization')
        ax.axhline(y=100, color='r', linestyle='--', linewidth=1, label='100% Limit')
        ax.set_ylabel(f"{op_type}\nUtilization (%)", fontsize=10)
        ax.set_ylim(0, 120)
        ax.grid(alpha=0.3)
        ax.legend(loc='upper right')

    axes[-1].set_xlabel("Clock Cycle", fontsize=12)
    fig.suptitle(title, fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.97])

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"[Visualizer] Utilization curve saved to: {output_path}")

    return fig


def plot_strategy_comparison(
    results: Dict[str, Dict],
    output_path: Optional[str] = None,
    title: str = "Strategy Comparison",
) -> plt.Figure:
    """
    Plot a bar chart comparing different scheduling strategies.
    Supports error bars for strategies with 'latency_std' field.

    Args:
        results: Dictionary mapping strategy_name -> summary dict.
        output_path: If provided, save figure to this path.
        title: Chart title.

    Returns:
        Matplotlib Figure object.
    """
    strategies = list(results.keys())
    latencies = [results[s]["total_latency"] for s in strategies]
    utilizations = [results[s]["overall_utilization"] * 100 for s in strategies]

    # Error bars for latency (if std available)
    latency_errors = [results[s].get("latency_std", 0) for s in strategies]

    colors = ['#3498db', '#e74c3c', '#2ecc71', '#9b59b6', '#f39c12']
    bar_colors = [colors[i % len(colors)] for i in range(len(strategies))]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Latency comparison
    bars1 = ax1.bar(strategies, latencies, color=bar_colors, edgecolor='black',
                    yerr=latency_errors, capsize=5, error_kw={'linewidth': 1.5})
    ax1.set_ylabel("Total Latency (cycles)", fontsize=11)
    ax1.set_title("Latency Comparison", fontsize=12, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3)
    for bar, val, err in zip(bars1, latencies, latency_errors):
        label = f"{val:.1f}" if err > 0 else str(int(val))
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + err + 0.5,
                label, ha='center', va='bottom', fontsize=10, fontweight='bold')

    # Utilization comparison
    bars2 = ax2.bar(strategies, utilizations, color=bar_colors, edgecolor='black')
    ax2.set_ylabel("Overall Utilization (%)", fontsize=11)
    ax2.set_title("Utilization Comparison", fontsize=12, fontweight='bold')
    ax2.set_ylim(0, 100)
    ax2.grid(axis='y', alpha=0.3)
    for bar, val in zip(bars2, utilizations):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f"{val:.1f}%", ha='center', va='bottom', fontsize=10, fontweight='bold')

    fig.suptitle(title, fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.95])

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"[Visualizer] Strategy comparison saved to: {output_path}")

    return fig


def plot_sensitivity_analysis(
    resource_configs: List[str],
    latencies: List[int],
    output_path: Optional[str] = None,
    title: str = "Sensitivity Analysis: Resources vs Latency",
) -> plt.Figure:
    """
    Plot a line chart showing how latency changes with resource allocation.

    Args:
        resource_configs: List of resource configuration labels.
        latencies: Corresponding latency values.
        output_path: If provided, save figure to this path.
        title: Chart title.

    Returns:
        Matplotlib Figure object.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.plot(resource_configs, latencies, marker='o', markersize=8, linewidth=2,
            color='#e74c3c', markerfacecolor='#3498db', markeredgewidth=2)
    ax.fill_between(range(len(resource_configs)), latencies, alpha=0.1, color='#e74c3c')

    ax.set_xlabel("Resource Configuration", fontsize=12)
    ax.set_ylabel("Total Latency (cycles)", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(alpha=0.3)

    # Annotate each point
    for i, (cfg, lat) in enumerate(zip(resource_configs, latencies)):
        ax.annotate(str(lat), (i, lat), textcoords="offset points",
                    xytext=(0, 10), ha='center', fontsize=10, fontweight='bold')

    plt.tight_layout()

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"[Visualizer] Sensitivity analysis saved to: {output_path}")

    return fig


def export_schedule_table(
    scheduled_nodes: Dict[str, Node],
    output_path: Optional[str] = None,
) -> str:
    """
    Export a text-based schedule table.

    Args:
        scheduled_nodes: Dictionary of node_id -> Node.
        output_path: If provided, write table to this file path.

    Returns:
        The table as a string.
    """
    # Sort nodes by start time, then by node_id
    nodes = sorted(scheduled_nodes.values(), key=lambda n: (n.start_time or 0, n.node_id))

    lines = []
    lines.append("=" * 80)
    lines.append(f"{'Node ID':<10} {'Type':<6} {'Start':<6} {'Finish':<7} {'Delay':<6} {'Res#':<5} {'ASAP':<5} {'ALAP':<5} {'Mobility':<9}")
    lines.append("-" * 80)
    for node in nodes:
        lines.append(
            f"{node.node_id:<10} {node.op_type:<6} {node.start_time or -1:<6} "
            f"{node.finish_time or -1:<7} {node.delay:<6} {node.resource_id or -1:<5} "
            f"{node.asap or -1:<5} {node.alap or -1:<5} {node.mobility if node.mobility is not None else -1:<9}"
        )
    lines.append("=" * 80)

    table = "\n".join(lines)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(table)
        print(f"[Visualizer] Schedule table saved to: {output_path}")

    return table


def plot_pareto_frontier(
    points: List,
    pareto_points: List,
    output_path: Optional[str] = None,
    title: str = "Area-Latency Pareto Frontier",
) -> plt.Figure:
    """
    Plot area-latency scatter with Pareto-optimal points highlighted.

    Args:
        points: List of (latency, area, label) tuples for all configurations.
        pareto_points: List of (latency, area, label) tuples for Pareto-optimal configs.
        output_path: If provided, save figure to this path.
        title: Chart title.

    Returns:
        Matplotlib Figure object.
    """
    fig, ax = plt.subplots(figsize=(10, 7))

    # All points in blue
    all_lat = [p[0] for p in points]
    all_area = [p[1] for p in points]
    ax.scatter(all_lat, all_area, c='#3498db', s=80, alpha=0.6,
               edgecolors='black', linewidth=0.5, label='All Configurations', zorder=2)

    # Pareto points in red with larger size
    if pareto_points:
        par_lat = [p[0] for p in pareto_points]
        par_area = [p[1] for p in pareto_points]
        ax.scatter(par_lat, par_area, c='#e74c3c', s=150, alpha=0.9,
                   edgecolors='darkred', linewidth=2, label='Pareto-Optimal', zorder=3)

        # Connect Pareto points with a staircase line
        ax.plot(par_lat, par_area, color='#e74c3c', linestyle='--',
                linewidth=2, alpha=0.7, zorder=1)

        # Annotate Pareto points
        for lat, area, lbl in pareto_points:
            ax.annotate(lbl, (lat, area), textcoords="offset points",
                        xytext=(8, 8), ha='left', fontsize=8,
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))

    ax.set_xlabel("Total Latency (cycles)", fontsize=12)
    ax.set_ylabel("Total Estimated Area (relative units)", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(alpha=0.3)
    ax.legend(loc='upper right', fontsize=10)

    plt.tight_layout()

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"[Visualizer] Pareto frontier plot saved to: {output_path}")

    return fig


def plot_dfg_topology(
    dfg,
    critical_path: Optional[List[str]] = None,
    output_path: Optional[str] = None,
    title: str = "DFG Topology",
) -> plt.Figure:
    """
    Draw the Data Flow Graph topology with nodes colored by operation type
    and critical path highlighted in red.

    Args:
        dfg: networkx DiGraph representing the DFG.
        critical_path: Optional list of node IDs on the critical path.
        output_path: If provided, save figure to this path.
        title: Chart title.

    Returns:
        Matplotlib Figure object.
    """
    import networkx as nx

    cp_set = set(critical_path or [])

    # Build color map for nodes
    node_colors = []
    node_sizes = []
    for nid in dfg.nodes():
        node = dfg.nodes[nid].get("node")
        if node:
            op_type = node.op_type
            color = _get_op_color(op_type)
            size = 800 if nid in cp_set else 500
        else:
            color = '#7f8c8d'
            size = 500
        node_colors.append(color)
        node_sizes.append(size)

    # Edge colors: red if both ends on critical path
    edge_colors = []
    for u, v in dfg.edges():
        if u in cp_set and v in cp_set:
            edge_colors.append('#e74c3c')
        else:
            edge_colors.append('#bdc3c7')

    fig, ax = plt.subplots(figsize=(12, 10))

    # Use hierarchical layout based on ASAP levels if available, else spring layout
    try:
        # Set layer attribute based on ASAP for multipartite layout
        for nid in dfg.nodes():
            node = dfg.nodes[nid].get("node")
            layer = node.asap if node and node.asap is not None else 0
            dfg.nodes[nid]['_layer'] = layer
        pos = nx.multipartite_layout(dfg, subset_key='_layer', align='vertical')
    except Exception:
        pos = nx.spring_layout(dfg, seed=42, k=1.5)

    # Draw edges
    nx.draw_networkx_edges(dfg, pos, edge_color=edge_colors, width=1.5,
                           arrowsize=15, ax=ax, node_size=node_sizes)

    # Draw nodes
    nx.draw_networkx_nodes(dfg, pos, node_color=node_colors, node_size=node_sizes,
                           edgecolors='black', linewidths=1.5, ax=ax)

    # Draw labels
    labels = {}
    for nid in dfg.nodes():
        node = dfg.nodes[nid].get("node")
        if node:
            labels[nid] = f"{nid}\n{node.op_type}"
        else:
            labels[nid] = nid
    nx.draw_networkx_labels(dfg, pos, labels, font_size=8, ax=ax)

    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.axis('off')

    # Legend
    patches = []
    seen_types = set()
    for nid in dfg.nodes():
        node = dfg.nodes[nid].get("node")
        if node and node.op_type not in seen_types:
            seen_types.add(node.op_type)
            patches.append(mpatches.Patch(color=_get_op_color(node.op_type), label=node.op_type))
    if cp_set:
        patches.append(mpatches.Patch(facecolor='none', label='Critical Path',
                                       edgecolor='#e74c3c', linewidth=2))
    ax.legend(handles=patches, loc='upper left', title='Legend')

    plt.tight_layout()

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"[Visualizer] DFG topology saved to: {output_path}")

    return fig


def plot_pipeline_analysis(
    results: list,
    baseline_latency: int,
    output_path: Optional[str] = None,
    title: str = "Pipelined Scheduling Analysis",
) -> plt.Figure:
    """
    Plot II (Initiation Interval) vs Effective Throughput.

    Args:
        results: List of dicts with keys 'ii', 'throughput', 'feasible'.
        baseline_latency: Non-pipelined baseline latency for reference.
        output_path: If provided, save figure to this path.
        title: Chart title.

    Returns:
        Matplotlib Figure object.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    feasible = [r for r in results if r['feasible']]
    infeasible = [r for r in results if not r['feasible']]

    # Plot 1: II vs Effective Throughput
    if feasible:
        ii_vals = [r['ii'] for r in feasible]
        thr_vals = [r['throughput'] for r in feasible]
        ax1.plot(ii_vals, thr_vals, marker='o', markersize=8, linewidth=2,
                 color='#3498db', label='Pipelined Throughput')
        ax1.scatter(ii_vals, thr_vals, s=100, c='#3498db', zorder=3, edgecolors='black')

    if infeasible:
        ii_vals_inf = [r['ii'] for r in infeasible]
        ax1.scatter(ii_vals_inf, [0]*len(ii_vals_inf), s=150, c='#e74c3c',
                    marker='x', linewidths=3, label='Infeasible', zorder=3)

    ax1.set_xlabel("Initiation Interval (II)", fontsize=12)
    ax1.set_ylabel("Effective Throughput (ops/cycle)", fontsize=12)
    ax1.set_title("Throughput vs II", fontsize=12, fontweight='bold')
    ax1.grid(alpha=0.3)
    ax1.legend(loc='best')

    # Plot 2: II vs Latency (with baseline reference)
    if feasible:
        ii_vals = [r['ii'] for r in feasible]
        lat_vals = [r['latency'] for r in feasible]
        ax2.plot(ii_vals, lat_vals, marker='s', markersize=8, linewidth=2,
                 color='#2ecc71', label='Pipelined Latency')
        ax2.scatter(ii_vals, lat_vals, s=100, c='#2ecc71', zorder=3, edgecolors='black')

    ax2.axhline(y=baseline_latency, color='#e74c3c', linestyle='--',
                linewidth=2, label=f'Baseline Latency={baseline_latency}')

    if infeasible:
        ii_vals_inf = [r['ii'] for r in infeasible]
        ax2.scatter(ii_vals_inf, [baseline_latency]*len(ii_vals_inf), s=150,
                    c='#e74c3c', marker='x', linewidths=3, label='Infeasible', zorder=3)

    ax2.set_xlabel("Initiation Interval (II)", fontsize=12)
    ax2.set_ylabel("Latency (cycles)", fontsize=12)
    ax2.set_title("Latency vs II", fontsize=12, fontweight='bold')
    ax2.grid(alpha=0.3)
    ax2.legend(loc='best')

    fig.suptitle(title, fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.95])

    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"[Visualizer] Pipeline analysis plot saved to: {output_path}")

    return fig
