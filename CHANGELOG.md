# Changelog

## [1.4.0] - 2026-07-19

Concurrency-safe PKCE state (mise-zikesa: two concurrent auth flows clobbered
each other's verifier, burning a consent click on "Invalid code verifier").

### Changed
- `.pkce_state.json` now keys verifiers by the OAuth `state` param — concurrent
  flows merge instead of clobbering. Legacy single-verifier files still redeem.
- Redeeming a flow consumes only its own entry; concurrent flows keep theirs
  (previously the whole file was unlinked).
- Redeem with no findable verifier now raises a clear ValueError BEFORE calling
  Google (the single-use code survives for a retry), instead of silently
  proceeding verifier-less into a guaranteed `invalid_grant`.
- A bare code (no redirect URL) with several flows in flight is refused —
  paste the full redirect URL, which carries the state.

### Added
- Mint-time self-check: the emitted URL's `code_challenge` is verified against
  the verifier re-read from disk; mismatch aborts loudly instead of handing out
  a doomed URL.
- `authenticate(state=...)` — selects the right verifier when redeeming a bare
  code while several flows are in flight (callback listeners know their state).
- Advisory flock + atomic replace around state-file writes (POSIX; degrades to
  atomic-replace-only elsewhere).

## [1.0.0] - 2026-03-18

Batterie-wide consistency pass: src/ migration, CI.

### Added
- `get_auth_url()` for remote/SSH two-phase auth flow
- PKCE verifier persistence so `--code` works across separate invocations

### Removed
- Manual flow removed in favour of two-phase auth

## 2026-03-08 — API Trim

### Changed
- Trimmed from 1112 to 430 lines, down to 2 essential functions
- Updated CLAUDE.md for the trimmed API surface

## 2026-02-16 — Open-Source Release

### Changed
- De-branded: stripped ITV references, added MIT license
- Renamed from `itv-google-auth` to `jeton`
- Rewrote README for external users

## 2026-01-23 — Type Checking

### Added
- `py.typed` marker for type checker support

## 2025-12-27 — Initial Release

### Added
- Google OAuth library with token management
- Post-auth feature for customizable success screens
- Tests and timezone bug fix

### Fixed
- Escaped HTML in post_auth values
- Handle naive datetime in `TokenStatus.check()`
