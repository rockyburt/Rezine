# -*- coding: utf-8 -*-
"""
    textpress.htmlprocessor
    ~~~~~~~~~~~~~~~~~~~~~~~

    We use plain old HTML as blog format so we use BeautifulSoup for
    parsing that. The output from beautiful soup is converted into a
    simplified doctree that is load and dumpable, and can emit events
    on rendering. Plugins can hook in at various places:

    `process-doc-tree`
        Called after the doc tree was created, plugins may want to
        traverse nodes, attach callbacks or replace child nodes.

    `setup-markup-parser`
        Called with the markup parser, that's the last and only chance
        for plugins to modify parsing rules.

    `process-node-callback`
        Called during rendering if there was a callback for a node.

    Plugins can either modify the tree (preferred because cached) or
    replace contents of a node at render time (just for dynamic content
    because slower).

    Here a small example plugin that displays the current time in all
    nodes that have a tp:contents="clock" attribute::

        from datetime import datetime

        def process_tree(event):
            doctree = event.data['doctree']
            for node in doctree.query('*[tp:contents=clock]'):
                del node.attributes['contents']
                node.add_render_callback('testplugin/show_clock')

        def node_callback(event):
            if event.data['identifier'] == 'testplugin/show_clock':
                time = datetime.now().strftime('%H:%M')
                if event.data['text_only']:
                    return time
                return event.data['node'].render(inject=time)

        def setup(app, plugin):
            app.connect_event('process-doc-tree', process_tree)
            app.connect_event('process-node-callback', node_callback)

    In the editor you can then have this snippet to trigger the
    execution::

        The current time is <span tp:contents="clock">time goes here</span>.

    Plugins have to make sure that they delete non HTML compatible
    attributes from the node they control to make sure the output isn't
    that bad. The preferred prefix for plugins is "tp:".

    Alternative Parsers
    ~~~~~~~~~~~~~~~~~~~

    Plugins may change the parser for some input data or reasons. Parsers
    should be subclasses of `textpress.htmlprocessor.BaseParser`

    :copyright: 2007 by Armin Ronacher.
    :license: GNU GPL.
"""
import pickle
from itertools import izip
from weakref import WeakKeyDictionary
from xml.sax.saxutils import quoteattr, escape

import BeautifulSoup as bt

from textpress.application import emit_event, get_request, get_application


#: list of self closing html tags for *rendering*
SELF_CLOSING_TAGS = ['br', 'img', 'area', 'hr', 'param', 'meta',
                     'link', 'base', 'input', 'embed', 'col']

#: cache for the default markup parser
_parser_cache = WeakKeyDictionary()


def parse(input_data, reason='unknown'):
    """
    Generate a doc tree out of the data provided. If we are not in unbound
    mode the `process-doc-tree` event is sent so that plugins can modify
    the tree in place. The reason is useful for plugins to find out if they
    want to render it or now. For example a normal blog post would have the
    reason 'post', an isolated page from a plugin maybe 'page' etc.

    The resulting tree structure is safe for pickeling.
    """
    # give plugins the possiblity to switch the parser
    for parser in emit_event('switch-markup-parser', input_data, reason):
        if parser is not None:
            break
    # or go with the default parser
    else:
        app = get_application()
        if app not in _parser_cache:
            _parser_cache[app] = parser = MarkupParser()
        else:
            parser = _parser_cache[app]
    return parser.parse(input_data, reason)


def dump_tree(tree):
    """Dump a doctree into a string."""
    # special case: empty tree
    if not tree:
        return ''
    def walk(node):
        children = [walk(n) for n in node.children]
        attr = [getattr(node, x) for x in _node_members]
        return _node_types[node.__class__], children, attr
    return pickle.dumps(walk(tree), 2)


def load_tree(data):
    """Load a doctree from a string."""
    # special case: empty data, return empty fragment
    if not data:
        return Fragment()
    def walk(node_type, children, attr, parent=None):
        node = object.__new__(_node_types_reverse[node_type])
        node.parent = parent
        node.children = c = list.__new__(NodeList)
        list.__init__(c, [walk(parent=node, *x) for x in children])
        c.node = node
        for key, value in izip(_node_members, attr):
            setattr(node, key, value)
        return node
    return walk(*pickle.loads(data))


def _query(nodes, rule):
    """
    Query some nodes.

    ``element/subelement``:
        query all given elements that also have a given subelement.

    ``/element/subelement``:
        query all given elements that are children of this element that
        have a given subelement.

    ``*/span``:
        get all non top level spans

    ``*/#``:
        get all non top level text nodes

    ``/+``:
        get all top level non text nodes

    ``*[id=foo]``
        get all elements with the id "foo".

    ``div[class!=syntax]``
        get all div elements for wich the class is not syntax.

    ``a[@id]``
        get all links with an ID

    ``h1[!id]``
        get all h1 headlines without an ID
    """
    if rule.startswith('/'):
        rule = rule[1:]
    else:
        nodes = _iter_all(nodes)
    parts = rule.split('/', 1)
    part = parts.pop(0)
    rest = parts and parts.pop() or None

    if part.endswith(']'):
        idx = part.index('[')
        rule = part[idx + 1:-1]
        part = part[:idx]
        if '=' in rule:
            key, value = rule.split('=')
            test = lambda x: x.attributes.get(key) == value
        elif '!=' in rule:
            key, value = rule.split('!=')
            test = lambda x: x.attributes.get(key) != value
        elif rule.startswith('!'):
            rule = rule[1:]
            test = lambda x: rule not in x.attributes
        elif rule.startswith('@'):
            rule = rule[1:]
            test = lambda x: rule in x.attributes
        else:
            raise ValueError('unknown rule')
    else:
        test = None

    if part == '#':
        nodes = (x for x in nodes if x.value is not None)
    elif part == '+':
        nodes = (x for x in nodes if x.value is None)
    elif part != '*':
        nodes = (x for x in nodes if x.name == part)
    if test is not None:
        nodes = (x for x in nodes if test(x))

    def traverse():
        for node in nodes:
            if rest:
                for n in node.query(rest):
                    yield n
            else:
                yield node
    return QueryResult(traverse())


def _iter_all(nodes):
    """Iterate over all nodes and ignore double matches."""
    seen_already = set()
    for node in nodes:
        if node not in seen_already:
            seen_already.add(node)
            yield node
            for n in node.children:
                if n not in seen_already:
                    seen_already.add(n)
                    yield n


class BaseParser(object):
    """
    Baseclass for all kinds of parsers.
    """

    def __init__(self):
        pass

    def parse(self, input_data, reason):
        """Return a fragment."""


class MarkupParser(BaseParser):
    """
    Special class that emits an `setup-markup-parser` event when setting up
    itself so that plugins can change the way elements are processed.

    Don't instanciate this parser yourself, better use the parse() method
    that caches parsers.
    """

    def __init__(self):
        self.isolated_tags = ['script', 'style', 'pre']
        self.self_closing_tags = ['br', 'img', 'area', 'hr', 'param', 'meta',
                                  'link', 'base', 'input', 'embed', 'col']
        self.nestable_block_tags = ['blockquote', 'div', 'fieldset', 'ins',
                                    'del']
        self.non_nestable_block_tags = ['address', 'form', 'p']
        self.nestable_inline_tags = ['span', 'font', 'q', 'object', 'bdo',
                                     'sub', 'sup', 'center']
        emit_event('setup-markup-parser', self, buffered=True)

        # rather bizarre way to subclass beautiful soup but since the library
        # itself isn't less bizarre...
        self._parser = p = type('_SoupParser', (bt.BeautifulSoup, object), {
            'SELF_CLOSING_TAGS':        dict.fromkeys(self.self_closing_tags),
            'QUOTE_TAGS':               self.isolated_tags,
            'NESTABLE_BLOCK_TAGS':      self.nestable_block_tags,
            'NON_NESTABLE_BLOCK_TAGS':  self.non_nestable_block_tags,
            'NESTABLE_INLINE_TAGS':     self.nestable_inline_tags
        })
        p.RESET_NESTING_TAGS = bt.buildTagMap(None,
            p.NESTABLE_BLOCK_TAGS, 'noscript', p.NON_NESTABLE_BLOCK_TAGS,
            p.NESTABLE_LIST_TAGS, p.NESTABLE_TABLE_TAGS
        )
        p.NESTABLE_TAGS = bt.buildTagMap([],
            p.NESTABLE_INLINE_TAGS, p.NESTABLE_BLOCK_TAGS,
            p.NESTABLE_LIST_TAGS, p.NESTABLE_TABLE_TAGS
        )

    def parse(self, input_data, reason):
        """Parse the data and convert it into a sane, processable format."""
        def convert_tree(node, root):
            if root:
                result = Fragment()
            else:
                result = Node(node.name, node._getAttrMap())
            add = result.children.append
            for child in node.contents:
                if isinstance(child, unicode):
                    # get rid of the navigable string, it breaks dumping
                    add(TextNode(child + ''))
                else:
                    add(convert_tree(child, False))
            return result
        bt_tree = self._parser(input_data, convertEntities=
                               self._parser.HTML_ENTITIES)
        tree = convert_tree(bt_tree, True)
        for item in emit_event('process-doc-tree', tree, input_data, reason):
            if item is not None:
                return item
        return tree


class Node(object):
    """
    Simple node class. Subclass this class and add your own render method to
    add dynamic stuff.
    """
    __slots__ = ('name', 'attributes', 'children', 'value', 'callback_data',
                 'parent')

    def __init__(self, name, attributes=None):
        self.name = name
        self.attributes = attributes or {}
        self.children = NodeList(self)
        self.value = None
        self.callback_data = None
        self.parent = None

    def render(self, inject=None):
        """
        Render the node. If `callback_data` is not None (a plugin patched
        that in the `process-doc-tree` phase) a `process-callback-node`
        event is sent with the node as only argument. If the plugin returns
        `None` the next plugins tries. If it returns a string it will be
        used instead of the normal HTML representation of the node.

        If inject is a string it will be rendered instead of the child
        elements and the callback will not be called. This is useful for
        callback nodes that just want to change the contents of a node.

        Injecting just works with the normal Node, not with a data, text
        or fragment node.
        """
        if inject is None:
            rv = self._render_callback(False)
            if rv is not None:
                return rv
        attributes = u' '.join(u'%s=%s' % (key, quoteattr(value)) for
                               key, value in self.attributes.iteritems())
        buf = ['<%s' % self.name]
        if attributes:
            buf.append(' ' + attributes)
        buf.append('>')
        if self.name not in SELF_CLOSING_TAGS:
            if inject is not None:
                buf.append(inject)
            else:
                for child in self.children:
                    buf.append(child.render())
            buf.append('</%s>' % self.name)
        return u''.join(buf)

    def _render_callback(self, text_only):
        """Helper frunction for render() and .text"""
        if self.callback_data:
            for identifier, data in self.callback_data:
                for item in emit_event('process-node-callback', identifier,
                                       data, self, text_only):
                    if item is not None:
                        return item

    @property
    def text(self):
        """Return the joined values of all data nodes."""
        #: if the callback wants something different do so.
        rv = self._render_callback(True)
        if rv is not None:
            return rv
        #: <br> thingies are linebreaks!
        if self.name == 'br':
            return u'\n'
        rv = u''.join(x.text for x in self)
        # if we are a paragraph make sure we put two \n at the end
        if self.name == 'p':
            rv += u'\n\n'
        return rv

    def add_render_callback(self, identifier, data=None):
        """Add a new callback to this node."""
        if self.callback_data is None:
            self.callback_data = []
        self.callback_data.append((identifier, data))

    def query(self, rule):
        """Query the node."""
        return _query(self.children, rule)

    def __unicode__(self):
        """Converting a node to unicode is the same as rendering."""
        return self.render()

    def __str__(self):
        """Converting a node to str is rendering and encoding to utf-8."""
        return self.render().encode('utf-8')

    def __iter__(self):
        """Iterate over the childnodes."""
        return iter(self.children)

    def __getitem__(self, item):
        """Get children or attributes."""
        if isinstance(item, (int, long)):
            return self.children[item]
        return self.attributes[item]

    def __contains__(self, item):
        """No contains check! Too magical"""
        raise TypeError()

    def __nonzero__(self):
        """Check if we have something in that node."""
        return bool((self.children or self.attributes or self.callback_data or
                     self.value))

    def __repr__(self):
        return u'<%s %r>' % (
            self.__class__.__name__,
            unicode(self)
        )


class NodeList(list):
    """
    A list that updates "parent" on set and delete.
    """
    __slots__ = ('node',)

    def __init__(self, node):
        list.__init__(self)
        self.node = node

    def __delitem__(self, idx):
        self.pop(idx)

    def __delslice__(self, start, end):
        for node in self[start:end]:
            node.parent = None
        list.__delslice__(self, start, end)

    def __setitem__(self, idx, item):
        if isinstance(idx, slice):
            raise TypeError('extended slicing not supported')
        if item.parent is not None:
            raise TypeError('%r already bound to %r' % (item, item.parent))
        node = self[idx]
        node.parent = None
        item.parent = self.node
        list.__setitem__(self, idx, item)

    def __setslice__(self, start, end, seq):
        idx = start
        for node, new in izip(self[start:end], seq):
            if new.parent is not None:
                raise TypeError('%r already bound to %r' % (item, item.parent))
            node.parent = None
            new.parent = self.node
            self[idx] = new
            idx += 1

    def extend(self, other):
        """Add all nodes from the sequence passed."""
        for item in other:
            self.append(item)
    __iadd__ = extend

    def append(self, item):
        """Append a node to the list."""
        if item.parent is not None:
            raise TypeError('%r already bound to %r' % (item, item.parent))
        item.parent = self.node
        list.append(self, item)

    def insert(self, pos, item):
        """Insert a node at a given position."""
        if item.parent is not None:
            raise TypeError('%r already bound to %r' % (item, item.parent))
        item.parent = self.node
        list.insert(self, pos, item)

    def pop(self, index=None):
        """Delete a node at index (per default -1) from the
        list and delete it."""
        if index is None:
            node = list.pop(self)
        else:
            node = list.pop(self, index)
        node.parent = None
        return node

    def remove(self, item):
        """Remove a node from the list."""
        for idx, node in self:
            if node is item:
                del self[idx]
                return
        raise ValueError('node not in list')

    def replace(self, node, new):
        """replace a node with a new one."""
        for idx, n in enumerate(self):
            if n == node:
                self[idx] = new
                return
        raise ValueError('node not in list')

    def _unsupported(self, *args, **kwargs):
        raise TypeError('unsupported operation')

    __imul__ = __mul__ = __rmul__ = _unsupported

    def __repr__(self):
        return '<%s %s>' % (
            self.__class__.__name__,
            list.__repr__(self)
        )


class QueryResult(object):
    """
    Represents the result of a query(). You can also further query this
    object.
    """
    __slots__ = ('_gen', '_results')

    def __init__(self, gen):
        self._gen = gen
        self._results = []

    @property
    def first(self):
        """Get the first node."""
        return self[0]

    @property
    def last(self):
        """
        Get the last node. This queries the all results first so you should
        try to use first if possible.
        """
        return self[-1]

    @property
    def text(self):
        """Return the joined values of all data nodes."""
        return u''.join(x.value for x in self if x.value is not None)

    def query(self, rule):
        """Apply the rule on all result nodes."""
        return _query(self, rule)

    def _fetchall(self):
        """Used internally to get all items from the generator."""
        if self._gen is not None:
            for item in self:
                pass

    def __getitem__(self, idx):
        """Get a specific result item."""
        if idx < 0:
            self._fetchall()
        if self._gen is None or idx < len(self._results):
            return self._results[idx]
        i = len(self._results)
        for item in self:
            if i == idx:
                return item
            i += 1
        raise IndexError(idx)

    def __len__(self):
        """Fetch all items and return the number of results."""
        self._fetchall()
        return len(self._results)

    def __iter__(self):
        """Iterate over the results."""
        if self._gen is None:
            for item in self._results:
                yield item
        else:
            for item in self._gen:
                self._results.append(item)
                yield item
            self._gen = None

    def __repr__(self):
        return '<%s %r>' % (
            self.__class__.__name__,
            list(self)
        )


class TextNode(Node):
    """Like a normal node just that it holds a value."""
    __slots__ = ()

    def __init__(self, value):
        Node.__init__(self, None)
        self.value = value

    @property
    def text(self):
        return self.value

    def render(self, inject=None):
        return escape(self.value)


class DataNode(Node):
    """A node with XML data in it."""
    __slots__ = ()

    def __init__(self, value):
        Node.__init__(self, None)
        self.value = value

    @property
    def text(self):
        return u''

    def render(self, inject=None):
        return self.value


class Fragment(Node):
    """The outermost node."""
    __slots__ = ()

    def __init__(self):
        Node.__init__(self, None)

    def render(self, inject=None):
        return ''.join(n.render() for n in self.children)


# helpers for the dumping system
_node_members = ('name', 'attributes', 'value', 'callback_data')
_node_types = {
    Node:           0,
    TextNode:       1,
    DataNode:       2,
    Fragment:       3,
}
_node_types_reverse = [Node, TextNode, DataNode, Fragment]
