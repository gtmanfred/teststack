clean:
	rm -rf docs/_html
	find . -name \*.pyc -delete
	find . -name __pycache__ -exec rmdir {} +

docs/_html:
	sphinx-build -b html docs docs/_html

serve-docs: docs/_html
	cd docs/_html && python3 -m http.server
