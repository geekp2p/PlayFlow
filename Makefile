.PHONY: up ps down logs

up:
	@docker compose up -d
	@bash tools/show-endpoints.sh

ps:
	@bash tools/show-endpoints.sh

down:
	@docker compose down

logs:
	@docker compose logs -f --tail=100
