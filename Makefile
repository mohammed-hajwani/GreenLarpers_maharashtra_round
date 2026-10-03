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
	$(PY) scripts/tune_thresholds.py
	$(PY) scripts/train_progress.py

eval:
	$(PY) scripts/evaluate.py
	$(PY) scripts/simulate_learners.py

demo-record:
	$(PY) scripts/record_demo.py

test:
	$(PY) -m pytest -q

gate:
	$(PY) scripts/gate.py $(STAGE)

app:
	$(PY) -m streamlit run app.py

.PHONY: setup data train eval demo-record test gate app
