#!/bin/bash
export PYTHONPATH=./backend
uvicorn app.main:app --reload --port 8000