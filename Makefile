.PHONY: dev test proto sovereign enforce unenforce demo
VENV := .venv/bin

dev:                     ## run the app on the host (no enforcement)
	$(VENV)/uvicorn app.main:app --reload --port 8117

test:                    ## router truth table + sovereignty checks
	@$(VENV)/python tests/test_router.py
	@$(VENV)/python tests/test_sovereignty.py

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
