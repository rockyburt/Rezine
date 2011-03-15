# -*- coding: utf-8 -*-
"""
Zine
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
    ]

try:
    import json
except ImportError:
    REQUIRES.append('simplejson')

setup(
    name='Zine',
    version='0.2dev-sz1',
    url='https://github.com/rockyburt/Zine',
    license='GPLv2',
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
            'zine-manage = zine.manage:main'
            ],
        },
    platforms='any',
    include_package_data=True,
    test_suite='tests.suite',
)
