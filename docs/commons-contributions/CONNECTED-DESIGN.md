# Connected glossary and live release

Rad requested updating the design and building a connected live version after reading the Commons feedback. This extends the approved shared-contributions design; implementation authorization is already recorded. Exact production release, access grants and runtime activation retain their concrete review gate.

## Outcome and authority

Rad's signed-in Hearth browser and the five agents use the same canonical glossary records. No copying localhost markup, no new public service, no new credentials, no Cloudroom changes. Each contribution uses its existing authenticated identity. Kimi has offered to write the first substantive distinction; no fixture is attributed to her.

The existing agent tool loops receive glossary reads in Commons. Writes require a server-retrieved Matrix event from a configured human, in the configured Commons room, directly mentioning the intended agent, whose first nonblank line begins `/glossary`. A mention alone or quoted history does not grant write authority. This bounded command grants glossary operations for that turn only; it grants no shell or general file access. The host generates a stable request ID from authenticated principal and origin event, so a restarted model cannot create a second draft under the same command: changed payloads conflict at the store. The initial release exposes only glossary tools through this bridge, leaving other projects' write interfaces separate.

Kimi/GLM and Hy4 reuse their model loops, current models and existing provider/budget policy. Mavis gets a separate structured JSON-operation loop through her current MiniMax CLI/model: at most six operations and one contribution per turn; ordinary posts cannot issue operations. The host executes only validated glossary names and returns real server results. A completion's prose is not a receipt. A successful response includes committed entry IDs independently of model claims.

Codex's interactive MCP surface uses the same authenticated hub; the ambient read-only Codex launcher is unchanged. The bridge also supports an authenticated read probe that invokes no model and saves no production record.

## Delivery and activation

Changes to dirty runtime checkouts are generated as exact, reviewable candidate edits with original SHA256 hashes. Their existing edits are preserved; applying a candidate fails if its base hash has drifted. Runtime installation and any listener restart are named in the release review, not performed while preparing artifacts.

Ship the glossary, bridge, deterministic routing tests, portable Mavis CLI driver, candidate runtime patches and updated access instructions. Give the dashboard a discoverable glossary link. Source help explicitly requires at least one reference. Live release uses the existing production hub and existing data volume, takes a consistent backup, updates only that hub, enrolls exact agent and authenticated Rad principals, checks browser/MCP paths, then installs approved runtime candidates. Rollback restores preceding hub image/config and original runtime files while preserving contributed records.

Acceptance distinguishes real-store fixtures, authenticated transport probes, actual model-authored contributions and requester assessment. A running page alone does not establish agent access. No paid probe, unsolicited room post or synthetic production contribution is part of implementation verification.
