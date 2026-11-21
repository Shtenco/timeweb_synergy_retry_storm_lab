PYTHON ?= python
export PYTHONPATH=src
.PHONY: test benchmark verify figures

test:
	$(PYTHON) -m unittest discover -s tests -v
benchmark:
	$(PYTHON) -m retrystorm --requests 240 --repeats 3 --workers 24 --rps 180 --backend-capacity 8 --seed 41 --output results/experiment_18
verify:
	$(PYTHON) scripts/verify_results.py results/experiment_18
figures:
	$(PYTHON) scripts/make_figures.py results/experiment_18 figures
