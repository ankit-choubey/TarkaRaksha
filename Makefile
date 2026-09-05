.PHONY: help status test-bootstrap clean

help:
	@echo "TarkaRaksha Control Plane - Commands"
	@echo "  make status         - Display persistent status and git state"
	@echo "  make test-bootstrap - Verify repository bootstrap integrity"
	@echo "  make clean          - Clean transient build and cache artifacts"

status:
	@echo "=== Git Status ==="
	@git status -s
	@echo "\n=== Brain Status ==="
	@cat brain/STATUS.md

test-bootstrap:
	@echo "Checking canonical master documents..."
	@test -f brain/TarkaRaksha_IDEA.md && echo "[✓] brain/TarkaRaksha_IDEA.md exists"
	@test -f brain/TarkaRaksha_Execution.md && echo "[✓] brain/TarkaRaksha_Execution.md exists"
	@test -f brain/TarkaRaksha_PreFinal.md && echo "[✓] brain/TarkaRaksha_PreFinal.md exists"
	@test -f brain/TarkaRaksha_TESTING.md && echo "[✓] brain/TarkaRaksha_TESTING.md exists"
	@echo "Checking control documents..."
	@test -f brain/STATUS.md && echo "[✓] brain/STATUS.md exists"
	@test -f AGENTS.md && echo "[✓] AGENTS.md exists"
	@test -f .agents/rules/tarkaraksha.md && echo "[✓] .agents/rules/tarkaraksha.md exists"
	@echo "Checking configuration files..."
	@test -f .gitignore && echo "[✓] .gitignore exists"
	@test -f .env.example && echo "[✓] .env.example exists"
	@test -f pyproject.toml && echo "[✓] pyproject.toml exists"
	@test -f README.md && echo "[✓] README.md exists"
	@test -f SECURITY.md && echo "[✓] SECURITY.md exists"
	@test -f LICENSE && echo "[✓] LICENSE exists"
	@echo "[✓] All T01 bootstrap checks passed."

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".DS_Store" -delete
