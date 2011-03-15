# -*- coding: utf-8 -*-
"""
    rezine.plugins.eric_the_fish
    ~~~~~~~~~~~~~~~~~~~~~~~~~~

    Annoying fish for the admin panel.  This is somewhat of an demonstration
    plugin because it uses quite a lot of the internal signaling and
    registration system.

    :copyright: (c) 2010 by the Rezine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
from os.path import dirname, join
from random import choice

# the API gives us access to a bunch of functions useful for plugins. The
# api module just acts as a collection module which is safe to star import.
# The objects' implementations are in different modules.
from rezine.api import *

# because we want to add an admin panel page for our fish we need the
# render_admin_response function that works like the normal render_response
# function, but assembles a navigation bar for the admin layout template
# and emits the `modify-admin-navigation-bar` event also use here.
from rezine.views.admin import render_admin_response

# the following method is used to show notifications in the admin panel.
from rezine.utils.admin import flash

# this function is used for redirecting the user to another page
from rezine.utils.http import redirect

# Because our fish uses JSON and JavaScript we use the dump_json function
# from the utils module.
from rezine.utils import dump_json

# TextField is used as a type of a configuration variable
from rezine.utils.forms import TextField

# the following exception is raised when the config could not be changed
from rezine.config import ConfigurationTransactionError

# we only want the admin to be able to configure eric. so we need the
# BLOG_ADMIN privilege
from rezine.privileges import BLOG_ADMIN

# import Rezine's database related stuff
from rezine.database import db

# the last thing is importing the Fortunes database mapped object.
from rezine.plugins.eric_the_fish.database import Fortune

# because we have an admin panel page we need to store the templates
# somewhere. So here we calculate the path to the templates and save them
# in this global variable.
TEMPLATES = join(dirname(__file__), 'templates')

# here we do the same for the shared files (css, fish images and javascript)
SHARED_FILES = join(dirname(__file__), 'shared')

# and that's just the list of skins we have.
SKINS = 'blue green pink red yellow'.split()


def inject_fish(req, context):
    """This is called before the admin response is rendered. We add the
    fish script and the stylesheet and then we add a new header snippet
    which basically is some HTML code that is added to the <head> section.
    In this header snippet we set the global `$ERIC_THE_FISH_SKIN` variable
    to the selected skin.
    """
    add_script(url_for('eric_the_fish/shared', filename='fish.js'))
    add_link('stylesheet', url_for('eric_the_fish/shared',
                                   filename='fish.css'), 'text/css')

    add_header_snippet(
        '<script type="text/javascript">'
            '$ERIC_THE_FISH_SKIN = %s;'
        '</script>' % dump_json(req.app.cfg['eric_the_fish/skin'])
    )


def add_eric_link(req, navigation_bar):
    """Called during the admin navigation bar setup. When the options menu is
    traversed we insert our eric the fish link before the plugins link.
    The outermost is the configuration editor, the next one the plugins
    link and then we add our fish link.
    """
    if not req.user.has_privilege(BLOG_ADMIN):
        return
    for link_id, url, title, children in navigation_bar:
        if link_id == 'options':
            children.insert(-3, ('eric_the_fish',
                                 url_for('eric_the_fish/config'),
                                 _('Eric The Fish')))


@require_privilege(BLOG_ADMIN)
def show_eric_options(req):
    """This renders the eric admin panel. Allow switching the skin and show
    the available skins.
    """
    new_skin = req.args.get('select')
    if new_skin in SKINS:
        try:
            req.app.cfg.change_single('eric_the_fish/skin', new_skin)
        except ConfigurationTransactionError, e:
            flash(_('The skin could not be changed.'), 'error')
        return redirect(url_for('eric_the_fish/config'))

    return render_admin_response('admin/eric_the_fish.html',
                                 'options.eric_the_fish',
        skins=[{
            'name':     skin,
            'active':   skin == req.app.cfg['eric_the_fish/skin']
        } for skin in SKINS]
    )


def get_fortune(req):
    """The servicepoint function. Just return one fortune from the database."""
    fortune_ids = db.session.query(Fortune.id).all()
    return {'fortune': db.session.query(Fortune).get(choice(fortune_ids)).text}


def setup(app, plugin):
    """This function is called by Rezine in the application initialisation
    phase. Here we connect to the events and register our template paths,
    url rules, views etc.
    """

    # since this plugin also shows how to do data migration, we need to register
    # eric's database upgrades repository.  Basically it should be a directory
    # which itself has a subdirectory named "versions" where the upgrade
    # script(s) reside.  In Eric's case we pass the plugin's directory which has
    # that subdirectory called "versions".
    app.register_upgrade_repository(plugin, dirname(__file__))

    # we want our fish to appear in the admin panel, so hook into the
    # correct event.
    app.connect_event('before-admin-response-rendered', inject_fish)

    # for our admin panel page we also add a link to the navigation bar.
    app.connect_event('modify-admin-navigation-bar', add_eric_link)

    # our fish has a configurable skin. So we register one for it which
    # defaults to blue.
    app.add_config_var('eric_the_fish/skin', TextField(default='blue'))

    # then we add some shared exports for the fish which points to the
    # shared files location from above. There we have all the CSS files
    # and static stuff.
    app.add_shared_exports('eric_the_fish', SHARED_FILES)

    # Whenever we click on the fish we want a quote to appear. Because the
    # quotes are stored on the server we add a servicepoint that sends one
    # quote back. Rezine provides JSON and XML export for this servicepoint
    # automatically, plugins may add more export formats.
    app.add_servicepoint('eric_the_fish/get_fortune', get_fortune)

    # for the admin panel we add a url rule. Because it's an admin panel
    # page located in options we add such an url rule.
    app.add_url_rule('/options/eric-the-fish', prefix='admin',
                     endpoint='eric_the_fish/config',
                     view=show_eric_options)

    # add our templates to the searchpath so that Rezine can find the
    # admin panel template for the fish config panel.
    app.add_template_searchpath(TEMPLATES)
