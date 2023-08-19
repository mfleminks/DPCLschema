.PHONY: check htmlcov


env:
	python3.10 -m venv env
	source env/bin/activate ; python -m pip install -r requirements.txt

check:
	python -m pytest --cov=.

htmlcov:
	python -m pytest --cov=. --cov-report=html
