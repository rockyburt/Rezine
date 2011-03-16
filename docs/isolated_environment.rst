.. _isolated_environment:

Isolated Environment
====================

The Rezine team suggests you use :term:`virtualenv`
to isolate the Rezine application from your standard Python environment.
Setting up and activating a :term:`virtualenv` is as simple as the following:

.. code-block:: console
 :linenos:

 wget http://pypi.python.org/packages/source/v/virtualenv/virtualenv-1.5.2.tar.gz
 tar zxf virtualenv-1.5.2.tar.gz
 python virtualenv-1.5.2/virtualenv.py rezine
 source rezine/bin/activate
