# Shelly Terminal Bench 2.0 Evaluation Report (v2)

**Date:** 2026-05-02  
**Model:** claude-opus-4-7  
**Settings:** effort=max, max-iterations=1000, --env local  
**Agent:** ShellyAgent (shellm with shelly persona + skills via -f)  
**Skills:** mem, web-research, file-tools, skill-author  
**Harness:** harbor with ShellmDockerEnvironment  
**Runtime:** 7h 38m 37s  

## Results Summary

| Metric | Value |
|--------|-------|
| Tasks completed | 89 / 89 (100%) |
| Tasks passed | 36 / 89 (40.4%) |
| Tasks failed | 53 / 89 (59.6%) |
| — Timeouts | 37 |
| — Wrong answers | 16 |
| [cmd] iteration failures | 0 |
| Mean reward | 0.404 |

## Comparison Across Runs

| Run | Tasks | Passed | Rate | [cmd] waste | Notes |
|-----|-------|--------|------|-------------|-------|
| shellm run 1 (partial) | 60/89 | 23 | 38.3% | 0% | Cancelled early |
| shelly run 1 (partial) | 20/89 | 7 | 35.0% | 62.7% | Before context fix |
| **shelly run 2 (full)** | **89/89** | **36** | **40.4%** | **0%** | **Context fix applied** |

## Passing Tasks (36)

| Task | Category |
|------|----------|
| bn-fit-modify | Bayesian networks |
| break-filter-js-from-html | Web/security |
| build-pmars | Build systems |
| cancel-async-tasks | Async programming |
| code-from-image | Code generation |
| compile-compcert | Build/compile |
| configure-git-webserver | Systems config |
| db-wal-recovery | Database internals |
| distribution-search | Statistics |
| feal-differential-cryptanalysis | Cryptography |
| financial-document-processor | Data processing |
| fix-git | Git/version control |
| git-multibranch | Git/version control |
| hf-model-inference | ML/inference |
| kv-store-grpc | Systems/networking |
| large-scale-text-editing | Text processing |
| log-summary-date-ranges | Data processing |
| mailman | Systems/email |
| mcmc-sampling-stan | Scientific computing |
| merge-diff-arc-agi-task | Data processing |
| modernize-scientific-stack | Refactoring |
| mteb-retrieve | ML/retrieval |
| multi-source-data-merger | Data processing |
| nginx-request-logging | Systems/web |
| password-recovery | Security |
| portfolio-optimization | Scientific computing |
| prove-plus-comm | Formal verification |
| pypi-server | Package management |
| pytorch-model-cli | ML tooling |
| pytorch-model-recovery | ML/debugging |
| query-optimize | Databases |
| reshard-c4-data | Data engineering |
| schemelike-metacircular-eval | PL/interpreters |
| sparql-university | Databases/RDF |
| sqlite-db-truncate | Databases |
| sqlite-with-gcov | Testing/coverage |

## Failing Tasks — Timeouts (37)

These tasks ran until harbor's agent timeout killed them. Many are extremely hard (expert time estimates of 30-120 minutes).

adaptive-rejection-sampler, build-cython-ext, caffe-cifar-10, chess-best-move, circuit-fibsqrt, cobol-modernization, count-dataset-tokens, crack-7z-hash, custom-memory-heap-crash, dna-assembly, extract-elf, extract-moves-from-video, feal-linear-cryptanalysis, filter-js-from-html, fix-ocaml-gc, git-leak-recovery, gpt2-codegolf, headless-terminal, llm-inference-batching-scheduler, make-doom-for-mips, make-mips-interpreter, model-extraction-relu-logits, overfull-hbox, path-tracing, polyglot-c-py, polyglot-rust-c, protein-assembly, raman-fitting, regex-chess, regex-log, rstan-to-pystan, sanitize-git-repo, torch-pipeline-parallelism, torch-tensor-parallelism, tune-mjcf, winning-avg-corewars, write-compressor

## Failing Tasks — Wrong Answers (16)

These tasks completed but the verifier rejected the output.

build-pov-ray, constraints-scheduling, dna-insert, fix-code-vulnerability, gcode-to-text, install-windows-3.11, largest-eigenval, mteb-leaderboard, openssl-selfsigned-cert, path-tracing-reverse, qemu-alpine-ssh, qemu-startup, sam-cell-seg, train-fasttext, video-processing, vulnerable-secret

## Impact of the [cmd] Context Fix

The context rendering fix (PR #8) completely eliminated the `[cmd]` marker bug:

| Metric | Before fix | After fix |
|--------|-----------|-----------|
| [cmd] iteration waste | 62.7% | 0% |
| Effective iterations | ~37% of budget | 100% of budget |
| Pass rate | 35% (partial) | 40.4% (full) |

Every iteration now executes real code instead of aborting on `[cmd]: command not found`.

## Recommendations

### High Impact

1. **Increase agent timeouts.** 37 of 53 failures (70%) were timeouts. Many tasks need more time, especially complex ones like path-tracing (1800s timeout) and regex-chess (3600s). Consider 2x default timeouts.

2. **Reduce effort for early iterations.** With effort=max, each LLM call takes 30-60s of thinking. The first few exploratory iterations (ls, pwd, cat) don't need this. Using effort=high for the first 5 iterations would save ~3 minutes per task.

3. **Better error recovery prompts.** 16 tasks produced wrong answers. Adding a self-verification step ("run the test suite before setting FINAL") could catch some of these.

### Medium Impact

4. **Task-specific skills.** The installed skills (mem, web-research, file-tools, skill-author) are general-purpose. Task-specific skills for common patterns (git recovery, build debugging, ML training) could help.

5. **Retry with different strategy on timeout.** When a task times out, retrying with a completely different approach (instead of continuing the same strategy) might help. The max-retries=1 setting should help but retries also time out on the same hard tasks.

6. **Pre-install common tools.** Many tasks need git, python3, build-essential. The setup phase installs these but it takes ~30s per task. Pre-baking them into the Docker image would save time.
