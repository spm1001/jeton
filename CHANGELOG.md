# Changelog

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
