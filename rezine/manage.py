#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    Start a Rezine Server
    ~~~~~~~~~~~~~~~~~~~

    This script opens a development server for Rezine.

    :copyright: (c) 2010 by the Rezine Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import sys
from optparse import OptionParser
from werkzeug import run_simple, Response, DispatcherMiddleware


from rezine._init_rezine import find_instance
from rezine import get_wsgi_app


def _make_root_app(real_location):
    return Response('''
    <!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN">
    <title>Page Not Found</title>
    <h2>Page Not Found</h2>
    <p>
      The blog was relocated to a different URL for testing purposes.
    <ul>
      <li><a href="%(blog)s">go to the blog</a></li>
    </ul>
    ''' % dict(blog=real_location), mimetype='text/html')


def main():
    parser = OptionParser(usage='%prog [options]')
    parser.add_option('--hostname', '-a', dest='hostname', default='127.0.0.1')
    parser.add_option('--port', '-p', dest='port', type='int', default=4000)
    parser.add_option('--no-reloader', dest='reloader', action='store_false',
                      default=True, help='Disable the reloader')
    parser.add_option('--no-debugger', dest='debugger', action='store_false',
                      default=True, help='Disable the debugger')
    parser.add_option('--threaded', dest='threaded', action='store_true',
                      default=False, help='Activate multithreading')
    parser.add_option('--profile', dest='profile', action='store_true',
                      help='Enable the profiler')
    parser.add_option('--mount', dest='mount', default='/',
                      help='If you want to mount the application somewhere '
                      'outside the URL root.  This is useful for debugging '
                      'URL generation problems.')
    parser.add_option('--instance', '-I', dest='instance',
                      help='Use the path provided as Rezine instance.')
    options, args = parser.parse_args()
    if args:
        parser.error('incorrect number of arguments')
    instance = options.instance or find_instance()
    if instance is None:
        parser.error('instance not found.  Specify path to instance')

    app = get_wsgi_app(instance)
    if options.profile:
        from werkzeug.contrib.profiler import ProfilerMiddleware
        app = ProfilerMiddleware(app, stream=sys.stderr)

    if options.mount != '/':
        mountpoint = options.mount.rstrip('/')
        if not mountpoint.startswith('/'):
            parser.error('mount point has to start with a slash.')
        app = DispatcherMiddleware(_make_root_app(mountpoint), {
            mountpoint: app
        })

    run_simple(options.hostname, options.port, app, threaded=options.threaded,
               use_reloader=options.reloader, use_debugger=options.debugger)


if __name__ == '__main__':
    main()
