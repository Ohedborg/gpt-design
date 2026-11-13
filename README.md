# GPT Design — v0.6.1

A personal Codex design-system studio with imports, live component exploration, editable guidelines and independent design-system publications. It is not a full canvas editor or a hosted multiuser service.

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

This repository stores plugin code in `plugins/gpt-design/` and publications in `design-systems/<system-name>-<id>/`. On each machine, install the plugin once, sign in with `gh auth login`, and connect `Ohedborg/gpt-design`, branch `main`, folder `design-systems`. Every person needs access to this private repository. New design-system publications are downloaded independently of plugin-code updates.

## Your Simple Design System

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

## Installation and development

Development source: `plugins/gpt-design`. Personal source: `~/.codex/plugins/gpt-design`. Marketplace: `~/.agents/plugins/marketplace.json` under PK Design Tools. Library and allowed import roots: `~/.codex/gpt-design/settings.json`. Plugin updates preserve that library and access configuration.

```sh
python3 install-personal.py
codex plugin add gpt-design@pk-design-tools --json
python3 -m unittest discover -s plugins/gpt-design/tests -v
```

Python 3.9+ serves the local studio and MCP stdio tools without third-party Python runtime dependencies. React previews additionally need the source's locked build dependencies. Read `skills/gpt-design/references/import-and-preview.md` before building/attaching a preview.

Data layout:

- `library/systems/<id>/system.json` — working draft and current publication pointer.
- `source/`, `assets/`, `previews/` — preserved source and draft preview artifacts.
- `history/` — previous draft manifests and preview backups.
- `releases/<number>/` — immutable publication snapshots, release notes and file hashes.

The server binds only to loopback, checks session tokens, request origins and allowed import roots, and rejects stale writes. Shared mutations check GitHub repository write access; local ownership is not ChatGPT workspace role enforcement. GPT Design is the user's custom plugin name, with no claim of official OpenAI or Anthropic authorship.
