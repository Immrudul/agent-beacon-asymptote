# Beacon Behavior

This project is basically an experiment around one question:

> once we can observe what coding agents are doing, can we actually understand **how** they solved a task instead of only checking whether they got the final answer right?

The project builds on top of [Agent Beacon](https://github.com/Asymptote-Labs/agent-beacon), which already does the hard part of collecting telemetry from different agent runtimes and normalizing it into one consistent stream of events.

Beacon can tell us things like:

```text
prompt.submitted
command.executed
tool.invoked
file.modified
approval.requested
token.usage
```

which is already very useful.

But I wanted to see what we could build one layer above that.

Instead of only having:

```text
command.executed
→ command.executed
→ tool.invoked
→ command.executed
```

we can try to turn that into something more human-readable:

```text
INSPECT_REPO
→ TEST_FAIL
→ DIAGNOSE
→ PATCH
→ TEST_PASS
→ VERIFY
```

And once we have that, we can start doing some pretty interesting things:

- inspect an agent run
- replay exactly what it did
- compare two different trajectories
- measure which one was more efficient
- define behavioral regression rules
- evaluate not just **whether** an agent solved a task, but **how it solved it**

That’s basically what this project does.

---

# The idea

The flow looks roughly like:

```text
Claude / Codex / Cursor / etc.
                |
                v
          Agent Beacon
                |
                v
      normalized telemetry
                |
                v
         Beacon Behavior
          /    |    \
         /     |     \
        v      v      v

    inspect   compare   replay
       \        |        /
        \       |       /
         v      v      v

       behavioral evaluation
```

The main idea is pretty simple:

> Beacon handles the messy problem of collecting telemetry from different agent runtimes, and this project tries to turn that telemetry into a useful behavioral representation.

So instead of downstream tooling caring whether an event came from Codex hooks, Claude telemetry, OTLP, polling, or something else, it can work with a higher-level representation of what the agent actually did.

The longer-term idea is basically:

```text
many agent runtimes
        ↓
Agent Beacon
        ↓
normalized agent activity
        ↓
behavioral trajectories
        ↓
debugging / evals / regression tests / comparisons
```

---

# What does a run actually look like?

For the main demo, I ran Codex against a small repository with a failing test.

The prompt was:

```text
Fix the failing test in this repository.

Constraints:
- Do not modify the tests.
- Diagnose the failure first.
- Make the smallest reasonable code change.
- Run the tests after your change and verify they pass.
```

Beacon captured the raw runtime activity.

Beacon Behavior then turns that into something like:

```text
INSPECT_REPO
→ ENV_ERROR
→ DIAGNOSE
→ TEST_FAIL
→ PATCH
→ TEST_PASS
→ VERIFY
```

A second run on the same task looked like:

```text
INSPECT_REPO
→ TEST_FAIL
→ DIAGNOSE
→ PATCH
→ TEST_PASS
```

Both agents technically solved the task.

But they did not solve it the same way.

That difference is where this project starts becoming useful.

---

# Why this is interesting

A normal coding-agent eval might stop here:

```text
tests passed = true
```

But imagine two runs.

Agent A:

```text
inspect repo
run failing test
find relevant code
make one small patch
run tests
verify result
```

Agent B:

```text
inspect repo
run wrong command
hit environment error
reread files
retry test
make patch
rerun test
inspect diff
```

Both might eventually pass.

But their trajectories are clearly different.

That becomes especially useful once we care about:

- debugging efficiency
- unnecessary tool usage
- repeated failures
- patch scope
- verification behavior
- whether the agent actually investigated before editing
- whether a model is consistently taking weird or expensive paths

So the goal here is not just:

> did the model solve it?

but also:

> what actually happened between the prompt and the final answer?

---

# Features

## Inspect a run

```bash
beacon-behavior show ../fixtures/codex-run-1.jsonl
```

This gives a session summary like:

```text
Outcome                  PASS
Task duration            51s
Test attempts            3
Failed attempts          1
Environment errors       1
Test verification        yes
Additional verification  yes

Input tokens             21,627
Cached input tokens      169,728
Output tokens            1,477
Reasoning tokens         409

Patch operations         1
Files modified           1
Tool calls               9
Commands executed        7
Trajectory length        7

Time to first test       15s
Time to patch            40s

Behavior pattern         DEBUG_FIX_VERIFY
```

and then the behavioral trajectory:

```text
INSPECT_REPO
→ ENV_ERROR
→ DIAGNOSE
→ TEST_FAIL
→ PATCH
→ TEST_PASS
→ VERIFY
```

There is also a verbose mode:

```bash
beacon-behavior show ../fixtures/codex-run-1.jsonl --verbose
```

which keeps the lower-level semantic steps instead of compressing them.

---

# Compare two agent runs

```bash
beacon-behavior diff \
  ../fixtures/codex-run-1.jsonl \
  ../fixtures/codex-run-2.jsonl
```

This compares both runs side by side.

For example:

```text
Metric                  Run 1              Run 2

Outcome                 PASS               PASS
Task duration           51s                35s
Test attempts           3                  2
Failed attempts         1                  1
Environment errors      1                  0

Tool calls              9                  5
Commands executed       7                  3
Trajectory length       7                  5

Time to first test      15s                15s
Time to patch           40s                30s

Behavior pattern        DEBUG_FIX_VERIFY   DEBUG_FIX_TEST
```

The cool part is that both runs solved the same task successfully, but the second one got there with fewer actions and without the environment error.

The trajectory comparison also makes the behavioral difference pretty obvious:

```text
Run 1
INSPECT_REPO → ENV_ERROR → DIAGNOSE → TEST_FAIL → PATCH → TEST_PASS → VERIFY

Run 2
INSPECT_REPO → TEST_FAIL → DIAGNOSE → PATCH → TEST_PASS
```

There is also a sequence-aware diff:

```text
  INSPECT_REPO
- ENV_ERROR
+ TEST_FAIL
  DIAGNOSE
- TEST_FAIL
  PATCH
  TEST_PASS
- VERIFY
```

The current diff is intentionally pretty simple. It is sequence-based rather than trying to invent some giant semantic similarity score.

---

# Behavioral regression tests

This is probably one of my favorite parts of the project.

We can define rules for what we consider acceptable agent behavior.

For example:

```yaml
require:
  - TEST_PASS

require_after_patch:
  - TEST_PASS

limits:
  test_attempts: 3
  files_modified: 2

require_additional_verification: true
```

Then run:

```bash
beacon-behavior eval \
  ../fixtures/codex-run-1.jsonl \
  --rules ../rules.yaml
```

Run 1:

```text
PASS  observed TEST_PASS
PASS  TEST_PASS occurred after PATCH
PASS  test attempts: 3 <= 3
PASS  files modified: 1 <= 2
PASS  additional verification observed

Result: PASS
```

But run 2:

```text
PASS  observed TEST_PASS
PASS  TEST_PASS occurred after PATCH
PASS  test attempts: 2 <= 3
PASS  files modified: 1 <= 2
FAIL  additional verification required but not observed

Result: FAIL
```

Which is interesting because:

```text
functional result = PASS
behavioral contract = FAIL
```

That means the eval is no longer only checking whether the code happened to work.

It can also enforce expectations around **how the task was solved**.

---

# Semantic replay

Another thing I wanted was a way to inspect a run like a flight recorder.

You can run:

```bash
beacon-behavior replay ../fixtures/codex-run-2.jsonl
```

and step through the agent behavior one action at a time.

For example:

```text
Step 1/4 COMMAND
Elapsed: 15s
Semantics: INSPECT_REPO, TEST_FAIL

Command:
Get-ChildItem -Force; ...; python -m pytest -q
```

then:

```text
Step 2/4 COMMAND
Elapsed: 20s
Semantics: READ_CODE, DIAGNOSE
```

then:

```text
Step 3/4 PATCH
Elapsed: 30s
Semantics: PATCH

Files:
solve.py

Patch:
- solved.append("G")
- solved.append("O")
+ solved.append("L")
+ solved.append("F")
```

and finally:

```text
Step 4/4 COMMAND
Elapsed: 35s
Semantics: TEST_PASS

Command:
python -m pytest -q; python -m py_compile solve.py
```

This is not trying to recreate the entire VM or filesystem state.

It is more like a **semantic session replay**:

```text
what did the agent do?
when did it do it?
what command did it run?
what happened?
what files changed?
what patch did it make?
```

which is enough to make weird agent behavior much easier to debug.

---

# Capturing runs directly from Beacon

You can also extract the latest completed agent turn directly from Beacon telemetry:

```bash
beacon-behavior capture latest \
  --output ../fixtures/latest.jsonl
```

The current implementation:

```text
runtime.jsonl
→ latest prompt.submitted
→ matching session
→ collect events
→ stop at token.usage
→ write standalone fixture
```

One slightly important thing I found while working on this is that:

> a Beacon session is not necessarily the same thing as a single agent run.

For example, multiple Codex turns can share the same `session.id`.

So the capture logic works around prompt/turn boundaries rather than blindly treating every session as one trajectory.

You can also restrict capture to a specific Beacon session:

```bash
beacon-behavior capture latest \
  --session <session-id> \
  --output ../fixtures/run.jsonl
```

---

# Behavioral taxonomy

The current semantic action set is intentionally pretty small.

Right now the project understands things like:

```text
PROMPT
INSPECT_REPO
READ_CODE
DIAGNOSE
ENV_ERROR
TEST_FAIL
PATCH
TEST_PASS
VERIFY
TOKENS
```

I kept this pretty conservative on purpose.

It would be very easy to immediately add 40 categories like:

```text
BUILD_FAIL
TYPECHECK_FAIL
LINT_FAIL
NETWORK_ACCESS
CREDENTIAL_ACCESS
TOOL_ERROR
DEPENDENCY_ERROR
...
```

but I would rather add those once real traces actually require them instead of designing a giant taxonomy in advance.

One example of where this already helped was separating:

```text
TEST_FAIL
```

from:

```text
ENV_ERROR
```

because one of the runs originally looked like it had two failed test attempts.

In reality:

```text
ENV_ERROR
→ TEST_FAIL
```

was much more accurate.

---

# Architecture

The project is currently pretty small.

```text
beacon_behavior/
├── cli.py
├── parser.py
├── models.py
├── trajectory.py
├── summary.py
├── compare.py
├── rules.py
├── replay.py
└── capture.py
```

## Parser

Reads Beacon JSONL, validates each event, and orders events by timestamp and sequence.

One thing that matters here is that telemetry may arrive asynchronously, so append order is not automatically treated as execution order.

## Trajectory builder

This is where raw Beacon activity gets turned into semantic actions.

For example:

```text
command.executed
```

might become:

```text
TEST_FAIL
```

or:

```text
INSPECT_REPO
```

depending on the command and output.

It also handles context.

For example, inspecting code before a patch probably means:

```text
DIAGNOSE
```

while inspecting code after a patch might mean:

```text
VERIFY
```

That kind of context matters a lot more than just labeling commands individually.

## Summary builder

Aggregates the run into metrics like:

```text
duration
test attempts
environment errors
token usage
patch operations
files modified
tool calls
trajectory length
time to first test
time to patch
```

and assigns a high-level behavior pattern such as:

```text
DEBUG_FIX_VERIFY
DEBUG_FIX_TEST
FIX_TEST
DIAGNOSE_ONLY
```

## Comparison engine

Takes two trajectories and compares:

```text
outcome
timing
tool usage
token usage
failures
patch scope
verification behavior
trajectory shape
```

along with a sequence diff.

## Rules engine

Loads behavioral requirements from YAML and evaluates a run against them.

The current rule system supports:

```text
required actions
required actions after a patch
numeric limits
required additional verification
```

This is intentionally a v1.

## Replay

Groups the semantic interpretations back around actual agent actions.

That distinction ended up mattering quite a bit.

One command might simultaneously mean:

```text
INSPECT_REPO
+
TEST_FAIL
```

So replay treats that as one real action with multiple semantic annotations instead of pretending the agent performed two separate actions.

---

# Installing

From the `beacon-behavior` directory:

```bash
pip install -e .
```

Then:

```bash
beacon-behavior --help
```

You should have:

```text
show
diff
eval
replay
capture
```

For example:

```bash
beacon-behavior show ../fixtures/codex-run-1.jsonl
```

```bash
beacon-behavior diff \
  ../fixtures/codex-run-1.jsonl \
  ../fixtures/codex-run-2.jsonl
```

```bash
beacon-behavior eval \
  ../fixtures/codex-run-1.jsonl \
  --rules ../rules.yaml
```

```bash
beacon-behavior replay \
  ../fixtures/codex-run-1.jsonl
```

---

# Why build this on top of Beacon?

The thing I like about Beacon is that it already sits at a really useful layer.

Different agent runtimes expose activity in completely different ways:

```text
hooks
plugins
OTLP
polling
runtime-specific integrations
```

Trying to build agent evals or debugging tooling directly against every one of those runtimes gets messy very quickly.

Beacon gives us a normalized stream first.

So the division becomes:

```text
runtime-specific collection
        ↓
      Beacon
        ↓
normalized agent telemetry
        ↓
  Beacon Behavior
        ↓
behavioral understanding
```

That means this project does not need Claude, Codex, Cursor, etc. to emit some new proprietary behavior format.

Beacon can remain the compatibility layer and this project can operate downstream from it.

The idea I find most interesting is basically:

> runtime differences should become irrelevant to downstream tooling.

Once the telemetry is normalized, the same behavioral debugging/eval tooling should theoretically work regardless of where the original actions came from.

---

# What still needs work?

This is definitely still a pretty scrappy MVP, and there are a lot of directions this could go.

I stopped once the core loop felt complete:

```text
capture
→ understand
→ inspect
→ compare
→ replay
→ evaluate
```

but some pretty obvious next steps would be:

- validate the behavioral abstraction across more runtimes
  - Claude Code
  - Cursor
  - Cline
  - etc.

- add richer semantic categories when real traces require them
  - build failures
  - lint failures
  - typecheck failures
  - tool errors
  - network activity
  - credential access

- make trajectory diffs more semantic
  - "one extra retry"
  - "verification missing"
  - "patch happened before diagnosis"
  - "run B took a more expensive path"

- expand behavioral rules
  - denied actions
  - arbitrary ordering constraints
  - per-action limits
  - token budgets
  - timing budgets
  - file allow/deny rules

- automatically detect suspicious or inefficient behavior
  - repeated commands
  - retry loops
  - unnecessary rereads
  - patches before investigation
  - excessive verification
  - large patch scope

- richer replay
  - interactive TUI
  - collapsible outputs
  - syntax highlighted patches
  - jump between steps
  - eventually maybe reconstruct file state

- better live capture
  - list recent turns
  - capture a specific turn
  - concurrent-session handling
  - cross-platform Beacon log paths

- build real cross-harness comparisons
  - same task
  - same initial repository
  - Codex vs Claude Code
  - compare trajectory, retries, time, tokens, patch scope, and verification

- run dataset-scale experiments
  - N tasks
  - M models / harnesses
  - K attempts
  - aggregate success + behavioral metrics

The bigger version of this could eventually become something like:

```text
agent telemetry
→ normalized trajectories
→ behavioral regression tests
→ debugging
→ evaluation
→ benchmarking
```

But for now I think the current project already demonstrates the part I actually wanted to explore:

```text
raw agent events
→ meaningful behavior
→ inspectable trajectories
→ measurable differences
→ process-aware evaluation
```

which is a lot more interesting than only asking:

```text
did the tests pass?
```

Honestly I know that was a lot but thank you for reading all that! Please feel free to clone the project, and of course feel free to reach out about anything as well!

My sincere thank yous, Mrudul

suresh.mrudul@gmail.com
mrudul.suresh@uwaterloo.ca
