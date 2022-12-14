ARG REGISTRY
ARG PYTHON_VERSION=3.9
FROM ${REGISTRY}/python:${PYTHON_VERSION}-slim
ENV PYTHON=True
WORKDIR /srv

RUN python -m pip install poetry

COPY ./ .
RUN poetry install --only main
