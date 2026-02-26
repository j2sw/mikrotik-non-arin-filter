.PHONY: venv deps non-arin us apnic-in-us build clean

venv:
	python3 -m venv venv

deps: venv
	./venv/bin/python -m pip install -U pip
	./venv/bin/pip install -r requirements.txt

non-arin:
	./generate-non-arin.sh

us: deps
	./venv/bin/python ./generate-geolite-us.py

apnic-in-us: deps
	./venv/bin/python ./generate-apnic-in-us.py

build: non-arin us apnic-in-us
	@echo "Done. Outputs: non-arin.rsc geo-allow-us.rsc apnic-in-us.rsc"

clean:
	rm -f non-arin.rsc geo-allow-us.rsc apnic-in-us.rsc delegated-apnic-latest
