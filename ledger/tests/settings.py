import os

import django


DEBUG = True

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'django_nose',
    'ledger',
    'ledger.tests',
)
if django.VERSION[:2] >= (1, 7):
    # Django switched the order of installed apps in 1.7.
    INSTALLED_APPS = tuple(reversed(INSTALLED_APPS))

SECRET_KEY = 'secretkey'

TEMPLATE_DIRS = (os.path.join(os.path.dirname(__file__), 'templates'),)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DBFILENAME', ':memory:')
    }
}

ROOT_URLCONF = "ledger.tests.urls"

ALLOWED_HOSTS = []

STATIC_FILE_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

STATIC_URL = '/static/'

TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
