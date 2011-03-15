# -*- coding: utf-8 -*-
"""
    rezine.plugins.dark_vessel_colorscheme
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    A dark colorscheme for vessel.

    :copyright: (c) 2010 by the Rezine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from os.path import join, dirname
from rezine.api import _
from rezine.plugins import vessel_theme


SHARED_FILES = join(dirname(__file__), 'shared')


def setup(app, plugin):
    app.add_shared_exports('dark_vessel_colorscheme', SHARED_FILES)
    vessel_theme.add_variation(u'dark_vessel_colorscheme::dark.css', _('Dark'))
