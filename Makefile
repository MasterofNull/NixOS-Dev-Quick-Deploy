COMPOSE_DIR := ai-stack/compose
COMPOSE := podman-compose -f $(COMPOSE_DIR)/docker-compose.yml
DEV_COMPOSE := $(COMPOSE) -f $(COMPOSE_DIR)/docker-compose.dev.yml

.PHONY: up up-full down restart ps logs health metrics dev-up dev-down pull build security-audit security-scan

up:
	$(COMPOSE) up -d

up-full:
	$(COMPOSE) --profile full up -d

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f

health:
	./scripts/ai-stack-health.sh

metrics:
	./scripts/collect-ai-metrics.sh

security-audit:
	./scripts/security-audit.sh

security-scan:
	./scripts/security-scan.sh

dev-up:
	$(DEV_COMPOSE) up -d

dev-down:
	$(DEV_COMPOSE) down

pull:
	$(COMPOSE) pull

build:
	$(COMPOSE) build
