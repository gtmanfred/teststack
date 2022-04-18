=============
Configuration
=============

The ``teststack.toml`` config file is located in each projects root directory,
preferably managed by git.

This file is managed by toml, so the end result is a dictionary, and you can
represent the options however you like as long as they result in the same
dictionary structure.

Client
======

By default, teststack uses docker, but it also provides a podman container
backend. If your project is using podman, you can specify it under the client
section.

.. code-block:: toml

    [client]
    name = "podman"

Tests
=====

A minimum version of teststack can be specified as well as any environment
varibles that just need to be set on the tests container outside of the auto
generated ones.

For steps, when ``teststack run`` is executed, it will run the steps top down
from your config file. If you want to run just one step, specify the step name
with the command flag.

Here are a few examples.

.. code-block:: toml

    [tests]
    min_version = "v0.4.0"
    steps = {
      "install": "poetry install",
      "tests": "poetry run coverage run -m pytest -v --junitxml=junit.xml {posargs}",
      "coverage": [
          "poetry run coverage report",
          "poetry run coverage xml",
          "poetry run coverage html"
      ]
    }
    environment = {
        "STACK": "local"
    }

.. code-block:: toml

    [tests]
    min_version = "v0.4.0"

    [tests.steps]
    install = "poetry install"
    tests = "poetry run coverage run -m pytest -v --junitxml=junit.xml {posargs}"
    report = [
        "poetry run coverage report",
        "poetry run coverage xml",
        "poetry run coverage html"
    ]

    [tests.environment]
    STACK = "local"

You can include ``{posargs}`` in one of your steps, and teststack will inject
unprocessed arguments to the ``run`` command to the test step.

.. code-block:: bash

    teststack run -- -k test_add_users tests/unit/test_users.py

results in the following command being run for the tests step.

.. code-block:: bash

    poetry run coverage run -m pytest -v --junitxml=junit.xml -k test_add_users test/unit/test_users.py

Services
========

The services containers are the helper containers for running your test suite.
Similarly to above, you can specify them in toml however you like, but the end
result must resolve to the same dictionary.

Example:

.. code-block:: toml

    [services.database]
    image = "postgres:12"

    [services.database.ports]
    "5432/tcp" = ""

    [services.database.environment]
    POSTGRES_USER = "fred"
    POSTGRES_PASSWORD = "secret"
    POSTGRES_DB = "tests"

    [services.database.export]
    POSTGRESQL_DB_URL = "postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{HOST}:{PORT;5432/tcp}/{POSTGRES_DB}"

Everything underneath ``services`` is dependent on what you have, but lets cover
the above example.

First you have the name of the service which is ``database`` and you can specify
the ``image`` for that service.

Next you have the ports section, which is a set of key value pairs of ports to
forward. You do need to specify a value for the assignment, but you can make it
an empty string if you don't care which port it forwards too, which should be
find as the ``env`` command should give you the variables that you need.

After that is the ``environment`` section, this is a list of key values that are
injected into the service container when it starts up. In this case, those
variables are used to setup the `postgres container image<https://hub.docker.com/_/postgres/>`_.

The last section is ``export``. These are the environment variables that will be
exported by the ``env`` command so they can be set in the ``tests`` container,
or set in your local environment for running tests against these containers. If
you look closely, you will see the variables from the ``environment`` section
can be used in format strings, as well as two special variables: ``HOST`` and
``PORT;####/(tcp|udp)``. These special variables correspond to the ip address of
the container and each of the ports you have elected to forward. They will be
set to the internal network values, or the docker network values based on if you
have passed the ``--inside`` flag to the ``env`` command.
