# Decision objective

## Decision-target ladder

| Level | Object | What it can support | What it cannot support by itself |
|---|---|---|---|
| L0 | Candidate proposed or format accepted | Search coverage and execution | Real-world utility |
| L1 | Effective state change and measurable simulated response | The intervention is represented and testable | Real-system effect or useful ranking |
| L2 | Paired computational improvement under fixed scenarios | A model- and contract-bounded improvement | Deployment utility or construct validity |
| L3 | Budget-matched verification utility | Fewer false positives, lower oracle cost, or better confirmation yield under the declared contract | Real-world validity unless experimentally anchored |
| L4 | Experimental / production measurement | Effect under the tested conditions | Generality beyond the tested design and context |

Never promote L0/L1/L2 to L3 because a verdict is labelled `pass`, a
candidate is historically unseen, or a direction transfers to a related
model.

## Before a campaign or algorithm change

1. Write the decision question as an action: *which candidate should receive
   the next verification budget, compared with what baseline?*
2. Declare the incumbent, candidate pool, starting labels, oracle budget,
   seeds, primary endpoint, confirmation scenarios, and stopping/failure
   rules.
3. Define the unit of comparison. Separate candidate-generation novelty,
   model response, process-recipe effect, and joint effects.
4. Keep standard contract labels, search utilities, and final verdicts in
   separate fields. A shaped search score is not a verdict.
5. Add a kill rule: if the editable intervention surface produces no
   effective state change or no measured response, stop adding planner
   layers and diagnose representation, bounds, mapping, or process coupling.

## Reframing workflow (claims only, no new runs)

Use this when asked to execute a conceptual conclusion inside a report or
manuscript without running new experiments.

1. Read the project specification, claim-boundary document, decision
   records, current draft, and worktree status. Preserve pre-existing
   uncommitted edits.
2. Append to the task ledger before editing: the question, evidence
   consulted, working decision, scope, and 3–5 likely overclaim risks.
3. Add one paragraph that distinguishes simulator score, computational
   attainment, paired confirmation, and verification-decision quality.
   State plainly which level remains unmeasured.
4. Update all language versions in parallel. Do not change frozen numbers,
   denominators, thresholds, protocols, or experimental status.
5. Create a versioned revision record and a durable decision note; update
   index/routing documents. Do not overwrite protected files without
   explicit approval.
6. Verify with a deterministic text check: central question present,
   unmeasured boundary present, no positive claim of measured decision
   utility, new records exist, and `git diff --check` passes.
7. Report what changed, what was verified, what was deliberately not
   executed, and any protected-file or export boundary.

## Adversarial review prompts

- Could a reader mistake a simulator verdict for a real-system result?
- Could a paired computational gain be read as experimental utility?
- Are accounting, capacity, model-lineage, or evaluator-sharing caveats
  hidden inside the headline?
- Does a new planner actually change the measured decision, or only an
  internal score?
- If the proposed module fails, is there a predeclared stopping and
  diagnosis path rather than another layer by default?
