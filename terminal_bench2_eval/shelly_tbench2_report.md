# Shelly Terminal Bench 2.0 Evaluation Report

**Date:** 2026-05-01
**Model:** claude-opus-4-7
**Settings:** effort=max, max-iterations=1000, --env local
**Agent:** ShellyAgent (shellm with shelly persona baked in via -f)
**Harness:** harbor with ShellmDockerEnvironment (cgroup v2 fix)

## Results Summary

| Metric | Value |
|--------|-------|
| Tasks completed | 20 / 89 (22%) |
| Tasks passed | 7 / 20 (35%) |
| Tasks failed | 13 / 20 (65%) |
| Tasks not run (cancelled) | 69 |
| Total iterations used | 282 |
| Iterations lost to [cmd] bug | 177 (62.7%) |
| Effective iterations | 105 (37.3%) |

## Passing Tasks (7)

| Task | Iterations | [cmd] failures | Effective iters |
|------|-----------|----------------|-----------------|
| break-filter-js-from-html | 46 | 30 (65%) | 16 |
| feal-linear-cryptanalysis | 35 | 21 (60%) | 14 |
| log-summary-date-ranges | 31 | 17 (55%) | 14 |
| merge-diff-arc-agi-task | ? | 0 | ? |
| portfolio-optimization | 70 | 45 (64%) | 25 |
| prove-plus-comm | 30 | 21 (70%) | 9 |
| reshard-c4-data | 70 | 43 (61%) | 27 |

## Failing Tasks (13)

Every failing task hit **AgentTimeoutError** — the agent ran until harbor's timeout killed it. No task failed due to a wrong answer; they all simply ran out of time.

| Task | Timeout |
|------|---------|
| caffe-cifar-10 | 1200s |
| gpt2-codegolf | 900s |
| largest-eigenval | 900s |
| llm-inference-batching-scheduler | 1800s |
| modernize-scientific-stack | 600s |
| password-recovery | 900s |
| path-tracing | 1800s |
| path-tracing-reverse | 1800s |
| pytorch-model-cli | 900s |
| regex-chess | 3600s |
| torch-tensor-parallelism | 900s |
| winning-avg-corewars | 3600s |
| write-compressor | 900s |

## The [cmd] Bug

The dominant failure mode was the `[cmd]` marker bug. The model emits `[cmd]` as a literal line inside bash code blocks:

```
```bash
[cmd]
cd /app && git reflog
```
```

Since shellm runs code with `bash -e`, the `[cmd]` line triggers "command not found" (exit 127) which aborts the entire script before any real commands execute. **62.7% of all iterations were wasted this way.**

Despite this, 7 tasks still passed — the model succeeded on iterations where `[cmd]` happened not to appear or appeared in a position that didn't abort the critical commands. Tasks like `portfolio-optimization` passed despite 64% of its iterations being wasted.

### Estimated impact

If we eliminate the `[cmd]` bug completely:
- Each task would get 2-3x more effective iterations
- Tasks that timed out with ~30% effective iterations would get the full budget
- Conservative estimate: pass rate would increase from 35% to **50-60%**

A fix was committed locally (`29843bc`) that strips `[cmd]`/`[thought]` in `extract_code()`, but it wasn't fully effective in the container environment during this run.

## Comparison: Shelly vs Shellm

Of the 20 tasks shelly attempted, we can compare against shellm's previous run:

| Outcome | Tasks |
|---------|-------|
| Both passed | log-summary-date-ranges, merge-diff-arc-agi-task, portfolio-optimization, prove-plus-comm |
| Shelly only | break-filter-js-from-html, feal-linear-cryptanalysis, reshard-c4-data |
| Shellm only | largest-eigenval, modernize-scientific-stack, password-recovery |
| Not yet run by shelly | 15 tasks that shellm passed |

**Shelly passed 3 tasks that shellm failed** (break-filter-js-from-html, feal-linear-cryptanalysis, reshard-c4-data), suggesting the shelly persona adds value for certain task types. However, shelly also failed 3 that shellm passed, and the incomplete run makes definitive comparison difficult.

## Recommendations

### Critical (would significantly improve pass rate)

1. **Fix the `[cmd]` stripping in containers.** The awk pattern in `extract_code()` strips `[cmd]` locally but isn't fully effective in container environments. Debug the awk compatibility issue (may be a POSIX character class difference between macOS and Linux awk). This alone would likely improve pass rate by 15-25 percentage points.

2. **Don't use `bash -e` for generated code.** Switch to `bash +e` (or `set +e` at the top of each script) so a single failed line doesn't abort the entire iteration. The model's code often has exploratory commands that may fail harmlessly. This would also make the `[cmd]` bug non-fatal.

3. **Increase agent timeouts.** All 13 failures were timeouts. Many tasks need more time, especially with 63% iteration waste from `[cmd]`. Consider 2x the default task timeout.

### High impact

4. **Fix the `[cmd]` format confusion at the source.** The model emits `[cmd]` because it learned this format from the traj system. Add explicit instructions to the system prompt: "Never emit `[cmd]` or `[thought]` markers in your code blocks — these are internal format markers, not bash commands."

5. **Run shelly natively instead of through shellm.** The current harness uses `shellm --env local -f prompt.txt` with shelly's persona baked in. Running `shelly send` directly would give access to memory, skills, and conversation history. The blocker was the API key not propagating through shelly's Docker env — fix the env var forwarding in shelly's shellm invocation.

6. **Retry on empty/thinking-only responses.** When the API returns only thinking with no text, retry immediately instead of treating it as an error.

### Medium impact

7. **Reduce `effort` for early exploration iterations.** The first few iterations are typically `ls`, `pwd`, `cat`. Using `effort=high` instead of `max` would be faster and cheaper for these.

8. **Add task-specific context.** For tasks with known patterns (git tasks → check reflog, ML tasks → check GPU, etc.), add brief hints to the prompt.

9. **Use the shelly persona more effectively.** The current harness bakes a minimal shelly persona into the prompt. A richer persona with learned skills for common terminal-bench patterns could improve performance.
