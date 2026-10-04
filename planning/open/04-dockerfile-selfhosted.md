# TICKET-04 — Dockerfile + docker-compose for self-hosted install

- **status:** open
- **priority:** P1
- **effort:** L
- **created:** 2026-10-03
- **owner:** unassigned

## Context

The #1 install friction today is Playwright: ~1.5 GB Chromium download,
Linux font/library pain, "it works on my Mac but not on my Ubuntu VM".
For an OSS launch, "pip install + playwright install + maybe apt-get"
is a wall most users won't climb.

Shipping a Dockerfile + docker-compose with everything pre-baked turns
the install into one command. That's table stakes for a self-hosted
tool to be taken seriously (cf. Immich, Paperless-ngx, Mealie).

## Scope

**In:**

- A `Dockerfile` at the repo root using a Playwright base image
  (`mcr.microsoft.com/playwright/python:v1.XX-jammy` or similar).
- A `docker-compose.yml` that:
  - mounts `./data` → `/app/data` so state persists on the host.
  - mounts `./user_config.py` as read-only.
  - exposes port 8765 (the local HTTP server).
  - sets `JOBS_DATA_DIR=/app/data`.
- A `.dockerignore` excluding `.venv*`, `__pycache__`, `data/`, `tests/`,
  `debug/`, `business/`, `.git/`.
- README section "Install (Docker)" with `docker compose up -d` + how
  to reach the UI at `http://localhost:8765`.

**Out of scope:**

- Multi-user support (one container = one user).
- Reverse proxy / HTTPS (user runs behind their own tailscale / Caddy
  if they expose it beyond localhost).
- ARM-specific build variants (one image, multi-arch via buildx).

## Design notes

- Playwright base image is heavy (~1 GB) but it saves the user from
  the `playwright install chromium` dance. Worth it.
- The HTTP server binds to `127.0.0.1` today — needs to bind to
  `0.0.0.0` inside the container so the host can reach it. Make this a
  config knob, default stays `127.0.0.1` for non-Docker runs.
- Ollama is NOT bundled — too big, too opinionated. Document how to
  point `OLLAMA_URL` at the host's Ollama via `host.docker.internal`.
- `ANTHROPIC_API_KEY` passed via environment variable, documented in
  `docker-compose.yml` with a commented-out example.

## Acceptance criteria

- [ ] `docker compose up` from a fresh clone produces a running UI at
      `http://localhost:8765` within 2 minutes on a modern Mac/Linux.
- [ ] State persists across `docker compose down && docker compose up`.
- [ ] Image size is < 2.5 GB (uncompressed).
- [ ] A GitHub Actions workflow builds + pushes the image on tagged
      releases (ghcr.io/<user>/jobs:vX.Y).
- [ ] README has a "Docker" section as the FIRST install option.
- [ ] `make test` stays green (the test suite is unchanged).

## Open questions

- Multi-arch? ARM users (Apple Silicon, Raspberry Pi) matter a lot
  for the self-hosted audience. Buildx + emulated ARM in CI is slow
  but doable.
- Should the image embed a specific `user_config.py` default pointing
  at 3-5 generic companies so first-run has SOMETHING to show, or
  stay empty and force the user through onboarding?
