import os


DEBUG = True

INSTALLED_APPS = (
    'capone.tests',
    'capone',
    'django.contrib.staticfiles',
    'django.contrib.sessions',
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.admin',
)

SECRET_KEY = 'secretkey'

TEMPLATE_DIRS = (os.path.join(os.path.dirname(__file__), 'templates'),)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'HOST': os.environ.get('POSTGRES_HOST', ''),
        'NAME': os.environ.get('POSTGRES_DB', 'capone_test_db'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'django'),
        'PORT': os.environ.get('POSTGRES_PORT', ''),
        'USER': os.environ.get('POSTGRES_USER', 'django'),
    },
}

ALLOWED_HOSTS = []

STATIC_FILE_FINDERS = (
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
)

STATIC_URL = '/static/'

MIDDLEWARE_CLASSES = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
