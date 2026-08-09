# ADR-013 — Local administration authentication and secret boundaries

- **Status:** Proposed
- **Date:** 2026-08-09

Architectural review approves the authentication and external-secret direction. Status remains
**Proposed** until the safe first-run token delivery/reset mechanism and privileged secret-helper
boundary are finalized and reviewed before Task 3.11 exits. These details do not block Tasks
3.1–3.5.

## Context

The Phase 3 WebUI controls sources and credentials on a household LAN. “Local network” is not an
authentication boundary: compromised clients, hostile pages and accidental router exposure remain
credible threats. The appliance also needs reversible SMB credentials and non-reversible account
passwords without placing secrets in Git or ordinary catalogue tables.

## Proposed decision

- Require a one-time, expiring, rate-limited setup token before the first administrator is created.
  Store only its digest and destroy it after successful claim.
- Store administrator passwords as versioned Argon2id hashes.
- Use opaque random server-side sessions. Persist only session-token digests with expiry/revocation;
  deliver tokens in HttpOnly, SameSite=Strict, narrowly scoped cookies and use `Secure` under HTTPS.
- Require CSRF tokens plus Origin/Host validation for mutations; deny cross-origin access by default.
- Bind administration only to configured local interfaces/networks by default. Internet exposure is
  unsupported without separately reviewed TLS/reverse-proxy deployment.
- Keep reversible SMB credentials and session/bootstrap secret material in root-owned mode-`0600`
  files under `/etc/nostalgiabox`, accessed through a narrow secret/helper boundary. DB rows store
  opaque references only. APIs can replace/delete SMB secrets but never read them back.
- Centrally redact tokens, cookies, passwords, CIFS secrets and sensitive subprocess/path details.

## Open item before acceptance

The safe, user-friendly physical/local delivery mechanism for the first setup token must be agreed
before the security implementation task completes. An unauthenticated “first browser wins” design
is rejected, and normal setup must not require exposing a Linux desktop or terminal.

## Consequences

- Server-side sessions allow immediate revocation and avoid putting claims/secrets in browser-readable
  tokens, at the cost of a small persistence/cleanup responsibility.
- LAN HTTP cannot guarantee confidentiality. Documentation must be explicit; later TLS support can
  strengthen transport without changing authentication semantics.
- A narrow privileged secret/mount helper requires careful protocol, ownership and input validation.
- Recovery/reset flows need physical/local authorization and audit design before acceptance.

## Rejected alternatives

- **No authentication on LAN:** local networks are not uniformly trusted.
- **First visitor claims device without a token:** creates a boot-time takeover race.
- **Plaintext/reversible passwords in SQLite:** broadens DB backup and API compromise impact.
- **SMB password in mount arguments/environment:** leaks through process inspection or diagnostics.
- **Browser local-storage bearer token:** increases exposure to script compromise and lacks robust
  server-side revocation.
