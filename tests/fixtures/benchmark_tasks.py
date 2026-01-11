"""用于对比 LLM providers 的固定基准测试任务

这些任务旨在测试计划生成的不同方面:
1. 简单单步任务
2. 复杂多约束任务
3. 多步候选任务
"""

from src.models.contracts import ProteinDesignTask


# 任务 1: 简单序列设计
TASK_SIMPLE = ProteinDesignTask(
    task_id="benchmark_simple",
    goal="设计一个 20 残基的螺旋肽",
    constraints={"length": 20, "structure": "helix"},
    metadata={"description": "简单的单约束任务"}
)


# 任务 2: 带长序列的复杂任务
TASK_COMPLEX = ProteinDesignTask(
    task_id="benchmark_complex",
    goal="预测结构并验证稳定性",
    constraints={
        "sequence": "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQAPILSRVGDGTQDNLSGAEKAVQVKVKALPDAQFEVVHSLAKWKRQTLGQHDFSAGEGLYTHMKALRPDEDRLSPLHSVYVDQWDWERVMGDGERQFSTLKSTVEAIWAGIKATEAAVSEEFGLAPFLPDQIHFVHSQELLSRYPDLDAKGRERAIAKDLGAVFLVGIGGKLSDGHRHDVRAPDYDDWSTPSELGHAGLNGDILVWNPVLEDAFELSSMGIRVDADTLKHQLALTGDEDRLELEWHQALLRGEMPQTIGGGIGQSRLTMLLLQLPHIGQVQAGVWPAAVRESVPSLL"
    },
    metadata={"description": "带长序列的复杂任务"}
)


# 任务 3: 多步工作流候选
TASK_MULTISTEP = ProteinDesignTask(
    task_id="benchmark_multistep",
    goal="生成序列、预测结构、评估安全性",
    constraints={"target": "therapeutic_antibody"},
    metadata={"description": "多步工作流规划任务"}
)


# 所有基准测试任务
BENCHMARK_TASKS = [TASK_SIMPLE, TASK_COMPLEX, TASK_MULTISTEP]
