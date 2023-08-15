.PHONY: check


check:
	python -m pytest --cov=.

env:
	python3.10 -m venv env
	source env/bin/activate ; python -m pip install -r requirements.txt
