# Task 3.6 — Managed SMB/NAS source support

## Implementation status

In progress. The backend adds typed non-secret SMB share configuration (`host`, `share`, optional
relative `subpath`) plus an opaque credential reference. Managed mount paths are derived only as
`/run/nostalgiabox/media/<source-id>`. The application defines narrow `SecretStore` and
`ManagedMountGateway` ports; it does not invoke shell commands, mount CIFS directly, or serialize a
password.

## Migration

`20260918_0007` follows `20260915_0006` and adds nullable SMB configuration/reference columns to
`media_sources`. It is reversible. No Dell/NAS validation has been run.

## Outstanding evidence

Fake-adapter lifecycle/compensation, scanner source-access integration, migration round-trip, and
Dell/NAS validation remain required before this task can be considered complete.
