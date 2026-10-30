---
name: advise
description: "Advise an AI-built product — profile the repo, apply rules P01–P32, return P0–P3 requirements with evidence, acceptance criteria and verification layer; optionally save the report"
argument-hint: "[path] [--save] [--no-score] [--lang zh|en]"
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
| `--save` | Also write the report to `<target>/.claude/nlpm-advise/<YYYY-MM-DD>.md` |
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

Wait for the single Markdown report.

### Step 5: Present and optionally save

Print the report unchanged.

If `--save`: create `<target>/.claude/nlpm-advise/` when missing and write the report to `<YYYY-MM-DD>.md` (append `-2`, `-3` when the file exists). Then append one line to `<target>/.omc/usage-log.md` when that file exists:

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
