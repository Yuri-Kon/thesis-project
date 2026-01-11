#!/bin/bash
# ESMFold Nextflow 端到端演示 - 快速运行脚本
#
# 使用方法:
#   ./run_demo.sh          # 运行模拟模式
#   ./run_demo.sh real     # 运行真实模式（需要云端服务）
#   ./run_demo.sh clean    # 清理输出目录

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印函数
print_header() {
  echo -e "${BLUE}======================================================================${NC}"
  echo -e "${BLUE}  $1${NC}"
  echo -e "${BLUE}======================================================================${NC}"
}

print_info() {
  echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
  echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
  echo -e "${RED}✗${NC} $1"
}

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 解析参数
MODE="${1:-mock}"

# 处理命令
case "$MODE" in
clean)
  print_header "清理输出目录"
  if [ -d "demo_output" ]; then
    rm -rf demo_output
    print_info "已删除 demo_output/"
  else
    print_info "输出目录不存在，无需清理"
  fi
  exit 0
  ;;

mock)
  print_header "ESMFold 端到端演示（模拟模式）"
  ;;

real)
  print_header "ESMFold 端到端演示（真实模式）"
  print_warning "真实模式需要云端服务器或本地 GPU"
  print_warning "请确保已配置环境变量："
  echo "  - ESMFOLD_API_URL"
  echo "  - ESMFOLD_API_KEY"
  echo ""
  ;;

*)
  print_error "未知模式: $MODE"
  echo ""
  echo "使用方法:"
  echo "  ./run_demo.sh          # 运行模拟模式"
  echo "  ./run_demo.sh real     # 运行真实模式"
  echo "  ./run_demo.sh clean    # 清理输出目录"
  exit 1
  ;;
esac

# 检查 Python 环境
print_info "检查 Python 环境..."
if ! command -v python &>/dev/null; then
  print_error "Python 未安装"
  exit 1
fi

PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
print_info "Python 版本: $PYTHON_VERSION"

# 检查项目依赖
print_info "检查项目依赖..."
if [ ! -f "requirements.txt" ]; then
  print_warning "requirements.txt 不存在"
else
  print_info "依赖文件存在"
fi

# 运行演示
print_header "开始运行演示"
echo ""

if [ "$MODE" = "mock" ]; then
  python examples/demo_esmfold_end_to_end.py --mode mock
else
  python examples/demo_esmfold_end_to_end.py --mode real
fi

EXIT_CODE=$?

# 显示结果
echo ""
if [ $EXIT_CODE -eq 0 ]; then
  print_header "演示完成"
  print_info "所有 artifacts 已保存到: demo_output/"
  echo ""
  echo "生成的文件:"
  if [ -d "demo_output" ]; then
    tree -L 2 demo_output/ 2>/dev/null || find demo_output/ -type f
  fi
  echo ""
  print_info "可用于论文的材料已准备好"
else
  print_header "演示失败"
  print_error "退出代码: $EXIT_CODE"
  exit $EXIT_CODE
fi
