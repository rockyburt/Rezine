# -*- coding: utf-8 -*-
"""
    zine.plugins.legacy_api
    ~~~~~~~~~~~~~~~~~~~~~~~

    This plugin adds support for various legacy APIs.  Currently the
    following APIs are at least partially supported:

    - WordPress
    - MetaWeblog
    - Blogger

    :copyright: (c) 2009 by the Zine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from zine.api import get_request, url_for, db
from zine.utils.xml import XMLRPC, Fault
from zine.models import User, Post, Category, STATUS_PUBLISHED, STATUS_DRAFT
from zine.privileges import CREATE_ENTRIES, CREATE_PAGES, BLOG_ADMIN, \
     MANAGE_CATEGORIES

from werkzeug import escape


def login(username, password):
    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        raise Fault(403, 'Bad login/pass combination.')
    if not user.is_manager:
        raise Fault(403, 'You need to be a manager in order to '
                    'use the blog RPC API')

    # store the user on the request object so that the functions
    # inside Zine work on the request of this user.
    request = get_request()
    request.user = user
    return request


def dump_post(post):
    """Dumps a post into a structure for the MetaWeblog API."""
    text = post.body.to_html()
    if post.intro:
        text = u'<div class="intro">%s</div>%s' % (post.intro.to_html(), text)
    link = url_for(post, _external=True)
    return dict(
        pubDate=post.pub_date,
        dateCreated=post.pub_date,
        userid=post.author.id,
        page_id=post.id,
        title=post.title,
        link=link,
        permaLink=link,
        description=text,
        author=post.author.email,
        categories=[x.name for x in post.categories],
        postid=post.id,
        page_status=post.status == STATUS_PUBLISHED and "published" or "draft",
        excerpt=post.intro.to_html(),
        text_more=post.body.to_html(),
        mt_keywords=[x.name for x in post.tags],
        mt_allow_comments=post.comments_enabled,
        mt_allow_pings=post.pings_enabled,
        wp_slug=post.slug,
        wp_password="",
        wp_author=post.author.display_name,
        wp_author_id=post.author.id,
        wp_author_display_name=post.author.display_name,
        date_created_gmt=post.pub_date,
        wp_page_template=post.extra.get('page_template')
    )


def dump_category(category):
    return dict(
        categoryId=category.id,
        description=category.name,
        categoryDescription=category.description,
        categoryName=category.name,
        # don't ask me... WordPress is doing that...
        htmlUrl=escape(url_for(category)),
        rssUrl=escape(url_for('blog/atom_feed', category=category.slug))
    )


def extract_text(struct):
    """Extracts the text information from a post struct."""
    text = struct.get('description', '')
    excerpt = struct.get('post_excerpt')
    if excerpt:
        text = u'<intro>%s</intro>\n%s' % (excerpt, text)
    return text


def select_parser(app, struct, default='html'):
    """Selects the parser from a struct.  If the parser was not found
    on the system, an XMLRPC fault is raised with an appropriate error
    message and code.
    """
    parser = struct.get('parser')
    if parser is None:
        return default
    if parser not in app.parsers:
        raise Fault(500, 'unknown parser')
    return parser


def generic_update(request, post, struct, publish):
    # if we got keywords provided, we put them on the post.
    # if an empty list came by, we remove them too, but if the
    # key is used for something that is not an array, we ignore it.
    keywords = struct.get('mt_keywords')
    if isinstance(keywords, list):
        post.bind_tags(keywords)

    if publish:
        post.status = STATUS_PUBLISHED
    else:
        post.status = STATUS_DRAFT

    if 'mt_allow_pings' in struct:
        post.pings_enabled = bool(struct['mt_allow_pings'])
    if 'mt_allow_comments' in struct:
        post.comments_enabled = bool(struct['mt_allow_comments'])


def generic_new_post(request, struct, publish, content_type):
    """Generic helper to create a new entry or page."""
    text = extract_text(struct)
    post = Post(struct['title'], request.user, text,
                parser=select_parser(request.app, struct),
                content_type=content_type)
    generic_update(request, post, struct, publish)
    return post


def generic_edit_post(request, post, struct, publish):
    """Generic helper to edit an entry or page."""
    post.parser = select_parser(request.app, struct)
    post.title = struct['title']
    post.text = extract_text(struct)
    generic_update(request, post, struct, publish)


def metaweblog_new_post(blog_id, username, password, struct, publish):
    request = login(username, password)
    if not request.user.has_privilege(CREATE_ENTRIES):
        raise Fault(403, 'you don\'t have the privileges to '
                    'create new posts')
    post = generic_new_post(request, struct, publish, 'entry')
    db.commit()
    return dump_post(post)


def metaweblog_edit_post(post_id, username, password, struct, publish):
    request = login(username, password)
    post = Post.query.get(post_id)
    if post is None:
        raise Fault(404, 'No such post')
    if not post.can_edit():
        raise Failt(403, 'missing privileges')
    generic_edit_post(request, post, struct, publish)
    db.commit()
    return dump_post(post)


def metaweblog_get_post(post_id, username, password):
    request = login(username, password)
    post = Post.query.get(post_id)
    if post is None or post.content_type != 'entry':
        raise Fault(404, 'No such post')
    if not post.can_read():
        raise Fault(403, 'You don\'t have access to this post')
    return dump_post(post)


def metaweblog_get_recent_posts(blog_id, username, password, number_of_posts):
    request = login(username, password)
    number_of_posts = min(50, number_of_posts)
    return map(dump_post, Post.query.filter_by(content_type='entry')
               .limit(number_of_posts).all())


def metaweblog_get_categories(blog_id, username, password):
    request = login(username, password)
    return map(dump_category, Category.query.all())


def blogger_delete_post(post_id, username, password, publish):
    request = login(username, password)
    entry = Post.query.get(post_id)
    if entry is None or entry.content_type != 'post':
        raise Fault(404, 'No such post')
    db.delete(entry)
    db.commit()
    return True


def blogger_get_users_blogs(username, password):
    request = login(username, password)
    return [{'isAdmin': request.user.has_privilege(BLOG_ADMIN),
             'url': request.app.cfg['blog_url'],
             'blogid': 1,
             'blogName': request.app.cfg['blog_title'],
             'xmlrpc': url_for("services/WordPress", _external=True)}]


def wp_get_page(blog_id, page_id, username, password):
    request = login(username, password)
    post = Post.query.get(page_id)
    if post is None or post.content_type != 'page':
        raise Fault(404, 'No such page')
    if not post.can_read():
        raise Fault(403, 'You don\'t have access to this page')
    return dump_post(post)


def wp_get_pages(blog_id, username, password, number_of_pages):
    request = login(username, password)
    return map(dump_post, Post.query.filter_by(content_type='page')
               .limit(numer_of_pages).all())


def wp_new_page(username, password, struct, publish):
    request = login(username, password)
    if not request.user.has_privilege(CREATE_PAGES):
        raise Fault(403, 'you don\'t have the privileges to '
                    'create new pages')
    post = generic_new_post(request, struct, publish, 'post')
    db.commit()
    return dump_post(post)


def wp_edit_page(blog_id, page_id, username, password, content, publish):
    request = login(username, password)
    page = Post.query.get(page_id)
    if not page or page.content_type != 'page':
        raise Fault(404, 'no such page')
    if not page.can_edit():
        raise Fault(403, 'you don\'t have access to this page')
    generic_edit_post(request, page, struct, publish)
    db.commit()
    return dump_post(post)


def wp_delete_page(blog_id, username, password, page_id):
    request = login(username, password)
    page = Page.query.get(page_id)
    if page is None or page.content_type != 'page':
        raise Fault(404, 'no such page')
    if not page.can_edit():
        raise Fault(403, 'you don\'t have privilegs to this post')
    db.delete(page)
    db.commit()
    return True


def wp_get_page_list(blog_id, username, password):
    request = login(username, password)
    return map(dump_page, Page.query.filter_by(content_type='page').all())


def wp_new_category(blog_id, username, password, struct):
    request = login(username, password)
    if not request.user.has_privilege(MANAGE_CATEGORIES):
        raise Fault(403, 'you are not allowed to manage categories')
    category = Category(struct['name'], struct.get('description', u''),
                        slug=struct.get('slug') or None)
    db.commit()
    return category.id


def wp_delete_category(blog_id, username, password, category_id):
    request = login(username, password)
    if not request.user.has_privilege(MANAGE_CATEGORIES):
        raise Fault(403, 'you are not allowed to manage categories')
    category = Category.query.get(category_id)
    if category is None:
        raise Fault(404, 'no such category')
    db.delete(category)
    db.commit()
    return category.id


def mt_get_post_categories(post_id, username, password):
    request = login(username, password)
    post = Post.query.get(post_id)
    if post is None or post.content_type != 'entry':
        raise Fault(404, 'no such post')
    if not post.can_read():
        raise Fault(403, 'you don\'t have privilegs to this post')
    return map(dump_category, post.categories)


def mt_set_post_categories(post_id, username, password, categories):
    request = login(username, password)
    post = Post.query.get(post_id)
    if post is None or post.content_type != 'entry':
        raise Fault(404, 'no such post')
    if not post.can_edit():
        raise Fault(403, 'you don\'t have privilegs to this post')
    ids = []
    names = []
    for category in categories:
        if 'categoryId' in category:
            ids.append(category['categoryId'])
        elif 'categoryName' in category:
            names.append(category['categoryName'])
    post.bind_categories(Category.query.filter(
        Category.id.in_(ids) |
        Category.name.in_(names)
    ).all())
    db.commit()
    return True


service = XMLRPC('legacy_apis')

# MetaWeblog
service.register_functions([
    (metaweblog_new_post, 'metaWeblog.newPost'),
    (metaweblog_edit_post, 'metaWeblog.editPost'),
    (metaweblog_get_post, 'metaWeblog.getPost'),
    (metaweblog_get_recent_posts, 'metaWeblog.getRecentPosts'),
    (metaweblog_get_categories, 'metaWeblog.getCategories')
])

# Blogger
service.register_functions([
    (blogger_delete_post, 'blogger.deletePost'),
    (blogger_get_users_blogs, 'blogger.getUsersBlogs')
])

# MetaWeblog Blogger-Aliases
service.register_functions([
    (blogger_delete_post, 'metaWeblog.deletePost')
])

# WordPress
service.register_functions([
    (blogger_get_users_blogs, 'wp.getUsersBlogs'),
    (wp_get_page, 'wp.getPage'),
    (wp_get_pages, 'wp.getPages'),
    (wp_new_page, 'wp.newPage'),
    (wp_edit_page, 'wp.editPage'),
    (wp_delete_page, 'wp.deletePage'),
    (wp_get_page_list, 'wp.getPageList'),
    (wp_new_category, 'wp.newCategory'),
    (wp_delete_category, 'wp.deleteCategory')
])

# MovableType
service.register_functions([
    (mt_get_post_categories, 'mt.getPostCategories'),
    (mt_set_post_categories, 'mt.setPostCategories')
])


def setup(app, plugin):
    # The WordPress API is marked as preferred even though we do not
    # preferr the API at all.  However if it's marked as preferred, so
    # that clients think we're a wordpress blog.  The WordPress API
    # despite being ugly and stupid is the one that seems to support
    # most of what we do too.
    #
    # All the services are available on one service.  For applications
    # that follow our RSD definition that's okay, they will go to the
    # correct endpoint, but some crappy software will try to call meta-
    # weblog functions on the wordpress endpoint and vice versa which
    # is why they internally point to the same service.
    app.add_api('MetaWeblog', False, service)
    app.add_api('WordPress', True, service)
    app.add_api('Blogger', False, service)
