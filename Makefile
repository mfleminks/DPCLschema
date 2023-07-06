.PHONY: cehck


check:
	python -m unittest tests/*.py

env:
	python3.10 -m venv env
	source env/bin/activate ; python -m pip install -r requirements.txt
