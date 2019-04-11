#!/usr/bin/env bash 

# To run tests from your shell first `pipenv shell`
# note you will need `cloudtoken -d` running for the testing to work locally

# to get less warningy output do `python -m pytest -v tests/unit --disable-warnings`

python -m pytest -v tests/unit
