Developers
==========

To work on Rezine you have to have a Mac running OS X, a BSD syystem or
Linux.  It's currently not possible to develop on Windows as some of
tools depend on a POSIX environment.  You may have success by using
cygwin, but we don't have any experience with it.

Creating a Development Environment
----------------------------------

The Rezine team suggests you use `virtualenv <http://pypi.python.org/pypi/virtualenv>`_
to separate dev work from your normal Python environment. Setting
up a virtualenv_ is as simple as the following:

.. code-block:: bash
 :linenos:

 wget http://pypi.python.org/packages/source/v/virtualenv/virtualenv-1.5.2.tar.gz
 tar zxf virtualenv-1.5.2.tar.gz
 python virtualenv-1.5.2/virtualenv.py rezine
 source rezine/bin/activate

Checking out the Code
---------------------

The source code repository is hosted at github here:

- `Rezine GitHub Project <https://github.com/rockyburt/Rezine>`_

Clone the branch using git:

.. code-block:: bash
 :linenos:

 git clone git://github.com/rockyburt/Rezine.git

Once the code has been cloned you can install it into your
development environment by simply using (assuming your virtualenv_
is still active) ``pip``:

.. code-block:: bash
 :linenos:

 cd Rezine
 pip install -e .

To leave the virtual environment run this command:

.. code-block:: bash
 :linenos:

 deactivate
