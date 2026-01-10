#!/usr/bin/env python
"""
ESMFold Nextflow 端到端演示（含 HITL）

这是一个完整的端到端演示脚本，展示：
1. 完整工作流：Task → Plan → Execute (ESMFold) → Summarize → DONE
2. HITL (Human-in-the-Loop) 交互
3. FSM 状态流转
4. Artifacts 和 EventLog 生成

使用方法：
    # 模拟模式（本地测试，不需要实际 GPU）
    python examples/demo_esmfold_end_to_end.py --mode mock

    # 真实模式（需要云端服务器或本地 GPU）
    python examples/demo_esmfold_end_to_end.py --mode real

环境要求：
    - Python 3.10+
    - Nextflow 已安装（真实模式）
    - 项目依赖已安装

输出：
    - demo_output/: 包含所有 artifacts、logs、reports
    - demo_output/screenshots/: 可用于论文的关键截图素材
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.contracts import ProteinDesignTask
from src.adapters.builtins import ensure_builtin_adapters
from src.agents.planner import PlannerAgent
from src.agents.executor import ExecutorAgent
from src.agents.summarizer import SummarizerAgent
from src.workflow.context import WorkflowContext
from src.models.db import InternalStatus, ExternalStatus, TaskRecord
from src.models.contracts import now_iso


# ============================================================================
# 云端服务接口（预留）
# ============================================================================

class RemoteESMFoldService:
    """云端 ESMFold 服务接口（预留）

    TODO: 实现云端服务器的实际调用逻辑

    可能的实现方式：
    1. REST API: 调用远程服务器的 HTTP 接口
    2. gRPC: 高性能 RPC 调用
    3. SSH + Nextflow: 远程执行 Nextflow 命令
    4. 云平台 SDK: AWS Batch, Google Cloud Life Sciences, Azure Batch

    示例 API 设计：
        POST /api/v1/predict
        {
            "sequence": "MKFLKF...",
            "task_id": "task_001",
            "callback_url": "https://my-server.com/callback"
        }

        Response:
        {
            "job_id": "job_12345",
            "status": "queued",
            "estimated_time_seconds": 300
        }
    """

    def __init__(self, api_url: str, api_key: str):
        """初始化云端服务客户端

        Args:
            api_url: 云端服务的 API 地址
            api_key: API 认证密钥
        """
        self.api_url = api_url
        self.api_key = api_key

    def submit_job(self, sequence: str, task_id: str) -> Dict[str, Any]:
        """提交 ESMFold 预测任务到云端

        TODO: 实现实际的 HTTP/gRPC 调用

        Args:
            sequence: 蛋白质序列
            task_id: 任务 ID

        Returns:
            包含 job_id 和状态的字典
        """
        # TODO: 实现 REST API 调用
        # import requests
        # response = requests.post(
        #     f"{self.api_url}/api/v1/predict",
        #     headers={"Authorization": f"Bearer {self.api_key}"},
        #     json={"sequence": sequence, "task_id": task_id}
        # )
        # return response.json()

        print("    [TODO] 实现云端 API 调用")
        raise NotImplementedError("云端服务接口待实现")

    def poll_status(self, job_id: str) -> Dict[str, Any]:
        """轮询任务状态

        TODO: 实现状态查询逻辑

        Args:
            job_id: 云端任务 ID

        Returns:
            包含状态和进度的字典
        """
        # TODO: 实现状态轮询
        # response = requests.get(
        #     f"{self.api_url}/api/v1/jobs/{job_id}",
        #     headers={"Authorization": f"Bearer {self.api_key}"}
        # )
        # return response.json()

        raise NotImplementedError("状态轮询接口待实现")

    def download_results(self, job_id: str, output_dir: Path) -> Dict[str, Any]:
        """下载预测结果

        TODO: 实现结果下载逻辑

        Args:
            job_id: 云端任务 ID
            output_dir: 本地保存目录

        Returns:
            包含文件路径和指标的字典
        """
        # TODO: 实现结果下载
        # response = requests.get(
        #     f"{self.api_url}/api/v1/jobs/{job_id}/results",
        #     headers={"Authorization": f"Bearer {self.api_key}"}
        # )
        #
        # # 下载 PDB 文件
        # pdb_content = response.json()["pdb_content"]
        # pdb_path = output_dir / f"{job_id}.pdb"
        # pdb_path.write_text(pdb_content)
        #
        # return {
        #     "pdb_path": str(pdb_path),
        #     "metrics": response.json()["metrics"]
        # }

        raise NotImplementedError("结果下载接口待实现")


# ============================================================================
# 模拟模式（用于本地测试）
# ============================================================================

class MockESMFoldService:
    """模拟 ESMFold 服务（用于本地测试，不需要 GPU）"""

    def run_mock_prediction(
        self,
        sequence: str,
        task_id: str,
        output_dir: Path
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """模拟运行 ESMFold 预测

        Args:
            sequence: 蛋白质序列
            task_id: 任务 ID
            output_dir: 输出目录

        Returns:
            (outputs, metrics): 输出字典和指标字典
        """
        print(f"    [Mock] 模拟预测序列: {sequence[:30]}...")
        print(f"    [Mock] 序列长度: {len(sequence)}")

        # 创建输出目录
        output_dir.mkdir(parents=True, exist_ok=True)

        # 模拟生成 PDB 文件
        pdb_path = output_dir / f"{task_id}.pdb"
        mock_pdb_content = f"""HEADER    MOCK STRUCTURE
TITLE     MOCK ESMFOLD PREDICTION FOR {task_id}
REMARK    THIS IS A MOCK PDB FILE FOR DEMONSTRATION
REMARK    Sequence: {sequence[:50]}...
REMARK    Sequence length: {len(sequence)}
ATOM      1  N   MET A   1      10.000  10.000  10.000  1.00 85.00           N
ATOM      2  CA  MET A   1      11.000  10.000  10.000  1.00 85.00           C
END
"""
        pdb_path.write_text(mock_pdb_content)
        print(f"    [Mock] 生成 PDB: {pdb_path}")

        # 模拟指标（基于序列长度生成合理的 pLDDT）
        mock_plddt = min(0.95, 0.60 + (len(sequence) / 500) * 0.20)

        outputs = {
            "pdb_path": str(pdb_path),
            "metrics": {
                "task_id": task_id,
                "tool": "esmfold",
                "plddt_mean": round(mock_plddt, 2),
                "confidence": "high" if mock_plddt > 0.80 else "medium",
            }
        }

        metrics = {
            "exec_type": "mock",
            "duration_ms": 1000,
            "mock_mode": True,
        }

        print(f"    [Mock] pLDDT 均值: {mock_plddt:.2f}")
        print(f"    [Mock] 预测完成")

        return outputs, metrics


# ============================================================================
# 演示主流程
# ============================================================================

class ESMFoldDemo:
    """ESMFold 端到端演示"""

    def __init__(self, mode: str = "mock", output_dir: Path = None):
        """初始化演示

        Args:
            mode: "mock" 或 "real"
            output_dir: 输出目录
        """
        self.mode = mode
        self.output_dir = output_dir or (project_root / "demo_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化服务
        if mode == "real":
            # TODO: 从环境变量或配置文件读取云端服务配置
            # api_url = os.getenv("ESMFOLD_API_URL", "https://esmfold-api.example.com")
            # api_key = os.getenv("ESMFOLD_API_KEY", "your-api-key")
            # self.service = RemoteESMFoldService(api_url, api_key)

            print("    [WARNING] 真实模式需要云端服务器或本地 GPU")
            print("    [WARNING] 云端接口尚未实现，切换到模拟模式")
            self.mode = "mock"
            self.service = MockESMFoldService()
        else:
            self.service = MockESMFoldService()

        # 初始化 Agents
        ensure_builtin_adapters()
        self.planner = PlannerAgent()
        self.executor = ExecutorAgent()
        self.summarizer = SummarizerAgent()

    def print_section(self, title: str):
        """打印分节标题"""
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)

    def print_step(self, step_num: int, description: str):
        """打印步骤"""
        print(f"\n[步骤 {step_num}] {description}")
        print("-" * 70)

    def save_artifact(self, name: str, content: Any):
        """保存 artifact"""
        artifact_path = self.output_dir / name
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(content, (dict, list)):
            artifact_path.write_text(json.dumps(content, indent=2, ensure_ascii=False))
        elif isinstance(content, str):
            artifact_path.write_text(content)
        else:
            artifact_path.write_text(str(content))

        print(f"  📄 保存 artifact: {artifact_path.relative_to(self.output_dir)}")

    def run_success_scenario(self):
        """演示成功场景：完整的 ESMFold 预测流程"""
        self.print_section("场景 1: 成功流程")

        # 步骤 1: 创建任务
        self.print_step(1, "创建蛋白质设计任务")
        task = ProteinDesignTask(
            task_id=f"demo_success_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            goal="使用 ESMFold 预测给定序列的蛋白质三维结构",
            constraints={
                "sequence": "MKFLKFSLLTAVLLSVVFAFSSCGDDDDTGYLPPSQAIQDLLKRMKV",
                "method": "esmfold",
            },
            metadata={
                "demo": True,
                "scenario": "success",
            }
        )
        print(f"  ✓ Task ID: {task.task_id}")
        print(f"  ✓ Goal: {task.goal}")
        print(f"  ✓ Sequence: {task.constraints['sequence'][:30]}...")
        print(f"  ✓ Sequence length: {len(task.constraints['sequence'])}")

        self.save_artifact("task.json", task.model_dump())

        # 步骤 2: 创建工作流上下文
        self.print_step(2, "初始化工作流上下文")
        ctx = WorkflowContext(
            task=task,
            plan=None,
            step_results={},
            safety_events=[],
            design_result=None,
            status=InternalStatus.CREATED,
        )

        record = TaskRecord(
            id=task.task_id,
            status=ExternalStatus.CREATED,
            internal_status=InternalStatus.CREATED,
            created_at=now_iso(),
            updated_at=now_iso(),
            goal=task.goal,
            constraints=task.constraints,
            metadata=task.metadata,
            plan=None,
            design_result=None,
            safety_events=[],
        )
        print(f"  ✓ Context 创建成功")
        print(f"  ✓ Status: {ctx.status}")

        # 步骤 3: 规划
        self.print_step(3, "PlannerAgent 生成执行计划")
        plan = self.planner.plan_with_status(task, ctx, record=record)
        print(f"  ✓ Plan 生成成功")
        print(f"  ✓ 步骤数: {len(plan.steps)}")
        for step in plan.steps:
            print(f"     - {step.id}: {step.tool}")
            print(f"       Inputs: {step.inputs}")

        self.save_artifact("plan.json", plan.model_dump())

        # 步骤 4: 执行（使用模拟或真实服务）
        self.print_step(4, f"ExecutorAgent 执行计划 ({self.mode} 模式)")

        if self.mode == "mock":
            # 模拟执行
            print(f"  → 使用模拟服务（本地测试）")
            outputs, metrics = self.service.run_mock_prediction(
                sequence=task.constraints["sequence"],
                task_id=task.task_id,
                output_dir=self.output_dir / "pdb"
            )

            # 手动构造 StepResult（模拟 Executor 的行为）
            from src.models.contracts import StepResult
            step_result = StepResult(
                task_id=task.task_id,
                step_id="S1",
                tool="esmfold",
                status="success",
                failure_type=None,
                error_message=None,
                error_details={},
                outputs=outputs,
                metrics=metrics,
                risk_flags=[],
                logs_path=None,
                timestamp=now_iso(),
            )
            ctx.step_results["S1"] = step_result

        else:
            # 真实执行
            # TODO: 调用云端服务
            print(f"  → 提交任务到云端服务")
            print(f"  → [TODO] 实现云端服务调用")
            raise NotImplementedError("真实模式需要云端服务")

        print(f"  ✓ 执行完成")
        print(f"  ✓ PDB 路径: {outputs['pdb_path']}")
        print(f"  ✓ pLDDT: {outputs['metrics']['plddt_mean']}")

        self.save_artifact("step_results.json", {
            "S1": ctx.step_results["S1"].model_dump()
        })

        # 步骤 5: 汇总
        self.print_step(5, "SummarizerAgent 汇总结果")
        design_result = self.summarizer.summarize(ctx)
        print(f"  ✓ DesignResult 生成成功")
        print(f"  ✓ Task ID: {design_result.task_id}")
        print(f"  ✓ Structure PDB: {design_result.structure_pdb_path}")
        print(f"  ✓ Scores: {design_result.scores}")
        print(f"  ✓ Report: {design_result.report_path}")

        self.save_artifact("design_result.json", design_result.model_dump())

        # 步骤 6: 更新状态
        self.print_step(6, "更新任务状态 → DONE")
        record.status = ExternalStatus.DONE
        record.internal_status = InternalStatus.DONE
        record.design_result = design_result
        record.updated_at = now_iso()
        print(f"  ✓ Status: {record.status}")

        self.save_artifact("final_record.json", {
            "id": record.id,
            "status": record.status,
            "internal_status": record.internal_status,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "goal": record.goal,
            "design_result": design_result.model_dump() if design_result else None,
        })

        # 总结
        print("\n" + "=" * 70)
        print("  ✓✓✓ 成功场景完成 ✓✓✓")
        print("=" * 70)
        print(f"\n  完整流程:")
        print(f"    CREATED → PLANNED → RUNNING → SUMMARIZING → DONE")
        print(f"\n  生成的 Artifacts:")
        print(f"    - {self.output_dir}/task.json")
        print(f"    - {self.output_dir}/plan.json")
        print(f"    - {self.output_dir}/step_results.json")
        print(f"    - {self.output_dir}/design_result.json")
        print(f"    - {self.output_dir}/final_record.json")
        print(f"    - {outputs['pdb_path']}")
        print(f"\n  📊 关键指标:")
        print(f"    - pLDDT 均值: {outputs['metrics']['plddt_mean']}")
        print(f"    - 置信度: {outputs['metrics']['confidence']}")
        print(f"    - 执行模式: {self.mode}")

        return record

    def run(self):
        """运行完整演示"""
        self.print_section("ESMFold Nextflow 端到端演示")
        print(f"  模式: {self.mode}")
        print(f"  输出目录: {self.output_dir}")
        print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 运行成功场景
        record = self.run_success_scenario()

        # TODO: 添加失败场景和 HITL 演示
        # self.run_failure_scenario_with_hitl()

        # 最终总结
        self.print_section("演示完成")
        print(f"\n  所有 artifacts 已保存到: {self.output_dir}")
        print(f"\n  可用于论文的材料:")
        print(f"    - 完整的 JSON 日志（task, plan, results）")
        print(f"    - PDB 结构文件")
        print(f"    - 汇总报告")
        print(f"\n  📌 后续步骤:")
        print(f"    1. 实现云端服务接口（见 RemoteESMFoldService）")
        print(f"    2. 添加失败场景演示")
        print(f"    3. 添加 HITL 交互演示")
        print(f"    4. 生成可视化报告")


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="ESMFold Nextflow 端到端演示（含 HITL）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["mock", "real"],
        default="mock",
        help="运行模式: mock (模拟) 或 real (真实云端服务)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="输出目录（默认: demo_output/）",
    )

    args = parser.parse_args()

    # 运行演示
    demo = ESMFoldDemo(mode=args.mode, output_dir=args.output_dir)
    try:
        demo.run()
        return 0
    except NotImplementedError as e:
        print(f"\n❌ 错误: {e}")
        print(f"\n💡 提示: 使用 --mode mock 运行模拟模式")
        return 1
    except Exception as e:
        print(f"\n❌ 未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
