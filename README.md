# run project
uvicorn blockchain_backend:app --reload

# local swagger
http://127.0.0.1:8000/docs

# Installation 
```python: make requerments.txt```
```pip install pipreqs```
```pipreqs /path/to/project```

# Hyperpayment

Two parts of the software, mainly runtime and dependencies are coming from `meta.json` and `bom.json`.

# Dependencies
Any python project must have [pyproject.toml](https://peps.python.org/pep-0621/).

Here is the guide how to add it: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/#dependencies-and-requirements.

Any project must have `bom.json` at the root. This boom must include the CycloneDX based Software Bill of Materials (SBOM).

For the python projects that uses virtual environments use the 
https://github.com/CycloneDX/cyclonedx-python

After installation of cyclonedx, generate the SBOM using the following command:

```cyclonedx-py environment -o bom.json --pyproject pyproject.toml```

# Environment
To fetch the programming language, we use this: https://github.com/github-linguist/linguist.
Simply install the above package, go to the repository and generate `environment.json`.