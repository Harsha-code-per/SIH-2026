# Playbook: verify containment

The problem statement calls network evidence *"the actual proof of the
sovereign claim, not just a statement of it."* This is how to produce it, and
how to tell if it has regressed.

## The three conditions

`contained` in the interface is true only when **all three** hold (D-8):

1. **Enforcement is detected** — the app container has no default route.
2. **An observer is running** — `tcpdump` inside the app container.
3. **Nothing has leaked** — no traffic left for a destination not on the
   allowlist.

Watching nothing leave is not the same as nothing being able to leave. A green
badge without condition 1 is a lie, and the code refuses to show one.

## Quick check

```bash
make up
make prove
```

Expected:

```
  no default route
  tripwire  blocked=True  1ms  gaierror: [Errno -3] Temporary failure in name resolution
```

The tripwire is blocked **at DNS** — the app cannot even resolve
`api.openai.com`, let alone connect to it.

## Full check, from inside the container

```bash
docker compose exec -T app python -c "
import socket
for host, port in [('1.1.1.1', 53), ('api.openai.com', 443), ('github.com', 443)]:
    try:
        socket.create_connection((host, port), timeout=4); print('REACHED ', host)
    except Exception as e:
        print('blocked ', host, type(e).__name__)
"
```

Every line must say `blocked`. Then the one permitted destination:

```bash
docker compose exec -T app python -c "
import socket; print(socket.gethostbyname('integrate.api.nvidia.com'))"
```

It must resolve to the **gateway's** address on `172.28.117.0/24`, not to
NVIDIA. That is how its traffic reaches the gateway rather than the internet.

## The gateway's own record

```bash
docker compose logs egress-gateway | grep -- '->'
```

Each outbound connection is logged with its upstream address. Every line should
point at NVIDIA and nothing else.

## Sovereign mode

```bash
make sovereign
```

The gateway is not started. The allowlist is empty. Now even NIM is
unreachable, and `make prove` should show the same result with no permitted
destination at all.

## For the demo video

Run `make watch` in a second terminal for an independent packet capture beside
the interface, and hit **Attempt external call** on camera. The `BLOCKED` line
appearing in the containment panel is the moment the problem statement asks for.

## Regression tests

`tests/test_sovereignty.py` pins the rules: the sovereign allowlist is empty,
the prototype one has exactly one host, a leak is never labelled allowed, quiet
without enforcement is never contained. Run `make test` after any change to
`app/egress.py`, `docker-compose.yml` or `egress/proxy.conf`.
