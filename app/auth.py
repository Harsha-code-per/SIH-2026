"""Users, sessions and roles.

Deliberately small and deliberately honest about what it is. Passwords are
hashed with PBKDF2 from the standard library, which is adequate for an
on-premise tool behind an org's own network and is not a substitute for the
enterprise SSO a refinery would actually federate against. The point here is
that every action in the audit log has a name against it.

Storage is a JSON file rather than a database: this is per-workstation software
with a handful of accounts, and a database would be a second thing to deploy,
back up and air-gap for no gain.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "users.json"
SECRET = ROOT / "data" / "secret.key"

PBKDF2_ROUNDS = 240_000
TOKEN_TTL = 12 * 3600

# What each role may do. Capabilities rather than a hierarchy, so a new role is
# a line here instead of a rethink.
ROLES: dict[str, set[str]] = {
    "engineer": {"run", "upload", "read_kb"},
    "approver": {"run", "upload", "read_kb", "approve"},
    "admin":    {"run", "upload", "read_kb", "approve",
                 "manage_kb", "manage_users", "manage_models", "read_audit"},
}


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt),
                             PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, rounds, salt, want = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(),
                                 bytes.fromhex(salt), int(rounds))
    except (ValueError, TypeError):
        return False
    # Constant time: a comparison that returns early leaks the hash by timing.
    return hmac.compare_digest(dk.hex(), want)


@dataclass
class User:
    username: str
    password: str                 # the hash, never the password
    role: str = "engineer"
    display: str = ""
    created: float = field(default_factory=time.time)
    last_seen: float = 0.0
    # Bumped to invalidate every token this user holds. Changing a password or
    # a role must not leave an old token working.
    token_version: int = 1

    def can(self, capability: str) -> bool:
        return capability in ROLES.get(self.role, set())

    def public(self) -> dict:
        d = asdict(self)
        d.pop("password")
        d["capabilities"] = sorted(ROLES.get(self.role, set()))
        return d


class Users:
    def __init__(self, path: Path = STORE, secret_path: Path | None = None):
        self.path = path
        self.secret_path = secret_path or path.with_name("secret.key")
        self.users: dict[str, User] = {}
        # Best-effort single-session logout. Tokens are signed rather than
        # stored, so this is the one piece of state a restart drops; a logged
        # out token becomes valid again until it expires. Changing a password
        # revokes properly, through token_version.
        self.revoked: set[str] = set()
        self.load()

    @property
    def secret(self) -> bytes:
        """A key of this deployment's own, generated once and kept at 0600.

        Signed tokens mean no session table, so restarting the service does not
        sign everybody out -- which it did, every time the container restarted.
        """
        if not self.secret_path.exists():
            self.secret_path.parent.mkdir(parents=True, exist_ok=True)
            self.secret_path.write_bytes(secrets.token_bytes(32))
            os.chmod(self.secret_path, 0o600)
        return self.secret_path.read_bytes()

    def _sign(self, payload: str) -> str:
        return hmac.new(self.secret, payload.encode(), hashlib.sha256).hexdigest()

    # -- storage ------------------------------------------------------------
    def load(self) -> None:
        if self.path.exists():
            self.users = {u["username"]: User(**u)
                          for u in json.loads(self.path.read_text())}
        if not self.users:
            self._seed()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(u) for u in self.users.values()], indent=2))
        tmp.replace(self.path)                      # atomic, so a crash cannot truncate
        os.chmod(self.path, 0o600)

    def _seed(self) -> None:
        """First run needs an account, and a fixed default password would be a
        back door in every deployment. One is generated and printed once."""
        pw = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(12)
        self.users["admin"] = User(username="admin", password=hash_password(pw),
                                   role="admin", display="Administrator")
        self.save()
        print(f"\n  Created the first account: admin / {pw}"
              f"\n  Change it after signing in. Set ADMIN_PASSWORD to choose it.\n",
              flush=True)

    # -- accounts -----------------------------------------------------------
    def add(self, username: str, password: str, role: str, display: str = "") -> User:
        username = username.strip().lower()
        if not username or not username.isascii() or " " in username:
            raise ValueError("username must be one ascii word")
        if username in self.users:
            raise ValueError(f"{username} already exists")
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}; expected one of {sorted(ROLES)}")
        if len(password) < 8:
            raise ValueError("password must be at least 8 characters")
        u = User(username=username, password=hash_password(password),
                 role=role, display=display or username.title())
        self.users[username] = u
        self.save()
        return u

    def remove(self, username: str) -> bool:
        if username not in self.users:
            return False
        # Locking everyone out of user management is not recoverable in an
        # air-gapped deployment without editing the file by hand.
        admins = [u for u in self.users.values() if u.role == "admin"]
        if self.users[username].role == "admin" and len(admins) == 1:
            raise ValueError("cannot remove the last administrator")
        del self.users[username]
        self.save()
        return True

    def set_password(self, username: str, password: str) -> None:
        if len(password) < 8:
            raise ValueError("password must be at least 8 characters")
        self.users[username].password = hash_password(password)
        self.users[username].token_version += 1
        self.save()

    def set_role(self, username: str, role: str) -> None:
        if role not in ROLES:
            raise ValueError(f"unknown role {role!r}")
        admins = [u for u in self.users.values() if u.role == "admin"]
        if self.users[username].role == "admin" and len(admins) == 1 and role != "admin":
            raise ValueError("cannot demote the last administrator")
        self.users[username].role = role
        self.users[username].token_version += 1     # old tokens carry the old role
        self.save()

    # -- sessions -----------------------------------------------------------
    def login(self, username: str, password: str) -> str | None:
        u = self.users.get((username or "").strip().lower())
        if not u or not verify_password(password, u.password):
            return None
        u.last_seen = time.time()
        self.save()
        payload = f"{u.username}:{u.token_version}:{int(time.time() + TOKEN_TTL)}"
        return f"{payload}.{self._sign(payload)}"

    def whoami(self, token: str | None) -> User | None:
        if not token or token in self.revoked:
            return None
        payload, _, signature = token.rpartition(".")
        if not payload or not hmac.compare_digest(signature, self._sign(payload)):
            return None
        try:
            username, version, expiry = payload.split(":")
            if time.time() > int(expiry):
                return None
        except ValueError:
            return None
        u = self.users.get(username)
        # A stale version means the password or role changed after this token
        # was issued, so it must stop working even though it is still signed.
        return u if u and str(u.token_version) == version else None

    def logout(self, token: str) -> None:
        self.revoked.add(token)


USERS = Users()
