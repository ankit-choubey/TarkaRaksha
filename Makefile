.PHONY: help status test-bootstrap test-env test clean

VENV_PYTHON = .venv/bin/python
VENV_PYTEST = .venv/bin/pytest

help:
	@echo "TarkaRaksha Control Plane - Commands"
	@echo "  make status         - Display persistent status and git state"
	@echo "  make test-bootstrap - Verify repository bootstrap integrity (C01)"
	@echo "  make test-env       - Verify environment setup end-to-end (C02)"
	@echo "  make test           - Run backend automated test suite"
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
	@test -f brain/CONTEXT.md && echo "[✓] brain/CONTEXT.md exists"
	@test -f brain/HANDOFF.md && echo "[✓] brain/HANDOFF.md exists"
	@test -f AGENTS.md && echo "[✓] AGENTS.md exists"
	@test -f .agents/rules/tarkaraksha.md && echo "[✓] .agents/rules/tarkaraksha.md exists"
	@echo "Checking configuration files..."
	@test -f .gitignore && echo "[✓] .gitignore exists"
	@test -f .env.example && echo "[✓] .env.example exists"
	@test -f pyproject.toml && echo "[✓] pyproject.toml exists"
	@test -f README.md && echo "[✓] README.md exists"
	@test -f SECURITY.md && echo "[✓] SECURITY.md exists"
	@test -f LICENSE && echo "[✓] LICENSE exists"
	@echo "Verifying absence of duplicate master documents in root..."
	@test ! -f TarkaRaksha_IDEA.md && echo "[✓] No root TarkaRaksha_IDEA.md"
	@test ! -f TarkaRaksha_Execution.md && echo "[✓] No root TarkaRaksha_Execution.md"
	@test ! -f TarkaRaksha_PreFinal.md && echo "[✓] No root TarkaRaksha_PreFinal.md"
	@test ! -f TarkaRaksha_TESTING.md && echo "[✓] No root TarkaRaksha_TESTING.md"
	@echo "Validating pyproject.toml TOML syntax..."
	@python3 -c "import tomllib; tomllib.loads(open('pyproject.toml').read())" && echo "[✓] pyproject.toml syntax valid"
	@echo "Performing credential and secret scan..."
	@python3 -c "import subprocess, sys; res = subprocess.run(['git', 'grep', '-i', '-E', 'sk_test_[0-9a-zA-Z]{10,}|sk_live_[0-9a-zA-Z]{10,}|rzp_test_[0-9a-zA-Z]{10,}|rzp_live_[0-9a-zA-Z]{10,}|gsk_[a-zA-Z0-9]{20,}|BEGIN PRIVATE KEY', ':(exclude)Makefile'], capture_output=True, text=True); sys.exit(1) if res.stdout.strip() else sys.exit(0)" && echo "[✓] No leaked credentials detected"
	@echo "[✓] All T01 bootstrap checks passed."

test-env:
	@test -x $(VENV_PYTHON) || (echo "[✗] Virtual environment .venv not found. Run python3 -m venv .venv" && exit 1)
	@$(VENV_PYTHON) scripts/verify_env.py
	@$(VENV_PYTEST) testing/unit/test_environment.py

test:
	@$(VENV_PYTEST)

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".DS_Store" -delete
	rm -rf frontend/.next frontend/out
