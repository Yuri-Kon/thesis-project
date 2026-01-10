#!/usr/bin/env python3
"""对比不同 LLM providers 的规划能力

此脚本通过不同的 providers 运行 3 个固定的基准测试任务
并输出可复现的对比日志。

用法:
    python scripts/compare_providers.py [--output OUTPUT_DIR] [--providers PROVIDER1,PROVIDER2,...]

示例:
    python scripts/compare_providers.py --output logs/provider_comparison
    python scripts/compare_providers.py --providers baseline,openai
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# 将项目根目录添加到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.planner import PlannerAgent, _DEFAULT_TOOL_REGISTRY
from src.llm.baseline_provider import BaselineProvider
from src.llm.base_llm_provider import ProviderConfig
from tests.fixtures.benchmark_tasks import BENCHMARK_TASKS


def get_available_providers() -> Dict[str, str]:
    """返回可用的 providers 及其描述"""
    providers = {"baseline": "简单确定性基线 provider"}

    # 检查 openai 是否可用
    try:
        from src.llm.openai_compatible_provider import OpenAICompatibleProvider

        providers["openai"] = "OpenAI 兼容 provider (GPT-4, 等)"
        providers["nemotron"] = "NVIDIA Nemotron via OpenAI 兼容 API (NIM_API_KEY)"
    except ImportError:
        pass

    return providers


def create_provider(name: str, api_key: Optional[str] = None) -> object:
    """根据名称创建 provider 实例

    Args:
        name: Provider 名称 (baseline, openai, nemotron)
        api_key: LLM providers 的可选 API 密钥

    Returns:
        Provider 实例

    Raises:
        ValueError: 如果 provider 名称未知
    """
    if name == "baseline":
        config = ProviderConfig(model_name="baseline")
        from src.llm.baseline_provider import BaselineProvider

        return BaselineProvider(config)

    elif name == "openai":
        from src.llm.openai_compatible_provider import OpenAICompatibleProvider

        config = ProviderConfig(
            model_name="gpt-4o-mini",
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            timeout=30,
            max_tokens=2000,
        )
        return OpenAICompatibleProvider(config)

    elif name == "nemotron":
        from src.llm.openai_compatible_provider import OpenAICompatibleProvider

        config = ProviderConfig(
            model_name="nvidia/nemotron-3-nano-30b-a3b",
            api_key=api_key or os.getenv("NIM_API_KEY") or os.getenv("NVIDIA_API_KEY"),
            timeout=300,
            max_tokens=4096,
            temperature=1.0,
            top_p=1.0,
            stream=False,
            # extra_body={
            #     "reasoning_budget": 16384,
            #     "chat_template_kwargs": {"enable_thinking": True},
            # },
            use_response_format=True,
        )
        endpoint = os.getenv(
            "NVIDIA_API_ENDPOINT", "https://integrate.api.nvidia.com/v1"
        )
        return OpenAICompatibleProvider(config, endpoint=endpoint)

    else:
        raise ValueError(f"Unknown provider: {name}")


def run_single_comparison(task, provider_name: str, provider, tool_registry) -> Dict:
    """通过 provider 运行单个任务并收集指标

    Args:
        task: 要处理的 ProteinDesignTask
        provider_name: Provider 的名称
        provider: Provider 实例
        tool_registry: 使用的工具注册表

    Returns:
        包含对比结果的 Dict
    """
    planner = PlannerAgent(tool_registry=tool_registry, llm_provider=provider)

    # 运行规划并测量时间
    start_time = time.time()
    try:
        plan = planner.plan(task)
        elapsed = time.time() - start_time
        success = True
        error = None
    except Exception as e:
        elapsed = time.time() - start_time
        success = False
        error = str(e)
        plan = None

    # 构建结果
    result = {
        "provider": provider_name,
        "task_id": task.task_id,
        "task_goal": task.goal,
        "task_constraints": task.constraints,
        "timestamp": datetime.utcnow().isoformat(),
        "elapsed_seconds": round(elapsed, 3),
        "success": success,
    }

    if success and plan:
        result["plan"] = {
            "task_id": plan.task_id,
            "steps": [
                {
                    "id": step.id,
                    "tool": step.tool,
                    "inputs": step.inputs,
                    "metadata": step.metadata,
                }
                for step in plan.steps
            ],
            "constraints": plan.constraints,
            "metadata": plan.metadata,
        }
        result["num_steps"] = len(plan.steps)
        result["tools_used"] = [step.tool for step in plan.steps]

        # 如果有说明则提取
        if "explanation" in plan.metadata:
            result["explanation"] = plan.metadata["explanation"]
    else:
        result["error"] = error

    return result


def main():
    parser = argparse.ArgumentParser(description="对比蛋白质设计规划的 LLM providers")
    parser.add_argument(
        "--output", "-o", default="logs/provider_comparison", help="对比日志的输出目录"
    )
    parser.add_argument(
        "--providers",
        "-p",
        default="baseline",
        help="要对比的 providers 的逗号分隔列表 (默认: baseline)",
    )
    parser.add_argument(
        "--api-key", help="LLM providers 的 API 密钥 (或通过环境变量设置)"
    )

    args = parser.parse_args()

    # 解析 provider 列表
    provider_names = [p.strip() for p in args.providers.split(",")]

    # 显示可用的 providers
    available = get_available_providers()
    print("可用的 providers:")
    for name, desc in available.items():
        print(f"  - {name}: {desc}")
    print()

    # 验证 providers
    for name in provider_names:
        if name not in available:
            print(f"错误: 未知的 provider '{name}'")
            print(f"可用: {', '.join(available.keys())}")
            sys.exit(1)

    # 创建输出目录
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 为此次运行创建时间戳
    run_timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # 运行对比
    all_results = []

    print(
        f"使用 {len(provider_names)} 个 provider(s) 运行 {len(BENCHMARK_TASKS)} 个基准测试任务...\n"
    )

    for task in BENCHMARK_TASKS:
        print(f"任务: {task.task_id} - {task.goal}")

        for provider_name in provider_names:
            print(f"  Provider: {provider_name}...", end=" ")

            try:
                provider = create_provider(provider_name, args.api_key)
                result = run_single_comparison(
                    task, provider_name, provider, _DEFAULT_TOOL_REGISTRY
                )
                all_results.append(result)

                if result["success"]:
                    print(f"✓ ({result['elapsed_seconds']}s, {result['num_steps']} 步)")
                else:
                    print(f"✗ 错误: {result.get('error', '未知')}")

            except Exception as e:
                print(f"✗ 创建 provider 失败: {e}")
                continue

        print()

    # 将结果写入 JSON Lines 格式
    jsonl_path = output_dir / f"comparison_{run_timestamp}.jsonl"
    with open(jsonl_path, "w") as f:
        for result in all_results:
            f.write(json.dumps(result) + "\n")

    print(f"结果已写入: {jsonl_path}")

    # 写入摘要报告
    summary_path = output_dir / f"summary_{run_timestamp}.json"
    summary = {
        "run_timestamp": run_timestamp,
        "providers": provider_names,
        "tasks": [task.task_id for task in BENCHMARK_TASKS],
        "total_runs": len(all_results),
        "results": all_results,
    }

    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"摘要已写入: {summary_path}")

    # 打印摘要表格
    print("\n" + "=" * 80)
    print("摘要")
    print("=" * 80)
    print(f"{'Provider':<15} {'任务':<20} {'步骤数':<8} {'耗时 (s)':<10} {'状态'}")
    print("-" * 80)

    for result in all_results:
        provider = result["provider"]
        task_id = result["task_id"]
        steps = result.get("num_steps", "-")
        elapsed = result["elapsed_seconds"]
        status = "✓" if result["success"] else "✗"

        print(f"{provider:<15} {task_id:<20} {steps:<8} {elapsed:<10.3f} {status}")

    print("=" * 80)


if __name__ == "__main__":
    main()
