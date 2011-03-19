# -*- coding: utf-8 -*-
"""
    _init_rezine
    ~~~~~~~~~~

    Helper to locate rezine and the instance folder.

    :copyright: (c) 2010 by the Rezine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from os.path import abspath, join, dirname, pardir, isfile
import sys

# set to None first because the installation replaces this
# with the path to the installed rezine library.
ZINE_LIB = None

if ZINE_LIB is None:
    ZINE_LIB = abspath(join(dirname(__file__), pardir))

# make sure we load the correct rezine
sys.path.insert(0, ZINE_LIB)

from rezine.manage import DEFAULT_INSTANCE_FOLDER


def find_instance():
    """Find the Rezine instance."""
    instance = None
    if isfile(join(DEFAULT_INSTANCE_FOLDER, 'rezine.ini')):
        instance = abspath(DEFAULT_INSTANCE_FOLDER)
    else:
        old_path = None
        path = abspath('.')
        while old_path != path:
            path = abspath(join(path, pardir))
            if isfile(join(path, 'rezine.ini')):
                instance = path
                break
            old_path = path
    return instance
