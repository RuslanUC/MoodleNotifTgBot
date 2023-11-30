#!/bin/bash

POETRY_VENV="$(poetry env info -p)"
export PATH="${PATH}:${POETRY_VENV}/bin"

poetry run python main.py
