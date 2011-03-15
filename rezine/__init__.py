# -*- coding: utf-8 -*-
"""
    rezine
    ~~~~

    Rezine is a simple python weblog software.


    Get a WSGI Application
    ======================

    To get the WSGI application for Rezine you can use the `make_app`
    function.  This function can either create a dispatcher for one instance
    or for multiple application instances where the current active instance
    is looked up in the WSGI environment.  The latter is useful for mass
    hosting via mod_wsgi or similar interfaces.

    Here a small example `rezine.wsgi` for mod_wsgi::

        from rezine import get_wsgi_app
        application = get_wsgi_app('/path/to/instance')


    :copyright: (c) 2010 by the Rezine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""

import pkg_resources

__version__ = pkg_resources.get_distribution('Rezine').version
__url__ = 'http://rezine.pocoo.org/'


# implementation detail.  Stuff in __all__ and the initial import has to be
# the same.  Everything that is not listed in `__all__` or everything that
# does not start with two leading underscores is wiped out on reload and
# the core module is *not* reloaded, thus stuff will get lost if it's not
# properly listed.
from rezine._core import setup, get_wsgi_app, override_environ_config
__all__ = ('setup', 'get_wsgi_app', 'override_environ_config')
