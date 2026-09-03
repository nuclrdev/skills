# Fullscreen plugins

Use `FullscreenNuclrPlugin` for a viewer or editor that replaces the normal Commander content area.

## Required behavior

In addition to the shared lifecycle, implement:

```java
JComponent panel();
boolean openResource(NuclrResource resource, AtomicBoolean cancelled);
```

Declare `"type": "Fullscreen"` and the required manifest `role` of `Viewer` or `Editor`. Role is metadata only in SDK 4; there is no Java `role()` method. A bundle may declare separate viewer and editor entry classes that share an implementation, as the core text and hex plugins do. SDK 4 registers only the two entry classes named in `plugin.json`; their shared abstract base does not need `@ExcludePlugin` unless the target host still uses legacy scan-based discovery.

## Viewer and editor semantics

- A `Viewer` never modifies the resource. Disable editing in the component and ensure save actions cannot run through alternate key bindings or event paths.
- An `Editor` should advertise support only when it can load safely. It may open a stream-only remote resource read-only, but its UI and menus must make that downgrade clear.
- Before saving a local file, track whether content changed and whether the backing file changed since open. Use a temporary sibling plus atomic replace when the filesystem supports it; handle fallback and failure without losing the original.
- On close with unsaved changes, offer an explicit save/discard/cancel decision. Cancellation must keep the editor open. During unload, do not assume modal interaction is safe; follow the current host close protocol.

Provide `menuItems(...)` for function-key actions such as save, search, and close. Route both menu/event-bus actions and direct `act(...)` calls through the same internal methods so keyboard, menu, and host dispatch behave identically. Confirm current host action strings before depending on them; `plugin.fullscreen.close` closes the screen, and the core editors namespace their own actions under their plugin (`plugin.text.editor.save`, `plugin.hex.editor.save`, and so on) rather than inventing new host-level strings. Follow that convention: prefix plugin-owned actions with the plugin's own identifier.

If implementing `NuclrEventListener`, make `isMessageSupported` reflect current capability so Commander can enable actions correctly. Subscribe once in `preinit` or `init`, and unsubscribe once in `unload`.

## UI and loading

Keep a single non-null root panel per plugin instance. Bind keyboard actions with Swing input/action maps at the appropriate ancestor focus scope. Derive `isFocused` from actual component focus when possible.

Perform content reads, decoding, parsing, indexing, and saves off the EDT when they can block. Check cancellation during long operations and prevent superseded loads from replacing newer content. Apply theme colors and fonts from `NuclrThemeScheme`, with UI defaults as fallbacks, and update already-created components in `updateTheme`.

Set `getWindowTitle()` from stable resource identity such as a path or resource name. Avoid rapidly changing state in the title unless the host explicitly supports it.

## Tests

Cover support detection, viewer immutability, editor save and failure paths, dirty tracking, close decisions, external modification conflicts, cancellation, event subscription cleanup, theme changes, and key/action routing. Run component mutations and assertions on the EDT. Use temporary files and fake stream-backed resources; do not overwrite repository fixtures.

Useful core plugins to inspect, both public under <https://github.com/nuclrdev>:

- [`plugin-screenpanel-text-editor`](https://github.com/nuclrdev/plugin-screenpanel-text-editor) for shared viewer/editor implementation, menus, focus, dirty state, and event actions.
- [`plugin-screenpanel-hex-editor`](https://github.com/nuclrdev/plugin-screenpanel-hex-editor) for separate manifest entries over a shared binary UI.
