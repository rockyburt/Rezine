# -*- coding: utf-8 -*-
"""
Rezine
========

A WSGI-based weblog engine in Python.
"""

from setuptools import setup, find_packages

REQUIRES = [
    'Werkzeug >= 0.6',
    'Jinja2 >= 2.5',
    'SQLAlchemy >= 0.6.1',
    'pytz >= 2011a',
    'Babel >= 0.9.4',
    'lxml >= 2.0',
    'sqlalchemy-migrate >= 0.6.1',
    'html5lib >= 0.90',
    'setuptools',
    ]

try:
    import json
except ImportError:
    REQUIRES.append('simplejson')

setup(
    name='Rezine',
    version='0.3dev',
    url='https://github.com/rockyburt/Rezine',
    license='BSD',
    author='Armin Ronacher',
    author_email='armin.ronacher@active-4.com',
    description='A WSGI-based weblog engine in Python',
    long_description=__doc__,
    zip_safe=False,
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content :: News/Diary',
    ],
    packages=find_packages(),
    install_requires=REQUIRES,
    entry_points={
        'console_scripts': [
            'rezine-manage = rezine.manage:main'
            ],
        },
    platforms='any',
    include_package_data=True,
    test_suite='tests.suite',
)
