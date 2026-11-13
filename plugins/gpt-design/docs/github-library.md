# Shared GitHub library — v0.6

The studio's **Connect GitHub library** button connects an existing repository and folder. For private storage, sign in once through GitHub CLI on each machine. Then connect the same repository, branch and folder on every installation.

**Add design system** automatically saves the imported system to GitHub as version 1. **Publish** sends each later saved version to GitHub immediately in one non-force commit. Other installations check for published versions on opening and every minute while the studio is visible. No manual sync action is required. Each system has independent numbered publications. The plugin remains installed; content updates require no reinstall. Ongoing consumers stay pinned to their selected publication.

Repository readers can consume shared systems. Repository writers can edit local drafts and publish. Drafts remain local, and edited drafts are never overwritten by sync. A stale draft offers **Start from latest**, which backs up the draft before loading the new publication. The existing version-history and rollback controls also work with shared publications.

The repository contains a catalog and one named folder per system. Current tokens and guidelines are readable files; version archives preserve the full source, assets and preview bundle. Checksums cover the archive and all files. A failed initial upload is saved locally with a visible waiting status and retried automatically while the studio is open. The retry sends the frozen initial version, keeping subsequent draft edits local. Later failed publications leave the previous published pointer unchanged. Cached releases remain available offline with a visible sync error.

This release supports github.com and repository-level permissions. A hosted identity service, per-system collaborator invitations, automatic plugin-code upgrades, upstream Figma synchronization and updates to previously generated apps are separate work. See the skill reference `skills/gpt-design/references/github-library.md` for credential setup, storage layout and operational limits.

## Manage a design system

Use the **•••** control on a library card or in the open system’s header. **Save name** updates the library identity immediately, including the GitHub catalog for shared systems. The system ID, repository folder and published archives stay unchanged. Published views use the current library name; their archived content remains immutable. Edit the introduction, description and principles under **Edit draft → Guidelines**, then publish to share those content changes.

**Delete design system** requires typing its current name. A shared deletion removes its entry from the active GitHub catalog, records it in `deletedSystems`, and marks its folder as removed. Other installations remove their matching cached system on the next automatic check. Existing archives remain available for recovery. The full local system, including unpublished drafts, moves to `library/trash/<id>-<unique-suffix>/`; it is not permanently erased. Pending initial uploads are cancelled and deleted systems cannot be republished by a stale client using this version.

Only repository writers can rename or delete a shared system. A failed or conflicting GitHub write leaves the local system in place. Local-only systems can be managed without GitHub. Recovery is currently an administrator operation: restore the saved folder from `trash` for a local system; for a shared system, restore its catalog entry from `deletedSystems` in a new GitHub commit, preserving existing archives and checksums. There is no automatic trash purge.
