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

VENDOR_SENTINEL:=.sentinel

.PHONY: venv
venv: $(VENV_ACTIVATE)

$(VENV_ACTIVATE): requirements*.txt
	test -f $@ || virtualenv --python=python3.6 $(VENV_DIR)
	$(WITH_VENV) pip install -r requirements-setup.txt
	$(WITH_VENV) pip install -e .
	$(WITH_VENV) pip install -r requirements-dev.txt
	touch $@

develop: setup migrate
	$(WITH_VENV) python setup.py develop

.PHONY: setup
setup: ##[setup] Run an arbitrary setup.py command
setup: init venv
ifdef ARGS
	$(WITH_VENV) python setup.py ${ARGS}
else
	@echo "Won't run 'python setup.py ${ARGS}' without ARGS set."
endif

.PHONY: init
init: $(VENDOR_SENTINEL)-init
$(VENDOR_SENTINEL)-init:
	test -z `psql postgres -U postgres -At -c "SELECT 1 FROM pg_roles WHERE rolname='django'" ` && createuser -u postgres -d django || true
	dropdb --if-exists capone_test_db -U postgres
	createdb -U django capone_test_db
	@touch $@

.PHONY: migrate
migrate: $(VENDOR_SENTINEL)-migrate
$(VENDOR_SENTINEL)-migrate: setup
	$(WITH_VENV) DBFILENAME=test.db ./manage.py migrate --settings=capone.tests.settings --noinput
	@touch $@

.PHONY: makemigrations
makemigrations: develop
	$(WITH_VENV) DBFILENAME=test.db ./manage.py makemigrations --settings=capone.tests.settings

.PHONY: shell
shell: develop
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
	find . -type f -name '*.pyc' -delete
	rm -rf coverage .coverage*
	dropdb --if-exists capone_test_db -U postgres

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
