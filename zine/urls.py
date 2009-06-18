# -*- coding: utf-8 -*-
"""
    zine.urls
    ~~~~~~~~~

    This module implements a function that creates a list of urls for all
    the core components.

    :copyright: (c) 2009 by the Zine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from werkzeug.routing import Rule, Submount

def make_urls(app):
    """Make the URLs for a new zine application."""
    blog_urls = [
        Rule('/', defaults={'page': 1}, endpoint='blog/index'),
        Rule('/feed.atom', endpoint='blog/atom_feed'),
        Rule('/page/<int:page>', endpoint='blog/index'),
        Rule('/archive', endpoint='blog/archive'),
        Submount(app.cfg['profiles_url_prefix'], [
            Rule('/', endpoint='blog/authors'),
            Rule('/<string:username>', defaults={'page': 1}, endpoint='blog/show_author'),
            Rule('/<string:username>/page/<int:page>', endpoint='blog/show_author'),
            Rule('/<string:author>/feed.atom', endpoint='blog/atom_feed'),
        ]),
        Submount(app.cfg['category_url_prefix'], [
            Rule('/<string:slug>', defaults={'page': 1}, endpoint='blog/show_category'),
            Rule('/<string:slug>/page/<int:page>', endpoint='blog/show_category'),
            Rule('/<string:category>/feed.atom', endpoint='blog/atom_feed')
        ]),
        Submount(app.cfg['tags_url_prefix'], [
            Rule('/', endpoint='blog/tags'),
            Rule('/<string:slug>', defaults={'page': 1}, endpoint='blog/show_tag'),
            Rule('/<string:slug>/page/<int:page>', endpoint='blog/show_tag'),
            Rule('/<string:tag>/feed.atom', endpoint='blog/atom_feed')
        ]),
        Submount(app.cfg['account_url_prefix'], [
            Rule('/', endpoint='account/index'),
            Rule('/login', endpoint='account/login'),
            Rule('/logout', endpoint='account/logout'),
            Rule('/delete', endpoint='account/delete'),
            Rule('/profile', endpoint='account/profile'),
            Rule('/system/about', endpoint='account/about_zine'),
            Rule('/system/help/', endpoint='account/help'),
            Rule('/system/help/<path:page>', endpoint='account/help'),
        ])
    ]
    admin_urls = [
        Rule('/', endpoint='admin/index'),
        Rule('/login', endpoint='admin/login', redirect_to='account/login'),    # XXX: Remove on Zine 0.3
        Rule('/logout', endpoint='admin/logout', redirect_to='account/logout'), # XXX: Remove on Zine 0.3
        Rule('/_bookmarklet', endpoint='admin/bookmarklet'),
        Rule('/entries/', endpoint='admin/manage_entries', defaults={'page': 1}),
        Rule('/entries/page/<int:page>', endpoint='admin/manage_entries'),
        Rule('/entries/new', endpoint='admin/new_entry'),
        Rule('/pages/', endpoint='admin/manage_pages', defaults={'page': 1}),
        Rule('/pages/page/<int:page>', endpoint='admin/manage_pages'),
        Rule('/pages/new', endpoint='admin/new_page'),
        Rule('/p/<int:post_id>', endpoint='admin/edit_post'),
        Rule('/p/<int:post_id>/delete', endpoint='admin/delete_post'),
        Rule('/p/<int:post_id>/comments', defaults={'page': 1, 'per_page': 20},
             endpoint='admin/show_post_comments'),
        Rule('/p/<int:post_id>/comments/page/<int:page>/per-page/<int:per_page>',
             endpoint='admin/show_post_comments'),
        Rule('/comments/', endpoint='admin/manage_comments',
             defaults={'page': 1, 'per_page': 20}),
        Rule('/comments/page/<int:page>/per-page/<int:per_page>',
             endpoint='admin/manage_comments'),
        Rule('/comments/unmoderated', defaults={'page': 1, 'per_page': 20},
             endpoint='admin/show_unmoderated_comments'),
        Rule('/comments/unmoderated/page/<int:page>/per-page/<int:per_page>',
             endpoint='admin/show_unmoderated_comments'),
        Rule('/comments/approved', defaults={'page': 1, 'per_page': 20},
             endpoint='admin/show_approved_comments'),
        Rule('/comments/approved/page/<int:page>/per-page/<int:per_page>',
             endpoint='admin/show_approved_comments'),
        Rule('/comments/blocked', defaults={'page': 1, 'per_page': 20},
             endpoint='admin/show_blocked_comments'),
        Rule('/comments/blocked/page/<int:page>/per-page/<int:per_page>',
             endpoint='admin/show_blocked_comments'),
        Rule('/comments/spam', defaults={'page': 1, 'per_page': 20},
             endpoint='admin/show_spam_comments'),
        Rule('/comments/spam/page/<int:page>/per-page/<int:per_page>',
             endpoint='admin/show_spam_comments'),
        Rule('/comments/<int:comment_id>', endpoint='admin/edit_comment'),
        Rule('/comments/<int:comment_id>/delete', endpoint='admin/delete_comment'),
        Rule('/comments/<int:comment_id>/approve', endpoint='admin/approve_comment'),
        Rule('/comments/<int:comment_id>/block', endpoint='admin/block_comment'),
        Rule('/comments/<int:comment_id>/spam', endpoint='admin/report_comment_spam'),
        Rule('/comments/<int:comment_id>/ham', endpoint='admin/report_comment_ham'),
        Rule('/categories/', endpoint='admin/manage_categories', defaults={'page': 1}),
        Rule('/categories/page/<int:page>', endpoint='admin/manage_categories'),
        Rule('/categories/new', endpoint='admin/new_category'),
        Rule('/categories/<int:category_id>', endpoint='admin/edit_category'),
        Rule('/categories/<int:category_id>/delete', endpoint='admin/delete_category'),
        Rule('/users/', endpoint='admin/manage_users', defaults={'page': 1}),
        Rule('/users/page/<int:page>', endpoint='admin/manage_users'),
        Rule('/users/new', endpoint='admin/new_user'),
        Rule('/users/<int:user_id>', endpoint='admin/edit_user'),
        Rule('/users/<int:user_id>/delete', endpoint='admin/delete_user'),
        Rule('/groups/', endpoint='admin/manage_groups'),
        Rule('/groups/new', endpoint='admin/new_group'),
        Rule('/groups/<int:group_id>', endpoint='admin/edit_group'),
        Rule('/groups/<int:group_id>/delete', endpoint='admin/delete_group'),
        Rule('/options/', endpoint='admin/options'),
        Rule('/options/basic', endpoint='admin/basic_options'),
        Rule('/options/urls', endpoint='admin/urls'),
        Rule('/options/theme/', endpoint='admin/theme'),
        Rule('/options/theme/configure', endpoint='admin/configure_theme'),
        Rule('/options/cache', endpoint='admin/cache'),
        Rule('/options/configuration', endpoint='admin/configuration'),
        Rule('/system/', endpoint='admin/information'),
        Rule('/system/maintenance', endpoint='admin/maintenance'),
        Rule('/system/log', defaults={'page': 1}, endpoint='admin/log'),
        Rule('/system/log/page/<int:page>', endpoint='admin/log'),
        Rule('/system/import/', endpoint='admin/import'),
        Rule('/system/import/<int:id>', endpoint='admin/inspect_import'),
        Rule('/system/import/<int:id>/delete', endpoint='admin/delete_import'),
        Rule('/system/export', endpoint='admin/export'),
        Rule('/system/plugins/', endpoint='admin/plugins'),
        Rule('/system/plugins/<plugin>/remove', endpoint='admin/remove_plugin'),
        Rule('/system/about', endpoint='admin/about_zine'),
        Rule('/system/help/', endpoint='admin/help'),
        Rule('/system/help/<path:page>', endpoint='admin/help'),
        Rule('/change_password', endpoint='admin/change_password',
             redirect_to='account/index')   # XXX: Remove on Zine 0.3
        Rule('/notifications', endpoint='admin/notification_settings')
    ]
    other_urls = [
        Rule('/<slug>', endpoint='blog/post', build_only=True),
        Rule('/_services/', endpoint='blog/service_rsd'),
        Rule('/_services/json/<path:identifier>', endpoint='blog/json_service'),
        Rule('/_services/xml/<path:identifier>', endpoint='blog/xml_service'),
        Rule('/_translations.js', endpoint='blog/serve_translations')
    ]

    # add the more complex url rule for archive and show post
    tmp = '/'
    for digits, part in zip(app.cfg['fixed_url_date_digits'] and (4, 2, 2)
                            or (0, 0, 0), ('year', 'month', 'day')):
        tmp += '<int(fixed_digits=%d):%s>/' % (digits, part)
        blog_urls.extend([
            Rule(tmp, defaults={'page': 1}, endpoint='blog/archive'),
            Rule(tmp + 'page/<int:page>', endpoint='blog/archive'),
            Rule(tmp + 'feed.atom', endpoint='blog/atom_feed')
        ])

    return [
        Submount(app.cfg['blog_url_prefix'], blog_urls),
        Submount(app.cfg['admin_url_prefix'], admin_urls)
    ] + other_urls
