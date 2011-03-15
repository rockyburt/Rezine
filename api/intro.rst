Introduction
============

To work on Rezine you have to have a Mac running OS X, a BSD syystem or
Linux.  It's currently not possible to develop on Windows as some of
tools depend on a POSIX environment.  You may have success by using
cygwin, but we don't have any experience with it.

Checking out the Code
---------------------

Depending on what feature you want to work on you should check out one
of the following mercurial repositories:

- ``http://dev.pocoo.org/hg/rezine-main`` — the main repository for new features
- ``http://dev.pocoo.org/hg/rezine-0.1`` — 0.1 maintenance branch for bugfixes and translations

If you have troubles selecting the correct branch, ask in the `IRC channel`_.

Clone the branch using hg::

    $ hg clone http://dev.pocoo.org/hg/rezine-0.1 rezine

Creating a Development Environment
----------------------------------

After you have cloned the code, step into the directory and initialize
a new virtual python environment::

    $ cd rezine
    $ ./scripts/setup-virtualenv env

Now you have a virtual environment called “env” in the root of your repository
initialized with all the libraries required for developing on that branch with
the correct version.

Make sure to enable it before working on Rezine::

    $ source env/bin/activate

To leave the virtual environment run this command::

    $ deactivate

Check in often and merge often with upstream.  When you're happy with the result,
create a bundle or patch and attach it to a ticket in the trac.


.. _IRC channel: http://rezine.pocoo.org/community/irc
