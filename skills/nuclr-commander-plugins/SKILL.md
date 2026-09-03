---
name: nuclr-commander-plugins
description: Create, extend, or repair Java plugins for Nuclr Commander using the platform SDK's FilePanel, QuickView, or Fullscreen extension types. Use for plugin scaffolding, manifests, Maven bundles, lifecycle behavior, resource adapters, Swing panels, and plugin-focused tests; do not use for changes confined to the Commander host application.
---

# Nuclr Commander plugins

Build a complete, testable plugin bundle that follows the SDK version present in the target project. Treat the SDK on the project's classpath as authoritative; the reference files in this skill describe SDK 4.0.0 and Java 25.

## Discover the contract

The SDK is published on Maven Central as `dev.nuclr:platform-sdk`, so a plugin project needs nothing but Maven and a JDK to build. Establish the contract in this order:

1. The SDK attached to the project. Read the interface being implemented from its sources JAR, or from <https://github.com/nuclrdev/plugins-sdk> — that README is the authoritative statement of the current contract and of what changed in 4.0.0.
2. An existing plugin of the same type. Every core plugin is a public repository under <https://github.com/nuclrdev>; the per-type reference files below name the most instructive ones. Reuse structure and conventions, never product-specific code, signing configuration, or namespaces.
3. The bundled [references/common-contract.md](references/common-contract.md), a self-contained snapshot of SDK 4.0.0. Use it when SDK sources are not at hand, and state the version assumed.

Prefer the SDK actually on the project's classpath over the bundled snapshot. If the working checkout also contains `platform-sdk/`, `commander/`, or `plugins/core/`, treat those sources as the working revision of the contract.

## Choose the extension type

Implement exactly one of the SDK's three direct plugin interfaces per entry class:

| User outcome | Interface | Manifest `type` | Read |
|---|---|---|---|
| Browse a filesystem, archive, service, or virtual hierarchy in a commander pane | `FilePanelNuclrPlugin` | `FilePanel` | [references/file-panel.md](references/file-panel.md) |
| Preview a supported resource in the side panel | `QuickViewNuclrPlugin` | `QuickView` | [references/quick-view.md](references/quick-view.md) |
| Open a full-window viewer or editor | `FullscreenNuclrPlugin` | `Fullscreen` | [references/fullscreen.md](references/fullscreen.md) |

A bundle may declare multiple entry classes, including more than one type. Keep each manifest entry aligned with the interface its class implements.

## Implement the plugin

1. Confirm the requested behavior, supported resources, read/write semantics, plugin identity, and whether the host may create multiple instances. Make conservative assumptions for missing presentation details; do not invent mutation capabilities.
2. Create a Maven project with `dev.nuclr:platform-sdk` in `provided` scope, Java 25, filtered `plugin.json`, unfiltered binary resources, a plugin JAR with a stable final name, copied runtime dependencies under `lib/`, and a flat distribution ZIP. Follow [references/common-contract.md](references/common-contract.md).
3. Implement the entry class and keep parsing, transport, and UI concerns in focused collaborators when they are non-trivial. `BaseNuclrPlugin` is `sealed` and cannot be implemented directly — extend one of the three permitted subtypes. Do not put declarative metadata methods in Java; SDK 4 moved identity and selection metadata to `plugin.json`. SDK 4 loads the exact entry classes declared in `plugin.json`; keep helper classes and test doubles out of that list. Use `@ExcludePlugin` only when working with legacy scan-based discovery or when the target host contract explicitly requires it.
4. Make lifecycle ownership explicit. Store the context in `preinit`, initialize only what is needed in `init`, cancel active work in `closeResource`, and release executors, streams, native handles, temporary files, subscriptions, and UI resources in `unload`.
5. Make capability checks null-safe, thread-safe, free of modal UI, and as cheap as practical. `supports` can run off the Swing event-dispatch thread. For expensive opening or actions, honor the supplied cancellation flag or callback. Marshal Swing mutations onto the EDT.
6. Use a stable constant from `uuid()` only for a singleton. When `singleton` is false, create a distinct UUID for every instance. A plugin entry's stable manifest `id` is not automatically its instance UUID.
7. Add tests around support detection, cancellation, lifecycle cleanup, resource navigation or rendering, malformed input, and any destructive behavior. Prefer service injection or package-private seams over live network, CLI, or desktop dependencies in unit tests.
8. Run the project's tests and package from a clean target directory. Validate source and bundle shape with the bundled `scripts/validate_plugin.py`. Resolve the script relative to this `SKILL.md` rather than assuming it is in the plugin project's working directory:

   ```text
   <skill-dir>/scripts/validate_plugin.py <project-dir> --archive <zip>
   ```

   Run it with whichever Python 3 launcher the platform provides (`python3`, `python`, or `py`). Inspect the ZIP root and confirm it does not contain `platform-sdk`.

## Delivery constraints

- Preserve unrelated user changes and the repository's existing naming, license, and build conventions.
- When adapting an existing plugin, take its structure and conventions only. A new plugin needs its own Maven coordinates, package namespace, plugin `id`, and URLs. Never inherit another project's signing configuration, keystore path, credentials, deploy scripts, or machine-specific paths.
- Default new third-party entries to `"developer": "Community"`. Use `Official` only when the user is building an official Nuclr component.
- Keep credentials, tokens, private keys, and machine-specific paths out of source control. Add signing only when requested and obtain secrets from properties or the environment.
- Do not claim success from compilation alone. Run relevant tests, package the ZIP, validate it, confirm the host actually loaded the build, and report any checks that could not run.
