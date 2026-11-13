# GPT Design — v0.6.2

A personal Codex design-system studio with imports, live component exploration, editable guidelines and independent design-system publications. It is not a full canvas editor or a hosted multiuser service.

## Fresh rebuild in another Codex environment

**Start here to build your own independent installation.** Give another Codex environment this README and the brief below. It should create a new project from the documented behavior and implementation references, with an empty library and new configuration. This is a rebuild task, not a request to clone this repository, copy the author's installation, or join the author's shared library.

This private repository must be readable by the new environment to inspect the implementation. Access to this reference repository does **not** select it as the new installation's publishing destination.

### Copy this brief into Codex

```text
Rebuild GPT Design as a fresh, independent Codex plugin in this environment.
Use this README and plugins/gpt-design/ as read-only implementation references.
Read individual source files through authorized GitHub access as needed. Do not
clone or fork this repository, copy an installed plugin/cache, or import its
existing design systems. Create the implementation in a new, empty project.

Keep the existing studio layout and neutral colors. Recreate:
- Imports from GitHub, local folders and uploaded files; tokens, assets,
  preserved component source, guidelines and source inspection.
- A library chooser, token editing, editable overview/guidelines, and component
  playgrounds when a source-specific preview has actually been built.
- Independent immutable publications, version history and rollback as a new
  release, with local working drafts and consumers pinned to a publication.
- Optional GitHub backing: adding a system uploads its initial version;
  publishing uploads the next version; other installations check automatically.
  Preserve dirty drafts, retry frozen initial uploads, reject stale writes,
  and keep credentials outside code, archives and committed configuration.
- Rename and confirmed deletion, shared catalog updates, and recovery copies.
- The studio MCP tools and import/build/review/maintenance skills.

Create fresh project-specific settings: plugin/marketplace identity, library
location, allowed import folders and optional GitHub destination. Ask only for
choices that are missing. Start with zero systems and GitHub disconnected.
Do not reuse Ohedborg/gpt-design as the destination, PK Design Tools registration,
any personal filesystem paths, saved system IDs, GitHub bindings, credentials,
preview artifacts or existing settings.json from the reference installation.

Adapt the installer, runtime settings namespace, plugin manifests and skill
instructions together. Existing GPT Design settings must not be loaded as a
fallback. Preserve other installed plugins and marketplace entries. If another
GPT Design installation exists, give this one a distinct identity and settings
location instead of overwriting it. Generate an installation report here; do
not copy the original report or claim its verification results as your own.

The bundled install-personal.py is for the original maintainer's setup. Do not
run it unchanged for this rebuild. Create an installer for this environment,
register its local marketplace, and verify the available Codex CLI commands.
Use Python 3.9+ for the local server. Live previews additionally need the actual
source project's locked dependencies and a reviewed source-specific adapter.
Do not execute imported source merely to scan tokens or component inventory.

Use a new Git repository only if requested for the new project, with its own
remote. Connect a shared library only to a destination selected by this user.
The shared folder can be design-systems/, with one stable folder per system.

Run the relevant tests, install this fresh build, and open it in Codex. Verify
an empty, disconnected first launch before adding disposable test content.
Exercise import, editing, publication, rename and deletion. If GitHub backing
is configured, verify automatic publication and updates in a second isolated
library without touching the reference repository's publications. Report what
was verified and any setup still required. Never claim the embedded UI works
based only on installation or server tests.
```

### Implementation map for the rebuilding agent

All paths below are relative to `plugins/gpt-design/`:

| Area | Reference |
| --- | --- |
| Plugin registration and launch | `plugin.json`, `.codex-plugin/plugin.json`, `mcp.json`, `.mcp.json` |
| MCP tools and embedded studio | `skills/gpt-design/scripts/mcp_server.py` |
| Imports, token storage and local HTTP API | `skills/gpt-design/scripts/gpt_design.py` |
| Studio layout, colors and interactions | `skills/gpt-design/assets/studio/` |
| Guidelines, preserved files and previews | `skills/gpt-design/scripts/studio_features.py` |
| Immutable releases and rollback | `skills/gpt-design/scripts/releases.py` |
| Automatic GitHub library updates | `skills/gpt-design/scripts/github_library.py` |
| Rename and recoverable deletion | `skills/gpt-design/scripts/system_management.py` |
| Consumer and maintenance workflows | `skills/` |
| Behavior checks and disposable import fixture | `tests/`, `examples/starter/` |

The current runtime uses Unix file locking (`fcntl`); a native Windows rebuild needs an equivalent locking implementation or a Unix environment such as WSL. The core studio has no third-party Python runtime dependencies. There is no compiled application bundle to inherit; preview builds are separate and depend on the imported source.

**Fresh configuration is part of the rebuild.** The reference runtime reads `~/.codex/gpt-design/settings.json`, and the reference installer preserves it. Merely changing the project folder does not isolate an installation. The rebuilding agent must give its runtime and skills the new settings location and create new `libraryPath` and `allowedRoots` values. Keep library data outside plugin caches. Do not seed the new library from this repository's `design-systems/`, local `library/`, `github-library.json`, history, trash or release archives. New imports receive new IDs.

Email sign-in, organization invitations and a hosted team service are **not implemented in this version**. A fresh build must not present those as working features. The current shared-library implementation uses each user's GitHub access. Plugin software upgrades and design-system publications are separate.

## Open and use

Open **GPT Design** in Codex. After updating, close and reopen the panel; if the old version remains, reload the plugin or restart Codex. Installation alone does not prove an already-open host has refreshed.

With multiple systems, the studio opens a chooser instead of restoring the last-opened system. An explicit system selection opens directly; with one system it opens automatically. Skills ask which system to use for each new task unless the user has already selected one, then retain that selection for the task. Named systems and IDs take precedence; ambiguous or missing names require clarification. Selected systems open at Overview, using the current published release when one exists. Choose **Edit draft** to maintain the saved working copy. Source files remain read-only. Changes do not modify the upstream repository.

- **Components:** real source examples with a Playground, source-derived properties, reset, light/dark theme and preview width. Boolean properties have Component default, true and false. Default properties establish initial state; controlled properties override it. Changing props restarts the example. There is no separate permutations view.
- **Guidelines:** edit the introduction, principles and component usage notes; copy prompts for the companion skills.
- **Colors and Typography:** inspect and edit saved tokens, compare simple light/dark declarations, add tokens and view type specimens.
- **Files and Assets:** search the stored source, inspect code and documentation, view or download preserved assets.
- **Publish:** freeze the saved draft with release notes. Publications include tokens, guidelines, source files, assets and compiled previews. Future draft changes cannot alter them.
- **Version history:** opens on demand from the history icon. View old releases or roll back by creating a new publication from the old content. The current working draft and all previous releases remain intact.

Publishing a system does not reinstall or republish the plugin. Use **Connect GitHub library** to choose a shared repository and design-systems folder. **Add design system** automatically uploads its initial version 1. **Publish** sends each later version directly to the connected repository. Other installations check on opening and every minute while the studio is visible, without a manual sync step. Failed initial uploads are visibly queued and retried automatically; retries preserve later draft edits. **Back up to GitHub** remains available only for older local publications. Without a connection, publications stay local. Repository readers can consume shared systems; writers can maintain and publish them. Per-system collaborator invitations and ChatGPT workspace identity remain future work. See [GitHub library setup](plugins/gpt-design/docs/github-library.md).

This repository stores plugin code in `plugins/gpt-design/` and the author’s publications in `design-systems/<system-name>-<id>/`. Only people explicitly joining the author’s existing library should connect `Ohedborg/gpt-design`, branch `main`, folder `design-systems`, using their own GitHub access. Independent rebuilds choose their own destination. New design-system publications are downloaded independently of plugin-code updates.

## Reference installation: Simple Design System

This describes the author’s existing data, not starter content for a fresh installation.

The existing system is retained at `library/systems/602d3a7cd1314732bfd4cb6678fb08d9`, pinned to figma/sds commit `05525f75192a3aa5d5690c5e41277ebd19d2efe1`. It contains 1,255 token declarations, 342 component source files, 568 preserved source/file entries, and 58 live examples across 31 story files. A source-file count is not a count of live examples. The preview uses real React components and source stories. CheckboxField and SwitchField use small direct-component adapters to expose supported state props that their source stories do not forward.

The runtime is built in an isolated checkout using the source lockfile. Imports do not execute source code. Previews run in an opaque sandboxed child frame without network or top-level navigation access. External fonts and images may fall back or be unavailable. Fixed compositions may have no editable props. The source and dependency license notices are retained with the snapshot/build checkout.

## Skills

- `$gpt-design` — import and inspect systems.
- `$gpt-design-build` — build from a pinned publication and its guidelines.
- `$gpt-design-review` — review against the real tokens, contracts and guidance.
- `$gpt-design-maintain` — maintain drafts, compare source changes, prepare previews, publish and roll back.

Consumer skills use the current publication by default and identify the version they used. Draft edits do not silently change a consumer's pinned version.

## Imports and limits

Choose one of three import sources: a **GitHub repository**, a **local folder**, or **uploaded files** such as CSS/JSON tokens, component source, fonts, images and guidelines. Figma links, `.fig` files and generic connector requests are no longer import routes. Existing saved snapshots remain available. Private repositories require an authorized checkout or connected tool. The static scanner extracts CSS/SCSS custom properties and JSON token leaves with provenance. It does not evaluate Sass, Tailwind configuration or arbitrary source code. Categories are inferred; aliases/composite values may remain in JSON and be omitted from conservative CSS export. There is no automatic continuous source sync or bidirectional Figma sync.

New imports preserve eligible source files. Older snapshots without source content report the missing content; restore it from their recorded commit rather than inventing files. Preview builds for other codebases require a reviewed adapter and actual browser verification; the included builder currently targets the SDS React story structure.

## Maintainer installation and development

These commands update the author’s existing registration and intentionally preserve its settings. For an independent installation, use the [fresh rebuild brief](#fresh-rebuild-in-another-codex-environment) and generate an environment-specific installer instead.

Development source: `plugins/gpt-design`. Personal source: `~/.codex/plugins/gpt-design`. Marketplace: `~/.agents/plugins/marketplace.json` under PK Design Tools. Library and allowed import roots: `~/.codex/gpt-design/settings.json`. Plugin updates preserve that library and access configuration.

```sh
python3 install-personal.py
codex plugin add gpt-design@pk-design-tools --json
python3 -m unittest discover -s plugins/gpt-design/tests -v
```

Python 3.9+ serves the local studio and MCP stdio tools without third-party Python runtime dependencies. React previews additionally need the source's locked build dependencies. Read `plugins/gpt-design/skills/gpt-design/references/import-and-preview.md` before building/attaching a preview.

Data layout:

- `library/systems/<id>/system.json` — working draft and current publication pointer.
- `source/`, `assets/`, `previews/` — preserved source and draft preview artifacts.
- `history/` — previous draft manifests and preview backups.
- `releases/<number>/` — immutable publication snapshots, release notes and file hashes.

The server binds only to loopback, checks session tokens, request origins and allowed import roots, and rejects stale writes. Shared mutations check GitHub repository write access; local ownership is not ChatGPT workspace role enforcement. GPT Design is the user's custom plugin name, with no claim of official OpenAI or Anthropic authorship.


## Manage a design system

Use the **•••** control on a library card or in the open system’s header. **Save name** updates the library identity immediately, including the GitHub catalog for shared systems. The system ID, repository folder and published archives stay unchanged. Published views use the current library name; their archived content remains immutable. Edit the introduction, description and principles under **Edit draft → Guidelines**, then publish to share those content changes.

**Delete design system** requires typing its current name. A shared deletion removes its entry from the active GitHub catalog, records it in `deletedSystems`, and marks its folder as removed. Other installations remove their matching cached system on the next automatic check. Existing archives remain available for recovery. The full local system, including unpublished drafts, moves to `library/trash/<id>-<unique-suffix>/`; it is not permanently erased. Pending initial uploads are cancelled and deleted systems cannot be republished by a stale client using this version.

Only repository writers can rename or delete a shared system. A failed or conflicting GitHub write leaves the local system in place. Local-only systems can be managed without GitHub. Recovery is currently an administrator operation: restore the saved folder from `trash` for a local system; for a shared system, restore its catalog entry from `deletedSystems` in a new GitHub commit, preserving existing archives and checksums. There is no automatic trash purge.
