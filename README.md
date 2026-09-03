# 🧩 Nuclr skills

[Agent Skills](https://agentskills.io/) for working with [Nuclr Commander](https://nuclr.dev).

Each skill is a self-contained folder with a `SKILL.md` entry point and optional references, scripts, and assets. The skills follow the open Agent Skills format and are not tied to a particular coding agent.

| Skill | Purpose |
|---|---|
| [`nuclr-commander-plugins`](skills/nuclr-commander-plugins/) | Build, extend, or repair Nuclr Commander plugins in Java — the SDK contract, manifest, Maven bundle, and a standalone bundle validator |

## 📦 Install

```bash
git clone https://github.com/nuclrdev/skills.git
```

Copy or symlink the desired skill directory — for example `skills/nuclr-commander-plugins/` — into the skills location documented by your coding agent. If the agent supports installing directly from a Git repository, provide this repository URL and the skill subdirectory.

## 📄 License

Apache-2.0. See [LICENSE](LICENSE).
