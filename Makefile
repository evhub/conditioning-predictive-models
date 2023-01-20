.PHONY: build
build:
	arara conditioning.tex

.PHONY: install
install:
	pip install -Ue .

.PHONY: convert
convert:
	python md_to_tex.py
