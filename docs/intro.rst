Introduction
============

Rezine provides quite a few features:

- of course, basic blog functionality: posting, comments, categories,
  tags, and ATOM feeds
- user, group and permission management
- theming support
- importers for WordPress and Atom feeds.
- an advanced plugin system
- a translatable interface (although with this first release, only
  English and German translations are available)

Requirements
============

- Python >= 2.6 *(not yet tested on 3.x)*

All other dependencies are installed automatically as part of the
``easy_install`` process.

Installation
============

Simple to install via ``easy_install``:

.. code-block:: console

 easy_install Rezine

*To install lxml you may need the development packages of libxml2 and libxslt*

Deploying with Apache mod_wsgi
------------------------------

The following example shows how to set up Rezine for Apache mod_wsgi.

1.  Create a new folder ``/var/rezine/yourblog1`` where *yourblog1* is a name
    that make sense for you.
2.  Copy the ``rezine.wsgi`` file from
    ``/path/to/python/lib/python2.6/site-packages/rezine/deployment``
    into the newly created folder and open it with an editor.
3.  Modify the ``INSTANCE_FOLDER`` variable to point to the *yourblog1* folder.
4.  Open your Apache vhost config or your Apache config, whatever you use
    and add the following lines:

    .. code-block:: apacheconf

     WSGIScriptAlias /yourblog1 /var/lib/rezine/yourblog1/rezine.wsgi

    This tells Apache that it should hook your blog into the webserver at
    `/yourblog1`.  You can also move it to a different vhost and mount it
    in the root or ask Apache to spawn as different user.  More details
    about that are available in the `mod_wsgi documentation`_.
5.  Make sure the user your Apache (or application if you configured a
    different user for mod_wsgi) has read and write access to the
    `yourblog1` folder.
6.  Reload your apache and go to the URL of your blog and follow the
    installation instructions.

Other Deployments
-----------------

Rezine can be deployed as a WSGI app anywhere where WSGI apps can
be deployed.  Examples for running web apps using FastCGI and regular
CGI can be found in the ``rezine/deployments/`` directory.

**One important restriction is that only one Rezine instance (blog)
can be run per Python interpreter.  Strange things will happen
if multiple instances are run.**

.. _mod_wsgi documentation: http://code.google.com/p/modwsgi/wiki/InstallationInstructions


Development Quickstart
----------------------

Make sure you have an :ref:`isolated_environment` before beginning.

For a quickstart with the development server do this:

.. code-block:: console
 :linenos:

 mkdir yourblog1
 rezine-manage -I yourblog1

After the first start you will find yourself in an installation wizard
that helps you to create the database tables and an administrator
account.


License and Copyright
=====================

Rezine is a fork of the `Zine <http://zine.pocoo.org/>`_ weblog software.
It is currently maintained by Rocky Burt.

Zine was mainly written by Armin Ronacher.  See the
files AUTHORS and THANKS for a complete list of contributors known as
the Rezine Team.

Rezine is released under a BSD-style license, see the LICENSE file for more
details.

Resources
=========

-  `Main repository <https://github.com/rockyburt/Rezine>`_
