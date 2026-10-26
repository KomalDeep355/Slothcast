PY ?= python
CLI = $(PY) -m slothcast.cli

.PHONY: install install-tabpfn test sample eval eval-sample forecast demo nightly clean

install:            ## core + dev deps
	$(PY) -m pip install -e ".[dev]"

install-tabpfn:     ## adds TabPFN (needs the model license accepted, see README)
	$(PY) -m pip install -e ".[dev,tabpfn]"

test:
	$(PY) -m pytest -q

sample:             ## write synthetic demo data (clearly labelled synthetic)
	$(CLI) demo-data

eval:               ## chronological evaluation on YOUR data (data/raw/checkins.csv)
	$(CLI) eval

eval-sample:        ## same, on the synthetic demo log
	$(CLI) eval --checkins data/sample/demo_log.csv

forecast:           ## tomorrow's deadline-risk forecast + plan
	$(CLI) forecast --task "DSA block" --minutes 120 --deadline-days 3 --energy 3

demo:               ## dashboard
	$(PY) -m streamlit run src/slothcast/app/main.py

nightly:            ## one-shot nightly run without Temporal
	$(CLI) nightly

clean:
	rm -rf results/*.png results/*.json results/*.md results/*.csv data/processed/* data/outbox .pytest_cache
