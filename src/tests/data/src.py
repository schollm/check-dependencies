# flake8: noqa
import dependency_check_test
import missing.bar
import missing.foo
import test_1
import test_main  # This is a test import provided by the test environment
from missing import baz

class X:
    import missing_class


def x():
    import missing  # Another time missing is imported
    import missing_def
