# Common SDK and bundle contract

This is a self-contained snapshot of the Nuclr platform SDK 4.0.0 conventions used by the core plugins. When local sources declare a newer contract, follow them instead and update the generated project consistently.

## Baseline and layout

- Java 25 or newer and Maven 3.9 or newer.
- Maven coordinate `dev.nuclr:platform-sdk:4.0.0` with `provided` scope, resolved from Maven Central; no Nuclr checkout is required to build a plugin. The Commander host supplies the SDK at runtime, so it must never be bundled. Latest version: <https://central.sonatype.com/artifact/dev.nuclr/platform-sdk>.
- Typical project layout:

```text
plugin-name/
|-- pom.xml
|-- LICENSE
|-- THIRD-PARTY-NOTICES.txt       when runtime dependencies require notices
`-- src/
    |-- assembly/plugin.xml
    |-- main/java/<package>/...Plugin.java
    |-- main/resources/plugin.json
    `-- test/java/<package>/...Test.java
```

The distribution ZIP root contains `plugin.json`, the plugin JAR, optional `lib/` runtime JARs, and any intentionally distributed legal or asset files. It must not add an enclosing top-level directory.

## Shared Java lifecycle

`BaseNuclrPlugin` is a **sealed** interface permitting exactly `FilePanelNuclrPlugin`, `QuickViewNuclrPlugin`, and `FullscreenNuclrPlugin`. Implementing it directly is a compile error, not merely a convention. An entry class implements one subtype plus:

```java
void preinit(NuclrPluginContext context);
NuclrPluginContext getContext();
void init();
void unload();
void closeResource();
NuclrResource getCurrentResource();
boolean supports(NuclrResource resource);
boolean onFocusGained();
void onFocusLost();
boolean isFocused();
String uuid();
```

Optional shared methods include `getWindowTitle()`, `updateTheme(NuclrThemeScheme)`, `contextMenuItems(...)`, and `act(...)`.

SDK 4 manifest-based discovery loads only the exact entry classes declared in `plugin.json`. Shared abstract bases, collaborators, and test doubles do not need `@ExcludePlugin` merely because they implement or extend a plugin type; keep them out of the manifest. `@ExcludePlugin` remains relevant to legacy scan-based discovery. If a manifest-declared class carries it, the host skips that declaration, which usually indicates a manifest error.

### What SDK 4.0.0 removed

Everything a plugin merely *declares* about itself left the Java interfaces and now lives in `plugin.json`. Do not write, call, or expect these methods; they no longer exist:

- Gone from `BaseNuclrPlugin`: `type()`, `id()`, `name()`, `version()`, `description()`, `author()`, `license()`, `website()`, `pageUrl()`, `docUrl()`, `is(Type)`, `developer()`, `singleton()`.
- Gone from the subtypes: `priority()` on `QuickViewNuclrPlugin`, `role()` on `FullscreenNuclrPlugin`.

The `Type`, `Developer`, and `Role` enums remain as the vocabulary for the corresponding manifest values, but no SDK method takes or returns them. The Java baseline also moved from 21 to 25.

`preinit` receives `NuclrPluginContext`, which exposes the event bus (`getEventBus()`), theme (`getTheme()`), settings (`getSettings()`), and locale (`getLocale()`). `NuclrSettings` is namespaced — `set(namespace, key, value)`, `get(namespace, key)`, `getOrDefault(namespace, key, default)` — so pick one namespace string per plugin, typically the manifest `id`, and keep every key under it. It also exposes `isDeveloperModeOn()`. If implementing `NuclrEventListener`, subscribe after context injection and always unsubscribe in `unload`. The event bus invokes listeners synchronously on the emitter's thread; event payload maps are untyped, so validate keys and values at the boundary.

`supports` may run on a background thread. It must be thread-safe, must not assume the EDT, and must not display modal UI. Do not consume a one-shot input stream merely to answer support unless the format cannot be identified another way and the cost is bounded.

`openResource` receives an `AtomicBoolean` cancellation flag. Check it before work, during bounded read/parse loops, and before publishing results. Cancel superseded work when a new resource opens. Swing component creation and mutation belong on the EDT; filesystem, subprocess, parsing, and network work do not.

`act` receives a `NuclrPluginCallback` for progress and cancellation. Use `onStart`, periodic `onProgress`, `onComplete`, and `onError` consistently. Context-menu queries run on the live UI path, so derive them from current state without blocking I/O; execute their action types in `act`.

Do not infer lifecycle events from payload-key names. The host manages enablement through `plugin.disable`; ordinary plugins do not subscribe to it as a lifecycle notification. Cleanup belongs in the `closeResource()` and `unload()` callbacks. `plugin.unload` is used by Commander when displacing a mounted file-panel instance, not as a universal unload callback, and `plugin.uuid` is a payload key rather than an event type. Subscribe only to events required by the selected extension type and verify their payload contract against the target Commander revision.

## Resources

Anything shown or opened is a `NuclrResource` subclass. Populate a stable non-null resource UUID because equality and hashing use only `uuid`. Set `name`, `fullPath`, `folder`, readability, length, timestamps, and other flags truthfully. Use a local `Path` when one exists; use `null` for virtual or remote resources. Override `openInputStream(OpenOption...)` for readable virtual content, returning a fresh stream whose caller can close it.

Keep backing-service objects out of serialized metadata when possible. Use typed resource subclasses or small stable metadata values for navigation identity. Parent entries normally have the display name `..` and enough state to reconstruct their target.

## Manifest

`src/main/resources/plugin.json` is the only source of plugin metadata in SDK 4:

```json
{
  "schemaVersion": 1,
  "version": "${project.version}",
  "platformSdkVersion": "${platform.sdk.version}",
  "plugins": [
    {
      "class": "com.example.nuclr.ExamplePlugin",
      "type": "QuickView",
      "id": "com.example.nuclr.example",
      "name": "Example Quick Viewer",
      "version": "${project.version}",
      "description": "Previews example resources.",
      "author": "Example Author",
      "license": "Apache-2.0",
      "website": "https://example.com",
      "pageUrl": "https://example.com/example-plugin",
      "docUrl": "https://example.com/example-plugin/docs",
      "developer": "Community",
      "singleton": true,
      "priority": 100
    }
  ]
}
```

Required top-level fields are `schemaVersion` (currently `1`), nonblank `version`, nonblank `platformSdkVersion`, and a nonempty `plugins` array. Every entry requires nonblank `class`, `type`, `id`, `name`, `author`, `license`, and `developer`. Entry `version` falls back to bundle `version`, though the core projects declare it explicitly. `description` and URLs are optional. IDs and classes must be unique inside the bundle.

Values are case-sensitive:

- `type`: `FilePanel`, `QuickView`, or `Fullscreen`.
- `developer`: `Official` or `Community`.
- `singleton`: defaults to `true` if omitted; declare it explicitly.
- `priority`: applies to QuickView and lower values win. Declare it explicitly.
- `role`: required for Fullscreen and is `Viewer` or `Editor`.
- `connections`: optional boolean for FilePanel, default `false`. Set it to `true` only when the panel's root listing is saved accounts agents use (servers, profiles, connections); Commander then shows that root as a tab in Configs → Connections, driving it through the plugin's own context menu and `act`. Pair it with `actions.json` so agents can use those accounts.

Filter only `plugin.json`; copying resources through a globally filtered resource block can corrupt icons and native binaries.

## Maven packaging

The POM should define at least:

```xml
<properties>
  <platform.sdk.version>4.0.0</platform.sdk.version>
  <maven.compiler.release>25</maven.compiler.release>
  <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
</properties>

<dependencies>
  <dependency>
    <groupId>dev.nuclr</groupId>
    <artifactId>platform-sdk</artifactId>
    <version>${platform.sdk.version}</version>
    <scope>provided</scope>
  </dependency>
</dependencies>
```

If the code uses Lombok on JDK 23+, configure annotation processing explicitly with compiler `<proc>full</proc>` or `annotationProcessorPaths`; otherwise omit Lombok. Mark host-provided APIs as `provided` — the host supplies SLF4J, and Lombok is compile-time only — so they are not copied into `lib/`. Keep libraries needed only by the plugin at runtime in normal compile/runtime scope so they are copied to `target/plugin/lib`.

Configure resources in two blocks: a filtered include for `plugin.json`, then an unfiltered block excluding it. Give `maven-jar-plugin` an explicit `<finalName>${project.artifactId}-${project.version}</finalName>` so the JAR name at the ZIP root stays stable and the copy step can name it. During `package`, copy runtime dependencies to `target/plugin/lib` with `includeScope=runtime` (which excludes `provided`, and so the SDK), copy the filtered manifest and project JAR to `target/plugin`, and use Maven Assembly with `appendAssemblyId=false`. Run `mvn clean test` and `mvn clean package`; using `clean` prevents stale libraries from surviving in `target/plugin`.

Use this assembly descriptor shape:

```xml
<assembly xmlns="http://maven.apache.org/plugins/maven-assembly-plugin/assembly/1.1.2"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://maven.apache.org/plugins/maven-assembly-plugin/assembly/1.1.2 https://maven.apache.org/xsd/assembly-1.1.2.xsd">
  <id>plugin</id>
  <formats><format>zip</format></formats>
  <includeBaseDirectory>false</includeBaseDirectory>
  <fileSets>
    <fileSet>
      <directory>${project.build.directory}/plugin</directory>
      <outputDirectory>/</outputDirectory>
      <includes><include>**/*</include></includes>
    </fileSet>
  </fileSets>
</assembly>
```

Legal files can be added explicitly under `<files>`. Never inherit another project's signing configuration, keystore path, or credentials. Release signing is a separate, user-authorized concern; an unsigned bundle with a valid manifest is enough for development sideloading, subject to the gating rules under [Getting the build to actually load](#getting-the-build-to-actually-load).

## Verification

At minimum:

1. Run unit tests in headless mode where practical.
2. Run `mvn clean package`.
3. Open the ZIP and check `plugin.json` and the plugin JAR are at its root.
4. Confirm Maven placeholders were resolved in the packaged manifest.
5. Confirm each declared class is in the JAR and matches its manifest type.
6. Confirm `lib/` contains required runtime dependencies but not `platform-sdk`.
7. Run the bundled validator at `scripts/validate_plugin.py`, resolving it from the skill directory.

### Getting the build to actually load

A green build is not a loaded plugin. Two host rules routinely make a correct bundle a no-op:

- **Trust takes precedence, then version.** Commander scans several plugin directories (a per-user one, the working directory, and a legacy jar-adjacent one). A verified candidate always beats an unverified candidate with the same plugin `id`, regardless of version; within the same trust level, the highest `version` wins. A rebuilt bundle at an equal or lower version than a same-trust copy is silently ignored. Bump the version or remove the shadowing copy, and confirm from the host's log which candidate was loaded.
- **Unverified bundles load from a different directory, behind three gates.** A locally built ZIP carries no signature the host can check, so it does not belong in the plugin directories above. It is installed through the plugin manager's **Install from file…** action, which copies it into `~/.nuclr/commander/plugins-local/`, and the loader takes it last, after every signed plugin has claimed its id. All three of the following must hold before it runs:
  1. **Developer mode is on** (Settings ▸ Advanced). Switching it off unloads every local plugin immediately.
  2. **The unverified-plugin risk warning has been accepted.** Acceptance is recorded by warning version and by a digest of its wording, so a revised warning is put in front of the user again.
  3. **That exact bundle has been approved**, recorded as the SHA-256 of the bytes the user saw. Copying a ZIP into `plugins-local/` is never enough on its own, and every rebuild changes the hash — install and approve again after each build, or the previously approved copy keeps running.

  A local bundle also cannot take over the `id` of an already-verified plugin, nor stand in for the mandatory file-panel bundle, so a fork of an existing plugin must change its `id` before it will load at all.
