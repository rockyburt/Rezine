# -*- coding: utf-8 -*-
"""
    textpress.plugins.pages
    ~~~~~~~~~~~~~~~~~~~~~~~

    Just a little plugin that supports static pages.

    It also provides a little widget that stores a navigation bar
    that renders all static pages.

    :copyright: Copyright 2007 by Christopher Grebs.
    :license: GNU GPL.
"""
from os.path import dirname, join
from random import choice

from textpress.api import *
from textpress.widgets import Widget
from textpress.views.admin import render_admin_response, flash
from textpress.models import ROLE_ADMIN
from textpress.utils import CSRFProtector, gen_slug, escape
from textpress import cache
from textpress.plugins.pages.database import Page, pages_table


TEMPLATES = join(dirname(__file__), 'templates')
SHARED_FILES = join(dirname(__file__), 'shared')


class PagesNavigation(Widget):
    """
    Show a little navigation as a widget
    """

    NAME = 'get_pages_navigation'
    TEMPLATE = 'widgets/pages_navigation.html'

    @staticmethod
    def get_display_name():
        return _('Pages Navigation')

    def __init__(self):
        p = pages_table.c
        pages = Page.objects.query
        ta = pages.filter_by(navigation_pos=None)
        self.pages = pages.filter(p.navigation_pos!=None).order_by(
            p.navigation_pos.asc()).all()
        self.pages.extend(ta.all())


def add_admin_link(request, navigation_bar):
    if request.user.role >= ROLE_ADMIN:
        navigation_bar += [
            ('pages', url_for('pages/show_pages'), _('Pages'), [
                ('overview', url_for('pages/show_pages'), _('Overview')),
                ('write', url_for('pages/write_page'), _('Write Page')),
        ])]


@require_role(ROLE_ADMIN)
def show_pages_overview(request):
    """This renders the plugins admin page."""
    return render_admin_response(
        'admin/pages.html',
        'pages.overview',
        pages=Page.objects.all()
    )

@require_role(ROLE_ADMIN)
def show_pages_write(request, page_id=None):
    csrf_protector = CSRFProtector()
    form = {}
    errors = []

    if page_id is None:
        # new page
        new_page = True
        form.update(
            key=u'', title=u'',
            raw_body=u'',
            navigation_pos=u'',
            parser=request.app.cfg['default_parser'],
        )
    else:
        # edit a page
        new_page = False
        page = Page.objects.get(page_id)
        if page is None:
            raise NotFound()
        form.update(
            key=page.key,
            title=page.title,
            raw_body=page.raw,
            navigation_pos=page.navigation_pos,
            parser=page.extra['parser']
        )

    if request.method == 'POST':
        csrf_protector.assert_safe()

        if request.form.get('cancel'):
            return redirect(url_for('pages/show_pages'))
        if request.form.get('delete') and not new_page:
            return redirect(url_for('pages/delete_page', page_id=page_id))

        form['title'] = title = request.form.get('title')
        if not title:
            errors.append(_('You have to provide a title'))

        form['key'] = key = request.form.get('key') or None
        if key is None:
            key = gen_slug(title)
        elif key:
            key = gen_slug(key)
        if u'/' in key:
            errors.append(_("A key can't contain a slash"))

        form['navigation_pos'] = navigation_pos = \
            request.form.get('navigation_pos') or None

        form['raw_body'] = raw_body = request.form.get('raw_body')
        if not raw_body:
            errors.append(_('You have to provide a content'))

        form['parser'] = parser = request.form.get('parser')
        if not parser:
            parser = request.app.cfg['default_parser']

        if not errors:
            if new_page:
                page = Page(key, title, raw_body, parser, navigation_pos)
            else:
                page.key = key
                page.title = title
                page.raw = raw_body
                page.navigation_pos = navigation_pos
                page.parser = parser
            db.commit()
            html_detail = '<a href="%s">%s</a>' % (
                escape(url_for(page)),
                escape(title)
            )
            if new_page:
                flash('The page %s was created successfully.' % html_detail)
            else:
                flash('The page %s was updated successfully.' % html_detail)
            return redirect(url_for('pages/show_pages'))
        else:
            for error in errors:
                flash(error, 'error')

    return render_admin_response(
        'admin/write_page.html',
        'pages.write',
        parsers=request.app.list_parsers(),
        form=form,
        csrf_protector=csrf_protector,
    )

@require_role(ROLE_ADMIN)
def show_pages_delete(request, page_id):
    page = Page.objects.get(page_id)
    if page is None:
        raise NotFound()
    csrf_protector = CSRFProtector()

    if request.method == 'POST':
        csrf_protector.assert_safe()

        if request.form.get('cancel'):
            return redirect(url_for('pages/write_page', page_id=page.page_id))
        elif request.form.get('confirm'):
            db.delete(page)
            flash(_('The page %s was deleted successfully.') %
                  escape(page.title), 'remove')
            db.commit()
            return redirect(url_for('pages/show_pages'))

    return render_admin_response('admin/delete_page.html', 'page.write',
        page=page,
        csrf_protector=csrf_protector,
    )


@cache.all_if_anonymous()
def show_page(self, key):
    page = Page.objects.query.filter_by(key=key).one()
    if page is None:
        raise NotFound()
    return render_response(
        'page_base.html',
        page=page
    )


def setup(app, plugin):
    from textpress.plugins.pages.database import upgrade_database
    app.connect_event('modify-admin-navigation-bar', add_admin_link)
    app.add_shared_exports('pages', SHARED_FILES)
    app.add_url_rule('/show_pages/', endpoint='pages/show_pages',
        prefix='admin')
    app.add_url_rule('/write_page/', endpoint='pages/write_page',
        prefix='admin')
    app.add_url_rule('/write_page/<int:page_id>/',
        endpoint='pages/write_page',
        prefix='admin')
    app.add_url_rule('/page/<key>/',
        endpoint='pages/show_page',
        prefix='blog')
    app.add_url_rule('/delete_page/<int:page_id>/',
        endpoint='pages/delete_page',
        prefix='admin')
    app.add_view('pages/show_pages', show_pages_overview)
    app.add_view('pages/write_page', show_pages_write)
    app.add_view('pages/show_page', show_page)
    app.add_view('pages/delete_page', show_pages_delete)
    app.add_template_searchpath(TEMPLATES)
    app.add_database_integrity_check(upgrade_database)
    app.add_widget(PagesNavigation)
