# Operations

Running, configuring and troubleshooting the workbench.

## Prerequisites

- **Docker** with Compose v2. That is the only hard requirement for running it.
- An **NVIDIA NIM API key** from <https://build.nvidia.com> for prototype mode.
- For development and tests on the host: Python 3.12 and
  [`uv`](https://github.com/astral-sh/uv).
- For sovereign mode: an NVIDIA GPU with the container toolkit installed.

## First run

```bash
git clone <repo> && cd SIH-2026
make up                        # creates .env from .env.example if missing
$EDITOR .env                   # set NVIDIA_API_KEY, optionally ADMIN_PASSWORD
make restart
make logs                      # the first admin password is printed here once
```

Open <http://127.0.0.1:8117> and sign in as `admin`.

The first build takes a few minutes — it installs Python dependencies and bakes
the embedding model into the image. After that, `make restart` takes seconds.

## Commands

| Command | Does |
|---|---|
| `make` | list everything below |
| `make up` | build and start the contained stack; install the secret hook |
| `make down` | stop it |
| `make restart` | rebuild the app image and restart it after a code change |
| `make logs` | follow app and gateway logs |
| `make open` | open the interface |
| `make prove` | show containment from inside the running app |
| `make sovereign` | start with no gateway — nothing reachable |
| `make test` | all 117 tests (sandbox tests need Docker) |
| `make test-v` | the same, naming each test |
| `make secrets` | scan every tracked file for credentials |
| `make verify-models` | check `models.yaml` against the live catalogue |
| `make sample` | regenerate the scanned report and P&ID fixtures |
| `make dev` | build the interface, then run on the host with autoreload — **no containment** |
| `make web` | build the interface into `static/` (needs Node) |
| `make web-dev` | interface with hot reload on :5173, proxying to the running stack |
| `make watch` | independent packet capture for a demo split-screen (sudo) |

## Configuration

`.env` (gitignored — never commit it):

| Variable | Required | Meaning |
|---|---|---|
| `NVIDIA_API_KEY` | prototype mode | NIM key. **Includes its trailing hyphen** if it has one |
| `ADMIN_PASSWORD` | no | seeds the first admin account; otherwise one is generated |
| `MODE` | no | `prototype` (default) or `sovereign` |
| `MODEL_ENDPOINT` | no | overrides the endpoint for the current mode |

`models.yaml` holds the model registry and routing rules. Changes take effect
on **Reload registry** in the Models tab, or on restart.

## Host development

For iterating on code without rebuilding the image:

```bash
uv venv --python 3.12 .venv && uv pip install -r requirements.txt
docker build -t wb-sandbox sandbox/     # the code sandbox image
make dev                                # http://127.0.0.1:8117, autoreload
```

For the interface, run the stack (`make up`) and then `make web-dev`: Vite
serves on <http://127.0.0.1:5173> with hot reload and proxies `/api` to the
stack. Needs Node 22 or newer on the host. `static/` is build output — edit
`web/src/`, never `static/`.

Host mode has **no containment** — the header will say *unenforced*. That is
correct, not a fault. Demonstrate from `make up`, never from `make dev`.

## Adding a teammate

Sign in as an admin, open the **Admin** tab, add the user with a role:

- **engineer** — runs tasks and uploads documents
- **approver** — also approves notes (workflow in roadmap F3)
- **admin** — also manages users, models, the knowledge base and the audit log

## Troubleshooting

**The page does not load / connection refused.**
The stack is not running — likely after a reboot. `make up`.

**Signed out after a restart.** Should no longer happen; tokens are signed, not
stored (D-39). If it does, `data/secret.key` was deleted, which invalidates
every token by design. Sign in again.

**"Your role cannot …" (HTTP 403).** Working as intended. An admin can change
the role in the Admin tab; the user must sign in again afterwards, because a
role change invalidates old tokens.

**The gateway container keeps exiting.** Check `make logs` for "host not found
in upstream". Upstreams resolve at request time (D-10); if this reappears,
`egress/proxy.conf` has lost its `resolver` line or `set $var` indirection.

**Every task fails with 403 from the model.** The NIM key is wrong. Check it
includes any trailing hyphen — without it, `/v1/models` still returns 200,
which is misleading.

**Tasks fail with 404 for a model.** The key is not entitled to that model.
`make verify-models`, then pick another from the usable set in
`docs/model-benchmark.md`.

**503 "ResourceExhausted".** The free NIM tier is saturated. The client retries
and falls back a tier automatically; wait and retry if it persists.

**Every search returns nothing inside the container.** The embedding model is
not baked into the image — the `Dockerfile` step that downloads it did not run
or its cache path changed. Rebuild with `make restart` and check the build log
for "embedding model baked in".

**Code tasks time out.** Check the app container has a Docker client:
`docker compose exec app docker version`. It needs `docker-cli`, not
`docker.io`, on Debian 13 (D-37). Also check `wb-sandbox` exists:
`docker images wb-sandbox` — `make up` builds it.

**Cannot delete files in `data/`.** Written by a root container before the
user mapping (D-38). Remove them through Docker:
`docker run --rm -v "$PWD/data:/d" alpine rm -rf /d/cache`.

**A task is slow.** Check which tier it routed to in the trace. On the hosted
endpoint L1 is slower than L2 (15s against 3.7s). A question that should need
the SOP but routed to L1 is a routing gap — add the vocabulary to `_ANALYZE`
in `app/router.py` with a test.

**Tests pass but a behaviour is broken.** Confirm the test actually ran:
`make test-v` names each one. A test appended after an `if __name__` block
never runs (D-41) — `tests/run.py` collects by import to prevent that.

## Proving containment

See `docs/playbooks/verify-containment.md`. In short:

```bash
make prove
#   no default route
#   tripwire  blocked=True  1ms  gaierror: [Errno -3] Temporary failure in name resolution
```

## Backups

Everything worth keeping is in `data/`:

- `data/kb/` — knowledge-base sources (also in git)
- `data/out/` — generated deliverables
- `data/audit.jsonl` — the audit trail
- `data/users.json` — accounts
- `data/secret.key` — token signing key; losing it signs everybody out

Everything else — the index, the cache — is rebuilt on demand.
