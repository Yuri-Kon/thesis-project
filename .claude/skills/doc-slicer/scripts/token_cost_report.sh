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

now_ns() {
    date +%s%N
}

file_sha() {
    python - "$1" <<'PY'
import hashlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
print(hashlib.sha256(path.read_bytes()).hexdigest())
PY
}

scenario_setup() {
    local name="$1"
    SCENARIO_DIR="$TMP_DIR/scenarios/$name"
    FRAG_TSV="$SCENARIO_DIR/fragments.tsv"
    FULL_TSV="$SCENARIO_DIR/full.tsv"
    COMBINED_OUT="$SCENARIO_DIR/combined.txt"
    mkdir -p "$SCENARIO_DIR"
    : >"$FRAG_TSV"
    : >"$FULL_TSV"
    : >"$COMBINED_OUT"
}

add_full_doc() {
    local label="$1"
    local path="$2"
    printf "%s\t%s\n" "$label" "$path" >>"$FULL_TSV"
}

run_docslice() {
    local label="$1"
    local out_path="$2"
    shift 2
    local start_ns end_ns duration_ms sha bytes
    start_ns="$(now_ns)"
    "$DOCSLICE" "$@" >"$out_path" 2>&1
    end_ns="$(now_ns)"
    duration_ms=$(( (end_ns - start_ns) / 1000000 ))
    bytes="$(wc -c < "$out_path" | tr -d ' ')"
    sha="$(file_sha "$out_path")"
    printf "%s\t%s\t%s\t%s\t%s\n" "$label" "$out_path" "$duration_ms" "$sha" "$bytes" >>"$FRAG_TSV"
    cat "$out_path" >>"$COMBINED_OUT"
    echo >>"$COMBINED_OUT"
}

assert_contains() {
    local file="$1"
    local pattern="$2"
    local message="$3"
    if ! grep -Fq "$pattern" "$file"; then
        echo "✗ $message"
        echo "  Pattern: $pattern"
        echo "  File: $file"
        echo "  Preview:"
        head -n 20 "$file" | sed 's/^/  /'
        exit 1
    fi
}

assert_table() {
    local file="$1"
    local message="$2"
    if grep -Fq "|---" "$file" || grep -Fq "|:---" "$file"; then
        return 0
    fi
    echo "✗ $message"
    echo "  Pattern: |--- or |:---"
    echo "  File: $file"
    echo "  Preview:"
    head -n 20 "$file" | sed 's/^/  /'
    exit 1
}

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

def load_fragments(path: str):
    entries = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            label, file_path, duration_ms, sha256, bytes_len = line.split("\t", 4)
            entries.append((label, file_path, int(duration_ms), sha256, int(bytes_len)))
    return entries

def load_full(path: str):
    entries = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            label, file_path = line.split("\t", 1)
            entries.append((label, file_path))
    return entries

frag_rows = []
for label, path, duration_ms, sha256, bytes_len in load_fragments(fragments_tsv):
    tokens = count_path(path)
    frag_rows.append((label, tokens, duration_ms, sha256, bytes_len))

full_rows = []
for label, path in load_full(full_tsv):
    tokens = count_path(path)
    bytes_len = Path(path).stat().st_size
    full_rows.append((label, tokens, bytes_len))

docslice_total = sum(tokens for _, tokens, _, _, _ in frag_rows)
full_total = sum(tokens for _, tokens, _ in full_rows)
docslice_bytes = sum(bytes_len for _, _, _, _, bytes_len in frag_rows)
full_bytes = sum(bytes_len for _, _, bytes_len in full_rows)
docslice_time = sum(duration_ms for _, _, duration_ms, _, _ in frag_rows)
delta = full_total - docslice_total
ratio = (docslice_total / full_total) if full_total else 0.0
reduction = (1.0 - ratio) * 100.0 if full_total else 0.0

print(f"Scenario: {scenario}")
print(f"Token report ({engine})")
print("DocSlice fragments:")
for label, tokens, duration_ms, sha256, bytes_len in frag_rows:
    share_slice = (tokens / docslice_total) * 100.0 if docslice_total else 0.0
    share_full = (tokens / full_total) * 100.0 if full_total else 0.0
    print(
        f"  - {label}: tokens={tokens}, share_slice={share_slice:.2f}%, "
        f"share_full={share_full:.2f}%, time_ms={duration_ms}, bytes={bytes_len}, "
        f"sha256={sha256[:12]}"
    )
print(f"DocSlice total: tokens={docslice_total}, time_ms={docslice_time}, bytes={docslice_bytes}")
print("Full docs:")
for label, tokens, bytes_len in full_rows:
    print(f"  - {label}: tokens={tokens}, bytes={bytes_len}")
print(f"Full total: tokens={full_total}, bytes={full_bytes}")
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

scenario_setup "simple"
add_full_doc "architecture.md" "$ARCH_DOC"
add_full_doc "system-implementation-design.md" "$IMPL_DOC"
run_docslice "fsm.states.definitions" "$SCENARIO_DIR/fsm_states_definitions.txt" --sid fsm.states.definitions
run_docslice "arch.contracts.decision" "$SCENARIO_DIR/arch_contracts_decision.txt" --sid arch.contracts.decision
run_docslice "obs.eventlog.schema" "$SCENARIO_DIR/obs_eventlog_schema.txt" --sid obs.eventlog.schema
assert_contains "$COMBINED_OUT" "状态列表" "Simple scenario missing FSM definitions"
assert_table "$COMBINED_OUT" "Simple scenario missing table structure"
assert_contains "$COMBINED_OUT" "EventLog" "Simple scenario missing EventLog schema"
print_report "简单场景：基本 token 消耗比较" "$FRAG_TSV" "$FULL_TSV"
echo

scenario_setup "medium"
add_full_doc "architecture.md" "$ARCH_DOC"
add_full_doc "system-implementation-design.md" "$IMPL_DOC"
run_docslice "arch.contracts.pending_action" "$SCENARIO_DIR/arch_contracts_pending_action.txt" --sid arch.contracts.pending_action
run_docslice "arch.contracts.decision" "$SCENARIO_DIR/arch_contracts_decision.txt" --sid arch.contracts.decision
run_docslice "fsm.transitions.overview" "$SCENARIO_DIR/fsm_transitions_overview.txt" --sid fsm.transitions.overview
run_docslice "obs.eventlog.mandatory_events" "$SCENARIO_DIR/obs_eventlog_mandatory_events.txt" --sid obs.eventlog.mandatory_events
assert_contains "$COMBINED_OUT" "PendingAction" "Medium scenario missing PendingAction"
assert_contains "$COMBINED_OUT" "Decision" "Medium scenario missing Decision"
assert_contains "$COMBINED_OUT" "状态转换规则" "Medium scenario missing FSM transitions overview"
assert_contains "$COMBINED_OUT" "事件日志" "Medium scenario missing event log requirements"
print_report "中等场景：可用性检验与性能测试" "$FRAG_TSV" "$FULL_TSV"
echo

scenario_setup "complex"
add_full_doc "architecture.md" "$ARCH_DOC"
add_full_doc "agent-design.md" "$AGENT_DOC"
add_full_doc "system-implementation-design.md" "$IMPL_DOC"
run_docslice "api.rest.overview" "$SCENARIO_DIR/api_rest_overview.txt" --sid api.rest.overview
run_docslice "agent.contracts.step_result" "$SCENARIO_DIR/agent_contracts_step_result.txt" --sid agent.contracts.step_result
run_docslice "fsm.states.definitions" "$SCENARIO_DIR/fsm_states_definitions.txt" --sid fsm.states.definitions
assert_contains "$COMBINED_OUT" '```' "Complex scenario missing code block"
assert_table "$COMBINED_OUT" "Complex scenario missing table structure"
assert_contains "$COMBINED_OUT" "StepResult" "Complex scenario missing StepResult definition"
print_report "复杂场景：表格与代码块混合" "$FRAG_TSV" "$FULL_TSV"
echo

scenario_setup "advanced"
add_full_doc "architecture.md" "$ARCH_DOC"
add_full_doc "agent-design.md" "$AGENT_DOC"
add_full_doc "core-algorithm-spec.md" "$ALGO_DOC"
add_full_doc "system-implementation-design.md" "$IMPL_DOC"
run_docslice "topic:hitl(max-lines=200)" "$SCENARIO_DIR/topic_hitl.txt" --topic hitl --max-lines 200
run_docslice "ref:arch#任务生命周期与状态机(FSM)" "$SCENARIO_DIR/ref_fsm_lifecycle.txt" --ref "DOC:arch#任务生命周期与状态机(FSM)"
run_docslice "topic:planning(max-chars=4000)" "$SCENARIO_DIR/topic_planning.txt" --topic planning --max-chars 4000
assert_contains "$COMBINED_OUT" "Topic: hitl" "Advanced scenario missing hitl topic output"
assert_contains "$COMBINED_OUT" "任务生命周期与状态机" "Advanced scenario missing FSM lifecycle section"
assert_contains "$COMBINED_OUT" "Topic: planning" "Advanced scenario missing planning topic output"
print_report "高级场景：主题切片与跨文档覆盖" "$FRAG_TSV" "$FULL_TSV"
echo

scenario_setup "long"
add_full_doc "system-implementation-design.md" "$IMPL_DOC"
run_docslice "obs.eventlog.mandatory_events" "$SCENARIO_DIR/obs_eventlog_mandatory_events.txt" --sid obs.eventlog.mandatory_events
run_docslice "api.rest.overview" "$SCENARIO_DIR/api_rest_overview.txt" --sid api.rest.overview
assert_contains "$COMBINED_OUT" "任务状态定义" "Long scenario missing task state definition"
assert_contains "$COMBINED_OUT" "REST API" "Long scenario missing REST API overview"
print_report "超长场景：大段规范与高负载" "$FRAG_TSV" "$FULL_TSV"
echo

echo "========================================"
echo "All token comparison scenarios completed ✓"
echo "========================================"
