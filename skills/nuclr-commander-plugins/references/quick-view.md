# QuickView plugins

Use `QuickViewNuclrPlugin` for a lightweight preview embedded in Commander's side panel.

## Required behavior

In addition to the shared lifecycle, implement:

```java
JComponent panel();
boolean openResource(NuclrResource resource, AtomicBoolean cancelled);
```

Declare `"type": "QuickView"`, an explicit `priority`, and usually `"singleton": true` in the manifest. When multiple quick viewers support a resource, the lowest priority wins. Use a narrow low number for a specialized format and a higher number for a broad fallback; confirm nearby core priorities before choosing.

## Selection and loading

- Make `supports` null-safe and deterministic. Prefer extension, MIME-like metadata, a bounded magic-header check, or another cheap discriminator. Do not show errors or mutate the panel during the probe.
- Return `false` from `openResource` when the resource became unsupported or opening never started. Return `true` only after accepting ownership of the preview operation.
- Before a new open, cancel or invalidate the previous operation. Use a generation token as well as cancellation when stale asynchronous results could arrive late.
- Read through `NuclrResource.openInputStream(...)` so remote and virtual resources work; use `getPath()` only as an optimization or when a third-party library strictly requires a local file. If materializing to a temporary file, bound disk use and delete it on close/unload.
- Never load an unbounded file fully into memory. Define a format-appropriate size, item, page, pixel, expansion, or parse-depth limit and explain truncation in the UI.
- Parse or render off the EDT. Publish a loading state, final view, and recoverable error state on the EDT, but do not show modal dialogs for normal preview failures.

`panel()` may construct lazily, but it must always return a non-null root component. Apply the current theme at creation and in `updateTheme`. Clear resource-specific content in `closeResource`; in `unload`, cancel work and release timers, listeners, executors, documents, media/native handles, and temporary files.

Quick views commonly do not accept focus; returning `false` from `onFocusGained` and `isFocused` is valid. If the preview is interactive, focus methods must reflect the component tree rather than a stale boolean.

## Tests

Cover supported and rejected filenames/content, null and folder resources, malformed or adversarial input, size limits, cancellation, superseded loads, cleanup, theme updates, and a meaningful property of rendered state. Run Swing assertions on the EDT and make headless behavior explicit.

Useful core plugins to inspect, all public under <https://github.com/nuclrdev>:

- [`plugin-quick-viewer-vcf`](https://github.com/nuclrdev/plugin-quick-viewer-vcf) for a small parser-plus-panel split.
- [`plugin-quick-viewer-text`](https://github.com/nuclrdev/plugin-quick-viewer-text) for broad fallback selection and asynchronous state.
- [`plugin-quick-viewer-image`](https://github.com/nuclrdev/plugin-quick-viewer-image), [`plugin-quick-viewer-pdf`](https://github.com/nuclrdev/plugin-quick-viewer-pdf), or [`plugin-quick-viewer-archive`](https://github.com/nuclrdev/plugin-quick-viewer-archive) for bounded rich-format parsing.
- [`plugin-quick-viewer-music-sdl2`](https://github.com/nuclrdev/plugin-quick-viewer-music-sdl2) or [`plugin-imagemagick-bridge`](https://github.com/nuclrdev/plugin-imagemagick-bridge) for native handles and external process bridges.
