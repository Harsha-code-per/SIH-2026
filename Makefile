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

proto:                   ## containerised, one pinned egress host
	docker compose up --build

sovereign:               ## containerised, no route out at all
	docker compose -f docker-compose.yml -f docker-compose.sovereign.yml up --build

enforce:                 ## install nftables rules for the current MODE
	sudo egress/sentinel.sh install $${MODE:-prototype}

unenforce:
	sudo egress/sentinel.sh remove

watch:                   ## the independent observer, for the demo split-screen
	sudo tcpdump -i any -n -q 'ip and not host 127.0.0.1 and not net 172.16.0.0/12 and not net 10.0.0.0/8'
