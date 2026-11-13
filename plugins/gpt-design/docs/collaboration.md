# Collaborator model for a shared GPT Design library

GitHub-backed publishing is available in v0.6. Repository readers can consume published systems; repository writers can maintain drafts and publish. Each installation connects the same repository, branch and folder using its own GitHub credentials. Drafts stay on the author's machine. See `github-library.md` for the implemented model.

The future hosted model would reuse the user's ChatGPT/Codex identity, without a separate company login requirement. The creator would become owner, with exclusive collaborator and ownership management. Named editors would maintain drafts and publish/roll back. Other authorized workspace consumers would view published releases and use the playground. This finer-grained model is not implemented; current authorization follows GitHub repository permissions.

A future shared service must derive the subject and workspace from verified identity, never a model-supplied user ID or email. Every system, source, asset, export, preview, publication and collaborator operation needs authorization at that service. Workspace membership grants consumption only; ownership or explicit editor membership grants mutations. Removing an editor takes effect on the next request. Personal forks may be editable without granting access to the canonical shared system. Old publications remain immutable and clients pin a release during generation.

Identity integration remains unresolved for this local installation. OpenAI documents Continue with ChatGPT for plugins, currently limited to selected commercial partners. Its login hint is not verified identity. The plugin API and available tools inspected do not establish a general workspace-member directory for this custom plugin. Pages sharing tools belong to Page/Space resources and are not a permission API for arbitrary GPT Design systems. Do not imply otherwise or scrape the host's private authentication state.

Reference: https://developers.openai.com/siwc/chatgpt-plugin (checked 2026-11-13).
