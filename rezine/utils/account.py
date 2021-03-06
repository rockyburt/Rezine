# -*- coding: utf-8 -*-
"""
    rezine.utils.account
    ~~~~~~~~~~~~~~~~~~

    This module implements various functions used by the account interface.

    :copyright: (c) 2010 by the Rezine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""

from rezine.privileges import ENTER_ACCOUNT_PANEL, require_privilege
from rezine.utils import local
from rezine.i18n import _


def flash(msg, type='info'):
    """Add a message to the message flash buffer.

    The default message type is "info", other possible values are
    "add", "remove", "error", "ok" and "configure". The message type affects
    the icon and visual appearance.

    The flashes messages appear only in the admin interface!
    """
    assert type in \
        ('info', 'add', 'remove', 'error', 'ok', 'configure', 'warning')
    if type == 'error':
        msg = (u'<strong>%s:</strong> ' % _('Error')) + msg
    if type == 'warning':
        msg = (u'<strong>%s:</strong> ' % _('Warning')) + msg

    local.request.session.setdefault('account/flashed_messages', []).\
            append((type, msg))


def require_account_privilege(expr=None):
    """Works like `require_privilege` but checks if the rule for
    `ENTER_ADMIN_PANEL` exists as well.
    """
    if expr:
        expr = ENTER_ACCOUNT_PANEL & expr
    else:
        expr = ENTER_ACCOUNT_PANEL
    return require_privilege(expr)
