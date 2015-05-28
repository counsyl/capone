import os
from setuptools import setup, find_packages

from pip.req import parse_requirements
from pip.download import PipSession


def read_file(filename):
    """Read a file into a string"""
    path = os.path.abspath(os.path.dirname(__file__))
    filepath = os.path.join(path, filename)
    try:
        return open(filepath).read()
    except IOError:
        return ''


requirements = ['django'] + [
    str(ir.req)
    for ir in parse_requirements('./requirements.txt', session=PipSession())]

test_requirements = [
    str(ir.req)
    for ir in parse_requirements('./requirements-dev.txt', session=PipSession())]

setup(
    name='counsyl-django-ledger',
    version=__import__('ledger').__version__,
    author='Steven Buss',
    author_email='root@counsyl.com',
    packages=find_packages(),
    include_package_data=True,
    url='https://github.counsyl.com/dev/ledger/',
    license='Copyright Counsyl, Inc.',
    description=' '.join(__import__('ledger').__doc__.splitlines()).strip(),
    classifiers=[
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Intended Audience :: Developers',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Framework :: Django',
        'Development Status :: 4 - Beta',
        'Operating System :: OS Independent',
    ],
    long_description=read_file('README.rst'),
    install_requires=requirements,
    tests_require=test_requirements,
    zip_safe=False,
)
