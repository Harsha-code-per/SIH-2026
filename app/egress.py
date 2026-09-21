"""Egress observation and enforcement.

Two layers, deliberately separate:

  enforcement  nftables (or `network: none` in sovereign mode) actually stops
               packets. Installed by egress/sentinel.sh. Requires root once.

  observation  tcpdump watches the wire and reports what really happened. This
               is independent of the app -- the app cannot lie to it, which is
               the entire point. A self-reported "no calls made" log proves
               nothing; captured packets do.

If tcpdump is unavailable we degrade to UNVERIFIED and say so loudly rather
than showing a reassuring green badge we cannot back up.
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import socket
import time
from dataclasses import dataclass, asdict

# tcpdump line -> (src, dst). Good enough to name destinations; we do not need
# to reconstruct the stream, only to prove where packets went.
_LINE = re.compile(r"IP6?\s+(\S+?)\s+>\s+(\S+?):")

LOOPBACK = ("127.0.0.1", "::1", "localhost")


@dataclass
class EgressEvent:
    ts: float
    dst: str
    verdict: str        # LOCAL | ALLOWED | LEAKED | BLOCKED
    detail: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


class EgressMonitor:
    """Captures outbound packets and classifies them against the allowlist."""

    def __init__(self, allowlist: list[str], mode: str):
        self.mode = mode
        self.allowlist = allowlist
        self.allow_ips = self._resolve(allowlist)
        self.events: list[EgressEvent] = []
        self.subscribers: set[asyncio.Queue] = set()
        self.status = "STARTING"
        self._proc: asyncio.subprocess.Process | None = None

    @staticmethod
    def _resolve(hosts: list[str]) -> set[str]:
        """Pin allowlisted hostnames to IPs now, so the UI can label traffic."""
        ips: set[str] = set()
        for h in hosts:
            try:
                for *_, sa in socket.getaddrinfo(h, 443, proto=socket.IPPROTO_TCP):
                    ips.add(sa[0])
            except OSError:
                pass  # offline, or sovereign mode: nothing to resolve
        return ips

    def _classify(self, dst: str) -> str:
        """Classify an *observed* packet.

        tcpdump only ever sees traffic that actually went out, so it can never
        report BLOCKED -- a drop is the absence of evidence. Anything that left
        the machine and was not on the allowlist is a LEAK, and is the one
        condition this whole system exists to make impossible.
        """
        host = dst.rsplit(".", 1)[0] if dst.count(".") == 4 else dst  # strip port
        if any(host.startswith(l) for l in LOOPBACK) or host.startswith(("172.", "10.")):
            return "LOCAL"
        if host in self.allow_ips or any(a in dst for a in self.allowlist):
            return "ALLOWED"
        return "LEAKED"

    async def _publish(self, ev: EgressEvent) -> None:
        self.events.append(ev)
        del self.events[:-500]
        for q in list(self.subscribers):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                pass

    async def start(self) -> None:
        if not shutil.which("tcpdump"):
            self.status = "UNVERIFIED (tcpdump not installed)"
            return
        # Ignore loopback and the local model endpoint; we care about what
        # leaves the machine.
        expr = "ip and not host 127.0.0.1 and not net 172.16.0.0/12 and not net 10.0.0.0/8"
        try:
            self._proc = await asyncio.create_subprocess_exec(
                "tcpdump", "-l", "-n", "-q", "-i", "any", expr,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            )
        except (OSError, PermissionError):
            self.status = "UNVERIFIED (tcpdump needs CAP_NET_RAW)"
            return
        self.status = "MONITORING"
        asyncio.create_task(self._pump())

    async def _pump(self) -> None:
        assert self._proc and self._proc.stdout
        async for raw in self._proc.stdout:
            m = _LINE.search(raw.decode("utf-8", "replace"))
            if not m:
                continue
            dst = m.group(2)
            verdict = self._classify(dst)
            if verdict == "LOCAL":
                continue
            await self._publish(EgressEvent(time.time(), dst, verdict))

    async def tripwire(self, target: str = "https://api.openai.com/v1/models") -> dict:
        """Deliberately attempt a call to a non-allowlisted host.

        This is the demo's proof-of-enforcement: it must fail, and the failure
        must also show up in the captured traffic.
        """
        host = target.split("://", 1)[-1].split("/", 1)[0]
        t0 = time.time()
        try:
            fut = asyncio.open_connection(host, 443)
            reader, writer = await asyncio.wait_for(fut, timeout=5)
            writer.close()
            result = {"blocked": False, "error": None,
                      "detail": f"Connection to {host}:443 SUCCEEDED -- egress is NOT contained."}
        except Exception as e:
            result = {"blocked": True, "error": f"{type(e).__name__}: {e}",
                      "detail": f"Connection to {host}:443 refused/unroutable."}
        result |= {"target": host, "elapsed_ms": round((time.time() - t0) * 1000),
                   "mode": self.mode, "allowlist": self.allowlist}
        # A tripwire that got through is a leak, not an allowed call -- the
        # target is deliberately chosen to be off the allowlist.
        await self._publish(EgressEvent(
            t0, f"{host}:443",
            "BLOCKED" if result["blocked"] else "LEAKED",
            "tripwire: " + result["detail"],
        ))
        return result

    def snapshot(self) -> dict:
        count = lambda v: sum(1 for e in self.events if e.verdict == v)
        leaked = count("LEAKED")
        return {
            "mode": self.mode,
            "status": self.status,
            "allowlist": self.allowlist or ["(empty - nothing may leave)"],
            "allowed_count": count("ALLOWED"),
            "blocked_count": count("BLOCKED"),
            "leaked_count": leaked,
            "contained": self.status.startswith("MONITORING") and leaked == 0,
            "events": [e.as_dict() for e in self.events[-50:]],
        }
