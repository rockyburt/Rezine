# -*- coding: utf-8 -*-
"""
    Rezine Test Suite
    ~~~~~~~~~~~~~~~

    This is the Rezine test suite. It collects all modules in the rezine
    package, builds a TestSuite with their doctests and executes them. It also
    collects the tests from the text files in this directory (which are too
    extensive to put them into the code without cluttering it up).

    :copyright: (c) 2010 by the Rezine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""

import sys
import os
from os.path import join, dirname
from unittest import TestSuite
from doctest import DocTestSuite, DocFileSuite
from tempfile import mkdtemp
from shutil import copytree

from rezine.manage import DEFAULT_INSTANCE_FOLDER

#: the modules in this list are not tested in a full run
untested = ['rezine.broken_plugins.hyphenation_en',
            'rezine.broken_plugins.hyphenation_en.hyphenate',
            'rezine.broken_plugins.notification']


def test_suite(modnames=[]):
    """Generate the test suite.

    The first argument is a list of modules to be tested. If it is empty (which
    it is by default), all sub-modules of the rezine package are tested.
    If the second argument is True, this function returns two objects: a
    TestSuite instance and a list of the names of the tested modules. Otherwise
    (which is the default) it only returns the former. This is done so that
    this function can be used as setuptools' test_suite.
    """

    # the app object is used for two purposes:
    # 1) plugins are not usable (i.e. not testable) without an initialised app
    # 2) for functions that require an application object as argument, you can
    #    write >>> my_function(app, ...) in the tests
    # The instance directory of this object is located in the tests directory.
    #
    from rezine import is_rezine_setup, setup_rezine, get_rezine

    if not is_rezine_setup():
        # instance files potentially get changed, lets
        # set them up in a temp dir first
        tmpdir = mkdtemp()
        instance_path = join(tmpdir, DEFAULT_INSTANCE_FOLDER)
        copytree(join(dirname(__file__), DEFAULT_INSTANCE_FOLDER), instance_path)
        app = setup_rezine(instance_path)
    else:
        app = get_rezine()

    suite = TestSuite()

    if modnames == []:
        modnames = find_tp_modules()
    test_files = os.listdir(dirname(__file__))
    for modname in modnames:
        if modname in untested:
            continue

        # the fromlist must contain something, otherwise the rezine
        # package is returned, not our module
        try:
            mod = __import__(modname, None, None, [''])
        except ImportError:
            # some plugins can have external dependencies (e.g. creoleparser,
            # pygments) that are not installed on the machine the tests are
            # run on. Therefore, just skip those (with an error message)
            if 'plugins.' in modname:
                sys.stderr.write('could not import plugin %s\n' % modname)
                continue
            else:
                raise

        suites = [DocTestSuite(mod, extraglobs={'app': app})]
        filename = modname[5:] + '.txt'
        if filename in test_files:
            globs = {'app': app}
            globs.update(mod.__dict__)
            suites.append(DocFileSuite(filename, globs=globs))
        for i, subsuite in enumerate(suites):
            # skip modules without any tests
            if subsuite.countTestCases():
                suite.addTest(subsuite)
    return suite


def find_tp_modules():
    """Find all sub-modules of the rezine package."""
    modules = []
    import rezine
    base = dirname(rezine.__file__)
    start = len(dirname(base))
    if base != 'rezine':
        start += 1

    for path, dirnames, filenames in os.walk(base):
        for filename in filenames:
            if filename.endswith('.py'):
                fullpath = join(path, filename)
                if filename == '__init__.py':
                    stripped = fullpath[start:-12]
                else:
                    stripped = fullpath[start:-3]

                modname = stripped.replace('/', '.')
                modules.append(modname)
    return modules
