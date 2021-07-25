import logging

import pytest

from app.application import create_app


@pytest.fixture(scope='session')
def app():
    with create_app().test_client() as test_app:
        yield test_app
