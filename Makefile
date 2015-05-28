# Makefile for packaging and testing this app. Should follow make contract
# at https://github.counsyl.com/techops/lambda-ci#make-build

PACKAGE_NAME=ledger
TEST_OUTPUT?=nosetests.xml
PYPI?=https://pypi.counsyl.com/counsyl/prod/

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
	$(WITH_VENV) pip install --no-deps -r requirements-setup.txt --index-url=${PYPI}
	$(WITH_VENV) pip install --no-deps -r requirements.txt  --index-url=${PYPI}
	$(WITH_VENV) pip install --no-deps -r requirements-dev.txt  --index-url=${PYPI}
.PHONY: venv
venv: $(VENV_ACTIVATE)

develop: venv
	$(WITH_VENV) python setup.py develop

.PHONY: setup
setup: venv

.PHONY: shell
shell: develop
	$(WITH_VENV) DBFILENAME=test.db ./manage.py syncdb --settings=ledger.tests.settings --noinput
	$(WITH_VENV) DBFILENAME=test.db ./manage.py shell --settings=ledger.tests.settings

.PHONY: runserver
runserver: develop
	$(WITH_VENV) DBFILENAME=test.db ./manage.py syncdb --settings=ledger.tests.settings --noinput
	$(WITH_VENV) DBFILENAME=test.db ./manage.py createsuperuser --settings=ledger.tests.settings
	$(WITH_VENV) DBFILENAME=test.db ./manage.py runserver --settings=ledger.tests.settings 0.0.0.0:8000

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
	rm -f nosetests* "${TEST_OUTPUT}" coverage .coverage

.PHONY: teardown
teardown:
	rm -rf .tox .venv

.PHONY: lint
lint: venv
	$(WITH_VENV) flake8 -v $(PACKAGE_NAME)/

.PHONY: test
test: venv
	$(WITH_VENV) \
	coverage erase ; \
	tox -v; \
	status=$$?; \
	coverage combine; \
	coverage html --directory=coverage --omit="tests*"; \
	coverage report; \
	xunitmerge nosetests-*.xml $(TEST_OUTPUT); \
	exit $$status;

.PHONY: dist
dist:
	python setup.py sdist
