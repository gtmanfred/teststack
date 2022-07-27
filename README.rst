Teststack
=========

.. image:: https://github.com/gtmanfred/teststack/workflows/Tests/badge.svg
    :target: https://github.com/gtmanfred/teststack

.. image:: https://img.shields.io/codecov/c/github/gtmanfred/teststack
    :target: https://codecov.io/gh/gtmanfred/teststack

.. image:: https://img.shields.io/pypi/v/teststack
    :target: https://pypi.org/project/teststack

.. image:: https://img.shields.io/pypi/l/teststack
    :target: http://www.apache.org/licenses/LICENSE-2.0

.. image:: https://img.shields.io/pypi/dm/teststack
    :target: https://pypi.org/project/figenv/

.. image:: https://readthedocs.org/projects/teststack/badge?version=latest&style=flat
    :target: https://teststack.readthedocs.org/

.. image:: https://img.shields.io/lgtm/grade/python/g/gtmanfred/teststack.svg?logo=lgtm&logoWidth=18
   :target: https://lgtm.com/projects/g/gtmanfred/teststack/context:python

Test an application with infrastructure.

teststack.toml
--------------

.. code-block:: toml

    [tests.steps]
    ping = "ping -c4 8.8.8.8"
    env = "env"
    raw = "{posargs}"

    [services.database]
    image = "postgres:12"

    [services.database.ports]
    "5432/tcp" = ""

    [services.database.environment]
    POSTGRES_USER = "bebop"
    POSTGRES_PASSWORD = "secret"
    POSTGRES_DB = "bebop"

    [services.database.export]
    SQLALCHEMY_DATABASE_URI = "postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{HOST}:{PORT;5432/tcp}/{POSTGRES_DB}"
    POSTGRES_MAIN_USER = "{POSTGRES_USER}"
    POSTGRES_MAIN_PASSWORD = "{POSTGRES_PASSWORD}"
    POSTGRES_MAIN_HOST = "{HOST}"
    POSTGRES_MAIN_RDS_HOST = "{HOST}"
    POSTGRES_MAIN_PORT = "{PORT;5432/tcp}"
    POSTGRES_MAIN_DBNAME = "{POSTGRES_DB}"

There are two main sections: ``tests`` and ``services``.

The ``test`` section is for information about the docker container that is going
to be used for testing. It renders the ``Dockerfile.j2``, and injects environment
variables for customization. The ``tests.steps`` section specifies which steps
should be run on a test machine. Any unprocessed commandline arguments that are
passed into teststack are stuck into commands as ``posargs``.

.. code-block:: bash

    teststack render
    teststack build
    teststack run -s raw -- pytest -k mytest
    teststack stop

The ``services`` section specifies the services that need to be started along side
a test container.  In this example, a postgres container is started.  Then the
ports specify which ports need to be exposed, so 5432/tcp. And what environment
variables should be passed to the service docker container when starting up, so
that it can be configured. In this case, we set the username, password and db
for the database. The three commands around the services are start, stop and
restart, they do what they say.

.. code-block:: bash

    teststack start
    teststack stop
    teststack restart

Everything that is set in the environment section is available when exporting.
The other special variables that are made available is the HOST of the docker
container. By default, the ``env`` command exports ``localhost`` for the ``{HOST}``
variable. And then the port that is exported has the number appended after a
semicolon. So if you have specified ``5432/tcp`` as a port for a service
container, the variable ``{PORT;5432/tcp}`` will be made available for exporting,
or to add to connection strings.

If however, the env is being used to start a test container (like run does) the
HOST variable will be the default docker network IPAddress of the container, and
the port will be just the port, and not adapted to the forwarding port on the
Host network.

If you choose to run tests locally, instead of in the tests container, you can
export the environment variables for the stack and source them or put them in a
file for something like vscode to read.

.. code-block:: bash

    $ source <(teststack env)
    $ teststack env --no-export > .env
