# FilePanel plugins

Use `FilePanelNuclrPlugin` for a browseable hierarchy shown in either Commander pane: filesystems, archives, remote machines, buckets, repositories, containers, or another virtual tree.

## Required behavior

In addition to the shared lifecycle, implement:

```java
NuclrResourceData openResource(NuclrResource resource, AtomicBoolean cancelled);
String getCurrentLocationDisplayText();
String getSelectionSummaryText(List<NuclrResource> selectedResources);
```

Useful optional contracts are the streaming `openResource(..., EntrySink)`, `getPluginMenuItems()`, `menuItems(...)`, `walkDescendants(...)`, and `openTerminal(...)`.

Return `null` when a resource does not belong to the plugin or cannot be recognized as an entry point. For a handled empty folder, return a non-null `NuclrResourceData` with columns and no child entries except any appropriate parent row.

## Navigation and listing

- Model every row as a `NuclrResource`; do not leak raw provider records into the UI layer.
- Set `currentResource` to the directory represented by the completed listing. Avoid publishing a partially switched state if opening is cancelled or fails.
- Columns bind **by name, not by position**. The host renders a cell as `resource.getMetadata().getOrDefault(columnName, "-")`, so every column name declared in `NuclrResourceData` must exist as a key in each row's metadata map, spelled identically. A missing key renders as `-`. The order of `columnNames` sets only the default display order, and the user may reorder or hide columns anyway.

  ```java
  var columns = List.of("Name", "Size", "Modified");
  data.setColumnNames(columns);

  var row = new MyResource(...);
  row.getMetadata().put("Name", entry.name());          // keys match columns exactly
  row.getMetadata().put("Size", humanReadable(entry));
  row.getMetadata().put("Modified", formatted(entry));
  ```
- Include an explicit `..` parent resource below a logical root. At the logical root, either omit it or supply a purpose-built close/back entry when embedding a mount-like panel.
- Make `supports` accept the plugin's own navigation resources. A mount-style panel may also accept an external source file only while no image is already open.
- Sort only when the provider owns ordering. If Commander menu actions perform sorting, return stable raw rows and expose the matching `filepanel.sort:*` menu action.
- Override the streaming overload for slow or large listings: call `sink.columns(...)` once before `sink.add(...)`, check cancellation between entries/pages, and still return the complete final data snapshot.

`getPluginMenuItems()` populates Alt+F1/Alt+F2 entry points. Return a holder whose menu resources are self-contained roots. Mount-style panels opened from a file may not need a drive-selector entry.

## Actions and transfer semantics

Host action and event strings in use across the core plugins:

| Action | Purpose |
|---|---|
| `filepanel.path.opened` | the user activated the focused entry; Commander resolves and opens its target |
| `filepanel.path.selected` | the focused row changed |
| `filepanel.navigate.to.path` | request navigation to a specific path |
| `filepanel.goto.folder` | jump-to-folder request |
| `filepanel.visibility.changed` | the panel was shown or hidden |
| `filepanel.view` | open the focused resource in a viewer |
| `filepanel.edit` | open the focused resource in an editor |
| `filepanel.copy` / `accept.copy` | outbound copy from this panel / inbound copy into it |
| `filepanel.move` / `accept.move` | outbound move / inbound move |
| `filepanel.delete` | delete to trash where the provider supports it |
| `filepanel.deletePermanent` | unrecoverable delete |
| `filepanel.makeFolder` | create a directory |
| `filepanel.unmark.entry` | clear a row's selection mark |
| `filepanel.sort:<criterion>[:<Column>]` | sorting; also `filepanel.sort:unsorted` and `filepanel.sort:dialog` |
| `refresh.panel` | refresh the panel that raised the event |
| `refresh.plugin.file.panel` | refresh a plugin-backed panel |
| `refresh.file.panels.at.paths` | refresh whichever panels are showing the given paths |

A copy or move pairs an outbound action on the source panel with the matching `accept.*` action on the destination, so a panel that implements `filepanel.copy` but not `accept.copy` can export but not import. Implementing move is a separate decision from implementing copy; do not assume one implies the other.

Payload keys are not action types. For example, `refresh.source.plugin.uuid` identifies the originating plugin instance in a refresh-event payload, and `plugin.uuid` is likewise a payload key. `plugin.unload` is a file-panel displacement request, not the lifecycle callback; release resources in `unload()`. Verify event names and payloads against the Commander version being targeted, and keep constants in one place. Treat `other` as the opposite or collaborating plugin and use `instanceof` for its subtype; SDK 4 has no runtime metadata methods such as `other.id()` or `other.is(...)`.

For outbound copy, use the selected rows, falling back to the focused row only when the selection is empty. For inbound copy, implement `accept.copy` only when the destination can genuinely write. Read-only panels should reject mutations clearly and must not silently acknowledge them. Check cancellation during recursion and byte-copy loops, report progress, resolve conflicts deliberately, and refresh only affected panel instances after success.

`walkDescendants` is heavy I/O. Honor its cancellation flag and `recursive=false`. Never follow provider links into cycles without a visited set or depth bound.

`openTerminal` returns `null` to request Commander's local shell fallback. Throw `IOException` when this plugin intended to provide a remote shell but could not start it. It runs off the EDT and may block for connection or authentication.

## Instance and cleanup rules

File panels are often multi-instance because both Commander panes can host the same provider. Use `"singleton": false` and a fresh UUID per Java instance unless the product explicitly needs one global panel. Do not share mutable current-directory or cancellation state between instances.

Close open archives, remote sessions, pagers, process streams, temporary materializations, and background executors. Temporary local copies of remote content need an ownership flag so a plugin never deletes the user's original file.

## Tests

Cover root and child navigation, parent behavior, empty folders, unsupported foreign resources, cancellation mid-listing, unique IDs, streaming sink order, selection summaries, and cleanup. For writable panels, test copy direction, conflict policy, traversal safety, partial failure, cancellation, and refresh events. Use fake provider services rather than real cloud accounts, remote hosts, containers, or credentials.

Useful core plugins to inspect, all public under <https://github.com/nuclrdev>:

- [`plugin-filepanel-fs2`](https://github.com/nuclrdev/plugin-filepanel-fs2) for local filesystem breadth, column metadata, and test seams.
- [`plugin-filepanel-docker`](https://github.com/nuclrdev/plugin-filepanel-docker) or [`plugin-filepanel-gcp`](https://github.com/nuclrdev/plugin-filepanel-gcp) for virtual hierarchies and streaming listings.
- [`plugin-filepanel-iso`](https://github.com/nuclrdev/plugin-filepanel-iso) or [`plugin-filepanel-zip`](https://github.com/nuclrdev/plugin-filepanel-zip) for mount-like, read-only panels and resource streaming.
- [`plugin-filepanel-s3`](https://github.com/nuclrdev/plugin-filepanel-s3), [`plugin-filepanel-net`](https://github.com/nuclrdev/plugin-filepanel-net), and [`plugin-filepanel-github`](https://github.com/nuclrdev/plugin-filepanel-github) for remote and credentialed providers.
