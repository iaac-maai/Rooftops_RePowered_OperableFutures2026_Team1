# Google Stitch connection

Requested project: **Roofscapes Research Studio**. Persistent design context is
stored in [design-tools.json](../design-tools.json). Its `project_url` and
`project_resource` identify the verified private project. Authentication and the
exact approved original HTML-reference upload are complete.

[Open Roofscapes Research Studio](https://stitch.google.com/projects/15516450235999637621)
(Google sign-in required; URL derived from the API-verified project resource).

The official endpoint `https://stitch.googleapis.com/mcp` is registered as the
global Codex MCP server `stitch`. Automatic OAuth registration returned
`Dynamic client registration not supported`. The connector therefore uses Stitch's
documented API-key authentication through a local Windows credential helper.
Registration and authentication are complete on this Windows account. The steps
below remain available for credential replacement or a different installation.

Use the masked setup window already opened, or launch it locally:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ui/integrations/setup-stitch.ps1
```

Sign in at [Stitch](https://stitch.google.com/?pli=1), create an API key in
Settings → API Keys, and paste it into that local masked prompt. Do not paste it
into chat. The credential is encrypted using Windows DPAPI for the current user
under local AppData (`Roofscapes/Stitch/credential.xml`), outside this repository.
The helper decrypts it only for request headers; it is not written to source,
browser JavaScript, exports, reports or Git. Never run the header helper directly
in a logged/shared terminal: its output is for Codex's internal header channel.

Setup verifies the MCP handshake/tool catalog and creates the explicitly requested
project if the service's creation schema is compatible. A prior uncertain creation
attempt must be reviewed using `list_projects` before retrying; the script avoids
blind duplicate creation. Project/screen identifiers are service-verified; the
derived browser-link basis is recorded explicitly in the configuration.

After successful setup, restart the Codex extension to load the new connector.
Verify registration with `codex mcp get stitch --json`; the header helper is redacted.
Account verification can be repeated without creating a project:

```powershell
.\.venv\Scripts\python.exe -m ui.integrations.stitch
```

Future Codex sessions: read `ui/design-tools.json` and this file. Once authenticated,
use the returned project resource for graphic changes, preserve the seven views
and data bindings, and review changes against `ui/docs/screenshots/`. Screenshot
references, the original prototype and [the project brief](../stitch/PROJECT_BRIEF.md)
are ready. The approved original HTML was uploaded once and verified read-only
through `list_screens`; its source hash/resource are recorded in the configuration.
No redesign or two-way backend synchronization was performed. Scientific files
remain the authority for numbers. The upload adapter follows Google's published
BatchCreateScreens contract and keeps credentials/signed file URLs out of logs.

Official references: [Google Stitch MCP setup](https://stitch.google.com/docs/mcp/setup/),
[Google-hosted readable setup](https://app-companion-430619.appspot.com/docs/mcp/setup/index.html),
[Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).
