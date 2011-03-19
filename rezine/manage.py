#!/usr/bin/env python

from os import path, mkdir
from rezine.utils.crypto import gen_pwhash, gen_secret_key, new_iid

DEFAULT_DATABASE_URI = 'sqlite://rezine.db'
DEFAULT_INSTANCE_FOLDER = 'rezine-blog'
DEFAULT_ADMIN_USERNAME = 'admin'
DEFAULT_ADMIN_PASSWORD = ''
DEFAULT_ADMIN_EMAIL = ''

CONFIG_HEADER = '''\
# Rezine configuration file
# This file is also updated by the Rezine admin interface.
# The charset of this file must be utf-8!

'''


def create_instance(instance_folder=DEFAULT_INSTANCE_FOLDER,
                    database_uri=DEFAULT_DATABASE_URI,
                    admin_username=DEFAULT_ADMIN_USERNAME,
                    admin_password=DEFAULT_ADMIN_PASSWORD,
                    admin_email=DEFAULT_ADMIN_EMAIL):
    """Create a new blog instance.
    """

    if not admin_password:
        raise ValueError('Must specify admin_password')

    if not admin_email:
        raise ValueError('Must specify admin_email')

    error = None

    # set up the initial config
    config_filename = path.join(instance_folder, 'rezine.ini')
    import rezine.application
    from rezine.config import Configuration

    if not path.exists(instance_folder):
        mkdir(instance_folder)
    cfg = Configuration(config_filename)
    t = cfg.edit()
    t.update(
        maintenance_mode=1,
        secret_key=gen_secret_key(),
        database_uri=database_uri,
        iid=new_iid(),
        # load one plugin by default for a better theme
        plugins='vessel_theme',
        theme='vessel'
    )
    cfg._comments['[rezine]'] = CONFIG_HEADER
    t.commit()

    from rezine.api import db
    from rezine.database import init_database
    try:
        e = db.create_engine(database_uri, instance_folder)
        init_database(e)
    except Exception, error:
        error = str(error).decode('utf-8', 'ignore')
    else:
        from rezine.database import users, user_privileges, privileges, \
             schema_versions
        from rezine.privileges import BLOG_ADMIN

        # a newly created database has a schema version corresponding
        # to the latest available version in the repository
        from rezine.upgrades import REPOSITORY_PATH
        from rezine.upgrades.customisation import Repository
        repo = Repository(REPOSITORY_PATH, 'Rezine')
        e.execute(schema_versions.insert(),
                  repository_id=repo.config.get('repository_id'),
                  repository_path=repo.path,
                  version=int(repo.latest))

        # create admin account
        user_id = e.execute(users.insert(),
            username=admin_username,
            pw_hash=gen_pwhash(admin_password),
            email=admin_email,
            real_name=u'',
            description=u'',
            extra={},
            display_name='$username',
            is_author=True
        ).inserted_primary_key[0]

        # insert a privilege for the user
        privilege_id = e.execute(privileges.insert(),
            name=BLOG_ADMIN.name
        ).inserted_primary_key[0]
        e.execute(user_privileges.insert(),
            user_id=user_id,
            privilege_id=privilege_id
        )


def main():
    from werkzeug import script

    def action_runserver(instance=('I', DEFAULT_INSTANCE_FOLDER),
                         hostname=('h', '0.0.0.0'), port=('p', 4000),
                         reloader=True, debugger=True,
                         evalex=True, threaded=False, processes=1):
        '''Start a new development server.'''
        from werkzeug.serving import run_simple
        from rezine import get_wsgi_app

        app = get_wsgi_app(instance)
        run_simple(hostname, port, app, reloader, debugger, evalex,
                   threaded=threaded, processes=processes)

    def action_newinstance(instance=('I', DEFAULT_INSTANCE_FOLDER),
                           database_uri=('d', DEFAULT_DATABASE_URI),
                           admin_username=('u', DEFAULT_ADMIN_USERNAME),
                           admin_password=('p', DEFAULT_ADMIN_PASSWORD),
                           admin_email=('e', DEFAULT_ADMIN_EMAIL)):
        '''Create a new instance'''

        create_instance(instance, database_uri, admin_username,
                        admin_password, admin_email)

    def action_shell(instance=('I', DEFAULT_INSTANCE_FOLDER)):
        """Start a new interactive python session."""

        from rezine import setup_rezine
        from code import interact

        rezine_app = setup_rezine(instance)
        namespace = {'rezine_app': rezine_app}

        banner = '''Interactive Rezine Shell

  namespace:
'''
        for k, v in namespace.items():
            banner += '    %s: %s\n' % (k, v.__doc__.split('\n')[0].strip())

        banner += '\n  Use dir() to inspect current namespace.'
        interact(banner, local=namespace)

    script.run()


if __name__ == '__main__':
    main()
