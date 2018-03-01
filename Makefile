PACKAGE_NAME=capone

ifdef TOX_ENV
	TOX_ENV_FLAG := -e $(TOX_ENV)
else
	TOX_ENV_FLAG :=
endif

.PHONY: default
default:
	python setup.py check build

VENV_DIR?=.venv
VENV_ACTIVATE=$(VENV_DIR)/bin/activate
WITH_VENV=. $(VENV_ACTIVATE);

.PHONY: venv
venv: $(VENV_ACTIVATE)

$(VENV_ACTIVATE): requirements*.txt
	test -f $@ || virtualenv --python=python2.7 $(VENV_DIR)
	$(WITH_VENV) pip install -r requirements-setup.txt
	$(WITH_VENV) pip install -e .
	$(WITH_VENV) pip install -r requirements-dev.txt
	touch $@

develop: setup
	$(WITH_VENV) python setup.py develop

.PHONY: setup
setup: ##[setup] Run an arbitrary setup.py command
setup: venv migrate
ifdef ARGS
	$(WITH_VENV) python setup.py ${ARGS}
else
	@echo "Won't run 'python setup.py ${ARGS}' without ARGS set."
endif

.PHONY: migrate
migrate: develop
	test -z `psql postgres -At -c "SELECT 1 FROM pg_roles WHERE rolname='django'" ` && createuser -d django || true
	dropdb --if-exists capone_test_db
	createdb capone_test_db
	$(WITH_VENV) DBFILENAME=test.db ./manage.py migrate --settings=capone.tests.settings --noinput

.PHONY: makemigrations
makemigrations: develop
	$(WITH_VENV) DBFILENAME=test.db ./manage.py makemigrations --settings=capone.tests.settings

.PHONY: shell
shell: migrate
	$(WITH_VENV) DBFILENAME=test.db ./manage.py shell --settings=capone.tests.settings

.PHONY: clean
clean:
	python setup.py clean
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg*/
	rm -rf .eggs
	find . -type f -name '*.pyc' -delete
	find . -name __pycache__ -delete
	rm -f MANIFEST
	rm -f test.db
	rm -f xunit.xml
	find . -type f -name '*.pyc' -delete
	rm -rf coverage .coverage*
	dropdb --if-exists capone_test_db

.PHONY: teardown
teardown:
	rm -rf .tox $(VENV_DIR)

.PHONY: lint
lint: venv
	$(WITH_VENV) flake8 -v $(PACKAGE_NAME)/

.PHONY: test
test: venv
	$(WITH_VENV) \
	coverage erase ; \
	tox -v $(TOX_ENV_FLAG)
	status=$$?;
	exit $$status;

# Distribution
VERSION=`$(WITH_VENV) python setup.py --version | sed 's/\([0-9]*\.[0-9]*\.[0-9]*\).*$$/\1/'`

.PHONY: version
version: venv
version: ## Print the computed semver version.
	@echo ${VERSION}

.PHONY: tag
tag: ##[distribution] Tag the release.
tag: venv
	echo "Tagging version as ${VERSION}"
	git tag -a ${VERSION} -m 'Version ${VERSION}'
	# We won't push changes or tags here allowing the pipeline to do that, so we don't accidentally do that locally.

.PHONY: dist
dist: venv
	$(WITH_VENV) python setup.py sdist

.PHONY: sdist
sdist: dist
	@echo "runs dist"
