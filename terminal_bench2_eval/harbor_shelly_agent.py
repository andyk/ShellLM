"""
Harbor harness for shelly agent.

Shelly is an interactive conversational agent built on top of shellm. It adds
persona management, memory, and skills on top of shellm's bash execution loop.

Under the hood, `shelly send <message>` invokes shellm with an enriched system
prompt that includes conversation history, persona context, and skill definitions.
The agent runs at top level directly inside the task container (no sandbox), but
shellm sub-calls use docker-in-docker for isolation.

Required env in the task container:
    ANTHROPIC_API_KEY            forwarded via --ae from the harbor CLI
    /var/run/docker.sock         mounted in via --mounts-json
    /usr/local/bin/shelly        copied in from the host

Configurable kwargs (passed via `--ak key=value`):
    effort           : Reasoning effort. default: max
    max_iterations   : Max iterations per shellm call. default: 1000
    docker_access    : top-level docker mode for shellm. default: none
    inactivity_timeout: seconds before killing idle exec. default: 600
    model            : Model name. default: claude-opus-4-7
"""

import os
import shlex
from pathlib import Path

from harbor.agents.base import BaseAgent
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


SHELLY_PERSONA = (
    "I am shelly, I am an AI with a persona, life context (e.g., memory), "
    "and skills. I am concise, smart, ambitious, and empathetic.\n\n"
    "## How I work\n"
    "I run inside shellm, which executes my bash code blocks in a loop until "
    "I set FINAL with my answer.\n\n"
    "IMPORTANT: When setting FINAL, I MUST use a heredoc to avoid bash "
    "interpreting backticks or special characters in my response:\n"
    "```bash\n"
    "FINAL=$(cat <<'ENDOFRESPONSE'\n"
    "My response with `backticks` and $pecial characters safely here.\n"
    "ENDOFRESPONSE\n"
    ")\n"
    "```\n"
)


def _load_skills(repo_dir: Path) -> str:
    """Read SKILL.md files from the repo's .skills/ directory."""
    skills_dir = repo_dir / ".skills"
    if not skills_dir.is_dir():
        return ""
    sections = []
    for skill_dir in sorted(skills_dir.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if skill_md.is_file():
            sections.append(f"### Skill: {skill_dir.name}\n{skill_md.read_text()}")
    if not sections:
        return ""
    return "## Installed skills\n\n" + "\n\n".join(sections) + "\n\n"

PROMPT_PREAMBLE = (
    SHELLY_PERSONA + "\n"
    "## Evaluation context\n"
    "You are evaluating on terminal-bench 2.0 inside the task's own "
    "container. The task fixture (files, services, etc.) lives right here "
    "in this filesystem (commonly under /app). Operate directly on it.\n\n"
    "## Mindset\n"
    "- THINK AS HARD AS YOU POSSIBLY CAN before each action.\n"
    "- DO NOT GIVE UP. If something fails, try a completely different approach.\n"
    "- Iterate relentlessly until the task is solved completely.\n"
    "- Verify your work end-to-end.\n"
    "- You have effort=max and 1000 iterations available; use them.\n\n"
    "## Recursion\n"
    "Use recursion aggressively via nested shellm sub-calls for independent "
    "sub-problems. Each nested sub-call MUST use docker-in-docker:\n"
    "    SHELLM_ALLOW_NESTED_DOCKER=1 shellm \\\n"
    "        --effort max --max-iterations 1000 \\\n"
    "        --docker-access dind \\\n"
    "        \"<sub-task description>\"\n\n"
    "=== TASK ===\n"
)


class ShellyAgent(BaseAgent):
    """
    Shelly harness for Harbor.

    Uploads the full shellm toolchain (shellm, llm, shelly, mem, skills, etc.)
    into the task container, then invokes `shelly send` with the task instruction.
    """

    SUPPORTS_ATIF: bool = False
    SUPPORTS_WINDOWS: bool = False

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        effort: str = "max",
        max_iterations: int = 1000,
        docker_access: str = "none",
        inactivity_timeout: int = 600,
        **kwargs,
    ):
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        self.effort = effort
        self.max_iterations = int(max_iterations)
        self.docker_access = docker_access
        self.inactivity_timeout = int(inactivity_timeout)
        self.host_bin_dir = self._find_bin_dir()
        self.host_repo_dir = self.host_bin_dir.parent
        self.skills_text = _load_skills(self.host_repo_dir)

    @staticmethod
    def name() -> str:
        return "shelly"

    def version(self) -> str:
        return "0.1.0"

    @staticmethod
    def _find_bin_dir() -> Path:
        """Find the directory containing shelly and its siblings."""
        from shutil import which

        for name in ("shelly", "shellm"):
            path = which(name)
            if path:
                p = Path(path).resolve()
                if p.parent.is_dir():
                    return p.parent
        for candidate in ("/usr/local/bin", "/usr/bin"):
            p = Path(candidate)
            if (p / "shelly").is_file() or (p / "shellm").is_file():
                return p
        raise FileNotFoundError("Cannot find shelly/shellm bin directory.")

    async def setup(self, environment: BaseEnvironment) -> None:
        """Install dependencies and the full shellm/shelly toolchain."""
        install_cmd = r"""
set -e
export DEBIAN_FRONTEND=noninteractive
if command -v apt-get >/dev/null 2>&1; then
  apt-get update -qq >/dev/null 2>&1 || true
  apt-get install -y -qq --no-install-recommends bash curl jq python3 \
      ca-certificates tmux procps git >/dev/null 2>&1 || \
    apt-get install -y --no-install-recommends bash curl jq python3 \
      ca-certificates tmux procps git
elif command -v apk >/dev/null 2>&1; then
  apk add --no-cache bash curl jq python3 ca-certificates tmux procps coreutils git
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y bash curl jq python3 ca-certificates tmux procps-ng git
elif command -v yum >/dev/null 2>&1; then
  yum install -y bash curl jq python3 ca-certificates tmux procps-ng git
fi

# Install docker CLI binary if missing or too old.
need_docker_cli=1
if command -v docker >/dev/null 2>&1; then
  client_ver=$(docker version --format '{{.Client.Version}}' 2>/dev/null || echo 0)
  major=$(echo "$client_ver" | cut -d. -f1)
  if [ "${major:-0}" -ge 24 ]; then
    need_docker_cli=0
  fi
fi
if [ "$need_docker_cli" -eq 1 ]; then
  arch=$(uname -m)
  case "$arch" in
    x86_64) DARCH=x86_64 ;;
    aarch64|arm64) DARCH=aarch64 ;;
    *) DARCH="$arch" ;;
  esac
  curl -fsSL "https://download.docker.com/linux/static/stable/$DARCH/docker-29.1.3.tgz" \
    -o /tmp/docker.tgz
  tar xzf /tmp/docker.tgz -C /tmp
  install /tmp/docker/docker /usr/local/bin/docker
  rm -rf /tmp/docker /tmp/docker.tgz
fi
docker version --format '{{.Client.Version}}' >/dev/null
"""
        await environment.exec(
            command=install_cmd,
            user="root",
            timeout_sec=600,
        )

        # Upload all shellm/shelly tools
        tools = [
            "shellm", "llm", "shelly", "mem", "skills",
            "shellm-docker", "shellm-docker-broker", "shellm-explore",
            "context", "glob", "put", "sub", "traj", "view",
        ]
        for tool in tools:
            src = self.host_bin_dir / tool
            if not src.is_file():
                self.logger.warning(f"tool {tool} not found at {src}")
                continue
            await environment.upload_file(
                source_path=src,
                target_path=f"/usr/local/bin/{tool}",
            )

        await environment.exec(
            command=(
                "chmod +x /usr/local/bin/shellm /usr/local/bin/llm "
                "/usr/local/bin/shelly /usr/local/bin/mem /usr/local/bin/skills "
                "/usr/local/bin/shellm-docker /usr/local/bin/shellm-docker-broker "
                "/usr/local/bin/shellm-explore /usr/local/bin/context "
                "/usr/local/bin/glob /usr/local/bin/put /usr/local/bin/sub "
                "/usr/local/bin/traj /usr/local/bin/view "
                "2>/dev/null; true"
            ),
            user="root",
        )

        # Upload skills so mem/skills tools work at runtime
        skills_dir = self.host_repo_dir / ".skills"
        if skills_dir.is_dir():
            for skill_dir in skills_dir.iterdir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.is_file():
                    await environment.exec(
                        command=f"mkdir -p /app/.skills/{skill_dir.name}",
                        user="root",
                    )
                    await environment.upload_file(
                        source_path=skill_md,
                        target_path=f"/app/.skills/{skill_dir.name}/SKILL.md",
                    )

        # Sanity check
        await environment.exec(
            command=(
                "set -e; "
                "shelly --help >/dev/null 2>&1 || "
                "  { echo 'shelly not runnable'; exit 1; }; "
                "shellm --help >/dev/null 2>&1 || "
                "  { echo 'shellm not runnable'; exit 1; }; "
                "command -v docker >/dev/null 2>&1 || "
                "  { echo 'docker CLI missing'; exit 1; }; "
                "docker info >/dev/null 2>&1 || "
                "  echo 'WARNING: docker daemon not reachable'; "
                "echo OK"
            ),
            user="root",
        )

    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        prompt = PROMPT_PREAMBLE + self.skills_text + instruction

        # Strip provider prefix from model name
        mn = ""
        if self.model_name:
            mn = self.model_name
            for prefix in ("anthropic/", "openai/", "google/", "gemini/"):
                if mn.startswith(prefix):
                    mn = mn[len(prefix):]
                    break

        env = {
            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
            "SHELLM_EFFORT": self.effort,
            "SHELLM_MAX_ITERATIONS": str(self.max_iterations),
            "SHELLM_DOCKER_ACCESS": self.docker_access,
            "SHELLM_INACTIVITY_TIMEOUT": str(self.inactivity_timeout),
            "SHELLM_TEMP_DOCKER": "1",
            "SHELLM_NO_BANNER": "1",
            "SHELLM_MODEL": mn or "claude-opus-4-7",
        }

        # Upload the prompt as a file to avoid ARG_MAX limits.
        prompt_file = self.logs_dir / "prompt.txt"
        prompt_file.write_text(prompt)
        await environment.upload_file(
            source_path=prompt_file,
            target_path="/tmp/.shelly_prompt",
        )

        # Shelly calls `shellm --env <persona>` which may create a Docker
        # container that doesn't inherit env vars. Write a .env file that
        # llm will source automatically, ensuring the API key is available
        # no matter how deeply nested the process chain gets.
        # Run shellm directly with shelly's persona baked into the prompt.
        # We avoid `shelly send` because it creates a named Docker env via
        # `shellm --env <persona>`, which drops env vars like ANTHROPIC_API_KEY.
        # The full prompt (persona + task) goes via -f to avoid ARG_MAX.
        cmd = (
            "set -o pipefail; "
            "mkdir -p /logs/agent; "
            "cd /app 2>/dev/null || cd / ; "
            "shellm --env local "
            f"--effort {shlex.quote(self.effort)} "
            f"--max-iterations {self.max_iterations} "
            "-f /tmp/.shelly_prompt "
            "'Solve the task described in the file context above.' "
            "2>&1 | tee /logs/agent/shelly.log; "
            "rm -f /tmp/.shelly_prompt"
        )

        result = await environment.exec(
            command=cmd,
            user="root",
            env=env,
            timeout_sec=None,
        )

        try:
            (self.logs_dir / "shelly.stdout.txt").write_text(result.stdout or "")
            (self.logs_dir / "shelly.stderr.txt").write_text(result.stderr or "")
            (self.logs_dir / "shelly.return_code.txt").write_text(
                str(result.return_code)
            )
        except Exception as e:
            self.logger.warning(f"failed to persist shelly logs: {e}")
