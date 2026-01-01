#!/bin/bash
# Token cost comparison scenarios for docslice.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
cd "$SCRIPT_DIR/.."

DOCSLICE="./scripts/docslice"
DESIGN_ROOT="$REPO_ROOT/../thesis-project.design"
ARCH_DOC="$DESIGN_ROOT/docs/design/architecture.md"
AGENT_DOC="$DESIGN_ROOT/docs/design/agent-design.md"
ALGO_DOC="$DESIGN_ROOT/docs/design/core-algorithm-spec.md"
IMPL_DOC="$DESIGN_ROOT/docs/design/system-implementation-design.md"

assert_file() {
    if [ ! -f "$1" ]; then
        echo "✗ Design doc not found: $1"
        exit 1
    fi
}

assert_file "$ARCH_DOC"
assert_file "$IMPL_DOC"
assert_file "$AGENT_DOC"
assert_file "$ALGO_DOC"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

print_report() {
    local scenario="$1"
    local fragments_tsv="$2"
    local full_tsv="$3"
    python - "$scenario" "$fragments_tsv" "$full_tsv" <<'PY'
import re
import sys
from pathlib import Path

scenario = sys.argv[1]
fragments_tsv = sys.argv[2]
full_tsv = sys.argv[3]

try:
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")

    def count_text(text: str) -> int:
        return len(enc.encode(text))

    engine = "tiktoken:cl100k_base"
except ImportError:
    def count_text(text: str) -> int:
        cjk = re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text)
        text_wo_cjk = re.sub(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", "", text)
        words = re.findall(r"[A-Za-z0-9_]+", text_wo_cjk)
        text_wo_words = re.sub(r"[A-Za-z0-9_]+", "", text_wo_cjk)
        other_nonspace = re.findall(r"\S", text_wo_words)
        return len(cjk) + len(words) + len(other_nonspace)

    engine = "fallback:heuristic"

def count_path(path: str) -> int:
    return count_text(Path(path).read_text(encoding="utf-8"))

def load_tsv(path: str):
    entries = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            label, file_path = line.split("\t", 1)
            entries.append((label, file_path))
    return entries

fragments = [(label, count_path(path)) for label, path in load_tsv(fragments_tsv)]
full_docs = [(label, count_path(path)) for label, path in load_tsv(full_tsv)]

docslice_total = sum(count for _, count in fragments)
full_total = sum(count for _, count in full_docs)
delta = full_total - docslice_total
ratio = (docslice_total / full_total) if full_total else 0.0
reduction = (1.0 - ratio) * 100.0 if full_total else 0.0

print(f"Scenario: {scenario}")
print(f"Token report ({engine})")
print("DocSlice fragments:")
for label, count in fragments:
    print(f"  - {label}: {count}")
print(f"DocSlice total: {docslice_total}")
print("Full docs:")
for label, count in full_docs:
    print(f"  - {label}: {count}")
print(f"Full total: {full_total}")
print(f"Delta: {delta}")
print(f"Ratio: {ratio:.4f}")
print(f"Reduction: {reduction:.2f}%")
if engine.startswith("fallback"):
    print("Note: install tiktoken for accurate token counts (python -m pip install tiktoken)")

if docslice_total < full_total:
    print("Result: PASS (token reduced)")
    sys.exit(0)

print("Result: FAIL (token not reduced)")
sys.exit(1)
PY
}

echo "========================================"
echo "Token Cost Comparison Scenarios"
echo "========================================"
echo

SCENARIO_DIR="$TMP_DIR/scenarios"
mkdir -p "$SCENARIO_DIR"

SCENARIO_SIMPLE="$SCENARIO_DIR/simple"
mkdir -p "$SCENARIO_SIMPLE"
FRAG_SIMPLE="$SCENARIO_SIMPLE/fragments.tsv"
FULL_SIMPLE="$SCENARIO_SIMPLE/full.tsv"
COMBINED_SIMPLE="$SCENARIO_SIMPLE/combined.txt"
: > "$FRAG_SIMPLE"
: > "$FULL_SIMPLE"
: > "$COMBINED_SIMPLE"
printf "architecture.md\t%s\n" "$ARCH_DOC" >> "$FULL_SIMPLE"
printf "system-implementation-design.md\t%s\n" "$IMPL_DOC" >> "$FULL_SIMPLE"
SIMPLE_SIDS=(
    "fsm.states.definitions"
    "arch.contracts.decision"
    "obs.eventlog.schema"
)
for SID in "${SIMPLE_SIDS[@]}"; do
    OUT_PATH="$SCENARIO_SIMPLE/${SID//./_}.txt"
    "$DOCSLICE" --sid "$SID" > "$OUT_PATH"
    printf "%s\t%s\n" "$SID" "$OUT_PATH" >> "$FRAG_SIMPLE"
    cat "$OUT_PATH" >> "$COMBINED_SIMPLE"
    echo >> "$COMBINED_SIMPLE"
done
if ! grep -q "状态列表" "$COMBINED_SIMPLE"; then
    echo "✗ Simple scenario missing FSM definitions"
    exit 1
fi
print_report "简单场景：基本 token 消耗比较" "$FRAG_SIMPLE" "$FULL_SIMPLE"
echo

SCENARIO_MEDIUM="$SCENARIO_DIR/medium"
mkdir -p "$SCENARIO_MEDIUM"
FRAG_MEDIUM="$SCENARIO_MEDIUM/fragments.tsv"
FULL_MEDIUM="$SCENARIO_MEDIUM/full.tsv"
COMBINED_MEDIUM="$SCENARIO_MEDIUM/combined.txt"
: > "$FRAG_MEDIUM"
: > "$FULL_MEDIUM"
: > "$COMBINED_MEDIUM"
printf "architecture.md\t%s\n" "$ARCH_DOC" >> "$FULL_MEDIUM"
printf "system-implementation-design.md\t%s\n" "$IMPL_DOC" >> "$FULL_MEDIUM"
MEDIUM_SIDS=(
    "arch.contracts.pending_action"
    "arch.contracts.decision"
    "fsm.transitions.overview"
    "obs.eventlog.mandatory_events"
)
for SID in "${MEDIUM_SIDS[@]}"; do
    OUT_PATH="$SCENARIO_MEDIUM/${SID//./_}.txt"
    "$DOCSLICE" --sid "$SID" > "$OUT_PATH"
    printf "%s\t%s\n" "$SID" "$OUT_PATH" >> "$FRAG_MEDIUM"
    cat "$OUT_PATH" >> "$COMBINED_MEDIUM"
    echo >> "$COMBINED_MEDIUM"
done
if ! grep -q "PendingAction" "$COMBINED_MEDIUM"; then
    echo "✗ Medium scenario missing PendingAction"
    exit 1
fi
if ! grep -q "Decision" "$COMBINED_MEDIUM"; then
    echo "✗ Medium scenario missing Decision"
    exit 1
fi
if ! grep -q "状态转换规则" "$COMBINED_MEDIUM"; then
    echo "✗ Medium scenario missing FSM transitions overview"
    exit 1
fi
if ! grep -q "事件日志" "$COMBINED_MEDIUM"; then
    echo "✗ Medium scenario missing event log requirements"
    exit 1
fi
print_report "中等场景：可用性检验与性能测试" "$FRAG_MEDIUM" "$FULL_MEDIUM"
echo

SCENARIO_ADVANCED="$SCENARIO_DIR/advanced"
mkdir -p "$SCENARIO_ADVANCED"
FRAG_ADVANCED="$SCENARIO_ADVANCED/fragments.tsv"
FULL_ADVANCED="$SCENARIO_ADVANCED/full.tsv"
COMBINED_ADVANCED="$SCENARIO_ADVANCED/combined.txt"
: > "$FRAG_ADVANCED"
: > "$FULL_ADVANCED"
: > "$COMBINED_ADVANCED"
printf "architecture.md\t%s\n" "$ARCH_DOC" >> "$FULL_ADVANCED"
printf "agent-design.md\t%s\n" "$AGENT_DOC" >> "$FULL_ADVANCED"
printf "core-algorithm-spec.md\t%s\n" "$ALGO_DOC" >> "$FULL_ADVANCED"
printf "system-implementation-design.md\t%s\n" "$IMPL_DOC" >> "$FULL_ADVANCED"

TOPIC_OUT="$SCENARIO_ADVANCED/topic_hitl.txt"
"$DOCSLICE" --topic hitl --max-lines 200 > "$TOPIC_OUT" 2>&1
printf "topic:hitl(max-lines=200)\t%s\n" "$TOPIC_OUT" >> "$FRAG_ADVANCED"
cat "$TOPIC_OUT" >> "$COMBINED_ADVANCED"
echo >> "$COMBINED_ADVANCED"

REF_OUT="$SCENARIO_ADVANCED/ref_fsm_lifecycle.txt"
"$DOCSLICE" --ref "DOC:arch#任务生命周期与状态机(FSM)" > "$REF_OUT"
printf "ref:arch#任务生命周期与状态机(FSM)\t%s\n" "$REF_OUT" >> "$FRAG_ADVANCED"
cat "$REF_OUT" >> "$COMBINED_ADVANCED"
echo >> "$COMBINED_ADVANCED"

PLANNING_OUT="$SCENARIO_ADVANCED/topic_planning.txt"
"$DOCSLICE" --topic planning --max-chars 4000 > "$PLANNING_OUT" 2>&1
printf "topic:planning(max-chars=4000)\t%s\n" "$PLANNING_OUT" >> "$FRAG_ADVANCED"
cat "$PLANNING_OUT" >> "$COMBINED_ADVANCED"
echo >> "$COMBINED_ADVANCED"

if ! grep -q "Topic: hitl" "$COMBINED_ADVANCED"; then
    echo "✗ Advanced scenario missing hitl topic output"
    exit 1
fi
if ! grep -q "任务生命周期与状态机" "$COMBINED_ADVANCED"; then
    echo "✗ Advanced scenario missing FSM lifecycle section"
    exit 1
fi
if ! grep -q "Topic: planning" "$COMBINED_ADVANCED"; then
    echo "✗ Advanced scenario missing planning topic output"
    exit 1
fi
print_report "高级场景：复杂文档结构和性能优化" "$FRAG_ADVANCED" "$FULL_ADVANCED"
echo

echo "========================================"
echo "All token comparison scenarios completed ✓"
echo "========================================"
