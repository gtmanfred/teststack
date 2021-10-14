html:
	sphinx-build -b html docs docs/_html

serve-docs: html
	cd docs/_html && python3 -m http.server
