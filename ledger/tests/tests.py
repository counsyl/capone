from __future__ import print_function

import os
import re
import unittest

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase


class TestCreateSuperUserCommand(TestCase):
    """
    Example test which asserts that a superuser with username admin
    is created by the createsuperusercommand
    """
    def test(self):
        get_user_model().objects.all().delete()
        call_command('createsuperuser')

        self.assertEqual(
            list(get_user_model().objects.all()),
            [get_user_model().objects.get(username='admin',
                                          is_superuser=True)]
        )


class TestBoilerplateFilledOut(TestCase):
    """
    All boilerplate strings in this app are "Lorem ipsum".

    This test should fail until all of them have been replaced, at
    which point this test can be deleted.
    """

    lorem_regex = re.compile(r'lorem ipsum', flags=re.IGNORECASE)

    def get_failing_lines(self, filepath):
        with open(filepath, 'r') as f:
            for i, line in enumerate(f):
                if self.lorem_regex.search(line):
                    yield (filepath, i, line)

    @unittest.expectedFailure
    def test(self):
        # Ignore files in third-party dependencies and .config files.
        ignorable_regex = re.compile('|'.join([
            r'(^|/)[.]\w',
            r'tests[.]py',
            r'[.]egg-info',
            r'/coverage/',
            r'nosetests',
            r'[.]pyc'
        ]))

        failing_lines = []
        project_root = os.path.normpath(
            os.path.join(os.path.dirname(__file__), '../../'))
        for (dirpath, dirnames, filenames) in os.walk(project_root):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if not ignorable_regex.search(filepath):
                    failing_lines.extend(self.get_failing_lines(filepath))

        for filepath, i, line in failing_lines:
            print('{} {}: {}'.format(filepath, i, line))

        self.assertEqual(failing_lines, [])
