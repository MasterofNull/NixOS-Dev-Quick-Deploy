.PHONY: up down restart ps logs health metrics security-audit security-scan

up:
	sudo systemctl start ai-stack.target command-center-dashboard-api.service command-center-dashboard-frontend.service

down:
	sudo systemctl stop command-center-dashboard-frontend.service command-center-dashboard-api.service ai-stack.target

restart:
	sudo systemctl restart ai-stack.target command-center-dashboard-api.service command-center-dashboard-frontend.service

ps:
	systemctl --no-pager --type=service | rg 'ai-stack|llama-cpp|qdrant|redis|postgresql|command-center-dashboard'

logs:
	@if [ -z "$(SERVICE)" ]; then \
		echo "Usage: make logs SERVICE=<systemd-unit>"; \
		exit 1; \
	fi
	journalctl -u $(SERVICE) -f

health:
	./scripts/ai-stack-health.sh

metrics:
	systemctl status --no-pager prometheus.service prometheus-node-exporter.service
	bash -lc '. ./config/service-endpoints.sh; curl -fsS "${PROMETHEUS_URL%/}/-/healthy"'

security-audit:
	./scripts/security-audit.sh

security-scan:
	./scripts/security-scan.sh
