# Issue #225 Write-Back Closeout

- issue: `#225`
- title: `W16-Release-5: 设计/实验文档回填与 issue 化准备`
- generated_at: `2026-04-26`
- dependency_status: `#222 closed`, `#224 closed`
- source_plan: `../thesis-project.design/plan/index(3.24-4.24).md`
- open_question_source: `../thesis-research-notes/notes/new-algorithm-open-questions.md`

## Completion Decision

Issue `#225` was not complete before this write-back. The hard blockers `#222` and `#224` are closed, but the repository did not yet contain a single closeout artifact that separates answered questions from open questions, aligns the design/experiment/backlog wording, and turns unfinished items into next-round issue drafts.

This document is the closeout artifact for that gap. It does not introduce new runtime behavior or new experiment groups.

## Evidence Inputs

| input | status | path |
| --- | --- | --- |
| Four-group W16 run matrix | available | `output/experiment/w16-expr-1/issue221-real-full-20260418b/runs_manifest.json` |
| W16 matrix summary | available | `output/experiment/w16-expr-1/issue221-real-full-20260418b/matrix_report.md` |
| Issue #222 aggregation rerun | generated for closeout | `output/experiment/w16-expr-1/issue222-analysis-20260426/` |
| Issue #222 overall metrics | generated for closeout | `output/experiment/w16-expr-1/issue222-analysis-20260426/overall_metrics.csv` |
| Issue #222 stratified metrics | generated for closeout | `output/experiment/w16-expr-1/issue222-analysis-20260426/difficulty_stratified_metrics.csv` |
| Issue #224 evidence index | tracked | `docs/evidence/issue-224/evidence-index.json` |
| Issue #224 figure/table templates | tracked | `docs/evidence/issue-224/figure-table-templates.md` |
| Issue #224 report template | tracked | `docs/evidence/issue-224/report-template.md` |
| Canonical group naming | design source | `../thesis-project.design/docs/experiment/algorithm-group-paper-mapping.md` |

The generated `output/` files remain local experiment artifacts because `output/` is intentionally ignored by the repository. The tracked closeout records their paths and summarizes the evidence needed by the next issues.

## Answered Questions

| question | answer | evidence |
| --- | --- | --- |
| Can the four canonical groups be executed under one matrix? | Yes. `static_top1`, `fixed_threshold_gate`, `dynamic_no_belief_state`, and `lite_belief_state` each have 7 runs in the W16 matrix. | `runs_manifest.json`, `matrix_report.md` |
| Are success/cost/recovery metrics aggregatable with one script? | Yes. The #222 analysis produced overall, difficulty-stratified, recovery/high-cost, chart, metric definition, and delta outputs. | `src/infra/w16_issue222_integration_analysis.py`, `issue222-analysis-20260426/` |
| Is canonical naming available for paper-facing rows? | Yes. #224 records the canonical internal groups and external `E0/E1/E2` mapping; historical `A0-A6` are aliases only. | `docs/evidence/issue-224/evidence-index.json` |
| Can the result package be traced from templates back to run evidence? | Partially yes. #224 defines the traceability chain, and #221/#222 provide manifest and aggregate inputs. Some case-level links still need final packaging. | `docs/evidence/issue-224/*`, `run_traceability_index.csv` |

## Current Result Boundaries

The current W16 result package supports a conservative statement:

- `static_top1` is the only group with successful runs in the available 7-run matrix: success rate `1.0000`, first-pass success rate `0.5714`, high-cost call mean `0.2857`, patch event mean `0.4286`.
- `fixed_threshold_gate`, `dynamic_no_belief_state`, and `lite_belief_state` all show success rate `0.0000` in the same matrix.
- Dynamic variants reduce duration and high-cost calls in this run set, but the available evidence does not prove an end-quality improvement over the static baseline.
- The `lite_belief_state` comparison against `dynamic_no_belief_state` is currently a cost/runtime signal, not a success-quality signal.

These boundaries should be preserved in design and experiment prose. Do not phrase the current W16 result as "belief-state improves success rate"; the available evidence does not support that.

## Open Questions

| open question | why still open | next handling |
| --- | --- | --- |
| Main thesis claim selection | Current results support cost/control framing more strongly than success-rate improvement. | Convert to next-round writing and experiment issue. |
| Belief-state incremental value | `dynamic_no_belief_state` and `lite_belief_state` both have zero success in the current matrix; only duration differs. | Add targeted task/rerun design before making a strong claim. |
| HITL and Safety scope | Current W16 package focuses Planner/Workflow recovery evidence and does not fully evaluate HITL/Safety fusion as algorithmic inputs. | Keep outside the main claim unless a follow-up issue adds evidence. |
| Case evidence completeness | #224 defines case templates, but the tracked closeout still depends on local `output/`, `data/logs`, and `data/snapshots` paths. | Package a minimal case bundle before thesis chapter drafting. |
| Negative-result explanation | Current dynamic variants are faster but unsuccessful in the matrix. | Write explicit limitations and failure analysis instead of smoothing the result. |

## Backlog Drafts

### Draft Issue A: W17-Claim-1 Result Claim Boundary And Negative-Result Framing

- priority: `p0`
- type: `docs`
- blocked-by: `#225`
- expected deliverable: one claim-boundary memo usable by thesis result/discussion sections.
- scope:
  - Choose the main claim from the current evidence: cost/control, recovery governance, or success quality.
  - State which claims are not supported by W16 evidence.
  - Convert negative results into explicit limitations.
- acceptance:
  - The memo cites `overall_metrics.csv`, `statistical_deltas.csv`, and this closeout.
  - It does not claim success-rate improvement for `lite_belief_state`.

### Draft Issue B: W17-Evidence-1 Minimal Case Bundle Packaging

- priority: `p0`
- type: `evaluation`
- blocked-by: `#224`, `#225`
- expected deliverable: a tracked case evidence bundle or manifest that resolves the #224 case templates.
- scope:
  - Select one loss-control, one static-vs-dynamic, and one failure case where evidence files exist.
  - Record run config, event log, snapshot, aggregate row, and report references.
  - Mark missing evidence explicitly.
- acceptance:
  - Each case links to `run_traceability_index.csv`.
  - Missing event log or snapshot refs are labeled as evidence gaps, not omitted.

### Draft Issue C: W17-Experiment-1 Belief-State Increment Rerun

- priority: `p1`
- type: `evaluation`
- blocked-by: `#222`, `#225`, `#249`
- expected deliverable: targeted rerun or ablation table focused on `dynamic_no_belief_state` versus `lite_belief_state`.
- scope:
  - Use canonical group IDs only.
  - Prefer tasks where runtime observations can affect the decision path.
  - Report success, duration, high-cost call count, patch/replan count, and action agreement.
- acceptance:
  - The analysis can distinguish "faster but not more successful" from "higher-quality adaptive decision".

### Draft Issue D: W17-Docs-1 Design And Experiment SSOT Sync

- priority: `p1`
- type: `docs`
- blocked-by: `#225`, `#248`, `#249`
- expected deliverable: design-repo patch aligning planning, experiment mapping, and open-question docs.
- scope:
  - Backfill the current W16 result boundary into `../thesis-project.design/docs/experiment/`.
  - Add carry-in references for `#248` and `#249`.
  - Keep `static_top1 / fixed_threshold_gate / dynamic_no_belief_state / lite_belief_state` as the only paper-facing internal groups.
- acceptance:
  - Design, experiment, and backlog wording all use the same group names and result boundary.
  - Open questions remain explicit.

## Consistency Matrix

| surface | wording to use | wording to avoid |
| --- | --- | --- |
| Design docs | "Lite belief-state is a runtime state-estimation module inside adaptive toolchain planning." | "A new controller or new FSM layer." |
| Experiment docs | "The current W16 matrix compares four canonical internal groups under a shared task set." | "A0-A6 are the main paper groups." |
| Results | "Dynamic variants reduce cost/runtime signals in this run set but do not yet improve success." | "Belief-state improves final success rate." |
| Backlog | "Carry forward #248 active tool metadata and #249 naming/output mapping as dependencies." | "Treat naming conversion as a later report-only cleanup." |

## Closeout Checklist

- [x] Answered and unanswered questions are separated.
- [x] Next-round issue drafts include priority, dependencies, and expected deliverables.
- [x] Design, experiment, and backlog wording is aligned around canonical group names.
- [x] Current result boundaries cite real W16 outputs.
- [x] Open questions remain explicit.
