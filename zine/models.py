# -*- coding: utf-8 -*-
"""
    zine.models
    ~~~~~~~~~~~

    The core models and query helper functions.

    :copyright: (c) 2010 by the Zine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from math import log
from datetime import date, datetime, timedelta
from urlparse import urljoin

from werkzeug.exceptions import NotFound

from zine.database import users, categories, posts, post_links, \
     post_categories, post_tags, tags, comments, groups, group_users, \
     privileges, user_privileges, group_privileges, texts, \
     notification_subscriptions, schema_versions, db
from zine.utils import zeml
from zine.utils.text import gen_slug, gen_timestamped_slug, build_tag_uri, \
     increment_string
from zine.utils.pagination import Pagination
from zine.utils.crypto import gen_pwhash, check_pwhash
from zine.utils.http import make_external_url
from zine.privileges import _Privilege, privilege_attribute, \
     add_admin_privilege, MODERATE_COMMENTS, ENTER_ADMIN_PANEL, BLOG_ADMIN, \
     VIEW_DRAFTS, VIEW_PROTECTED, MODERATE_OWN_ENTRIES, MODERATE_OWN_PAGES
from zine.application import get_application, get_request, url_for

from zine.i18n import to_blog_timezone

#: all kind of states for a post
STATUS_DRAFT = 1
STATUS_PUBLISHED = 2
STATUS_PROTECTED = 3
STATUS_PRIVATE = 4

#: Comment Status
COMMENT_MODERATED = 0
COMMENT_UNMODERATED = 1
COMMENT_BLOCKED_USER = 2
COMMENT_BLOCKED_SPAM = 3
COMMENT_BLOCKED_SYSTEM = 4
COMMENT_DELETED = 5

#: moderation modes
MODERATE_NONE = 0
MODERATE_ALL = 1
MODERATE_UNKNOWN = 2


class _ZEMLContainer(object):
    """A mixin for objects that have ZEML markup stored."""

    parser_reason = None

    @property
    def parser_missing(self):
        """If the parser for this post is not available this property will
        be `True`.  If such as post is edited the text area is grayed out
        and tells the user to reinstall the plugin that provides that
        parser.  Because it doesn't know the name of the plugin, the
        preferred was is telling it the parser which is available using
        the `parser` property.
        """
        app = get_application()
        return self.parser not in app.parsers

    def touch_parser_data(self):
        """Mark the parser data as modified."""
        # this is enough for sqlalchemy to pick it up as as change.
        # it will only compare the object's identity.
        self.parser_data = dict(self.parser_data)

    def _get_parser(self):
        if self.parser_data is not None:
            return self.parser_data.get('parser')

    def _set_parser(self, value):
        if self.parser_data is None:
            self.parser_data = {}
        self.parser_data['parser'] = value
        self.touch_parser_data()

    parser = property(_get_parser, _set_parser, doc="The name of the parser.")
    del _get_parser, _set_parser

    @property
    def body(self):
        """The body as ZEML element."""
        if self.parser_data is not None:
            return self.parser_data.get('body')

    def _parse_text(self, text):
        from zine.parsers import parse
        self.parser_data['body'] = parse(text, self.parser, self.parser_reason)

    def _get_text(self):
        return self._text

    def _set_text(self, value):
        if self.parser_data is None:
            self.parser_data = {}
        self._text = value
        self._parse_text(value)
        self.touch_parser_data()

    text = property(_get_text, _set_text, doc="The raw text.")
    del _get_text, _set_text

    def find_urls(self):
        """Iterate over all urls in the text.  This will only work if the
        parser for this post is available, otherwise an exception is raised.
        The URLs returned are absolute URLs.
        """
        from zine.parsers import parse
        if self.parser_missing:
            raise TypeError('parser is missing, urls cannot be looked up.')
        found = set()
        this_url = url_for(self, _external=True)
        tree = parse(self.text, self.parser, 'linksearch')
        for node in tree.query('a[href]'):
            href = urljoin(this_url, node.attributes['href'])
            if href not in found:
                found.add(href)
                yield href


class _ZEMLDualContainer(_ZEMLContainer):
    """Like the ZEML mixin but with intro and body sections."""

    def _parse_text(self, text):
        from zine.parsers import parse
        self.parser_data['intro'], self.parser_data['body'] = \
            zeml.split_intro(parse(text, self.parser, self.parser_reason))

    @property
    def intro(self):
        """The intro as zeml element."""
        if self.parser_data is not None:
            return self.parser_data.get('intro')


class CommentCounterExtension(db.AttributeExtension):
    """A simple attribute extension that helps the post to reflect
    the number of public comments on the post table.

    This will not count or "uncount" blocked or unmoderated comments.
    To fight this problem there is a :meth:`Post.sync_comment_count`
    method that should be called after comment moderation on affected
    comments.
    """

    def append(self, state, value, initiator):
        instance = state.obj()
        if not value.blocked:
            instance._comment_count += 1
        return value

    def remove(self, state, value, initiator):
        instance = state.obj()
        if not value.blocked:
            instance._comment_count -= 1

    def set(self, state, value, oldvalue, initiator):
        return value


class UserQuery(db.Query):
    """Add some extra query methods to the user object."""

    def get_nobody(self):
        return AnonymousUser()

    def authors(self):
        return self.filter_by(is_author=True)


class SchemaVersion(object):
    """Represents a database schema version."""

    query = db.query_property(db.Query)

    def __init__(self, repos, version=0):
        self.repository_id = repos.config.get('repository_id')
        self.repository_path = repos.path
        self.version = version


class User(object):
    """Represents an user.

    If you change something on this model, even default values, keep in mind
    that the websetup does not use this model to create the admin account
    because at that time the Zine system is not yet ready. Also update
    the code in `zine.websetup.WebSetup.start_setup`.
    """

    query = db.query_property(UserQuery)
    is_somebody = True

    def __init__(self, username, password, email, real_name=u'',
                 description=u'', www=u'', is_author=False):
        self.username = username
        if password is not None:
            self.set_password(password)
        else:
            self.disable()
        self.email = email
        self.www = www
        self.real_name = real_name
        self.description = description
        self.extra = {}
        self.display_name = u'$username'
        self.is_author = is_author

    @property
    def is_manager(self):
        return self.has_privilege(ENTER_ADMIN_PANEL)

    @property
    def is_admin(self):
        return self.has_privilege(BLOG_ADMIN)

    def _set_display_name(self, value):
        self._display_name = value

    def _get_display_name(self):
        from string import Template
        return Template(self._display_name).safe_substitute(
            username=self.username,
            real_name=self.real_name
        )

    display_name = property(_get_display_name, _set_display_name)
    own_privileges = privilege_attribute('_own_privileges')

    @property
    def privileges(self):
        """A read-only set with all privileges."""
        result = set(self.own_privileges)
        for group in self.groups:
            result.update(group.privileges)
        return frozenset(result)

    def has_privilege(self, privilege):
        """Check if the user has a given privilege.  If the user has the
        BLOG_ADMIN privilege he automatically has all the other privileges
        as well.
        """
        return add_admin_privilege(privilege)(self.privileges)

    def set_password(self, password):
        self.pw_hash = gen_pwhash(password)

    def check_password(self, password):
        if self.pw_hash == '!':
            return False
        return check_pwhash(self.pw_hash, password)

    def disable(self):
        self.pw_hash = '!'

    @property
    def disabled(self):
        return self.pw_hash == '!'

    def get_url_values(self):
        if self.is_author:
            return 'blog/show_author', {
                'username': self.username
            }
        return self.www or '#'

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.username
        )


class Group(object):
    """Wraps the group table."""

    def __init__(self, name):
        self.name = name

    privileges = privilege_attribute('_privileges')

    def has_privilege(self, privilege):
        return add_admin_privilege(privilege)(self.privileges)

    def get_url_values(self):
        # TODO: a public view is missing!
        return 'admin/edit_group', {'group_id': self.id}

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.name
        )


class AnonymousUser(User):
    """Fake model for anonymous users."""
    id = -1
    is_somebody = is_author = False
    display_name = 'Nobody'
    real_name = description = username = ''
    own_privileges = privileges = property(lambda x: frozenset())

    def __init__(self):
        pass

    def __nonzero__(self):
        return False

    def check_password(self, password):
        return False


class _PostQueryBase(db.Query):
    """Add some extra methods to the post model."""

    def type(self, content_type):
        """Filter all posts by a given type."""
        return self.filter_by(content_type=content_type)

    def for_index(self):
        """Return all the types for the index."""
        types = get_application().cfg['index_content_types']
        if len(types) == 1:
            return self.filter_by(content_type=types[0])
        return self.filter(Post.content_type.in_(types))

    def published(self, ignore_privileges=False, user=None):
        """Return a queryset for only published posts."""
        if not user:
            req = get_request()
            user = req and req.user

        if ignore_privileges or not user:
            # Anonymous. Return only public entries.
            return self.filter(
                (Post.status == STATUS_PUBLISHED) &
                (Post.pub_date <= datetime.utcnow())
            )
        elif not user.has_privilege(VIEW_PROTECTED):
            # Authenticated user without protected viewing privilege
            # Return public and their own private entries
            return self.filter(
                ((Post.status == STATUS_PUBLISHED) |
                 ((Post.status == STATUS_PRIVATE) &
                  (Post.author_id == user.id))) &
                (Post.pub_date <= datetime.utcnow())
            )
        else:
            # Authenticated and can view protected.
            # Return public, protected and their own private
            return self.filter(
                ((Post.status == STATUS_PUBLISHED) |
                 (Post.status == STATUS_PROTECTED) |
                 ((Post.status == STATUS_PRIVATE) &
                  (Post.author_id == user.id))) &
                (Post.pub_date <= datetime.utcnow())
            )

    def drafts(self, ignore_user=False, user=None):
        """Return a query that returns all drafts for the current user.
        or the user provided or no user at all if `ignore_user` is set.
        """
        if user is None and not ignore_user:
            req = get_request()
            if req and req.user:
                user = req.user
        query = self.filter(Post.status == STATUS_DRAFT)
        if user is not None:
            query = query.filter(Post.author_id == user.id)
        return query

    def get_list(self, endpoint=None, page=1, per_page=None,
                 url_args=None, raise_if_empty=True):
        """Return a dict with pagination, the current posts, number of pages,
        total posts and all that stuff for further processing.
        """
        if per_page is None:
            app = get_application()
            per_page = app.cfg['posts_per_page']

        # send the query
        offset = per_page * (page - 1)
        postlist = self.order_by(Post.pub_date.desc()) \
                       .offset(offset).limit(per_page).all()

        # if raising exceptions is wanted, raise it
        if raise_if_empty and (page != 1 and not postlist):
            raise NotFound()

        pagination = Pagination(endpoint, page, per_page,
                                self.count(), url_args)

        return {
            'pagination':       pagination,
            'posts':            postlist
        }

    def get_archive_summary(self, detail='months', limit=None,
                            ignore_privileges=False):
        """Query function to get the archive of the blog. Usually used
        directly from the templates to add some links to the sidebar.
        """
        # XXX: currently we also return months without articles in it.
        # other blog systems do not, but because we use sqlalchemy we have
        # to go with the functionality provided.  Currently there is no way
        # to do date truncating in a database agnostic way.  When this is done
        # ignore_privileges should no longer be a noop
        last = self.filter(Post.pub_date != None) \
                   .order_by(Post.pub_date.asc()).first()
        now = datetime.utcnow()

        there_are_more = False
        result = []

        if last is not None:
            now = date(now.year, now.month, now.day)
            oldest = date(last.pub_date.year, last.pub_date.month,
                          last.pub_date.day)
            result = [now]

            there_are_more = False
            if detail == 'years':
                now, oldest = [x.replace(month=1, day=1) for x in now, oldest]
                while True:
                    now = now.replace(year=now.year - 1)
                    if now < oldest:
                        break
                    result.append(now)
                else:
                    there_are_more = True
            elif detail == 'months':
                now, oldest = [x.replace(day=1) for x in now, oldest]
                while limit is None or len(result) < limit:
                    if not now.month - 1:
                        now = now.replace(year=now.year - 1, month=12)
                    else:
                        now = now.replace(month=now.month - 1)
                    if now < oldest:
                        break
                    result.append(now)
                else:
                    there_are_more = True
            elif detail == 'days':
                while limit is None or len(result) < limit:
                    now = now - timedelta(days=1)
                    if now < oldest:
                        break
                    result.append(now)
                else:
                    there_are_more = True
            else:
                raise ValueError('detail must be years, months, or days')

        return {
            detail:     result,
            'more':     there_are_more,
            'empty':    not result
        }

    def latest(self, ignore_privileges=False):
        """Filter for the latest n posts."""
        return self.published(ignore_privileges=ignore_privileges)

    def date_filter(self, year, month=None, day=None):
        """Filter all the items that match the given date."""
        if month is None:
            return self.filter(
                (Post.pub_date >= datetime(year, 1, 1)) &
                (Post.pub_date < datetime(year + 1, 1, 1))
            )
        elif day is None:
            return self.filter(
                (Post.pub_date >= datetime(year, month, 1)) &
                (Post.pub_date < (month == 12 and
                               datetime(year + 1, 1, 1) or
                               datetime(year, month + 1, 1)))
            )
        return self.filter(
            (Post.pub_date >= datetime(year, month, day)) &
            (Post.pub_date < datetime(year, month, day) +
                             timedelta(days=1))
        )

    def search(self, query):
        """Search for posts by a query."""
        # XXX: use a sophisticated search
        q = self
        for word in query.split():
            q = q.filter(
                posts.c.body.like('%%%s%%' % word) |
                posts.c.intro.like('%%%s%%' % word) |
                posts.c.title.like('%%%s%%' % word)
            )
        return q.all()


class _PostBase(object):
    """Represents one blog post."""

    @property
    def _privileges(self):
        return get_application().content_type_privileges[self.content_type]

    @property
    def EDIT_OWN_PRIVILEGE(self):
        """The edit-own privilege for this content type."""
        return self._privileges[1]

    @property
    def EDIT_OTHER_PRIVILEGE(self):
        """The edit-other privilege for this content type."""
        return self._privileges[2]

    @property
    def root_comments(self):
        """Return only the comments for this post that don't have a parent."""
        return [x for x in self.comments if x.parent is None]

    @property
    def visible_comments(self):
        """Return only the comments for this post that are visible to
        the user.
        """
        return [x for x in self.comments if x.visible]

    @property
    def visible_root_comments(self):
        """Return only the comments for this post that are visible to
        the user and that don't have a parent.
        """
        return [x for x in self.comments if x.visible and x.parent is None]

    @property
    def comment_count(self):
        """The number of visible comments."""
        req = get_request()

        # if the model was loaded with .lightweight() there are no comments
        # but a _comment_count we can use.
        if not db.attribute_loaded(self, 'comments'):
            return self._comment_count

        # otherwise the comments are already available and we can savely
        # filter it.
        if req and req.user.is_manager:
            return len(self.comments)
        return len([x for x in self.comments if not x.blocked])

    @property
    def comment_feed_url(self):
        """The link to the comment feed."""
        return make_external_url(self.slug.rstrip('/') + '/feed.atom')

    @property
    def is_draft(self):
        """True if this post is unpublished."""
        return self.status == STATUS_DRAFT

    def sync_comment_count(self):
        """Sync the reflected comment count."""
        self._comment_count = Comment.query.comments_for_post(self) \
            .filter(Comment.status==0).count()

    def set_auto_slug(self):
        """Generate a slug for this post."""
        #cfg = get_application().cfg
        slug = gen_slug(self.title)
        if not slug:
            slug = to_blog_timezone(self.pub_date).strftime('%H%M')

        full_slug = gen_timestamped_slug(slug, self.content_type, self.pub_date)

        if full_slug != self.slug:
            while Post.query.autoflush(False).filter_by(slug=full_slug) \
                      .limit(1).count():
                full_slug = increment_string(full_slug)
            self.slug = full_slug

    def touch_times(self, pub_date=None):
        """Touches the times for this post.  If the pub_date is given the
        `pub_date` is changed to the given date.  If it's not given the
        current time is assumed if the post status is set to published,
        otherwise it's set to `None`.

        Additionally the `last_update` is always set to now.
        """
        now = datetime.utcnow()
        if pub_date is None and self.status == STATUS_PUBLISHED:
            pub_date = now
        self.pub_date = pub_date
        self.last_update = now

    def bind_slug(self, slug=None):
        """Binds a new slug to the post.  If the slug is `None`/empty a new
        automatically generated slug is created.  Otherwise that slug is
        used and assigned.
        """
        if not slug:
            self.set_auto_slug()
        else:
            self.slug = slug

    def bind_tags(self, tags):
        """Rebinds the tags to a list of tags (strings, not tag objects)."""
        current_map = dict((x.name, x) for x in self.tags)
        currently_attached = set(x.name for x in self.tags)
        new_tags = set(tags)

        # delete outdated tags
        for name in currently_attached.difference(new_tags):
            self.tags.remove(current_map[name])

        # add new tags
        for name in new_tags.difference(currently_attached):
            self.tags.append(Tag.get_or_create(name))

    def bind_categories(self, categories):
        """Rebinds the categories to the list passed.  The list of objects
        must be a list of category objects.
        """
        currently_attached = set(self.categories)
        new_categories = set(categories)

        # delete outdated categories
        for category in currently_attached.difference(new_categories):
            self.categories.remove(category)

        # attach new categories
        for category in new_categories.difference(currently_attached):
            self.categories.append(category)

    def can_edit(self, user=None):
        """Checks if the given user (or current user) can edit this post."""
        if user is None:
            user = get_request().user

        return (
            user.has_privilege(self.EDIT_OTHER_PRIVILEGE) or
            (self.author == user and
             user.has_privilege(self.EDIT_OWN_PRIVILEGE))
        )

    def can_read(self, user=None):
        """Check if the current user or the user provided can read-access
        this post. If there is no user there must be a request object
        for this thread defined.
        """
        # published posts are always accessible
        if self.status == STATUS_PUBLISHED and self.pub_date is not None and \
           self.pub_date <= datetime.utcnow():
            return True

        if user is None:
            user = get_request().user

        # users that are allowed to look at drafts may pass
        if user.has_privilege(VIEW_DRAFTS):
            return True

        # if this is protected and user can view protected, allow them
        if self.status == STATUS_PROTECTED and self.pub_date is not None and \
            self.pub_date <= datetime.utcnow() and \
            user.has_privilege(VIEW_PROTECTED):
             return True

        # if we have the privilege to edit other entries or if we are
        # a blog administrator we can always look at posts.
        if user.has_privilege(self.EDIT_OTHER_PRIVILEGE):
            return True

        # otherwise if the user has the EDIT_OWN_PRIVILEGE and the
        # author of the post, he may look at it as well
        if user.id == self.author_id and \
           user.has_privilege(self.EDIT_OWN_PRIVILEGE):
            return True

        return False

    @property
    def is_published(self):
        """`True` if the post is visible for everyone."""
        return self.can_read(AnonymousUser())

    @property
    def is_private(self):
        """`True` if the post is marked private."""
        return self.status == STATUS_PRIVATE

    @property
    def is_protected(self):
        """`True` if the post is marked protected."""
        return self.status == STATUS_PROTECTED

    @property
    def is_scheduled(self):
        """True if the item is scheduled for appearing."""
        return self.status == STATUS_PUBLISHED and \
               self.pub_date > datetime.utcnow()

    def get_url_values(self):
        return self.slug

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.title
        )


class PostQuery(_PostQueryBase):
    """Add some extra methods to the post model."""

    def theme_lightweight(self, key):
        """A query for lightweight settings based on the theme.  For example
        to use the lightweight settings for the author overview page you can
        use this query::

            Post.query.theme_lightweight('author_overview')
        """
        theme_settings = get_application().theme.settings
        deferred = theme_settings.get('sql.%s.deferred' % key)
        lazy = theme_settings.get('sql.%s.lazy' % key)
        return self.lightweight(deferred, lazy)


class SummarizedPostQuery(_PostQueryBase):
    """Add some extra methods to the summarized post model."""


class Post(_PostBase, _ZEMLDualContainer):
    """A full blown post."""

    query = db.query_property(PostQuery)
    parser_reason = 'post'

    def __init__(self, title, author, text, slug=None, pub_date=None,
                 last_update=None, comments_enabled=True,
                 pings_enabled=True, status=STATUS_PUBLISHED,
                 parser=None, uid=None, content_type='entry', extra=None):
        app = get_application()
        self.content_type = content_type
        self.title = title
        self.author = author
        if parser is None:
            parser = app.cfg['default_parser']

        self.parser = parser
        self.text = text or u''
        if extra:
            self.extra = dict(extra)
        else:
            self.extra = {}

        self.comments_enabled = comments_enabled
        self.pings_enabled = pings_enabled
        self.status = status

        # set times now, they depend on status being set
        self.touch_times(pub_date)
        if last_update is not None:
            self.last_update = last_update

        # now bind the slug for which we need the times set.
        self.bind_slug(slug)

        # generate a UID if none is given
        if uid is None:
            uid = build_tag_uri(app, self.pub_date, content_type, self.slug)
        self.uid = uid


class SummarizedPost(_PostBase):
    """Like a regular post but without text and parser data."""

    query = db.query_property(SummarizedPostQuery)

    def __init__(self):
        raise TypeError('You cannot create %r instance' % type(self).__name__)


class PostLink(object):
    """Represents a link in a post.  This can be used for podcasts or other
    resources that require ``<link>`` categories.
    """

    def __init__(self, post, href, rel='alternate', type=None, hreflang=None,
                 title=None, length=None):
        self.post = post
        self.href = href
        self.rel = rel
        self.type = type
        self.hreflang = hreflang
        self.title = title
        self.length = length

    def as_dict(self):
        """Return the values as dict.  Useful for feed building."""
        result = {'href': self.href}
        for key in 'rel', 'type', 'hreflang', 'title', 'length':
            value = getattr(self, key, None)
            if value is not None:
                result[key] = value
        return result

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.href
        )


class CategoryQuery(db.Query):
    """Also categories have their own manager."""

    def get_or_create(self, slug, name=None):
        """Get the category for this slug or create it if it does not exist."""
        category = self.filter_by(slug=slug).first()
        if category is None:
            if name is None:
                name = slug
            category = Category(name, slug=slug)
        return category


class Category(object):
    """Represents a category."""

    query = db.query_property(CategoryQuery)

    def __init__(self, name, description='', slug=None):
        self.name = name
        if slug is None:
            self.set_auto_slug()
        else:
            self.slug = slug
        self.description = description

    def set_auto_slug(self):
        """Generate a slug for this category."""
        full_slug = gen_slug(self.name)
        if not full_slug:
            # if slug generation failed we select the highest category
            # id as base for slug generation.
            category = Category.query.autoflush(False) \
                               .order_by(Category.id.desc()).first()
            full_slug = unicode(category and category.id or u'1')
        if full_slug != self.slug:
            while Category.query.autoflush(False) \
                          .filter_by(slug=full_slug).limit(1).count():
                full_slug = increment_string(full_slug)
            self.slug = full_slug

    def get_url_values(self):
        return 'blog/show_category', {
            'slug':     self.slug
        }

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.name
        )


class CommentQuery(db.Query):
    """The manager for comments"""

    def post_lightweight(self):
        """Lightweight query that sets loading options for a light post
        (not text etc.)
        """
        return self.lightweight(deferred=('post.text', 'post.parser_data',
                                          'post.extra'), lazy=('user',))

    def approved(self):
        """Return only the approved comments."""
        return self.filter(Comment.status == COMMENT_MODERATED)

    def all_blocked(self):
        """Return all blocked comments, by user, by spam checker or by system.
        """
        return self.filter(Comment.status.in_([COMMENT_BLOCKED_USER,
                                               COMMENT_BLOCKED_SPAM,
                                               COMMENT_BLOCKED_SYSTEM]))

    def blocked(self):
        """Filter all comments blocked by user(s)
        """
        return self.filter(Comment.status == COMMENT_BLOCKED_USER)

    def unmoderated(self):
        """Filter all the unmoderated comments and comments blocked by a user
        or system.
        """
        return self.filter(Comment.status == COMMENT_UNMODERATED)

    def spam(self):
        """Filter all the spam comments."""
        return self.filter(Comment.status == COMMENT_BLOCKED_SPAM)

    def system(self):
        """Filter all the spam comments."""
        return self.filter(Comment.status == COMMENT_BLOCKED_SYSTEM)

    def latest(self, limit=None, ignore_privileges=False, ignore_blocked=True):
        """Filter the list of non blocked comments for anonymous users or
        all comments for admin users.
        """
        query = self

        # only the approved if blocked are ignored
        if ignore_blocked:
            query = query.approved()

        # otherwise if we don't ignore the privileges we only want
        # the approved if the user does not have the MODERATE_COMMENTS
        # privileges.
        elif not ignore_privileges:
            req = get_request()
            if req:
                user = req.user
                if not user.has_privilege(MODERATE_COMMENTS |
                                          MODERATE_OWN_ENTRIES |
                                          MODERATE_OWN_PAGES):
                    query = query.approved()

                elif user.has_privilege(MODERATE_OWN_ENTRIES |
                                        MODERATE_OWN_PAGES):
                    query = query.for_user(user)

        return query

    def for_user(self, user=None):
        request = get_request()
        user = user or request.user
        if user.has_privilege(MODERATE_COMMENTS):
            return self
        elif user.has_privilege(MODERATE_OWN_ENTRIES | MODERATE_OWN_PAGES):
            return self.filter(Comment.post_id.in_(
                db.session.query(Post.id).filter(Post.author_id==user.id))
            )
        return self


    def comments_for_post(self, post):
        """Return all comments for the blog post."""
        return self.filter(Comment.post_id == post.id)


class Comment(_ZEMLContainer):
    """Represent one comment."""

    query = db.query_property(CommentQuery)
    parser_reason = 'comment'

    def __init__(self, post, author, text, email=None, www=None, parent=None,
                 pub_date=None, submitter_ip='0.0.0.0', parser=None,
                 is_pingback=False, status=COMMENT_MODERATED):
        self.post = post
        if isinstance(author, basestring):
            self.user = None
            self._author = author
            self._email = email
            self._www = www
        else:
            assert email is www is None, \
                'email and www can only be provided if the author is ' \
                'an anonymous user'
            self.user = author

        if parser is None:
            parser = get_application().cfg['comment_parser']
        self.parser = parser
        self.text = text or ''
        self.parent = parent
        if pub_date is None:
            pub_date = datetime.utcnow()
        self.pub_date = pub_date
        self.blocked_msg = None
        self.submitter_ip = submitter_ip
        self.is_pingback = is_pingback
        self.status = status

    def _union_property(attribute, user_attribute=None):
        """An attribute that can exist on a user and the comment."""
        user_attribute = user_attribute or attribute
        attribute = '_' + attribute
        def get(self):
            if self.user:
                return getattr(self.user, user_attribute)
            return getattr(self, attribute)
        def set(self, value):
            if self.user:
                raise TypeError('can\'t set this attribute if the comment '
                                'does not belong to an anonymous user')
            setattr(self, attribute, value)
        return property(get, set)

    email = _union_property('email')
    www = _union_property('www')
    author = _union_property('author', 'display_name')
    del _union_property

    def unbind_user(self):
        """If a user is deleted, the cascading rules would also delete all
        the comments created by this user, or cause a transaction error
        because the relation is set to restrict, depending on the current
        phase of the moon (this changed a lot in the past, i expect it to
        continue to change).

        This method unsets the user and updates the comment builtin columns
        to the values from the user object.
        """
        assert self.user is not None
        self._email= self.user.email
        self._www = self.user.www
        self._author = self.user.display_name
        self.user = None

    def _get_status(self):
        return self._status

    def _set_status(self, value):
        was_blocked = self.blocked
        self._status = value
        now_blocked = self.blocked

        # update the comment count on the post if the moderation flag
        # changed from blocked to unblocked or vice versa
        if was_blocked != now_blocked:
            self.post._comment_count = (self.post._comment_count or 0) + \
                                       (now_blocked and -1 or +1)

    status = property(_get_status, _set_status)
    del _get_status, _set_status

    @property
    def anonymous(self):
        """True if this comment is an anonymous comment."""
        return self.user is None

    @property
    def requires_moderation(self):
        """This is `True` if the comment requires moderation with the
        current moderation settings.  This does not check if the comment
        is already moderated.
        """
        if not self.anonymous:
            return False
        moderate = get_application().cfg['moderate_comments']
        if moderate == MODERATE_ALL:
            return True
        elif moderate == MODERATE_NONE:
            return False
        return db.execute(comments.select(
            (comments.c.author == self._author) &
            (comments.c.email == self._email) &
            (comments.c.status == COMMENT_MODERATED)
        )).fetchone() is None

    def make_visible_for_request(self, request=None):
        """Make the comment visible for the current request."""
        if request is None:
            request = get_request()
        comments = set(request.session.get('visible_comments', ()))
        comments.add(self.id)
        request.session['visible_comments'] = tuple(comments)

    def visible_for_user(self, user=None):
        """Check if the current user or the user given can see this comment"""
        request = get_request()
        if user is None:
            user = request.user
        if self.post.author is user and \
           user.has_privilege(MODERATE_OWN_ENTRIES | MODERATE_OWN_PAGES):
            return True
        elif user.has_privilege(MODERATE_COMMENTS):
            # User is able to manage comments. It's visible.
            return True
        elif self.id in request.session.get('visible_comments', ()):
            # Comment was made visible for current request. It's visible
            return True
        # Finally, comment is visible if not blocked
        return not self.blocked

    @property
    def visible(self):
        """Check the current session it can see the comment or check against the
        current user.  To display a comment for a request you can use the
        `make_visible_for_request` function.  This is useful to show a comment
        to a user that submitted a comment which is not yet moderated.
        """
        request = get_request()
        if request is None:
            return True
        return self.visible_for_user(request.user)

    @property
    def visible_children(self):
        """Only the children that are visible for the current user."""
        return [x for x in self.children if x.visible]

    @property
    def blocked(self):
        """This is true if the status is anything but moderated."""
        return self.status != COMMENT_MODERATED

    @property
    def is_spam(self):
        """This is true if the comment is currently flagged as spam."""
        return self.status == COMMENT_BLOCKED_SPAM

    @property
    def is_unmoderated(self):
        """True if the comment is not yet approved."""
        return self.status == COMMENT_UNMODERATED

    @property
    def is_deleted(self):
        """True if the comment has been deleted."""
        return self.status == COMMENT_DELETED

    def get_url_values(self):
        return url_for(self.post) + '#comment-%d' % self.id

    def summarize(self, chars=140, ellipsis=u'…'):
        """Summarizes the comment to the given number of characters."""
        words = self.body.to_text(simple=True).split()
        words.reverse()
        length = 0
        result = []
        while words:
            word = words.pop()
            length += len(word) + 1
            if length >= chars:
                break
            result.append(word)
        if words:
            result.append(ellipsis)
        return u' '.join(result)

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            self.author
        )


class TagQuery(db.Query):

    def get_cloud(self, max=None, ignore_privileges=False):
        """Get a categorycloud."""
        # XXX: ignore_privileges is currently ignored and no privilege
        # checking is performed.  As a matter of fact only published posts
        # appear in the cloud.

        # get a query
        pt = post_tags.c
        p = posts.c
        t = tags.c

        q = ((pt.tag_id == t.tag_id) &
             (pt.post_id == p.post_id) &
             (p.status == STATUS_PUBLISHED) &
             (p.pub_date <= datetime.utcnow()))

        s = db.select(
            [t.tag_id, t.slug, t.name,
             db.func.count(p.post_id).label('s_count')],
            q, group_by=[t.slug, t.name, t.tag_id]).alias('post_count_query').c

        options = {'order_by': [db.asc(s.s_count)]}
        if max is not None:
            options['limit'] = max

        # the label statement circumvents a bug for sqlite3 on windows
        # see #65
        q = db.select([s.tag_id, s.slug, s.name, s.s_count.label('s_count')],
                      **options)

        items = [{
            'id':       row.tag_id,
            'slug':     row.slug,
            'name':     row.name,
            'count':    row.s_count,
            'size':     100 + log(row.s_count or 1) * 20
        } for row in db.execute(q)]

        items.sort(key=lambda x: x['name'].lower())
        return items


class Tag(object):
    """A single tag."""
    query = db.query_property(TagQuery)

    def __init__(self, name, slug=None):
        self.name = name
        if slug is None:
            self.set_auto_slug()
        else:
            self.slug = slug

    @staticmethod
    def get_or_create(name):
        tag = Tag.query.filter_by(name=name).first()
        if tag is not None:
            return tag
        return Tag(name)

    def set_auto_slug(self):
        full_slug = gen_slug(self.name)
        if not full_slug:
            # if slug generation failed we select the highest category
            # id as base for slug generation.
            tag = Tag.query.autoflush(False).order_by(Tag.id.desc()).first()
            full_slug = unicode(tag and tag.id or u'1')
        if full_slug != self.slug:
            while Tag.query.autoflush(False) \
                          .filter_by(slug=full_slug).limit(1).count():
                full_slug = increment_string(full_slug)
            self.slug = full_slug

    def get_url_values(self):
        return 'blog/show_tag', {'slug': self.slug}

    def __repr__(self):
        return u'<%s %r>' % (
            self.__class__.__name__,
            self.name
        )


class NotificationSubscription(object):
    """NotificationSubscriptions are part of the notification system.
    An `NotificationSubscription` object expresses that the user the interest
    belongs to _is interested in_ the occurrence of a certain kind of event.
    That data is then used to inform the user once such an interesting event
    occurs. The NotificationSubscription also knows via what notification
    system the user wants to be notified.
    """

    def __init__(self, user, notification_system, notification_id):
        self.user = user
        self.notification_system = notification_system
        self.notification_id = notification_id

    def __repr__(self):
        return "<%s (%s, %r, %r)>" % (
            self.__class__.__name__,
            self.user,
            self.notification_system,
            self.notification_id
        )


# connect the tables.
db.mapper(SchemaVersion, schema_versions)
db.mapper(User, users, properties={
    'id':               users.c.user_id,
    'display_name':     db.synonym('_display_name', map_column=True),
    'posts':            db.dynamic_loader(Post,
                                          backref=db.backref('author', lazy=True),
                                          query_class=PostQuery,
                                          cascade='all, delete, delete-orphan'),
    'comments':         db.dynamic_loader(Comment,
                                          backref=db.backref('user', lazy=False),
                                          cascade='all, delete'),
    '_own_privileges':  db.relation(_Privilege, lazy=True,
                                    secondary=user_privileges,
                                    collection_class=set,
                                    cascade='all, delete')
})
db.mapper(Group, groups, properties={
    'id':               groups.c.group_id,
    'users':            db.dynamic_loader(User, backref=db.backref('groups', lazy=True),
                                          query_class=UserQuery,
                                          secondary=group_users),
    '_privileges':      db.relation(_Privilege, lazy=True,
                                    secondary=group_privileges,
                                    collection_class=set,
                                    cascade='all, delete')
})
db.mapper(_Privilege, privileges, properties={
    'id':               privileges.c.privilege_id,
})
db.mapper(Category, categories, properties={
    'id':               categories.c.category_id,
    'posts':            db.dynamic_loader(Post, secondary=post_categories,
                                          query_class=PostQuery)
}, order_by=categories.c.name)
db.mapper(Comment, db.join(comments, texts), properties={
    'id':           comments.c.comment_id,
    'text_id':      [comments.c.text_id, texts.c.text_id],
    '_text':        texts.c.text,
    'text':         db.synonym('_text'),
    '_author':      comments.c.author,
    'author':       db.synonym('_author'),
    '_email':       comments.c.email,
    'email':        db.synonym('_email'),
    '_www':         comments.c.www,
    'www':          db.synonym('_www'),
    '_status':      comments.c.status,
    'status':       db.synonym('_status'),
    'children':     db.relation(Comment,
        primaryjoin=comments.c.parent_id == comments.c.comment_id,
        order_by=[db.asc(comments.c.pub_date)],
        backref=db.backref('parent', remote_side=[comments.c.comment_id],
                           primaryjoin=comments.c.parent_id ==
                                comments.c.comment_id),
        lazy=True
    )
}, order_by=comments.c.pub_date.desc(), primary_key=[comments.c.comment_id])
db.mapper(PostLink, post_links, properties={
    'id':           post_links.c.link_id,
})
db.mapper(Tag, tags, properties={
    'id':           tags.c.tag_id,
    'posts':        db.dynamic_loader(Post, secondary=post_tags,
                                      query_class=PostQuery)
}, order_by=tags.c.name)
db.mapper(Post, db.join(posts, texts), properties={
    'id':               posts.c.post_id,
    'text_id':          [posts.c.text_id, texts.c.text_id],
    '_text':            texts.c.text,
    'text':             db.synonym('_text'),
    'comments':         db.relation(Comment, backref=db.backref('post', lazy=True),
                                    primaryjoin=posts.c.post_id ==
                                        comments.c.post_id,
                                    order_by=[db.asc(comments.c.pub_date)],
                                    lazy=False,
                                    cascade='all, delete, delete-orphan',
                                    extension=CommentCounterExtension()),
    'links':            db.relation(PostLink, backref='post',
                                    cascade='all, delete, delete-orphan'),
    'categories':       db.relation(Category, secondary=post_categories, lazy=False,
                                    order_by=[db.asc(categories.c.name)]),
    'tags':             db.relation(Tag, secondary=post_tags, lazy=False,
                                    order_by=[tags.c.name]),
    '_comment_count':   posts.c.comment_count,
    'comment_count':    db.synonym('_comment_count')
}, order_by=posts.c.pub_date.desc(), primary_key=[posts.c.post_id])
db.mapper(SummarizedPost, posts, properties={
    'id':               posts.c.post_id,
    'comments':         db.relation(Comment,
                                    primaryjoin=posts.c.post_id ==
                                        comments.c.post_id,
                                    order_by=[db.asc(comments.c.pub_date)],
                                    lazy=True, viewonly=True),
    'links':            db.relation(PostLink, viewonly=True, lazy=True),
    'categories':       db.relation(Category, secondary=post_categories, lazy=True,
                                    order_by=[db.asc(categories.c.name)],
                                    viewonly=True),
    'tags':             db.relation(Tag, secondary=post_tags, lazy=True,
                                    viewonly=True, order_by=[tags.c.name]),
    'comment_count':    db.synonym('_comment_count', map_column=True)
}, order_by=posts.c.pub_date.desc())
db.mapper(NotificationSubscription, notification_subscriptions, properties={
    'id':               notification_subscriptions.c.subscription_id,
    'user':             db.relation(User, uselist=False, lazy=False,
                            backref=db.backref('notification_subscriptions',
                                               lazy='dynamic'
                            )
                        )
})
