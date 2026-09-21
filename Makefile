.PHONY: dev test proto sovereign enforce unenforce demo
VENV := .venv/bin

dev:                     ## run the app on the host (no enforcement)
	$(VENV)/uvicorn app.main:app --reload --port 8117

test:                    ## every check; sandbox ones need docker
	@for t in tests/test_*.py; do \
	  $(VENV)/python $$t >/dev/null 2>&1 && echo "  ok   $$t" || echo "  FAIL $$t"; \
	done

test-v:                  ## the same, with each assertion named
	@for t in tests/test_*.py; do echo "== $$t"; $(VENV)/python $$t || exit 1; done

sample:                  ## regenerate the scanned inspection report fixture
	$(VENV)/python scripts/make_scanned_sample.py

verify-models:           ## check models.yaml against the live catalogue
	$(VENV)/python -m app.verify_models

proto:                   ## containerised; exactly one destination reachable
	docker compose up --build

sovereign:               ## containerised; no gateway, nothing reachable
	docker compose -f docker-compose.yml -f docker-compose.sovereign.yml up --build

down:
	docker compose down

prove:                   ## show containment from inside the running app
	@docker compose exec -T app sh -c 'awk "NR>1 && \$$2==\"00000000\" {f=1} END {print f?\"  HAS default route\":\"  no default route\"}" /proc/net/route'
	@docker compose exec -T app python -c "import socket;\
	[print(f'  unreachable  {h}') if not __import__('contextlib').suppress() else 0 for h in []]" 2>/dev/null; true
	@curl -s -X POST http://127.0.0.1:8117/api/tripwire | $(VENV)/python -c "import json,sys;r=json.load(sys.stdin);print(f\"  tripwire blocked={r['blocked']} in {r['elapsed_ms']}ms -- {r['error']}\")"

enforce unenforce:       ## optional host-level nftables, belt to the braces
	sudo egress/sentinel.sh $(if $(filter enforce,$@),install,remove) $${MODE:-prototype}

watch:                   ## the independent observer, for the demo split-screen
	sudo tcpdump -i any -n -q 'ip and not host 127.0.0.1 and not net 172.16.0.0/12 and not net 10.0.0.0/8'
