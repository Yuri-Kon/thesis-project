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
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# 将项目根目录添加到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.planner import PlannerAgent, _DEFAULT_TOOL_REGISTRY
from src.llm.provider_registry import create_provider, load_provider_catalog
from tests.fixtures.benchmark_tasks import BENCHMARK_TASKS

DEFAULT_CONFIG_PATH = Path("configs/llm_providers.json")


def get_available_providers(catalog) -> Dict[str, str]:
    """返回可用的 providers 及其描述"""
    providers = {}
    for name, settings in catalog.providers.items():
        providers[name] = settings.description or settings.provider_type
    return providers


def run_single_comparison(
    task,
    provider_name: str,
    provider,
    tool_registry,
    *,
    provider_settings,
) -> Dict:
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
        "provider_type": provider_settings.provider_type,
        "model": provider_settings.model_name,
        "endpoint": provider_settings.endpoint,
        "provider_config": {
            "timeout": provider_settings.timeout,
            "max_tokens": provider_settings.max_tokens,
            "temperature": provider_settings.temperature,
            "top_p": provider_settings.top_p,
            "stream": provider_settings.stream,
            "use_response_format": provider_settings.use_response_format,
            "extra_body": provider_settings.extra_body,
        },
        "task_id": task.task_id,
        "task_goal": task.goal,
        "task_constraints": task.constraints,
        "timestamp": datetime.utcnow().isoformat(),
        "elapsed_seconds": round(elapsed, 3),
        "success": success,
        "candidates": [],
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
        result["candidates"] = plan.metadata.get("candidates", [])

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
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Provider 配置文件路径 (JSON)",
    )

    args = parser.parse_args()

    # 加载 provider 配置
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = project_root / config_path
    if not config_path.exists():
        print(f"错误: 找不到配置文件 {config_path}")
        sys.exit(1)
    catalog = load_provider_catalog(config_path)

    # 解析 provider 列表
    provider_names = [p.strip() for p in args.providers.split(",") if p.strip()]

    # 显示可用的 providers
    available = get_available_providers(catalog)
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
            settings = catalog.providers[provider_name]
            print(
                f"  Provider: {provider_name} ({settings.model_name})...",
                end=" ",
            )

            try:
                provider = create_provider(
                    settings,
                    api_key_override=args.api_key,
                )
                result = run_single_comparison(
                    task,
                    provider_name,
                    provider,
                    _DEFAULT_TOOL_REGISTRY,
                    provider_settings=settings,
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
    print(
        f"{'Provider':<12} {'Model':<32} {'任务':<20} {'步骤数':<8} {'耗时 (s)':<10} {'状态'}"
    )
    print("-" * 80)

    for result in all_results:
        provider = result["provider"]
        model = result.get("model", "-")
        task_id = result["task_id"]
        steps = result.get("num_steps", "-")
        elapsed = result["elapsed_seconds"]
        status = "✓" if result["success"] else "✗"

        print(
            f"{provider:<12} {model:<32} {task_id:<20} {steps:<8} {elapsed:<10.3f} {status}"
        )

    print("=" * 80)


if __name__ == "__main__":
    main()
