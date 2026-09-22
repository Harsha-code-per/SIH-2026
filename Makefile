.DEFAULT_GOAL := help
.PHONY: help up down logs restart open dev test test-v prove sample verify-models sovereign enforce unenforce watch
VENV := .venv/bin
URL  := http://127.0.0.1:8117

help:                    ## list commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

# ---- the stack: containerised, containment enforced --------------------------

up:                      ## build + start everything, detached (reads .env)
	@test -f .env || { cp .env.example .env; echo "  created .env -- add your NVIDIA_API_KEY to it"; }
	docker build -q -t wb-sandbox sandbox/ >/dev/null
	docker compose up -d --build
	@printf "\n  $(URL)   (make logs · make down · make prove)\n"

down:                    ## stop everything
	docker compose down

logs:                    ## follow app + gateway logs
	docker compose logs -f --tail 50

restart:                 ## rebuild the app image and restart it
	docker compose up -d --build app

open:                    ## open the UI in the browser
	xdg-open $(URL) 2>/dev/null || open $(URL)

sovereign:               ## the stack with no gateway: nothing reachable
	docker compose -f docker-compose.yml -f docker-compose.sovereign.yml up -d --build

prove:                   ## show containment from inside the running app
	@docker compose exec -T app sh -c \
	  'awk "NR>1 && \$$2==\"00000000\" {f=1} END {print f?\"  HAS default route\":\"  no default route\"}" /proc/net/route'
	@curl -s -X POST $(URL)/api/tripwire | python3 -c \
	  "import json,sys;r=json.load(sys.stdin);print(f\"  tripwire  blocked={r['blocked']}  {r['elapsed_ms']}ms  {r['error']}\")"

# ---- host mode: fast iteration, no containment ------------------------------

dev:                     ## run on the host with autoreload (no enforcement)
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

# ---- optional host-level extras ---------------------------------------------

enforce unenforce:       ## host nftables, belt to the braces (needs sudo)
	sudo egress/sentinel.sh $(if $(filter enforce,$@),install,remove) $${MODE:-prototype}

watch:                   ## independent packet observer, for a demo split-screen
	sudo tcpdump -i any -n -q 'ip and not host 127.0.0.1 and not net 172.16.0.0/12 and not net 10.0.0.0/8'
