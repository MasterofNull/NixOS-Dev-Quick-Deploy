K8S_DIR := ai-stack/kubernetes
KUBECTL := kubectl --request-timeout=60s
NAMESPACE := ai-stack

.PHONY: up down restart ps logs health metrics security-audit security-scan

up:
	$(KUBECTL) apply -k $(K8S_DIR)

down:
	$(KUBECTL) scale deploy -n $(NAMESPACE) --replicas=0 --all

restart:
	$(KUBECTL) rollout restart deploy -n $(NAMESPACE) --all

ps:
	$(KUBECTL) get pods -n $(NAMESPACE)

logs:
	@if [ -z "$(SERVICE)" ]; then \
		echo "Usage: make logs SERVICE=<deployment>"; \
		exit 1; \
	fi
	$(KUBECTL) logs -n $(NAMESPACE) deploy/$(SERVICE) -f

health:
	./scripts/ai-stack-health.sh

metrics:
	./scripts/collect-ai-metrics.sh

security-audit:
	./scripts/security-audit.sh

security-scan:
	./scripts/security-scan.sh
