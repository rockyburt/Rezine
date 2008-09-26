"""
    zine.utils
    ~~~~~~~~~~

    This package implements various functions used all over the code.

    :copyright: 2007 by Armin Ronacher, Georg Brandl.
    :license: GNU GPL.
"""
import os
from urlparse import urlparse

try:
    from simplejson import dumps as dump_json, loads as load_json
except ImportError:
    from json import dumps as dump_json, loads as load_json

from werkzeug import url_quote, Local, LocalManager, ClosingIterator

# load dynamic constants
from zine._dynamic import *


# our local stuff
local = Local()
local_manager = LocalManager([local])


def build_tag_uri(app, date, resource, identifier):
    """Build a unique tag URI for this blog."""
    host, path = urlparse(app.cfg['blog_url'])[1:3]
    if ':' in host:
        host = host.split(':', 1)[0]
    path = path.strip('/')
    if path:
        path = ',' + path
    if not isinstance(identifier, basestring):
        identifier = str(identifier)
    return 'tag:%s,%s%s/%s:%s' % (host, date.strftime('%Y-%m-%d'), path,
                                  url_quote(resource), url_quote(identifier))


class RequestLocal(object):
    """All attributes on this object are request local and deleted after the
    request finished. The request local object itself must be stored somewhere
    in a global context and never deleted.
    """

    def __init__(self, **vars):
        self.__dict__.update(_vars=vars)
        for key, value in vars.iteritems():
            if value is None:
                value = lambda: None
            vars[key] = value

    @property
    def _storage(self):
        return local.request_locals.setdefault(id(self), {})

    def __getattr__(self, name):
        if name not in self._vars:
            raise AttributeError(name)
        if name not in self._storage:
            self._storage[name] = self._vars[name]()
        return self._storage[name]

    def __setattr__(self, name, value):
        if name not in self._vars:
            raise AttributeError(name)
        self._storage[name] = value
