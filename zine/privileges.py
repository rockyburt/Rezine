# -*- coding: utf-8 -*-
"""
    zine.privileges
    ~~~~~~~~~~~~~~~

    This module contains a list of builtin privileges.

    :copyright: (c) 2009 by the Zine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug.exceptions import Forbidden

from zine.database import db
from zine.application import get_application, get_request
from zine.i18n import lazy_gettext


__all__ = ['DEFAULT_PRIVILEGES', 'Privilege']

DEFAULT_PRIVILEGES = {}


class _Expr(object):

    def __and__(self, other):
        return _And(self, other)

    def __or__(self, other):
        return _Or(self, other)

    def __call__(self, privileges):
        return False


class _Bin(_Expr):

    def __init__(self, a, b):
        self.a = a
        self.b = b


class _And(_Bin):

    def __call__(self, privileges):
        return self.a(privileges) and self.b(privileges)


class _Or(_Bin):

    def __call__(self, privileges):
        return self.a(privileges) or self.b(privileges)


class _Privilege(object):
    """Internal throw-away class used for the association proxy."""

    def __init__(self, name):
        self.name = name

    @property
    def privilege(self):
        return get_application().privileges.get(self.name)


class Privilege(_Expr):

    def __init__(self, name, explanation, privilege_dependencies=()):
        self.name = name
        self.explanation = explanation
        self.dependencies = privilege_dependencies

    def __call__(self, privileges):
        return self in privileges

    def __repr__(self):
        return u'<%s %r>' % (
            self.__class__.__name__,
            self.name
        )


def add_admin_privilege(privilege):
    """If privilege is none, BLOG_ADMIN is returned, otherwise BLOG_ADMIN
    is "or"ed to the expression.
    """
    if privilege is None:
        privilege = BLOG_ADMIN
    elif privilege != BLOG_ADMIN:
        privilege = BLOG_ADMIN | privilege
    return privilege


def bind_privileges(container, privileges):
    """Binds the privileges to the container.  The privileges can be a list
    of privilege names, the container must be a set.  This is called for
    the HTTP round-trip in the form validation.
    """
    app = get_application()
    current_map = dict((x.name, x) for x in container)
    currently_attached = set(x.name for x in container)
    new_privileges = set(privileges)

    # remove out-dated privileges
    for name in currently_attached.difference(new_privileges):
        container.remove(current_map[name])

    # add new privileges
    for name in new_privileges.difference(currently_attached):
        container.add(app.privileges[name])
        for privilege in app.privileges[name].dependencies:
            container.add(privilege)


def require_privilege(expr):
    """Requires BLOG_ADMIN privilege or one of the given."""
    def wrapped(f):
        def decorated(request, *args, **kwargs):
            if request.user.has_privilege(expr):
                return f(request, *args, **kwargs)
            raise Forbidden()
        decorated.__name__ = f.__name__
        decorated.__module__ = f.__module__
        decorated.__doc__ = f.__doc__
        return decorated
    return wrapped


def assert_privilege(expr):
    """Like the `require_privilege` decorator but for asserting."""
    if not get_request().user.has_privilege(expr):
        raise Forbidden()


def privilege_attribute(lowlevel_attribute):
    """Returns a proxy attribute for privilege access."""
    def creator_func(privilege):
        if not isinstance(privilege, Privilege):
            raise TypeError('%r is not a privilege object' %
                            type(privilege).__name__)
        priv = _Privilege.query.filter_by(name=privilege.name).first()
        if priv is None:
            priv = _Privilege(privilege.name)
        return priv
    return db.association_proxy(lowlevel_attribute, 'privilege',
                                creator=creator_func)


def _register(name, description, privilege_dependencies=()):
    """Register a new builtin privilege."""
    priv = Privilege(name, description, privilege_dependencies)
    DEFAULT_PRIVILEGES[name] = priv
    globals()[name] = priv
    __all__.append(name)


_register('ENTER_ADMIN_PANEL', lazy_gettext(u'can enter admin panel'))
_register('BLOG_ADMIN', lazy_gettext(u'can administer the blog'))
_register('CREATE_ENTRIES', lazy_gettext(u'can create new entries'),
          (ENTER_ADMIN_PANEL,))
_register('EDIT_OWN_ENTRIES', lazy_gettext(u'can edit their own entries'),
          (ENTER_ADMIN_PANEL, CREATE_ENTRIES))
_register('EDIT_OTHER_ENTRIES', lazy_gettext(u'can edit another person\'s entries'),
          (ENTER_ADMIN_PANEL,))
_register('CREATE_PAGES', lazy_gettext(u'can create new pages'),
          (ENTER_ADMIN_PANEL,))
_register('EDIT_OWN_PAGES', lazy_gettext(u'can edit their own pages'),
          (ENTER_ADMIN_PANEL, CREATE_PAGES))
_register('EDIT_OTHER_PAGES', lazy_gettext(u'can edit another person\'s pages'),
          (ENTER_ADMIN_PANEL,))
_register('VIEW_DRAFTS', lazy_gettext(u'can view drafts'))
_register('MANAGE_CATEGORIES', lazy_gettext(u'can manage categories'),
          (ENTER_ADMIN_PANEL,))
_register('MODERATE_COMMENTS', lazy_gettext(u'can moderate comments'),
          (ENTER_ADMIN_PANEL,))
_register('MODERATE_OWN_ENTRIES', lazy_gettext(u'can moderate comments on it\'s own entries'),
          (ENTER_ADMIN_PANEL, CREATE_ENTRIES))
_register('MODERATE_OWN_PAGES', lazy_gettext(u'can moderate comments on it\'s own pages'),
          (ENTER_ADMIN_PANEL, CREATE_PAGES))
_register('VIEW_PROTECTED', lazy_gettext(u'can view protected entries'))


CONTENT_TYPE_PRIVILEGES = {
    'entry':    (CREATE_ENTRIES, EDIT_OWN_ENTRIES, EDIT_OTHER_ENTRIES),
    'page':     (CREATE_PAGES, EDIT_OWN_PAGES, EDIT_OTHER_PAGES)
}
