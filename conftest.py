import pytest


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Enable database access for all tests.

    PyTest doesn't allow database access by default, so we create a fixture with `autouse=True` at
    the top level of the project to automatically give all tests access to the database.  As we
    extend the use of PyTest, especially to "database disallowed" tests, and as we clean up and
    make more apparent the dependencies of each test, we can narrow the scope of this fixture,
    eventually removing it.

    See https://pytest-django.readthedocs.io/en/latest/faq.html?highlight=enable_db_access_for_all_tests#how-can-i-give-database-access-to-all-my-tests-without-the-django-db-marker.
    """


@pytest.fixture(autouse=True, params=[False, True])
def parametrize_entire_test_suite_by_use_tz(request, settings, db):
    settings.USE_TZ = request.param
