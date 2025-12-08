#!/bin/bash
# 测试运行脚本

echo "运行所有测试..."
pytest tests/ -v

echo ""
echo "运行单元测试..."
pytest tests/unit/ -v -m unit

echo ""
echo "运行集成测试..."
pytest tests/integration/ -v -m integration

echo ""
echo "运行API测试..."
pytest tests/api/ -v -m api