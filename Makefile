PY ?= .venv/Scripts/python.exe
STAGE ?= 0
URL ?=

setup:
	$(PY) -m pip install -r requirements.txt
	$(PY) -m pip install -e .

data:
	$(PY) scripts/generate_data.py

train:
	$(PY) scripts/train.py

eval:
	$(PY) scripts/evaluate.py

test:
	$(PY) -m pytest -q

gate:
	$(PY) scripts/gate.py $(STAGE)

app:
	$(PY) -m streamlit run app.py

deploy-dry:
	$(PY) scripts/deploy_space.py --dry-run

smoke:
	$(PY) scripts/smoke_remote.py --url $(URL)

.PHONY: setup data train eval test gate app deploy-dry smoke
