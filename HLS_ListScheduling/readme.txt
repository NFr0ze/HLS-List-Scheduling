作者：

姓名：陈润锴
学号：23362012


资源约束下高层次综合列表调度算法的优化实现与评估

Implementation and Evaluation of Resource-Constrained List Scheduling in HLS

项目简介:

这个项目主要实现了高层次综合（HLS）里核心的资源约束列表调度算法（List Scheduling），并拓展了资源绑定（Binding）和流水线调度（Pipelining）两个模块。里面包含完整的ASAP/ALAP静态时序分析、基于Mobility的优先级调度引擎、三级规模的测试数据集、六类对照实验以及可视化输出。


环境要求(requirements文件中有说明）：

Python 3.10 或更高版本。

运行后会在 experiments/results/ 目录下生成所有图表和结果。

 experiments.py一键运行全部实验

_
命令行参数:

运行单个实验

策略对比
python experiments/compare_strategies.py

灵敏度分析
python experiments/sensitivity_analysis.py

帕累托前沿分析
python experiments/pareto_analysis.py

流水线调度实验
python experiments/pipeline_test.py


核心算法:

1. ASAP / ALAP 静态时序分析
ASAP：拓扑排序正向遍历，算无限资源下各节点最早开始时间
ALAP：反向拓扑排序，在给定延迟约束下算最晚开始时间
Mobility: 反映调度灵活度

2. List Scheduling 主引擎
1. 初始化时钟周期 cycle = 0
2. 维护就绪列表：所有前驱节点已完成调度的节点
3. 优先级排序：Mobility越小优先级越高（关键路径优先）
4. 资源分配：按优先级将节点分配给可用资源，受资源限额约束
5. 重复直到所有节点调度完成

3. 资源绑定（Binding）
贪心区间划分：将执行时间不重叠的同类型操作映射到共享硬件单元
MUX开销计算：每个共享单元需要多路选择器切换不同输入
面积估算：功能单元面积 + MUX面积 

4. 流水线调度（Pipelining）
Modulo Scheduling：基于启动间隔（II）的模调度
资源约束：在模II意义下满足资源限额
有效吞吐率：总操作数 / (延迟 + (N-1) × II)

5. 可视化输出
甘特图：按运算类型分组的调度时间轴，关键路径红色高亮
资源利用率曲线：各类型运算单元随时间的利用率变化
DFG拓扑图：数据流图的节点连接结构，关键路径红色高亮
对比图表：策略对比柱状图、灵敏度分析折线图、帕累托前沿散点图、流水线分析双图

测试数据集:

小规模   功能验证 : data/small/*.json
中规模   工程应用 : data/medium/*.json
大规模   压力测试 : data/large/*.json

对照实验:

1. 策略对比：Mobility-First / CP-First / LDF-First vs 随机选择策略（20次平均）
2. 灵敏度分析：改变资源配额，观察Latency的边际效应
3. 面积-延迟帕累托优化：网格搜索资源配置，绘制帕累托最优点
4. 流水线调度：改变启动间隔II，观察有效吞吐率与可行性边界
5. 复杂度验证：验证运行时间随节点数线性增长
6. 可调度性分析：收紧延迟约束，观察调度边界
7. 资源绑定：评估资源共享的MUX开销与面积估算



声明：

本项目在开发过程中使用了AI辅助工具（Claude）进行代码框架设计和文档撰写辅助。
