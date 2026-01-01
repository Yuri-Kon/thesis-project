#!/bin/bash
# Test script for docslice

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "========================================"
echo "Testing docslice - Deterministic Spec Slicer"
echo "========================================"
echo

# Test 1: Help command
echo "Test 1: --help"
./scripts/docslice --help > /dev/null
echo "✓ --help works"
echo

# Test 2: Extract by SID (simple comment marker)
echo "Test 2: --sid with simple comment marker"
OUTPUT=$(./scripts/docslice --sid arch.overview.layers --no-metadata)
if [[ "$OUTPUT" == *"分层架构"* ]]; then
    echo "✓ --sid (comment marker) works"
else
    echo "✗ --sid (comment marker) failed"
    exit 1
fi
echo

# Test 3: Extract by SID (begin_end marker)
echo "Test 3: --sid with begin_end marker"
OUTPUT=$(./scripts/docslice --sid arch.contracts.pending_action --no-metadata)
if [[ "$OUTPUT" == *"PendingAction"* ]]; then
    echo "✓ --sid (begin_end marker) works"
else
    echo "✗ --sid (begin_end marker) failed"
    exit 1
fi
echo

# Test 4: Extract by SID (inline marker)
echo "Test 4: --sid with inline marker"
OUTPUT=$(./scripts/docslice --sid fsm.states.waiting_plan_confirm --no-metadata)
if [[ "$OUTPUT" == *"WAITING_PLAN_CONFIRM"* ]]; then
    echo "✓ --sid (inline marker) works"
else
    echo "✗ --sid (inline marker) failed"
    exit 1
fi
echo

# Test 5: Extract by reference
echo "Test 5: --ref with DOC reference"
OUTPUT=$(./scripts/docslice --ref "DOC:arch#分层架构" --no-metadata)
if [[ "$OUTPUT" == *"分层架构"* ]]; then
    echo "✓ --ref works"
else
    echo "✗ --ref failed"
    exit 1
fi
echo

# Test 6: Extract by topic
echo "Test 6: --topic extraction"
OUTPUT=$(./scripts/docslice --topic hitl --max-lines 50 2>&1)
if [[ "$OUTPUT" == *"SID: arch.contracts.pending_action"* ]] || [[ "$OUTPUT" == *"Topic: hitl"* ]]; then
    echo "✓ --topic works"
else
    echo "✗ --topic failed"
    exit 1
fi
echo

# Test 7: Topic with max-chars limit
echo "Test 7: --topic with max-chars limit"
OUTPUT=$(./scripts/docslice --topic hitl --max-chars 5000 2>&1)
if [[ "$OUTPUT" == *"Total chars"* ]]; then
    echo "✓ --topic with max-chars works"
else
    echo "✗ --topic with max-chars failed"
    exit 1
fi
echo

# Test 8: Lint validation
echo "Test 8: --lint validation"
./scripts/docslice --lint > /dev/null
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
OUTPUT1=$(./scripts/docslice --sid arch.overview.layers)
OUTPUT2=$(./scripts/docslice --sid arch.overview.layers)
if [[ "$OUTPUT1" == "$OUTPUT2" ]]; then
    echo "✓ Output is deterministic"
else
    echo "✗ Output is not deterministic"
    exit 1
fi
echo

# Test 10: Error handling - invalid SID
echo "Test 10: Error handling for invalid SID"
if ./scripts/docslice --sid invalid.sid.notexist 2>&1 | grep -q "Error"; then
    echo "✓ Invalid SID error handling works"
else
    echo "✗ Invalid SID error handling failed"
    exit 1
fi
echo

echo "========================================"
echo "All tests passed! ✓"
echo "========================================"
