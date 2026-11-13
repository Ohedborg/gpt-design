# Shared GitHub library — v0.6

The studio's **Connect GitHub library** button connects an existing repository and folder. For private storage, sign in once through GitHub CLI on each machine. Then connect the same repository, branch and folder on every installation.

**Publish** sends the saved system to GitHub in one non-force commit. Other installations download published versions when opening the library or choosing **Sync now**. Each system has independent numbered publications. The plugin remains installed; content updates require no reinstall. Ongoing consumers stay pinned to their selected publication.

Repository readers can consume shared systems. Repository writers can edit local drafts and publish. Drafts remain local, and edited drafts are never overwritten by sync. A stale draft offers **Start from latest**, which backs up the draft before loading the new publication. The existing version-history and rollback controls also work with shared publications.

The repository contains a catalog and one named folder per system. Current tokens and guidelines are readable files; version archives preserve the full source, assets and preview bundle. Checksums cover the archive and all files. A failed upload leaves the published pointer unchanged. Cached releases remain available offline with a visible sync error.

This release supports github.com and repository-level permissions. A hosted identity service, per-system collaborator invitations, automatic plugin-code upgrades, upstream Figma synchronization and updates to previously generated apps are separate work. See the skill reference `skills/gpt-design/references/github-library.md` for credential setup, storage layout and operational limits.
