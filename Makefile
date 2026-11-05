# Foods pipeline — operational entry points (Plan §9 P0: "make smoke 通过").
#
# `smoke` runs the instrument-level unit tests only (alignment math, anchor
# mapping, attack-tolerance direction, Hawkes recovery, intake rule, JSON
# repair). It needs no network, no GPU and no corpus, so it is the check to run
# after any code change and the first thing to run on a new machine.
# `test` additionally picks up any future test_*.py; files named diag_*/probe_*
# in tests/ are diagnostics that talk to the live manifest and are never run
# by either target.

# Prefer the project venv: the system interpreter has no numpy/vllm deps.
PY ?= $(shell [ -x ./venv/bin/python ] && echo ./venv/bin/python || echo python3)

.PHONY: smoke test figures

smoke:
	$(PY) -m unittest discover -s tests -p 'smoke_test.py' -v

test:
	$(PY) -m unittest discover -s tests -p 'test_*.py' -v

figures:
	$(PY) -m foods_pipeline.cli figures
