---
name: advise
description: "Advise an AI-built product — profile the repo, apply rules P01–P36, return P0–P3 requirements with evidence, acceptance criteria and verification layer; optionally save the report"
argument-hint: "[path] [--save] [--out DIR] [--state-dir DIR] [--model haiku|sonnet|opus] [--no-score] [--lang zh|en]"
allowed-tools: Read, Write, Glob, Grep, Bash, Task
---

## User Input

```text
$ARGUMENTS
```

## Workflow

### Step 1: Resolve target and flags

| Input | Behavior |
|-------|----------|
| (empty) | Target = current working directory |
| absolute path | Target = that path |
| relative path | Target = `<cwd>/<path>` |
| `--save` | Also save the report (see Step 5 for the location rule) |
| `--out DIR` | Save the report to `DIR/<YYYY-MM-DD>.md` instead; implies `--save` |
| `--state-dir DIR` | Read gitignored project state, such as `.omc/usage-log.md`, from `DIR`. Use it when `target` is a clean clone |
| `--model NAME` | Run the advisor on `haiku`, `sonnet` or `opus` (default: the agent's own model). Use cheaper models for routine runs; Step 4b catches invented evidence |
| `--no-score` | Skip the NL artifact scoring step |
| `--lang en` | English report (default `zh`) |

If the target does not exist or is not a directory → "Target path not found: {path}". Stop.

### Step 2: Load config

Read `<target>/.claude/nlpm.local.md` if it exists. Extract `score_threshold` (default 70) and `advise.lang` (default `zh`; a `--lang` flag wins over the file).

### Step 3: Score NL artifacts (unless `--no-score`)

Discover artifacts with `${CLAUDE_PLUGIN_ROOT}/commands/shared/discover.md` (categories A and B). If at least one artifact is found, dispatch the `nlpm:scorer` agent exactly as `/nlpm:score` does and keep the per-file table as `nl_scores`. If none are found, set `nl_scores = none`.

### Step 4: Dispatch the advisor

Dispatch the `nlpm:advisor` agent with:

- `target` (absolute path)
- `profile_hints`: any free text the user included after the path
- `nl_scores`
- `lang`
- `state_dir`, when given
- the `model` dispatch parameter, when `--model` is given

Wait for the single Markdown report.

### Step 4b: Verify the evidence

Write the report to a temporary file and run:

```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/nlpm-advise-verify" <report-file> --target <target> [--state-dir <state_dir>] --json
```

- Exit 0: continue.
- Exit 1: for each `failed` finding, move its table row and issue block to "待确认" and add the verifier's reason. Do not silently fix the citation. When `table_mismatch` is set, add the table's missing rows to the block or move them to "待确认". Then recount the findings and rewrite the one-sentence judgment if it relied on a failed finding, so no part of the report still presents it as fact.
- Findings reported as `unverifiable` stay in the table, marked "证据未机器核验". The citation names only a file, or the evidence is command output.
- Exit 2 (no valid `nlpm-findings` block): add one line at the top of the report saying the evidence was not machine-checked.

In the `nlpm-findings` block, add `"verification": "verified" | "failed" | "unverifiable"` to every entry. Keep failed entries in the block so reports can be compared, because automation must act only on `verified` entries.

Print the verifier's one-line summary under the report title.

### Step 5: Present and optionally save

Print the report unchanged.

If `--save`, choose the location, because a report lists the product's weaknesses and must not be committed by accident:

1. `--out DIR` when given.
2. `<target>/.claude/nlpm-advise/` when `target` is not a git repository, or when `git -C <target> check-ignore -q .claude/nlpm-advise/x.md` exits 0.
3. Otherwise `~/.claude/nlpm-advise/<repository-name>/`, and say in one line that the in-repo path is not gitignored.

Create the directory when missing and write the report to `<YYYY-MM-DD>.md` (append `-2`, `-3` when the file exists). Then append one line to `<target>/.omc/usage-log.md` when that file exists:

```
- <YYYY-MM-DD> nlpm advise: <count P0> P0 / <count P1> P1 / <count P2> P2 — report .claude/nlpm-advise/<file>
```

Do not create `.omc/usage-log.md` if it is missing; that file is the maintainer's own gate-1 evidence.

### Step 6: Next step line

End with one line: "下一步：先做清单里的第一条 P0（或 P1）；完成后重跑 `/nlpm:advise --save` 对比。" (English equivalent when `lang = en`.)

## Error Handling

| Situation | Response |
|---|---|
| Target is a file, not a directory | "Point /nlpm:advise at the repository root, not a file." |
| Advisor returns no report within its run | "The advisor returned nothing; rerun with `--no-score` to shorten the job, or point at a sub-directory." |
| `--save` cannot write (read-only location) | print the report and say the save failed with the OS error |

## Output Format

The report follows the output contract in `${CLAUDE_PLUGIN_ROOT}/skills/nlpm/product-advising/SKILL.md` section 5: one-line verdict, five-line profile, findings table (P0 first), issue-ready requirement blocks for every P0 and P1, Won't list, not-applicable list, NL artifact scores.
