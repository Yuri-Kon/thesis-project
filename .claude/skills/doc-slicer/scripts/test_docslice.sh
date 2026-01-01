#!/bin/bash
# Test script for docslice

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
DOCSLICE="./scripts/docslice"

echo "========================================"
echo "Testing docslice - Deterministic Spec Slicer"
echo "========================================"
echo

# Test 1: Help command
echo "Test 1: --help"
"$DOCSLICE" --help > /dev/null
echo "✓ --help works"
echo

# Test 2: Extract by SID (simple comment marker)
echo "Test 2: --sid with simple comment marker"
OUTPUT=$("$DOCSLICE" --sid arch.overview.layers --no-metadata)
if [[ "$OUTPUT" == *"分层架构"* ]]; then
    echo "✓ --sid (comment marker) works"
else
    echo "✗ --sid (comment marker) failed"
    exit 1
fi
echo

# Test 3: Extract by SID (begin_end marker)
echo "Test 3: --sid with begin_end marker"
OUTPUT=$("$DOCSLICE" --sid arch.contracts.pending_action --no-metadata)
if [[ "$OUTPUT" == *"PendingAction"* ]]; then
    echo "✓ --sid (begin_end marker) works"
else
    echo "✗ --sid (begin_end marker) failed"
    exit 1
fi
echo

# Test 4: Extract by SID (inline marker)
echo "Test 4: --sid with inline marker"
OUTPUT=$("$DOCSLICE" --sid fsm.states.waiting_plan_confirm --no-metadata)
if [[ "$OUTPUT" == *"WAITING_PLAN_CONFIRM"* ]]; then
    echo "✓ --sid (inline marker) works"
else
    echo "✗ --sid (inline marker) failed"
    exit 1
fi
echo

# Test 5: Extract by reference
echo "Test 5: --ref with DOC reference"
OUTPUT=$("$DOCSLICE" --ref "DOC:arch#分层架构" --no-metadata)
if [[ "$OUTPUT" == *"分层架构"* ]]; then
    echo "✓ --ref works"
else
    echo "✗ --ref failed"
    exit 1
fi
echo

# Test 6: Extract by topic
echo "Test 6: --topic extraction"
OUTPUT=$("$DOCSLICE" --topic hitl --max-lines 50 2>&1)
if [[ "$OUTPUT" == *"SID: arch.contracts.pending_action"* ]] || [[ "$OUTPUT" == *"Topic: hitl"* ]]; then
    echo "✓ --topic works"
else
    echo "✗ --topic failed"
    exit 1
fi
echo

# Test 7: Topic with max-chars limit
echo "Test 7: --topic with max-chars limit"
OUTPUT=$("$DOCSLICE" --topic hitl --max-chars 5000 2>&1)
if [[ "$OUTPUT" == *"Total chars"* ]]; then
    echo "✓ --topic with max-chars works"
else
    echo "✗ --topic with max-chars failed"
    exit 1
fi
echo

# Test 8: Lint validation
echo "Test 8: --lint validation"
"$DOCSLICE" --lint > /dev/null
LINT_EXIT=$?
if [ $LINT_EXIT -eq 0 ]; then
    echo "✓ --lint works (no errors found)"
else
    echo "✗ --lint found errors"
    exit 1
fi
echo

# Test 9: Deterministic output (same input = same output)
echo "Test 9: Deterministic output test"
OUTPUT1=$("$DOCSLICE" --sid arch.overview.layers)
OUTPUT2=$("$DOCSLICE" --sid arch.overview.layers)
if [[ "$OUTPUT1" == "$OUTPUT2" ]]; then
    echo "✓ Output is deterministic"
else
    echo "✗ Output is not deterministic"
    exit 1
fi
echo

# Test 10: Error handling - invalid SID
echo "Test 10: Error handling for invalid SID"
if "$DOCSLICE" --sid invalid.sid.notexist 2>&1 | grep -q "Error"; then
    echo "✓ Invalid SID error handling works"
else
    echo "✗ Invalid SID error handling failed"
    exit 1
fi
echo

# Golden cases
echo "Test 11: Golden cases - FSM WAITING_* SIDs"
WAITING_CASES=(
    "fsm.states.waiting_plan_confirm:WAITING_PLAN_CONFIRM"
    "fsm.states.waiting_patch_confirm:WAITING_PATCH_CONFIRM"
    "fsm.states.waiting_replan_confirm:WAITING_REPLAN_CONFIRM"
)
for entry in "${WAITING_CASES[@]}"; do
    SID="${entry%%:*}"
    EXPECTED="${entry##*:}"
    OUTPUT=$("$DOCSLICE" --sid "$SID" --no-metadata)
    if [[ "$OUTPUT" == *"$EXPECTED"* ]]; then
        echo "✓ $SID resolves"
    else
        echo "✗ $SID failed to resolve"
        exit 1
    fi
done
echo

echo "Test 12: Golden cases - HITL / Decision SIDs"
HITL_CASES=(
    "arch.contracts.pending_action:PendingAction"
    "arch.contracts.decision:Decision"
)
for entry in "${HITL_CASES[@]}"; do
    SID="${entry%%:*}"
    EXPECTED="${entry##*:}"
    OUTPUT=$("$DOCSLICE" --sid "$SID" --no-metadata)
    if [[ "$OUTPUT" == *"$EXPECTED"* ]]; then
        echo "✓ $SID resolves"
    else
        echo "✗ $SID failed to resolve"
        exit 1
    fi
done
echo

echo "Test 13: Golden cases - Candidate gating SID"
OUTPUT=$("$DOCSLICE" --sid planner.algorithm.hitl_gate)
if [[ "$OUTPUT" == *"# SID: planner.algorithm.hitl_gate"* ]]; then
    echo "✓ planner.algorithm.hitl_gate resolves"
else
    echo "✗ planner.algorithm.hitl_gate failed to resolve"
    exit 1
fi
echo

echo "Test 14: Golden cases - EventLog schema SID"
OUTPUT=$("$DOCSLICE" --sid obs.eventlog.schema)
if [[ "$OUTPUT" == *"# SID: obs.eventlog.schema"* ]]; then
    echo "✓ obs.eventlog.schema resolves"
else
    echo "✗ obs.eventlog.schema failed to resolve"
    exit 1
fi
echo

echo "Test 15: Golden cases - topic planning"
OUTPUT=$("$DOCSLICE" --topic planning --max-lines 50 2>&1)
if [[ "$OUTPUT" == *"Topic: planning"* ]]; then
    echo "✓ topic planning resolves"
else
    echo "✗ topic planning failed to resolve"
    exit 1
fi
echo

echo "Test 16: Token cost reduction with docslice"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
DESIGN_ROOT="$REPO_ROOT/../thesis-project.design"
ARCH_DOC="$DESIGN_ROOT/docs/design/architecture.md"
IMPL_DOC="$DESIGN_ROOT/docs/design/system-implementation-design.md"
if [ ! -f "$ARCH_DOC" ] || [ ! -f "$IMPL_DOC" ]; then
    echo "✗ Design docs not found: $ARCH_DOC or $IMPL_DOC"
    exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
DOCSLICE_OUTPUT="$TMP_DIR/docslice_output.txt"
DOCSLICE_DIR="$TMP_DIR/docslice"
SID_MAP="$TMP_DIR/sid_map.txt"
mkdir -p "$DOCSLICE_DIR"
: > "$DOCSLICE_OUTPUT"
: > "$SID_MAP"

TOKEN_SIDS=(
    "fsm.states.definitions"
    "arch.contracts.decision"
    "obs.eventlog.schema"
)
for SID in "${TOKEN_SIDS[@]}"; do
    OUT_PATH="$DOCSLICE_DIR/${SID//./_}.txt"
    "$DOCSLICE" --sid "$SID" > "$OUT_PATH"
    cat "$OUT_PATH" >> "$DOCSLICE_OUTPUT"
    echo >> "$DOCSLICE_OUTPUT"
    printf "%s\t%s\n" "$SID" "$OUT_PATH" >> "$SID_MAP"
done

if ! grep -q "状态列表" "$DOCSLICE_OUTPUT"; then
    echo "✗ docslice output missing FSM definitions"
    exit 1
fi
if ! grep -q "Decision" "$DOCSLICE_OUTPUT"; then
    echo "✗ docslice output missing Decision contract"
    exit 1
fi
if ! grep -q "EventLog" "$DOCSLICE_OUTPUT"; then
    echo "✗ docslice output missing EventLog schema"
    exit 1
fi

python - "$DOCSLICE_OUTPUT" "$ARCH_DOC" "$IMPL_DOC" "$SID_MAP" <<'PY'
import re
import sys
from pathlib import Path

docslice_output = sys.argv[1]
arch_doc = sys.argv[2]
impl_doc = sys.argv[3]
sid_map = sys.argv[4]

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

sid_counts = []
with open(sid_map, "r", encoding="utf-8") as handle:
    for line in handle:
        line = line.strip()
        if not line:
            continue
        sid, path = line.split("\t", 1)
        sid_counts.append((sid, count_path(path)))

docslice_total = count_path(docslice_output)
full_arch = count_path(arch_doc)
full_impl = count_path(impl_doc)
full_total = full_arch + full_impl
delta = full_total - docslice_total
ratio = (docslice_total / full_total) if full_total else 0.0
reduction = (1.0 - ratio) * 100.0 if full_total else 0.0

print(f"Token report ({engine})")
print("DocSlice fragments:")
for sid, count in sid_counts:
    print(f"  - {sid}: {count}")
print(f"DocSlice total: {docslice_total}")
print("Full docs:")
print(f"  - architecture.md: {full_arch}")
print(f"  - system-implementation-design.md: {full_impl}")
print(f"Full total: {full_total}")
print(f"Delta: {delta}")
print(f"Ratio: {ratio:.4f}")
print(f"Reduction: {reduction:.2f}%")
if engine.startswith("fallback"):
    print("Note: install tiktoken for accurate token counts (python -m pip install tiktoken)")

if docslice_total < full_total:
    print(f"✓ Token cost reduced ({docslice_total} < {full_total})")
    sys.exit(0)

print(f"✗ Token cost not reduced ({docslice_total} >= {full_total})")
sys.exit(1)
PY
echo

echo "========================================"
echo "All tests passed! ✓"
echo "========================================"
