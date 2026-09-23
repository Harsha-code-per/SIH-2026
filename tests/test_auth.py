"""Accounts, roles and sessions.

The point of authentication here is not to keep a determined attacker out of a
machine they are already sitting at -- it is that every line in the audit log
has a name against it, and that a deployment does not ship with a password
everyone knows.
"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth import ROLES, Users, hash_password, verify_password


def fresh() -> Users:
    return Users(path=Path(tempfile.mkdtemp()) / "users.json")


def test_a_password_verifies_only_against_itself():
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("Correct horse battery staple", h)
    assert not verify_password("", h)


def test_the_same_password_hashes_differently_each_time():
    """Equal hashes would tell an attacker which accounts share a password."""
    assert hash_password("same") != hash_password("same")


def test_a_malformed_hash_fails_closed():
    for bad in ("", "nonsense", "pbkdf2_sha256$notanumber$aa$bb"):
        assert not verify_password("anything", bad)


def test_the_first_account_gets_a_generated_password():
    """A fixed default would be a back door in every deployment."""
    a, b = fresh(), fresh()
    assert a.users["admin"].password != b.users["admin"].password


def test_login_returns_a_token_that_identifies_the_user():
    u = fresh()
    u.add("arun", "inspection2026", "engineer")
    token = u.login("arun", "inspection2026")
    assert token and u.whoami(token).username == "arun"
    assert u.login("arun", "wrong") is None
    assert u.whoami("not-a-token") is None


def test_logout_invalidates_the_token():
    u = fresh()
    u.add("arun", "inspection2026", "engineer")
    t = u.login("arun", "inspection2026")
    u.logout(t)
    assert u.whoami(t) is None


def test_an_expired_token_stops_working():
    u = fresh()
    u.add("arun", "inspection2026", "engineer")
    payload = f"arun:1:{int(time.time()) - 1}"
    assert u.whoami(f"{payload}.{u._sign(payload)}") is None


def test_roles_carry_different_capabilities():
    u = fresh()
    eng = u.add("arun", "inspection2026", "engineer")
    apr = u.add("priya", "inspection2026", "approver")
    adm = u.users["admin"]
    assert eng.can("run") and not eng.can("approve")
    assert apr.can("approve") and not apr.can("manage_users")
    assert adm.can("manage_users") and adm.can("read_audit")


def test_the_last_administrator_cannot_be_removed_or_demoted():
    """Locking everyone out of user management is unrecoverable air-gapped."""
    u = fresh()
    u.add("arun", "inspection2026", "engineer")
    for act in (lambda: u.remove("admin"), lambda: u.set_role("admin", "engineer")):
        try:
            act()
            assert False, "should have refused"
        except ValueError as e:
            assert "last administrator" in str(e)
    u.add("second", "inspection2026", "admin")
    assert u.remove("admin") is True


def test_weak_and_malformed_accounts_are_refused():
    u = fresh()
    for args, why in [(("arun", "short", "engineer"), "password"),
                      (("arun", "inspection2026", "wizard"), "role"),
                      (("two words", "inspection2026", "engineer"), "username")]:
        try:
            u.add(*args)
            assert False, f"should have refused {why}"
        except ValueError:
            pass


def test_a_duplicate_username_is_refused():
    u = fresh()
    u.add("arun", "inspection2026", "engineer")
    try:
        u.add("ARUN", "inspection2026", "engineer")
        assert False, "usernames are case-insensitive and must be unique"
    except ValueError:
        pass


def test_removing_a_user_invalidates_their_tokens():
    """A signed token names a user; if the user is gone it resolves to nobody."""
    u = fresh()
    u.add("arun", "inspection2026", "engineer")
    t = u.login("arun", "inspection2026")
    u.remove("arun")
    assert u.whoami(t) is None


def test_the_password_hash_is_never_exposed():
    u = fresh()
    pub = u.add("arun", "inspection2026", "engineer").public()
    assert "password" not in pub
    assert pub["capabilities"] == sorted(ROLES["engineer"])


def test_accounts_survive_a_restart():
    path = Path(tempfile.mkdtemp()) / "users.json"
    a = Users(path=path)
    a.add("arun", "inspection2026", "engineer")
    b = Users(path=path)
    assert b.login("arun", "inspection2026")


def test_a_token_survives_a_restart():
    """Tokens were held in memory, so restarting the service signed everybody
    out. They are signed instead, and no session table is kept."""
    path = Path(tempfile.mkdtemp()) / "users.json"
    a = Users(path=path)
    a.add("arun", "inspection2026", "engineer")
    t = a.login("arun", "inspection2026")
    restarted = Users(path=path)
    assert restarted.whoami(t) is not None


def test_a_forged_or_tampered_token_is_rejected():
    u = fresh()
    u.add("arun", "inspection2026", "engineer")
    t = u.login("arun", "inspection2026")
    payload, _, sig = t.rpartition(".")
    name, version, expiry = payload.split(":")
    for bad in (f"admin:{version}:{expiry}.{sig}",        # different user
                f"{name}:{version}:{int(expiry) + 99999}.{sig}",  # longer life
                f"{payload}.{'0' * len(sig)}",            # wrong signature
                payload, "", "nonsense"):
        assert u.whoami(bad) is None, bad


def test_changing_a_password_invalidates_outstanding_tokens():
    u = fresh()
    u.add("arun", "inspection2026", "engineer")
    t = u.login("arun", "inspection2026")
    assert u.whoami(t)
    u.set_password("arun", "newpassword2026")
    assert u.whoami(t) is None, "an old token must not survive a password change"


def test_changing_a_role_invalidates_outstanding_tokens():
    """Otherwise a demoted user keeps their old capabilities until expiry."""
    u = fresh()
    u.add("arun", "inspection2026", "admin")
    t = u.login("arun", "inspection2026")
    u.set_role("arun", "engineer")
    assert u.whoami(t) is None


def test_each_deployment_signs_with_its_own_key():
    a, b = fresh(), fresh()
    a.add("arun", "inspection2026", "engineer")
    b.add("arun", "inspection2026", "engineer")
    assert b.whoami(a.login("arun", "inspection2026")) is None
