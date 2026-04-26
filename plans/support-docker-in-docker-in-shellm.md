# Plan: opt-in Docker-in-Docker support for shellm

## Summary

Support Docker usage from inside shellm's Docker execution environment without changing the default safety model. The default remains: shellm uses Docker as a sandbox when available, but generated code does not get access to Docker. Docker access becomes an explicit opt-in.

There are four useful modes:

1. `none`: today's behavior. No Docker access from generated code.
2. `broker`: expose a shellm-owned broker endpoint, not the Docker daemon. Generated code can ask for a narrow set of container operations, and the host broker validates the request before calling Docker with fixed safe flags.
3. `socket`: mount the host Docker socket and install a Docker CLI in the shellm container. This is the fastest path and supports most "run docker from the agent" workflows, but it gives generated code root-equivalent control over the host Docker daemon.
4. `dind`: run a Docker daemon inside the shellm container. This is closer to true Docker-in-Docker and avoids controlling the host daemon directly, but it requires a privileged container and more setup.

Implement `broker` first as the recommended middle path. Keep `socket` as an explicitly unsafe convenience mode, then add `dind` behind the same interface if true nested daemon support is still useful.

## Current behavior

- `shellm` refuses to use Docker when it detects `/.dockerenv`, so a shellm process started inside any container always registers a local env.
- Generated code is executed in a Docker container when the host daemon is available, but that container does not receive a Docker socket, Docker CLI, Docker daemon, or privileged permissions.
- Recursive `shellm` calls from inside a Docker-backed run are forced local by passing `SHELLM_ENV=local`.
- Persisted envs store the container id and image, but not the capability shape of the container. Reusing an old env after changing Docker access mode could silently attach to the wrong kind of container unless we add metadata checks.

Relevant locations:

- `shellm`: Docker setup and run flags live in `docker_setup()`.
- `shellm`: env attach/register logic lives in `env_resolve()` and `env_register()`.
- `shellm`: execution env vars are assembled before `execute_code()`.
- `README.md`: Docker behavior and configuration docs need updating.

## User-facing interface

Add:

```bash
shellm --docker-access none     "normal sandboxed task"
shellm --docker-access broker   "task that needs bounded helper containers"
shellm --docker-access socket   "task that needs docker commands"
shellm --docker-access dind     "task that needs an inner docker daemon"
```

Environment variables:

```bash
SHELLM_DOCKER_ACCESS=none|broker|socket|dind
SHELLM_DOCKER_BROKER_TRANSPORT=auto|socket|filesystem
SHELLM_DOCKER_SOCKET=/var/run/docker.sock
SHELLM_ALLOW_NESTED_DOCKER=0|1
```

Defaults:

- `SHELLM_DOCKER_ACCESS=none`
- `SHELLM_DOCKER_BROKER_TRANSPORT=auto`
- `SHELLM_DOCKER_SOCKET=/var/run/docker.sock`
- `SHELLM_ALLOW_NESTED_DOCKER=0`

Behavior:

- `none`: exactly today's behavior.
- `broker`: generated code gets a `shellm-docker` CLI that talks to a host-side shellm broker. The broker calls host Docker only after validating a narrow operation request.
- `socket`: the shellm execution container can run `docker ...` against the host daemon. This is not a strong sandbox.
- `dind`: the shellm execution container starts and uses its own inner daemon. This is not a strong sandbox if the outer container is privileged.
- `SHELLM_ALLOW_NESTED_DOCKER=1`: allows a shellm process that is itself already inside a container to use Docker if a daemon is reachable. Keep this separate from `--docker-access` so recursive shellm nesting stays deliberate.

## Implementation steps

### 1. Add configuration and parsing

- Add defaults near the existing Docker config:
  - `SHELLM_DOCKER_ACCESS="${SHELLM_DOCKER_ACCESS:-none}"`
  - `SHELLM_DOCKER_BROKER_TRANSPORT="${SHELLM_DOCKER_BROKER_TRANSPORT:-auto}"`
  - `SHELLM_DOCKER_SOCKET="${SHELLM_DOCKER_SOCKET:-/var/run/docker.sock}"`
  - `SHELLM_ALLOW_NESTED_DOCKER="${SHELLM_ALLOW_NESTED_DOCKER:-0}"`
- Add `--docker-access MODE` to option parsing.
- Validate `MODE` as `none`, `broker`, `socket`, or `dind`.
- Validate `SHELLM_DOCKER_BROKER_TRANSPORT` as `auto`, `socket`, or `filesystem`.
- Update `usage_text()` and the README configuration table.

### 2. Add a bash broker mode

Add a host-side `shellm-docker-broker` Bash script and an in-container `shellm-docker` Bash client.

Transport:

- Prefer `socat` when available. This keeps the broker request/response lifecycle clean while staying aligned with shellm's Unix-tool philosophy: Bash owns the policy, `socat` owns the socket plumbing.
- `SHELLM_DOCKER_BROKER_TRANSPORT=auto` selects `socket` when host `socat` is available and the execution container can install or use `socat`; otherwise it selects `filesystem`.
- `SHELLM_DOCKER_BROKER_TRANSPORT=socket` requires `socat` and fails clearly if it is unavailable on either side.
- `SHELLM_DOCKER_BROKER_TRANSPORT=filesystem` forces the polling transport.
- If `socat` is not available, fall back to a filesystem transport under `$HOME/.shellm/docker-broker/$env_name`.
- If the fallback is too limited for a requested operation, fail with a clear message suggesting `socat`.

Socket transport shape:

- Host broker listens on a Unix socket under `$HOME/.shellm/docker-broker/$env_name/broker.sock`.
- `docker_setup()` mounts only that broker socket into the execution container.
- Generated code calls `shellm-docker`, not `docker`.
- `shellm-docker` serializes a narrow request, sends it to the broker, streams output, and exits with the broker-provided exit code.

Filesystem fallback shape:

- Host and container share a broker directory under `$HOME/.shellm/docker-broker/$env_name`.
- `shellm-docker` writes request files into `requests/`.
- The broker polling loop validates and executes requests, then writes stdout, stderr, and exit status into `responses/`.
- Include request timeouts and stale-file cleanup.

Allowed operations should be explicit verbs, not arbitrary Docker CLI pass-through:

```bash
shellm-docker run IMAGE -- CMD...
shellm-docker build DIR TAG
shellm-docker ps
shellm-docker logs ID
shellm-docker rm ID
```

Broker policy:

- Allowed:
  - run containers from requested images
  - mount only `$SHELLM_WORKDIR` at the same path
  - set a small allowlist of env vars
  - apply CPU, memory, process, and timeout limits
  - optionally publish selected high ports
- Denied:
  - `--privileged`
  - `--cap-add`
  - `--device`
  - `--pid host`
  - `--net host`
  - `--ipc host`
  - arbitrary bind mounts
  - Docker socket mounts
  - host root mounts such as `-v /:/host`

Request encoding:

- Prefer a simple JSON request parsed with `jq`, since shellm already depends on `jq`.
- Never `eval` request content.
- Validate image names, paths, container ids, tags, and verbs with allowlist regexes before invoking Docker.
- Invoke Docker with arrays, not string-built command lines.

Host-side complexity:

- MVP broker: roughly 150-250 lines of Bash.
- Safer broker with validation, logging, timeouts, and filesystem fallback: roughly 350-600 lines.
- shellm integration: roughly 100 lines.

This is more complex than raw socket mode, but it is the only proposed mode that gives agents useful container-spawning ability without handing them the host Docker daemon.

### 3. Refactor Docker run flag assembly

Inside `docker_setup()`:

- Introduce arrays:
  - `docker_run_flags`
  - `docker_env_flags`
  - `extra_mounts`
- Keep the existing mounts for:
  - `$HOME/.shellm`
  - the `shellm` executable
  - out-of-workspace context file directories
- Also mount a custom workdir explicitly when it is not under `$HOME/.shellm`, because child containers using the host daemon need the same host path to exist.

For `broker` mode:

- Start or attach the host broker before starting the shellm execution container.
- Mount the broker socket or broker filesystem directory into the execution container.
- Mount/install the `shellm-docker` client into `/usr/local/bin/shellm-docker`.
- For socket transport, make `socat` available in the execution container.
- Do not mount `/var/run/docker.sock`.
- Do not add `--privileged`.
- Do not install the real Docker CLI unless another mode asks for it.

For `socket` mode:

- Verify `SHELLM_DOCKER_SOCKET` exists and is a Unix socket.
- Mount it into the execution container as `/var/run/docker.sock`.
- Add `DOCKER_HOST=unix:///var/run/docker.sock`.
- Add the socket's group id with `--group-add` when available, using a portable helper for GNU/BSD `stat`.
- Do not add `--privileged`.

For `dind` mode:

- Add `--privileged`.
- Add `DOCKER_HOST=unix:///var/run/docker.sock`.
- Add a persistent inner daemon data directory, probably under the env/run area, such as `$HOME/.shellm/docker-data/$env_name` or another env-specific path.
- Consider `--tmpfs /run` and `--tmpfs /tmp` if dockerd needs clean runtime dirs.

### 4. Install Docker tooling only when requested

Split the existing root setup block into helpers:

- `docker_install_base_tools()`: today's `jq curl python3 tmux sudo`.
- `docker_install_broker_client()`: install or mount `shellm-docker` for `broker` mode, and install `socat` only when the selected broker transport needs it.
- `docker_install_docker_cli()`: install the Docker CLI and compose plugin if available.
- `docker_start_inner_daemon()`: only for `dind`; start `dockerd`, wait for `docker info`, and fail clearly if it cannot start.

Policy:

- If `SHELLM_DOCKER_ACCESS=none`, Docker tooling is not installed.
- If `SHELLM_DOCKER_ACCESS=broker`, install only the `shellm-docker` client. The real Docker CLI is intentionally absent unless the user picks `socket` or `dind`.
- If Docker access is requested and setup fails, fail the run. A warning is too weak because the user asked for Docker support.
- Keep the package installation compatible with the current `apt-get` assumption in shellm. Later, this can be generalized for non-Debian images.

### 5. Forward Docker env into generated code

In `execute_code()` or while assembling `env_vars`:

- Pass `SHELLM_DOCKER_ACCESS`.
- In `broker` mode, pass:
  - `SHELLM_DOCKER_BROKER` as the mounted broker endpoint
  - `SHELLM_DOCKER_TRANSPORT=socket|filesystem`
- In `socket` and `dind` modes, pass `DOCKER_HOST=unix:///var/run/docker.sock`.
- Optionally pass `DOCKER_BUILDKIT=1`.
- Avoid forwarding arbitrary host Docker env vars by default, especially TLS-related values, because the socket and inner daemon modes should be deterministic.

### 6. Make persisted env reuse capability-aware

Extend env metadata:

- `docker_access`
- `docker_broker_transport` for broker mode
- `docker_socket` for socket mode
- `privileged` for dind mode

Update `env_resolve()` so it only reattaches when the stored metadata matches the requested capability mode. If it does not match:

- For implicit env reuse: skip that env and create a new one.
- For explicit `--env NAME`: fail with a clear message telling the user to use a different env, destroy the env, or request the same access mode.

This prevents a confusing case where `shellm --docker-access socket --env project` reuses a container that was created without the socket mount.

### 7. Manage broker lifecycle

For persisted envs:

- Keep the broker alive for as long as the env's execution container is alive.
- Store broker pid, socket path, transport type, and log path in the env metadata directory.
- On env attach, verify the broker is still alive and responsive.
- If the execution container exists but the broker is stale, restart the broker if metadata matches.

For `--temp-docker`:

- Stop the broker during cleanup.
- Remove socket files and temporary request/response files.

Broker logs:

- Write broker logs under `$HOME/.shellm/docker-broker/$env_name/broker.log`.
- Include rejected requests with a reason, but redact env values and command output where appropriate.

### 8. Preserve recursive shellm safety by default

Keep the current default where generated code receives `SHELLM_ENV=local` during Docker-backed execution. That prevents accidental recursive container nesting.

Add an explicit escape hatch:

- If `SHELLM_ALLOW_NESTED_DOCKER=1`, do not force recursive shellm calls to `SHELLM_ENV=local`.
- Update the `/.dockerenv` guard so an already-containerized shellm process may use Docker only when `SHELLM_ALLOW_NESTED_DOCKER=1` and `docker info` succeeds.
- Keep `SHELLM_MAX_DEPTH` as the recursion guard.

This keeps ordinary nested `shellm` calls lightweight while allowing advanced users to opt into sibling containers or true nested daemon behavior.

### 9. Update the system prompt

When Docker access is enabled, add a short "Docker access" section:

- `broker`: use `shellm-docker`, not `docker`; only bounded container operations are available; workspace mounts are managed by the broker.
- `socket`: Docker commands control the host Docker daemon; child bind mounts must use host-visible paths. `$SHELLM_WORKDIR` is mounted at the same path when possible.
- `dind`: Docker commands use an inner daemon; images and containers are scoped to the shellm env.

Also update the existing Docker sandbox wording so it does not claim full host isolation when socket mode is active.

### 10. Documentation

Update README:

- Add examples for `--docker-access broker`.
- Add examples for `--docker-access socket` and `--docker-access dind`.
- Document the security implications:
  - broker mode is the recommended constrained mode
  - socket mode is not a strict sandbox
  - dind mode requires privileged container permissions
- Document env reuse behavior.
- Document the custom workdir caveat for host-daemon bind mounts.
- Document optional `socat` support and the filesystem fallback.

## Verification plan

No-Docker-access regression:

```bash
shellm --temp-docker --new-env "run docker version and report the error"
```

Expected: generated code should not have Docker access unless it installs or discovers something independently.

Socket mode smoke:

```bash
shellm --temp-docker --new-env --docker-access socket "run docker version, docker ps, and docker run --rm hello-world"
```

Workspace bind mount smoke:

```bash
shellm --temp-docker --new-env --docker-access socket \
  'use docker run to write child-ok.txt into $SHELLM_WORKDIR, then verify the file exists'
```

Env reuse smoke:

```bash
shellm --env did-test --docker-access socket "run docker ps"
shellm --env did-test --docker-access none "say whether this reused or rejected the env"
```

Expected: the second command should reject the mismatched env or require a fresh env.

Broker mode smoke:

```bash
shellm --temp-docker --new-env --docker-access broker \
  "use shellm-docker to run alpine:latest echo hi"
```

Broker policy smoke:

```bash
shellm --temp-docker --new-env --docker-access broker \
  "try to mount / from a child container and report the broker rejection"
```

Expected: the broker rejects the unsafe mount request before host Docker is invoked.

Broker fallback smoke:

```bash
SHELLM_DOCKER_BROKER_TRANSPORT=filesystem \
  shellm --temp-docker --new-env --docker-access broker \
  "use shellm-docker to run alpine:latest echo hi"
```

Expected: shellm uses the filesystem transport without requiring `socat`.

Dind smoke, after phase 2:

```bash
shellm --temp-docker --new-env --docker-access dind \
  "run docker info, build a tiny image, and run it"
```

Nested shellm smoke:

```bash
SHELLM_ALLOW_NESTED_DOCKER=1 shellm --temp-docker --new-env --docker-access socket \
  'call shellm recursively and have the child run docker ps'
```

## Recommended rollout

1. Land the config, docs, metadata, and broker mode with `socat` transport.
2. Add filesystem fallback for broker mode.
3. Add regression tests around flag parsing, broker request validation, and env reuse with a fake `docker` shim.
4. Add real integration smoke tests that run only when Docker is available.
5. Add raw `socket` mode as an explicitly unsafe escape hatch if still needed.
6. Land `dind` mode as a later phase if true nested daemon behavior remains useful.
7. Revisit non-Debian base images and rootless Docker once the basic broker capability is proven.

## Open questions

- Should broker mode be the only documented Docker-access mode at first, with `socket` and `dind` left experimental?
- Should broker mode require `socat`, or is the filesystem fallback important enough to support from day one?
- Which verbs belong in the first broker release: only `run`, or also `build`, `ps`, `logs`, and `rm`?
- Should broker mode allow image names freely, or require an image allowlist?
- Should broker-spawned containers persist after a request, or should the MVP force `--rm`?
- Should `dind` data persist per env, per run, or only when `--temp-docker` is off?
- Should socket mode be named `host-socket` instead of `socket` to make the security tradeoff more obvious?
- Should shellm require a confirmation-style env var for socket mode, such as `SHELLM_ALLOW_HOST_DOCKER=1`, or is the explicit flag enough?
- Should Docker compose support be required for MVP, or best-effort only?
