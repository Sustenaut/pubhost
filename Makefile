# pubhost: a repository's hosting, its modules, workflow and actions. The
# targets every Python package shares (venv, functional, lock, sync-check,
# wheel, clean, help) are pubrules-python.mk's, which pubrules sync writes.
include pubrules-python.mk

.PHONY: check

check: sync-check functional ## Everything CI runs
