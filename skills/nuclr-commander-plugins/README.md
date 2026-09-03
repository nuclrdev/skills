# Nuclr Commander plugin skill

An [Agent Skill](https://agentskills.io/) for building [Nuclr Commander](https://github.com/nuclrdev/commander) plugins in Java.

Nuclr Commander is a cross-platform dual-pane file manager whose functionality is almost entirely pluggable. This skill teaches an AI coding agent the plugin contract — the three extension interfaces, the `plugin.json` manifest, the Maven bundle layout, and the lifecycle and threading rules — so that asking for "a quick viewer for X" produces a complete, tested, correctly packaged bundle instead of a plausible-looking sketch.

## Install

Clone the repository:

```bash
git clone https://github.com/nuclrdev/skills.git
```

Copy or symlink `skills/nuclr-commander-plugins/` into the skills location documented by your coding agent. Agents that support Git-based installation can install from `https://github.com/nuclrdev/skills.git` and select the `skills/nuclr-commander-plugins` subdirectory.

After installation, compatible agents can select the skill automatically from its description or invoke it explicitly as `nuclr-commander-plugins`, using the invocation syntax supported by that agent.

## What it covers

| File | Contents |
|---|---|
| `SKILL.md` | Entry point: how to establish the contract, pick an extension type, and what "done" means |
| `references/common-contract.md` | Self-contained SDK 4.0.0 snapshot — lifecycle, resources, manifest, Maven packaging, verification |
| `references/file-panel.md` | `FilePanelNuclrPlugin`: navigation, columns, host actions, transfer semantics |
| `references/quick-view.md` | `QuickViewNuclrPlugin`: selection priority, bounded loading, panel lifecycle |
| `references/fullscreen.md` | `FullscreenNuclrPlugin`: viewer vs editor, save safety, menus and key routing |
| `scripts/validate_plugin.py` | Checks a plugin project and its packaged ZIP without needing Maven or a Commander install |
| `scripts/tests/` | Fixture-driven tests for the validator: `python3 scripts/tests/test_validate_plugin.py` |

## The validator

The validator is also useful independently of an AI coding agent:

```bash
python3 scripts/validate_plugin.py path/to/plugin-project \
        --archive target/plugin-1.0.0.zip
```

A relative `--archive` path is resolved against the current directory first, and against the project directory when it is not found there, so both `--archive target/plugin-1.0.0.zip` and a path written from the current directory work.

It verifies the POM's SDK dependency and scope, the manifest's schema and required fields, the enum vocabulary for `type` / `developer` / `role`, per-type rules such as QuickView `priority`, id and class uniqueness, the flat ZIP layout, that no Maven placeholder anywhere in the packaged manifest was left unresolved, that `platform-sdk` is not bundled, and that every class the manifest declares is actually present in the packaged JAR. Exit code is non-zero when any error is found.

## Requirements

- Java 25+ and Maven 3.9+, matching the SDK baseline
- `dev.nuclr:platform-sdk` from [Maven Central](https://central.sonatype.com/artifact/dev.nuclr/platform-sdk) — no Nuclr checkout needed
- Python 3.10+ to run the validator

## Related

- [Plugin SDK](https://github.com/nuclrdev/plugins-sdk) — interfaces, javadoc, and the authoritative contract
- [Nuclr Commander](https://github.com/nuclrdev/commander) — the host application
- Example plugins, all public under [github.com/nuclrdev](https://github.com/nuclrdev): `plugin-quick-viewer-vcf`, `plugin-filepanel-zip`, `plugin-screenpanel-text-editor`, and others named in the reference files

## License

Apache-2.0. See [LICENSE](../LICENSE).
