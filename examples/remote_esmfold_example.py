"""
Remote ESMFold Adapter 使用示例

本示例展示如何使用 RemoteESMFoldAdapter 通过远程 REST API 调用 ESMFold 服务。
"""
from pathlib import Path

from src.adapters.remote_esmfold_adapter import RemoteESMFoldAdapter
from src.models.contracts import PlanStep, ProteinDesignTask
from src.workflow.context import WorkflowContext


def example_remote_esmfold_usage():
    """展示如何使用 RemoteESMFoldAdapter"""

    # 1. 创建远程适配器（使用 base_url）
    adapter = RemoteESMFoldAdapter(
        base_url="http://esmfold-service.example.com:8000",
        output_dir=Path("output/remote"),
    )

    # 2. 创建任务和上下文
    task = ProteinDesignTask(
        task_id="task_001",
        goal="Predict structure for a test sequence",
        constraints={},
    )
    context = WorkflowContext(task=task)

    # 3. 定义计划步骤
    step = PlanStep(
        id="S1",
        tool="esmfold",
        inputs={
            "sequence": "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV"
        },
        metadata={},
    )

    # 4. 解析输入
    resolved_inputs = adapter.resolve_inputs(step, context)
    print(f"Resolved inputs: {resolved_inputs}")

    # 5. 执行远程预测
    # 注意：这将提交作业、轮询状态、并下载结果
    # 实际使用时需要确保远程服务可用
    try:
        outputs, metrics = adapter.run_local(resolved_inputs)

        print(f"Prediction completed!")
        print(f"Outputs: {outputs}")
        print(f"Metrics: {metrics}")

        # 6. 访问结果
        if "pdb_path" in outputs:
            print(f"PDB file saved to: {outputs['pdb_path']}")

        if "artifacts" in outputs:
            print(f"Artifacts: {outputs['artifacts']}")

    except Exception as e:
        print(f"Remote prediction failed: {e}")


def example_custom_remote_service():
    """展示如何使用自定义的 RemoteModelInvocationService"""
    from src.engines.remote_model_service import RESTModelInvocationService

    # 创建自定义配置的 REST 服务
    service = RESTModelInvocationService(
        base_url="http://custom-service.example.com:8000",
        timeout=60.0,  # 60秒超时
        poll_interval=10.0,  # 每10秒轮询一次
        max_poll_attempts=30,  # 最多轮询30次（总共5分钟）
    )

    # 使用自定义服务创建适配器
    adapter = RemoteESMFoldAdapter(
        service=service,
        output_dir=Path("output/custom"),
    )

    print(f"Created adapter with custom service: {adapter}")


if __name__ == "__main__":
    print("=== Remote ESMFold Adapter Examples ===\n")

    print("Example 1: Basic usage with base_url")
    print("Note: This is a demonstration. The service URL is not real.\n")
    # example_remote_esmfold_usage()

    print("\nExample 2: Custom service configuration")
    example_custom_remote_service()

    print("\nFor actual usage, ensure:")
    print("1. The remote service is running and accessible")
    print("2. The service implements the expected REST API endpoints:")
    print("   - POST /predict - Submit job")
    print("   - GET /job/{job_id} - Poll status")
    print("   - GET /results/{job_id} - Download results")
