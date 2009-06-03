# -*- coding: utf-8 -*-
"""
    zine.database
    ~~~~~~~~~~~~~

    This module is a rather complex layer on top of SQLAlchemy 0.4.
    Basically you will never use the `zine.database` module except you
    are a core developer, but always the high level
    :mod:`~zine.database.db` module which you can import from the
    :mod:`zine.api` module.


    :copyright: (c) 2009 by the Zine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import re
import os
import sys
import time
import urlparse
from os import path
from datetime import datetime, timedelta
from types import ModuleType
from copy import deepcopy

import sqlalchemy
from sqlalchemy import orm
from sqlalchemy.interfaces import ConnectionProxy
from sqlalchemy.orm.interfaces import AttributeExtension
from sqlalchemy.exc import ArgumentError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.util import to_list
from sqlalchemy.engine.url import make_url, URL
from sqlalchemy.types import MutableType, TypeDecorator
from sqlalchemy.ext.associationproxy import association_proxy

from werkzeug import url_decode
from werkzeug.exceptions import NotFound

from zine.utils import local_manager


if sys.platform == 'win32':
    _timer = time.clock
else:
    _timer = time.time


_sqlite_re = re.compile(r'sqlite:(?:(?://(.*?))|memory)(?:\?(.*))?$')


def get_engine():
    """Return the active database engine (the database engine of the active
    application).  If no application is enabled this has an undefined behavior.
    If you are not sure if the application is bound to the active thread, use
    :func:`~zine.application.get_application` and check it for `None`.
    The database engine is stored on the application object as `database_engine`.
    """
    from zine.application import get_application
    return get_application().database_engine


def create_engine(uri, relative_to=None, debug=False):
    """Create a new engine.  This works a bit like SQLAlchemy's
    `create_engine` with the difference that it automaticaly set's MySQL
    engines to 'utf-8', and paths for SQLite are relative to the path
    provided as `relative_to`.

    Furthermore the engine is created with `convert_unicode` by default.
    """
    # special case sqlite.  We want nicer urls for that one.
    if uri.startswith('sqlite:'):
        match = _sqlite_re.match(uri)
        if match is None:
            raise ArgumentError('Could not parse rfc1738 URL')
        database, query = match.groups()
        if database is None:
            database = ':memory:'
        elif relative_to is not None:
            database = path.join(relative_to, database)
        if query:
            query = url_decode(query).to_dict()
        else:
            query = {}
        info = URL('sqlite', database=database, query=query)

    else:
        info = make_url(uri)

        # if mysql is the database engine and no connection encoding is
        # provided we set it to utf-8
        if info.drivername == 'mysql':
            info.query.setdefault('charset', 'utf8')

    options = {'convert_unicode': True}

    # alternative pool sizes / recycle settings and more.  These are
    # interpreter wide and not from the config for the following reasons:
    #
    # - system administrators can set it independently from the webserver
    #   configuration via SetEnv and friends.
    # - this setting is deployment dependent should not affect a development
    #   server for the same instance or a development shell
    for key in 'pool_size', 'pool_recycle', 'pool_timeout':
        value = os.environ.get('ZINE_DATABASE_' + key.upper())
        if value is not None:
            options[key] = int(value)

    # if debugging is enabled, hook the ConnectionDebugProxy in
    if debug:
        options['proxy'] = ConnectionDebugProxy()

    return sqlalchemy.create_engine(info, **options)


def secure_database_uri(uri):
    """Returns the database uri with confidental information stripped."""
    obj = make_url(uri)
    if obj.password:
        obj.password = '***'
    return unicode(obj).replace(u':%2A%2A%2A@', u':***@', 1)


def attribute_loaded(model, attribute):
    """Returns true if the attribute of the model was already loaded."""
    # XXX: this works but it relys on a specific implementation in
    # SQLAlchemy.  Figure out if SA provides a way to query that information.
    return attribute in model.__dict__


class ConnectionDebugProxy(ConnectionProxy):
    """Helps debugging the database."""

    def cursor_execute(self, execute, cursor, statement, parameters,
                       context, executemany):
        start = _timer()
        try:
            return execute(cursor, statement, parameters, context)
        finally:
            from zine.application import get_request
            from zine.utils.debug import find_calling_context
            request = get_request()
            if request is not None:
                request.queries.append((statement, parameters, start,
                                        _timer(), find_calling_context()))


class ZEMLParserData(TypeDecorator):
    """Holds parser data.  The implementation is rather ugly because it does
    not really compare the trees for performance reasons but only the dirty
    flags.  This might change in future versions if there is some sort of
    support for this kind of hackery in SQLAlchemy or if we find a fast way
    to compare the trees.
    """

    impl = sqlalchemy.Binary

    def process_bind_param(self, value, dialect):
        if value is None:
            return
        from zine.utils.zeml import dump_parser_data, RootElement
        return dump_parser_data(value)

    def process_result_value(self, value, dialect):
        from zine.utils.zeml import load_parser_data
        try:
            return load_parser_data(value)
        except ValueError: # Parser data invalid. Database corruption?
            from zine.i18n import _
            from zine.utils import log
            log.exception(_(u'Error when loading parsed data from database. '
                            u'Maybe the database was manually edited and got '
                            u'corrupted? The system returned an empty value.'))
            return {}

    def copy_value(self, value):
        return deepcopy(value)

    def compare_values(self, x, y):
        return x is y

    def is_mutable(self):
        return False


class Query(orm.Query):
    """Default query class."""

    def lightweight(self, deferred=None, lazy=None):
        """Send a lightweight query which deferes some more expensive
        things such as comment queries or even text and parser data.
        """
        args = map(db.lazyload, lazy or ()) + map(db.defer, deferred or ())
        return self.options(*args)

    def first(self, raise_if_missing=False):
        """Return the first result of this `Query` or None if the result
        doesn't contain any rows.  If `raise_if_missing` is set to `True`
        a `NotFound` exception is raised if no row is found.
        """
        rv = orm.Query.first(self)
        if rv is None and raise_if_missing:
            raise NotFound()
        return rv


session = orm.scoped_session(lambda: orm.create_session(get_engine(),
                             autoflush=True, autocommit=False),
                             local_manager.get_ident)


# configure a declarative base.  This is unused in the code but makes it easier
# for plugins to work with the database.
class ModelBase(object):
    """Internal baseclass for `Model`."""
Model = declarative_base(name='Model', cls=ModelBase, mapper=session.mapper)
ModelBase.query = session.query_property(Query)


#: create a new module for all the database related functions and objects
sys.modules['zine.database.db'] = db = ModuleType('db')
key = value = mod = None
for mod in sqlalchemy, orm:
    for key, value in mod.__dict__.iteritems():
        if key in mod.__all__:
            setattr(db, key, value)
del key, mod, value

#: forward some session methods to the module as well
for name in 'delete', 'save', 'flush', 'execute', 'begin', 'mapper', \
            'commit', 'rollback', 'clear', 'refresh', 'expire', \
            'query_property':
    setattr(db, name, getattr(session, name))

#: and finally hook our own implementations of various objects in
db.Model = Model
db.Query = Query
db.get_engine = get_engine
db.create_engine = create_engine
db.session = session
db.ZEMLParserData = ZEMLParserData
db.mapper = session.mapper
db.association_proxy = association_proxy
db.attribute_loaded = attribute_loaded
db.AttributeExtension = AttributeExtension

#: called at the end of a request
cleanup_session = session.remove

#: metadata for the core tables and the core table definitions
metadata = db.MetaData()


users = db.Table('users', metadata,
    db.Column('user_id', db.Integer, primary_key=True),
    db.Column('username', db.String(30)),
    db.Column('real_name', db.String(180)),
    db.Column('display_name', db.String(180)),
    db.Column('description', db.Text),
    db.Column('extra', db.PickleType),
    db.Column('pw_hash', db.String(70)),
    db.Column('email', db.String(250)),
    db.Column('www', db.String(200)),
    db.Column('is_author', db.Boolean)
)

groups = db.Table('groups', metadata,
    db.Column('group_id', db.Integer, primary_key=True),
    db.Column('name', db.String(30))
)

group_users = db.Table('group_users', metadata,
    db.Column('group_id', db.Integer, db.ForeignKey('groups.group_id')),
    db.Column('user_id', db.Integer, db.ForeignKey('users.user_id'))
)

privileges = db.Table('privileges', metadata,
    db.Column('privilege_id', db.Integer, primary_key=True),
    db.Column('name', db.String(50), unique=True)
)

user_privileges = db.Table('user_privileges', metadata,
    db.Column('user_id', db.Integer, db.ForeignKey('users.user_id')),
    db.Column('privilege_id', db.Integer,
              db.ForeignKey('privileges.privilege_id'))
)

group_privileges = db.Table('group_privileges', metadata,
    db.Column('group_id', db.Integer, db.ForeignKey('groups.group_id')),
    db.Column('privilege_id', db.Integer,
              db.ForeignKey('privileges.privilege_id'))
)

categories = db.Table('categories', metadata,
    db.Column('category_id', db.Integer, primary_key=True),
    db.Column('slug', db.String(50)),
    db.Column('name', db.String(50)),
    db.Column('description', db.Text)
)

texts = db.Table('texts', metadata,
    db.Column('text_id', db.Integer, primary_key=True),
    db.Column('text', db.Text),
    db.Column('parser_data', db.ZEMLParserData),
    db.Column('extra', db.PickleType)
)

posts = db.Table('posts', metadata,
    db.Column('post_id', db.Integer, primary_key=True),
    db.Column('pub_date', db.DateTime),
    db.Column('last_update', db.DateTime),
    db.Column('slug', db.String(200), index=True, nullable=False),
    db.Column('uid', db.String(250)),
    db.Column('title', db.String(150)),
    db.Column('text_id', db.Integer, db.ForeignKey('texts.text_id')),
    db.Column('author_id', db.Integer, db.ForeignKey('users.user_id')),
    db.Column('comments_enabled', db.Boolean),
    db.Column('comment_count', db.Integer, nullable=False, default=0),
    db.Column('pings_enabled', db.Boolean),
    db.Column('content_type', db.String(40), index=True),
    db.Column('status', db.Integer),
)

post_links = db.Table('post_links', metadata,
    db.Column('link_id', db.Integer, primary_key=True),
    db.Column('post_id', db.Integer, db.ForeignKey('posts.post_id')),
    db.Column('href', db.String(250), nullable=False),
    db.Column('rel', db.String(250)),
    db.Column('type', db.String(100)),
    db.Column('hreflang', db.String(30)),
    db.Column('title', db.String(200)),
    db.Column('length', db.Integer)
)

tags = db.Table('tags', metadata,
    db.Column('tag_id', db.Integer, primary_key=True),
    db.Column('slug', db.String(150), unique=True, nullable=False),
    db.Column('name', db.String(100), unique=True, nullable=False)
)

post_categories = db.Table('post_categories', metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('posts.post_id')),
    db.Column('category_id', db.Integer, db.ForeignKey('categories.category_id'))
)

post_tags = db.Table('post_tags', metadata,
    db.Column('post_id', db.Integer, db.ForeignKey('posts.post_id')),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.tag_id'))
)

comments = db.Table('comments', metadata,
    db.Column('comment_id', db.Integer, primary_key=True),
    db.Column('post_id', db.Integer, db.ForeignKey('posts.post_id')),
    db.Column('user_id', db.Integer, db.ForeignKey('users.user_id')),
    db.Column('author', db.String(160)),
    db.Column('email', db.String(250)),
    db.Column('www', db.String(200)),
    db.Column('text_id', db.Integer, db.ForeignKey('texts.text_id')),
    db.Column('is_pingback', db.Boolean, nullable=False),
    db.Column('parent_id', db.Integer, db.ForeignKey('comments.comment_id')),
    db.Column('pub_date', db.DateTime),
    db.Column('blocked_msg', db.String(250)),
    db.Column('submitter_ip', db.String(100)),
    db.Column('status', db.Integer, nullable=False)
)

redirects = db.Table('redirects', metadata,
    db.Column('redirect_id', db.Integer, primary_key=True),
    db.Column('original', db.String(200), unique=True),
    db.Column('new', db.String(200))
)

notification_subscriptions = db.Table('notification_subscriptions', metadata,
    db.Column('subscription_id', db.Integer, primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('users.user_id')),
    db.Column('notification_system', db.String(50)),
    db.Column('notification_id', db.String(100)),
    db.UniqueConstraint('user_id', 'notification_system', 'notification_id')
)


def init_database(engine):
    """This is called from the websetup which explains why it takes an engine
    and not a zine application.
    """
    # XXX: consider using something like this for mysql:
    #   cx = engine.connect()
    #   cx.execute('set storage_engine=innodb')
    #   metadata.create_all(cx)
    metadata.create_all(engine)
