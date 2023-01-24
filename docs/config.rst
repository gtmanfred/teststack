=============
Configuration
=============

The ``teststack.toml`` config file is located in each projects root directory,
preferably managed by git.

There is also a ``teststack.local.toml`` file that can be configured so that
users can overwrite stuff in the teststack.toml file without modifying it. This
file should be included in the repos .gitignore file.

Environment Variables
=====================

Environment Variables can be used inside of the configuration file as python
format strings.

The following will inject the ``$DOCKER_REPO`` environment variable into the configuration at
access time.

.. code-block::

    [tests.buildargs]
    REGISTRY = "{DOCKER_REPO}"

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
    min_version = "v0.11.0"
    steps = {
      "install": "poetry install",
      "tests": "poetry run coverage run -m pytest -v --junitxml=junit.xml {posargs}",
      "coverage": [
          "poetry run coverage report",
          "poetry run coverage xml",
          "poetry run coverage html"
      ]
    }
    import = {
        "command": "poetry run flask run -h 0.0.0.0",
        "setup": [
            "poetry run alembic upgrade head"
        ]
    }
    environment = {
        "STACK": "local"
    }
    export = {
        "TESTAPP_URL": "http://{HOST}:{POST;5000/tcp}/"
    }

.. code-block:: toml

    [tests]
    min_version = "v0.11.0"

    [tests.steps]
    install = "poetry install"
    tests = "poetry run coverage run -m pytest -v --junitxml=junit.xml {posargs}"
    report = [
        "poetry run coverage report",
        "poetry run coverage xml",
        "poetry run coverage html"
    ]

    [tests.import]
    command = "poetry run flask run -h 0.0.0.0"
    setup = [
        "poetry run alembic upgrade head",
        "poetry run python -m scripts.seed_data"
    ]

    [tests.environment]
    STACK = "local"

    [tests.export]
    TESTAPP_URL = "http://{HOST}:{POST;5000/tcp}/"

tests.min_version
-----------------

.. code-block:: toml

    [tests]
    min_version = "v0.11.0"

The minimum version of teststack that can be used to run this configuration.

tests.copy
----------

This is a list of files to copy out of the tests container when ``teststack
copy`` is run.

.. code-block:: toml

    [tests]
    copy = [
        "junit.xml",
        "coverage.xml"
    ]

This is only specifically useful if the current working directory is not mounted
to the container.

tests.steps
-----------

.. code-block:: toml

    [tests.steps]
    install = "pip install .[tests]"
    tests = "pytest -vx --junit-xml=junit.xml {posargs}"

A list of commands to execute (in order) for ``teststack run``.

``{posargs}`` can be included in one of the steps, and teststack will inject
unprocessed arguments to the ``run`` command to the test step.

.. code-block:: bash

    teststack run -- -k test_add_users tests/unit/test_users.py

results in the following command being run for the tests step.

.. code-block:: bash

    poetry run coverage run -m pytest -v --junitxml=junit.xml -k test_add_users test/unit/test_users.py

requires
~~~~~~~~

Requires is used to specify if another step must be run first before running
this step. In the below example, the install command will be run before the
tests command.

.. code-block:: toml

    [tests.steps]
    install = "pip install .[tests]"

    [tests.steps.tests]
    command = "coverage run -m pytest -v"
    requires = "install"

check
~~~~~

Check is used to determine if a command needs to be run. It also supersedes
requires. If a step is required by another step, if that other step's check
returns a 0 exit code, then the required step will also not be run.

In the below config, if the generated client directory does not exist, then the
apt repo data will be retrieved and java will be installed, so that it can be
used to build a swagger client. If the client does not need to be build, the
dependencies will also not be installed as part of the teststack run steps.

.. code-block:: toml

    [tests.steps.client-deps]
    command = [
        "apt update",
        "apt install -y openjdk-11-jre"
    ]
    user = "root"

    [tests.steps.client]
    command = "make client"
    requires = [
        "client-deps"
    ]
    check = "test -d clients/python/generated/"

    [tests.steps.tests]
    command = "coverage run -m pytest"
    requires = [
        "client"
    ]

tests.environment
-----------------

.. code-block:: toml

    [tests.environment]
    AWS_DEFAULT_REGION = "blah"

Environment variables to inject into the tests container. This should not be
secret data, it should just be fake data that is required to run the test suite.

tests.ports
-----------

.. code-block:: toml

    [tests.ports]
    "5000/tcp" = ""

This sets the ports that should be forwarded to the host, and also which ports
should be included for exporting an environment variables.

The protocol must be specified (tcp or udp).

tests.export
------------

.. code-block:: toml

    [tests.export]
    TESTAPP_URL = "http://{HOST}:{PORT;5000/tcp}/"

Exports are environment variables to add to test containers that import this
service repository. It exposes the same magic variables as exports below in
servives.

tests.buildargs
---------------

These arguments are passed into a Dockerfile during the build step. They can be
used to as arguments for templating a Dockerfile instead of jinja2.

.. code-block:: toml

    [tests.buildargs]
    REGISTRY = "https://ecr.io/1293485/"

.. code-block:: Dockerfile

    ARG REGISTRY
    FROM ${REGISTRY}/nodejs:latest

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

services.<name>
---------------

``image`` specifies the image to use for starting a service.

``build`` can be used to specify building a docker image from the context of a directory.

.. code-block:: toml

    [services.database]
    build = "services/postgres"

services.<name>.ports
---------------------

.. code-block:: toml

    [services.database.ports]
    "5432/tcp" = ""

The ports section is a set of key value pairs of ports to forward. If no port to
forward to is specified like in the example, a random unused port one is used.
Not specifying a port to forward too is preferred, because those ports are are
useable for exporting environment variables, so the can be programatically
discovered.

services.<name>.environment
---------------------------

.. code-block:: toml

    [services.database.environment]
    POSTGRES_USER = "fred"
    POSTGRES_PASSWORD = "secret"
    POSTGRES_DB = "tests"

this is a list of key values that are injected into the service container when
it starts up. In this case, those variables are used to setup the `postgres
container image<https://hub.docker.com/_/postgres/>`_.

services.<name>.exports
-----------------------

.. code-block:: toml

    [services.database.export]
    POSTGRESQL_DB_URL = "postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{HOST}:{PORT;5432/tcp}/{POSTGRES_DB}"

The export section is used to specify environment variables that should be
exported about the service. This makes it accessible programatically, the
environment variables the app uses can be specified here to hook everything up
together.

All of the environment variables from ``service.<name>.environments`` are able
to be used in a format string in this section, as well as the HOST and PORT
environment variables. These special variables correspond to the ip address of
the container and each of the ports that have been forwarded. They will be set
to the internal network values, or the docker network values based on if the
``--inside`` flag to the ``env`` command. The ``--inside`` argument is used to 
collect the environment variables to add to the testing container.

service.<name>.import
---------------------

Other repositories can also be imported as services.

.. code-block:: toml

    [service.testapp.import]
    repo = "ssh://github.com/gtmanfred/testapp"
    ref = "dev"

This is all that needs to be specified to import an application. The rest of the
settings are set on the other service repositories.

``repo`` is a path or url that points to a directory with a ``teststack.toml`` file.
``ref`` points to the reference, a commit, branch, or tag if the repo is a git
repository.

This will then start that other services environment and export the environment
variables in the ``export`` block of its test container into the current
environment.
