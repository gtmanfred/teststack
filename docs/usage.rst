=====
Usage
=====

Tips about using teststack.

All of this is extra, the basic command you should need is only ``teststack
run``.

Getting the Environment Setup
=============================

There are a handful of commands that are just about creating and tearing down
the containers in the environment.

The first step that happens usually is ``render``.  The jinja2 file for the
docker container needs to be rendered to a Dockerfile. This step may be skipped
if there is no template file but the Dockerfile already exists so a template is
not required. The render step also will not be run if the modified time of the
dockerfile is more recent than the template file. This allows the user to modify
the dockerfile without rerendering it everytime.

Renders are triggered for the build command based on what was stated in the
previous paragraph. And builds are triggered whenever there is a new tag
discovered based on the current git repository.

.. code-block:: bash

    teststack render
    teststack build

Once you have a container image build, we can start the containers for the
environment.  Start will start all of the containers, with the option to not run
``tests`` container, which is the one that was just build. If you specify to not
run the tests container, then the image will not be triggered to be built.

.. code-block:: bash

    teststack start
    teststack start -n
    teststack stop
    teststack restart

The last two commands are more about running tests in that ``tests`` container.

There is ``exec`` which puts you in the tests container, with all the
environment variables set so you can do whatever you want. Then there is ``run``
which runs in order, the steps specified in the ``teststack.toml`` file.

.. code-block:: bash

    teststack exec
    teststack run
    teststack run -s tests -- -k test_add_users tests/unit/test_users.py

Running Tests Outside of Containers
===================================

Once you have the environment setup and your testing containers started, you
also have the option to run the tests directly from your device instead of in
the tests container.

If you are using something like the Test Runner for vscode, you can generate a
``.env`` file to hold environment variables in.

.. code-block:: bash

    testsack env -n > .env

Or you could just source the output to run the tests against this environment
from your cli shell.

.. code-block:: bash

    source <(teststack env)
    pytest -v tests/unit/test_users.py
