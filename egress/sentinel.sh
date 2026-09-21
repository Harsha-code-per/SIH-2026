#!/usr/bin/env bash
# Egress enforcement for the workbench container network.
#
# Prototype mode : default-deny, with exactly the hosts in models.yaml allowed.
# Sovereign mode : the compose override puts the network on `internal: true`,
#                  so there is no route out at all and these rules are belt to
#                  that braces.
#
# Scoped to the workbench subnet only -- it never touches the rest of the host.
#
#   sudo egress/sentinel.sh install [prototype|sovereign]
#   sudo egress/sentinel.sh status
#   sudo egress/sentinel.sh remove
set -euo pipefail

SUBNET="${WB_SUBNET:-172.28.117.0/24}"
TABLE="sovereign_wb"
MODE="${2:-${MODE:-prototype}}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

need_root() { [[ $EUID -eq 0 ]] || { echo "needs root: sudo $0 $*" >&2; exit 1; }; }

allowlist() {
  python3 - "$ROOT/models.yaml" "$MODE" <<'PY'
import sys, yaml
cfg = yaml.safe_load(open(sys.argv[1]))
print("\n".join(cfg["modes"][sys.argv[2]].get("egress_allow") or []))
PY
}

install_rules() {
  need_root "$@"
  nft delete table inet "$TABLE" 2>/dev/null || true
  nft add table inet "$TABLE"
  nft add chain inet "$TABLE" fwd \
      '{ type filter hook forward priority -10; policy accept; }'

  # Resolve the allowlist to addresses now and pin them.
  local ips=()
  while read -r host; do
    [[ -z "$host" ]] && continue
    while read -r ip; do ips+=("$ip"); done < <(getent ahostsv4 "$host" | awk '{print $1}' | sort -u)
  done < <(allowlist)

  if ((${#ips[@]})); then
    nft add set inet "$TABLE" allowed '{ type ipv4_addr; }'
    nft add element inet "$TABLE" allowed "{ $(IFS=,; echo "${ips[*]}") }"
    nft add rule inet "$TABLE" fwd ip saddr "$SUBNET" ip daddr @allowed accept
  fi

  # Local traffic is fine; anything else leaving the subnet is logged and dropped.
  nft add rule inet "$TABLE" fwd ip saddr "$SUBNET" ip daddr "$SUBNET" accept
  nft add rule inet "$TABLE" fwd ip saddr "$SUBNET" \
      log prefix '"SOVEREIGN-DROP "' level warn
  nft add rule inet "$TABLE" fwd ip saddr "$SUBNET" drop

  echo "installed: mode=$MODE subnet=$SUBNET allowed=${ips[*]:-<none>}"
}

case "${1:-status}" in
  install) install_rules "$@" ;;
  remove)  need_root "$@"; nft delete table inet "$TABLE" 2>/dev/null || true
           echo "removed" ;;
  status)  nft list table inet "$TABLE" 2>/dev/null || echo "not installed (no enforcement active)" ;;
  allowlist) allowlist ;;
  *) echo "usage: $0 {install|remove|status|allowlist} [prototype|sovereign]" >&2; exit 2 ;;
esac
