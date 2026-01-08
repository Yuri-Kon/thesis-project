#!/usr/bin/env python
"""
ESMFold 适配器手动测试脚本

演示如何直接调用 ESMFoldAdapter 执行结构预测。

使用方法：
    python examples/esmfold_manual_test.py

环境要求：
    - Nextflow 已安装
    - 项目根目录下的 nf/modules/esmfold.nf 存在
"""

from __future__ import annotations

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.adapters.esmfold_adapter import ESMFoldAdapter
from src.models.contracts import PlanStep, ProteinDesignTask
from src.workflow.context import WorkflowContext


def main():
    """运行 ESMFold 手动测试"""
    print("=" * 60)
    print("ESMFold 适配器手动测试")
    print("=" * 60)

    # 1. 创建适配器
    print("\n[1] 创建 ESMFoldAdapter...")
    module_path = project_root / "nf" / "modules" / "esmfold.nf"
    if not module_path.exists():
        print(f"错误：Nextflow 模块不存在: {module_path}")
        return 1

    adapter = ESMFoldAdapter(
        module_path=module_path,
        nextflow_profile="test",
    )
    print(f"   ✓ Adapter 创建成功")
    print(f"   - 模块路径: {module_path}")
    print(f"   - Profile: test")

    # 2. 创建测试任务和上下文
    print("\n[2] 创建测试任务...")
    task = ProteinDesignTask(
        task_id="manual_test_001",
        goal="测试 ESMFold 结构预测",
        constraints={},
    )
    context = WorkflowContext(task=task)
    print(f"   ✓ 任务创建成功")
    print(f"   - Task ID: {task.task_id}")

    # 3. 创建计划步骤
    print("\n[3] 创建 PlanStep...")
    test_sequence = "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV"
    step = PlanStep(
        id="S1",
        tool="esmfold",
        inputs={"sequence": test_sequence},
        metadata={},
    )
    print(f"   ✓ 步骤创建成功")
    print(f"   - Step ID: {step.id}")
    print(f"   - 序列: {test_sequence[:30]}...")
    print(f"   - 序列长度: {len(test_sequence)}")

    # 4. 解析输入
    print("\n[4] 解析输入参数...")
    try:
        resolved_inputs = adapter.resolve_inputs(step, context)
        print(f"   ✓ 输入解析成功")
        print(f"   - sequence: {resolved_inputs['sequence'][:30]}...")
        print(f"   - task_id: {resolved_inputs['task_id']}")
        print(f"   - step_id: {resolved_inputs['step_id']}")
    except Exception as e:
        print(f"   ✗ 输入解析失败: {e}")
        return 1

    # 5. 执行预测
    print("\n[5] 执行 ESMFold 预测...")
    print("   注意：这将调用 Nextflow，可能需要几秒到几分钟")
    try:
        outputs, metrics = adapter.run_local(resolved_inputs)
        print(f"   ✓ 预测执行成功")
    except Exception as e:
        print(f"   ✗ 预测执行失败: {e}")
        import traceback

        traceback.print_exc()
        return 1

    # 6. 显示结果
    print("\n[6] 预测结果:")
    print("   输出 (outputs):")
    for key, value in outputs.items():
        if isinstance(value, dict):
            print(f"     - {key}:")
            for k, v in value.items():
                print(f"         {k}: {v}")
        else:
            print(f"     - {key}: {value}")

    print("\n   指标 (metrics):")
    for key, value in metrics.items():
        print(f"     - {key}: {value}")

    # 7. 验证关键输出
    print("\n[7] 验证结果...")
    errors = []

    if "pdb_path" not in outputs:
        errors.append("缺少 pdb_path")
    else:
        pdb_path = Path(outputs["pdb_path"])
        if not pdb_path.exists():
            errors.append(f"PDB 文件不存在: {pdb_path}")
        else:
            print(f"   ✓ PDB 文件存在: {pdb_path}")

    if "metrics" not in outputs:
        errors.append("缺少 metrics")
    else:
        output_metrics = outputs["metrics"]
        if "plddt_mean" not in output_metrics:
            errors.append("metrics 中缺少 plddt_mean")
        else:
            print(f"   ✓ pLDDT 均值: {output_metrics['plddt_mean']}")

    if metrics.get("exec_type") != "nextflow":
        errors.append(f"exec_type 应为 'nextflow'，实际为 '{metrics.get('exec_type')}'")
    else:
        print(f"   ✓ 执行类型: nextflow")

    if "duration_ms" not in metrics:
        errors.append("metrics 中缺少 duration_ms")
    else:
        print(f"   ✓ 执行耗时: {metrics['duration_ms']} ms")

    # 8. 总结
    print("\n" + "=" * 60)
    if errors:
        print("测试失败 ✗")
        print("\n发现的问题:")
        for error in errors:
            print(f"  - {error}")
        return 1
    else:
        print("测试成功 ✓")
        print("\n所有验收标准已满足：")
        print("  ✓ 适配器可正常创建和初始化")
        print("  ✓ 输入参数正确解析")
        print("  ✓ Nextflow 执行成功")
        print("  ✓ 产出合法 StepResult（含 pdb_path）")
        print("  ✓ 指标数据完整（pLDDT、执行类型、耗时）")
        return 0


if __name__ == "__main__":
    sys.exit(main())
