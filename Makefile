# Makefile for packaging and testing this app. Should follow make contract
# at https://github.counsyl.com/techops/lambda-ci#make-build

PACKAGE_NAME=ledger
TEST_OUTPUT?=nosetests.xml
PYPI?=https://pypi.counsyl.com/counsyl/prod/+simple/

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
	$(WITH_VENV) pip install -r requirements-setup.txt --index-url=${PYPI}
	$(WITH_VENV) pip install -e . --index-url=${PYPI}
	$(WITH_VENV) pip install -r requirements-dev.txt  --index-url=${PYPI}
	touch $@

develop: venv
	$(WITH_VENV) python setup.py develop

.PHONY: setup
setup: ##[setup] Run an arbitrary setup.py command
setup: venv
ifdef ARGS
	$(WITH_VENV) python setup.py ${ARGS}
else
	@echo "Won't run 'python setup.py ${ARGS}' without ARGS set."
endif

.PHONY: migrate
migrate: develop
	dropdb --if-exists ledger_test_db
	createdb ledger_test_db
	$(WITH_VENV) DBFILENAME=test.db ./manage.py migrate --settings=tests.settings --noinput

.PHONY: shell
shell: migrate
	$(WITH_VENV) DBFILENAME=test.db ./manage.py shell --settings=tests.settings

.PHONY: runserver
runserver: migrate
	$(WITH_VENV) DBFILENAME=test.db ./manage.py runserver --settings=tests.settings 0.0.0.0:8000

.PHONY: clean
clean:
	python setup.py clean
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg*/
	rm -rf __pycache__/
	rm -f MANIFEST
	rm -f test.db
	rm -f $(TEST_OUTPUT)
	find $(PACKAGE_NAME) -type f -name '*.pyc' -delete
	rm -rf nosetests* "${TEST_OUTPUT}" coverage .coverage
	dropdb --if-exists ledger_test_db

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
	tox -v $(TOX_ENV_FLAG); \
	status=$$?; \
	coverage combine; \
	coverage html --directory=coverage --omit="*tests*"; \
	coverage report --fail-under=100 --show-missing; \
	coverage_code=$$?; \
	xunitmerge nosetests-*.xml $(TEST_OUTPUT); \
	if [ $$coverage_code > 0 ] ; then echo "Failed: Test coverage is not 100%."; fi; \
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
