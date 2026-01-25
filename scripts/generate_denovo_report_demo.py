#!/usr/bin/env python3
"""生成 de novo 设计报告的演示脚本

生成两份报告：
1. 成功的 de novo 设计任务
2. 失败并进入 WAITING_* 的任务
"""
from pathlib import Path

from src.models.contracts import (
    ProteinDesignTask,
    Plan,
    PlanStep,
    StepResult,
    SafetyResult,
    RiskFlag,
    now_iso,
)
from src.workflow.context import WorkflowContext
from src.agents.summarizer import (
    generate_de_novo_report,
    write_de_novo_reports,
    SummarizerAgent,
)


def create_success_scenario():
    """创建成功场景的报告"""
    print("=" * 60)
    print("生成成功场景报告")
    print("=" * 60)

    # 创建任务
    task = ProteinDesignTask(
        task_id="denovo_success_001",
        goal="de_novo_design",
        constraints={
            "goal_type": "de_novo_design",
            "length_range": [50, 80],
            "description": "设计一个稳定的 alpha 螺旋蛋白",
        },
        metadata={
            "created_by": "demo_script",
            "experiment": "thesis_week5",
        },
    )

    # 创建计划
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="protein_mpnn",
                inputs={
                    "goal": "de_novo_design",
                    "length_range": [50, 80],
                },
                metadata={"description": "使用 ProteinMPNN 进行序列设计"},
            ),
            PlanStep(
                id="S2",
                tool="esmfold",
                inputs={"sequence": "S1.sequence"},
                metadata={"description": "使用 ESMFold 预测结构"},
            ),
        ],
        constraints=task.constraints,
        metadata={"plan_version": "v1"},
        explanation="de_novo_design 任务采用序列设计→结构预测两步链路。",
    )

    # 创建上下文
    context = WorkflowContext(
        task=task,
        plan=plan,
        step_results={},
        safety_events=[],
    )

    # 模拟序列设计结果
    designed_sequence = (
        "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLRAPGAADDKELVAQIAK"
        "QQHNIAGQDPSSVKDHVPLMSQQEGLFDEIIQR"
    )
    mpnn_result = StepResult(
        task_id=task.task_id,
        step_id="S1",
        tool="protein_mpnn",
        status="success",
        inputs={
            "goal": "de_novo_design",
            "length_range": [50, 80],
        },
        outputs={
            "sequence": designed_sequence,
            "sequence_score": -2.34,
            "candidates": [
                {"sequence": designed_sequence, "score": -2.34},
            ],
        },
        metrics={
            "exec_type": "python",
            "duration_ms": 1523,
            "backend": "local_gpu",
        },
        risk_flags=[],
        timestamp=now_iso(),
    )
    context.step_results["S1"] = mpnn_result

    # 模拟结构预测结果
    esmfold_result = StepResult(
        task_id=task.task_id,
        step_id="S2",
        tool="esmfold",
        status="success",
        inputs={"sequence": designed_sequence},
        outputs={
            "pdb_path": "output/pdb/denovo_success_001.pdb",
            "metrics": {
                "task_id": task.task_id,
                "tool": "esmfold",
                "plddt_mean": 0.87,
                "confidence": "high",
                "residue_count": len(designed_sequence),
            },
        },
        metrics={
            "exec_type": "nextflow",
            "duration_ms": 45230,
            "provider": "local",
        },
        risk_flags=[],
        timestamp=now_iso(),
    )
    context.step_results["S2"] = esmfold_result

    # 生成报告
    report = generate_de_novo_report(context)
    report_dir = Path("output/reports")
    json_path, md_path = write_de_novo_reports(report, report_dir)

    print(f"JSON 报告: {json_path}")
    print(f"Markdown 报告: {md_path}")
    print()
    print("Markdown 报告内容:")
    print("-" * 40)
    print(md_path.read_text())

    return json_path, md_path


def create_failure_scenario():
    """创建失败场景的报告"""
    print("\n" + "=" * 60)
    print("生成失败场景报告")
    print("=" * 60)

    # 创建任务
    task = ProteinDesignTask(
        task_id="denovo_failure_001",
        goal="de_novo_design",
        constraints={
            "goal_type": "de_novo_design",
            "length_range": [100, 150],
            "description": "设计一个较长的膜蛋白序列",
        },
        metadata={
            "created_by": "demo_script",
            "experiment": "thesis_week5",
        },
    )

    # 创建计划
    plan = Plan(
        task_id=task.task_id,
        steps=[
            PlanStep(
                id="S1",
                tool="protein_mpnn",
                inputs={
                    "goal": "de_novo_design",
                    "length_range": [100, 150],
                },
                metadata={},
            ),
            PlanStep(
                id="S2",
                tool="esmfold",
                inputs={"sequence": "S1.sequence"},
                metadata={},
            ),
        ],
        constraints=task.constraints,
        metadata={"plan_version": "v1"},
    )

    # 创建上下文
    context = WorkflowContext(
        task=task,
        plan=plan,
        step_results={},
        safety_events=[],
    )

    # S1 成功
    partial_sequence = "MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQLRAPGAADDKELVAQIAK" * 2
    mpnn_result = StepResult(
        task_id=task.task_id,
        step_id="S1",
        tool="protein_mpnn",
        status="success",
        inputs={"goal": "de_novo_design", "length_range": [100, 150]},
        outputs={
            "sequence": partial_sequence,
            "sequence_score": -1.89,
        },
        metrics={"exec_type": "python", "duration_ms": 2341},
        risk_flags=[],
        timestamp=now_iso(),
    )
    context.step_results["S1"] = mpnn_result

    # S2 失败
    esmfold_result = StepResult(
        task_id=task.task_id,
        step_id="S2",
        tool="esmfold",
        status="failed",
        failure_type="tool_execution_error",
        error_message="CUDA out of memory. Tried to allocate 2.5 GiB.",
        error_details={
            "cuda_error": "OutOfMemoryError",
            "requested_memory": "2.5 GiB",
            "available_memory": "1.2 GiB",
        },
        inputs={"sequence": partial_sequence},
        outputs={},
        metrics={"exec_type": "nextflow", "duration_ms": 12340},
        risk_flags=[],
        timestamp=now_iso(),
    )
    context.step_results["S2"] = esmfold_result

    # 添加安全事件（模拟系统进入 WAITING_PATCH 状态）
    safety_event = SafetyResult(
        task_id=task.task_id,
        phase="step",
        scope="step:S2",
        risk_flags=[
            RiskFlag(
                level="warn",
                code="RESOURCE_EXHAUSTED",
                message="GPU 内存不足，建议使用远程 NIM 服务或减少序列长度",
                scope="step",
                step_id="S2",
                details={"suggestion": "use_nim_fallback"},
            )
        ],
        action="warn",
        timestamp=now_iso(),
    )
    context.safety_events.append(safety_event)

    # 生成报告
    report = generate_de_novo_report(context)
    report_dir = Path("output/reports")
    json_path, md_path = write_de_novo_reports(report, report_dir)

    print(f"JSON 报告: {json_path}")
    print(f"Markdown 报告: {md_path}")
    print()
    print("Markdown 报告内容:")
    print("-" * 40)
    print(md_path.read_text())

    return json_path, md_path


def main():
    """主函数"""
    print("De Novo 设计报告生成演示")
    print("=" * 60)

    # 确保输出目录存在
    Path("output/reports").mkdir(parents=True, exist_ok=True)

    # 生成两种场景的报告
    success_json, success_md = create_success_scenario()
    failure_json, failure_md = create_failure_scenario()

    print("\n" + "=" * 60)
    print("生成完成！")
    print("=" * 60)
    print(f"成功场景: {success_md}")
    print(f"失败场景: {failure_md}")


if __name__ == "__main__":
    main()
