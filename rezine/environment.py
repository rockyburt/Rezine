# -*- coding: utf-8 -*-
"""
    rezine.environment
    ~~~~~~~~~~~~~~~~

    This module can figure how Rezine is installed and where it has to look
    for shared information.  Currently it knows about two modes: development
    environment and installation on a posix system.  OS X should be special
    cased later and Windows support is missing by now.

    File Locations
    --------------

    The files are located at different places depending on the environment.

    development
        in development mode all the files are relative to the rezine
        package::

            rezine/                           application code
                plugins/                    builtin plugins
                shared/                     core shared data
                templates/                  core templates
                i18n/                       translations

    posix
        On a posix system (including Linux) the files are distributed to
        different locations on the file system below the prefix which is
        /usr in the following example::

            /usr/lib/rezine/
                rezine/                       application code
                plugins/                    builtin plugins with symlinks
                                            to stuff in /usr/share/rezine
            /usr/share/rezine/
                htdocs/core                 core shared data
                templates/core              core templates
                i18n/                       translations

    :copyright: (c) 2010 by the Rezine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from os.path import realpath, dirname, join, pardir, isdir


# the platform name
from os import name as PLATFORM


# the path to the contents of the rezine package
PACKAGE_CONTENTS = realpath(dirname(__file__))

# the path to the folder where the "rezine" package is stored in.
PACKAGE_LOCATION = realpath(join(PACKAGE_CONTENTS, pardir))

# name of the domain for the builtin translations
LOCALE_DOMAIN = 'messages'

# true if the LC_MESSAGES folder is in use for the core domains
# (gettext based lookup is used then).  This does not affect
# translations from non-core plugins
USE_GETTEXT_LOOKUP = False

# check development mode first.  If there is a shared folder we must be
# in development mode.
SHARED_DATA = join(PACKAGE_CONTENTS, 'shared')
if isdir(SHARED_DATA):
    MODE = 'development'
    BUILTIN_PLUGIN_FOLDER = join(PACKAGE_CONTENTS, 'plugins')
    BUILTIN_TEMPLATE_PATH = join(PACKAGE_CONTENTS, 'templates')
    LOCALE_PATH = join(PACKAGE_CONTENTS, 'i18n')

# a Rezine installation on a posix system
elif PLATFORM == 'posix':
    MODE = 'posix'
    share = join(PACKAGE_LOCATION, pardir, pardir, 'share')
    BUILTIN_PLUGIN_FOLDER = realpath(join(PACKAGE_LOCATION, 'plugins'))
    BUILTIN_TEMPLATE_PATH = realpath(join(share, 'rezine', 'templates', 'core'))
    SHARED_DATA = realpath(join(share, 'rezine', 'htdocs', 'core'))
    LOCALE_PATH = realpath(join(share, 'locale'))
    LOCALE_DOMAIN = 'rezine'
    USE_GETTEXT_LOOKUP = True
    del share

# a Rezine installation on windows
elif PLATFORM == 'nt':
    raise NotImplementedError('Installation on windows is currently not '
                              'possible.  Consider using Rezine in development '
                              'mode.')

else:
    raise EnvironmentError('Could not determine Rezine environment')


# get rid of the helpers
del realpath, dirname, join, pardir, isdir
