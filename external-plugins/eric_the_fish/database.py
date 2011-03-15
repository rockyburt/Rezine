# -*- coding: utf-8 -*-
"""
    rezine.plugins.eric_the_fish.databse
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Database tables and objects for the "Annoying fish for the admin panel".

    :copyright: (c) 2010 by the Rezine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""

from rezine.database import db, metadata

fortunes = db.Table('eric_the_fish_fortunes', metadata,
    db.Column('id', db.Integer, primary_key=True),
    db.Column('text', db.Text, nullable=False)
)

class Fortune(object):
    query = db.query_property(db.Query)
    def __init__(self, text):
        self.text = text

db.mapper(Fortune, fortunes)
