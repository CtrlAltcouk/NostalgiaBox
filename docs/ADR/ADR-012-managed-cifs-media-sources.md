# ADR-012 — Use managed OS CIFS mounts for SMB/NAS media sources

- **Status:** Proposed
- **Date:** 2026-08-09

## Context

Phase 3 must let the administration WebUI configure SMB/NAS sources while the scanner, ffprobe and
MPV all need a stable path. Credentials, reconnects, boot ordering, permissions and network loss
must be controlled without giving the non-root backend broad privilege.

Options are direct SMB access inside Python, NostalgiaBox-managed OS CIFS mounts, or requiring every
administrator to pre-mount shares externally.

## Proposed decision

Use OS CIFS mounts managed through a narrow NostalgiaBox infrastructure boundary. Each source has a
stable mount path under `/run/nostalgiabox/media/<source-id>`. A privileged helper or templated
systemd mount integration owns validated mount/unmount operations and boot/network ordering. The
backend and MPV access the mounted filesystem as the dedicated non-root identity.

Store credentials in root-owned mode-`0600` files outside Git and the catalogue DB. Catalogue rows
contain only an opaque credential reference. Never put passwords in process arguments, API
responses or logs.

Externally pre-mounted paths remain an expert/local-folder option, not the primary managed SMB UX.

## Rationale

- Scanner, ffprobe and MPV share one kernel filesystem and path/permission model.
- Linux CIFS/systemd provide mature reconnect and ordering mechanisms.
- The Python core avoids implementing an SMB client and duplicating authentication/session logic.
- A narrow privileged boundary is easier to review than running the backend as root.

## Consequences and constraints

- Mount configuration and helper inputs need strict allow-list validation and injection tests.
- Source unavailability must not mark catalogue files missing.
- Credential replacement/deletion and mount cleanup must be transactional at the application level.
- Exact mount options, helper protocol and systemd unit design require review and Dell/NAS testing
  before ADR acceptance/implementation.
- The live SQLite database must never reside on the mounted share.

## Rejected alternatives

- **Direct Python SMB:** credentials/reconnects and a second path model would sit inside the app;
  MPV would still need compatible access.
- **Externally pre-mounted only:** cannot provide the required WebUI-managed lifecycle or reliable
  appliance setup, though it remains useful for expert deployments.
