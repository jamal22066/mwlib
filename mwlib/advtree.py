"""
The parse tree generated by the parser is a 1:1 representation of the mw-markup.
Unfortunally these trees have some flaws if used to geenerate derived documents.

This module seeks to rebuild the parstree
to be:
 * more logical markup
 * clean up the parse tree
 * make it more accessible
 * allow for validity checks
 * implement rebuilding strategies

Usefull Documentation:
http://en.wikipedia.org/wiki/Wikipedia:Don%27t_use_line_breaks
http://meta.wikimedia.org/wiki/Help:Advanced_editing
"""

import weakref
from mwlib.parser import Magic, Math,  _VListNode, Ref # not used but imported
from mwlib.parser import Item, ItemList, Link, NamedURL, Node, Table, Row, Cell, Paragraph, PreFormatted
from mwlib.parser import Section, Style, TagNode, Text, URL, Timeline
from mwlib.parser import CategoryLink, SpecialLink, ImageLink,  Article, Book, Chapter


class AdvancedNode():
    """
    MixIn Class that extends Nodes so they become easier accessible

    allows to traverse the tree in any direction and 
    build derived convinience functions
    """
    _parentref = None # weak referece to parent element
    isinlinenode = False # must be set before instancing (see below)
    isblocknode = property(lambda s:not s.isinlinenode)

    def moveto(self, targetnode, prefix=False):
        """"
        moves this node after target node
        if prefix is true, move in front of target node
        """
        self.parent.removeChild(self)
        tp = targetnode.parent
        idx = tp.children.index(targetnode)
        if not prefix:
            idx+=1
        tp.children = tp.children[:idx] + [self] + tp.children[idx:]
        self._parentref = weakref.ref(tp)
        
    def appendChild(self, c):
        self.children.append(c)
        c._parentref = weakref.ref(self)
        
    def removeChild(self, c):
        self.replaceChild(c, [])

    def replaceChild(self, c, newchildren = []):
        idx = self.children.index(c)
        self.children.remove(c)
        c._parentref = None
        if newchildren:
            self.children = self.children[:idx] + newchildren + self.children[idx:]
            for nc in newchildren:
                nc._parentref = weakref.ref(self)

    def getParents(self):
        if self.parent:
            return self.parent.getParents() + [self.parent]
        else:
            return []

    def getParent(self):
        if not self._parentref:
            return None
        x = self._parentref()
        if not x:
            raise weakref.ReferenceError
        return x
    
    def getClassInParents(self, klass):
        "returns first parent w/ klass"
        for p in self.parents:
            if p.__class__ == klass:
                return p

    def getClassInChildren(self, klass):
        "returns all children /including self)  w/ klass"
        return [p for p in self.allchildren() if p.__class__ == klass]
        
    def getSiblings(self):
        return (c for c in self.getAllSiblings() if c!=self)

    def getAllSiblings(self):
        "all siblings plus me my self and i"
        if self.parent:
            return self.parent.children
        return []

    def getPrevious(self):
        "return previous sibling"
        s = self.getAllSiblings()
        try:
            idx = s.index(self)
        except ValueError:
            return None
        if idx -1 <0:
            return None
        else:
            return s[idx-1]

    def getNext(self):
        "return next sibling"
        s = self.getAllSiblings()
        try:
            idx = s.index(self)
        except ValueError:
            return None
        if idx+1 >= len(s):
            return None
        else:
            return s[idx+1]

    def getLast(self):
        "return last sibling"
        s = self.getAllSiblings()
        if s:
            return s[-1]

    def getFirst(self):
        "return first sibling"
        s = self.getAllSiblings()
        if s:
            return s[0]

    def getLastChild(self):
        "return last child of this node"
        if self.children:
            return self.children[-1]

    def getFirstChild(self):
        "return first child of this node"
        if self.children:
            return self.children[0]

    parent = property(getParent)
    parents = property(getParents)
    next = property(getNext)
    previous = property(getPrevious)
    siblings = property(getSiblings)
    last = property(getLast)
    first = property(getFirst)
    lastchild = property(getLastChild)
    firstchild = property(getFirstChild)
    


# --------------------------------------------------------------------------
# MixinClasses w/ special behaviour
# -------------------------------------------------------------------------

class AdvancedSection(AdvancedNode):
    h_level = 0 # sthis is set if it originates from an H1, H2, ... TagNode
    def getSectionLevel(self):
        return 1 + [p.__class__ for p in self.getParents()].count(self.__class__)

class AdvancedImageLink(AdvancedNode):
    isinlinenode = property( lambda s: s.isInline() )


class AdvancedMath(AdvancedNode):
    def _isinlinenode(self):
        if self.caption.strip().startswith("\\begin{align}")  or \
                self.caption.strip().startswith("\\begin{alignat}"):
            return False
        return True
    isinlinenode = property( lambda s: s._isinlinenode() )

# Nodes we defined above and that are separetly handled in extendClasses
_advancedNodesMap = {Section: AdvancedSection, ImageLink:AdvancedImageLink, 
                     Math:AdvancedMath}
       

# --------------------------------------------------------------------------
# Missing as Classes derived from parser.Style
# -------------------------------------------------------------------------

    
class Emphasized(Style, AdvancedNode):
    "EM"
    pass

class Strong(Style, AdvancedNode):
    pass

class DefinitionList(Style, AdvancedNode):
    "DL"
    pass

class DefinitionTerm(Style, AdvancedNode):
    "DT"
    pass

class DefinitionDefinition(Style, AdvancedNode):
    "DD"
    pass

class Blockquote(Style, AdvancedNode):
    "margins to left &  right"
    pass

class Indented(Style, AdvancedNode):
    "margin to the left"

class Overline(Style, AdvancedNode):
    _style = "overline"

class Underline(Style, AdvancedNode):
    _style = "underline"

class Sub(Style, AdvancedNode):
    _style = "sub"

class Sup(Style, AdvancedNode):
    _style = "sup"

class Small(Style, AdvancedNode):
    _style = "small"

class Cite(Style, AdvancedNode):
    _style = "cite"

_styleNodeMap = dict( (k._style,k) for k in [Overline, Underline, Sub, Sup, Small, Cite] )

# --------------------------------------------------------------------------
# Missing as Classes derived from parser.TagNode
# -------------------------------------------------------------------------


class BreakingReturn(TagNode, AdvancedNode):
    _tag = "code"

class BreakingReturn(TagNode, AdvancedNode):
    _tag = "br"

class HorizontalRule(TagNode, AdvancedNode):
    _tag = "hr"

class Index(TagNode, AdvancedNode):
    _tag = "index"

class Teletyped(TagNode, AdvancedNode):
    _tag = "tt"

class Reference(TagNode, AdvancedNode):
    _tag = "tt"

class Gallery(TagNode, AdvancedNode):
    _tag = "gallery"

class Center(TagNode, AdvancedNode):
    _tag = "center"
    
_tagNodeMap = dict( (k._tag,k) for k in [BreakingReturn, HorizontalRule, Index, Teletyped, Reference, Gallery, Center] )



# --------------------------------------------------------------------------
# InlineNode and BlockNode separation for AdvancedNode.isinlinenode
# -------------------------------------------------------------------------

"""
For writers it is usefull to know whether elements are inline (within a paragraph) or not.
We define list for both, which are used in AdvancedNode as:

AdvancedNode.isinlinenode
AdvancedNode.isblocknode

Image depends on result of Image.isInline() see above

Open Issues: Math, Magic, (unknown) TagNode 

"""
_blockNodesMap = (Book, Chapter, Article, Section, Paragraph, 
                  PreFormatted, Cell, Row, Table, Item, 
                  ItemList, Timeline, Cite, HorizontalRule, Gallery, Indented, 
                  DefinitionList, DefinitionTerm, DefinitionDefinition)

for k in _blockNodesMap:  
  k.isinlinenode = False

_inlineNodesMap = (URL, NamedURL, Link, CategoryLink, SpecialLink, Style,
               Text, Index, Teletyped, BreakingReturn, Reference, Strong,Emphasized, 
               Sub, Sup, Small, Underline, Overline)

for k in _inlineNodesMap:  
  k.isinlinenode = True


# --------------------------------------------------------------------------
# funcs for extending the nodes
# -------------------------------------------------------------------------

def MixIn(pyClass, mixInClass, makeFirst=False):
  if mixInClass not in pyClass.__bases__:
    if makeFirst:
      pyClass.__bases__ = (mixInClass,) + pyClass.__bases__
    else:
      pyClass.__bases__ += (mixInClass,)

def extendClasses(node):
    MixIn(node.__class__, _advancedNodesMap.get(node.__class__, AdvancedNode))
    for c in node.children[:]:
        extendClasses(c)
        c._parentref = weakref.ref(node)            

# --------------------------------------------------------------------------
# funcs for repairing the tree
# -------------------------------------------------------------------------


def fixTagNodes(node):
    """
    detect known TagNode(s) and assoiciate aprroriate Nodes
    """
    for c in node.children:
        if c.__class__ == TagNode:
            if c.caption in _tagNodeMap:
                c.__class__ = _tagNodeMap[c.caption]
            elif c.caption in ("h1", "h2", "h3", "h4", "h5", "h6"):
                c.__class__ = Section 
                MixIn(c.__class__, AdvancedSection)
                c._h_level = int(c.caption[1])
                c.caption = ""
            else:
                print "unknowntagnode", c
                raise Exception, "unknown tag %s" % c.caption # FIXME
        fixTagNodes(c)


def fixStyle(node):
    """
    parser.Style Nodes are mapped to logical markup
    dection of DefinitionList depends on removeNodes
    and removeNewlines
    """
    if not node.__class__ == Style:
        return
    # replace this node by a more apporiate
    if node.caption == "''": 
        node.__class__ = Emphasized
        node.caption = ""
    elif node.caption=="'''''":
        node.__class__ = Strong
        node.caption = ""
        em = Emphasized("''")
        em.children = node.children
        node.children = [em]
    elif node.caption == "'''":
        node.__class__ = Strong
        node.caption = ""
    elif node.caption == ";": 
        # this starts a definition list ? DL [DT->DD, ...]
        # check if previous node is DefinitionList, if not create one
        if node.previous.__class__ == DefinitionList:
            node.__class__ = DefinitionTerm
            node.moveto(node.previous.lastchild)
        else:
            node.__class__ = DefinitionList
            dt = DefinitionTerm()
            dt.children = node.children
            node.children = []
            node.appendChild(dt)
    elif node.caption.startswith(":"): 
        if node.previous.__class__ == DefinitionList:
            node.__class__ = DefinitionDefinition
            node.moveto(node.previous.lastchild)
            node.caption = ""
        else:
            node.__class__ = Indented
    elif node.caption in _styleNodeMap:
        node.__class__ = _styleNodeMap[node.caption]
        node.caption = ""
    else:
        raise Exception, "unknown style %s" % node.caption # FIXME
    return node

def fixStyles(node):
    if node.__class__ == Style:
        fixStyle(node)
    for c in node.children[:]:
        fixStyles(c)

def removeNodes(node):
    """
    the parser generates empty Node elements that do 
    nothing but group other nodes. we remove them here
    """
    if node.__class__ == Node:
        node.parent.replaceChild(node, node.children)
    for c in node.children[:]:
        removeNodes(c)

def removeNewlines(node):
    """
    remove newlines, tabs, spaces if we are next to a blockNode
    """
    if node.__class__ == Text:
        if node.caption.strip() == u"":
            prev = node.previous or node.parent # previous sibling node or parentnode 
            next = node.next or node.parent.next
            if next.isblocknode or prev.isblocknode: 
                node.parent.removeChild(node)    
        else:
          node.caption = node.caption.replace("\n", " ")
      
    for c in node.children[:]:
        removeNewlines(c)

def removeBreakingReturns(node):
    """
    remove breakingReturns  if we are next to a blockNode
    """
    for c in node.children[:]:
        if c.__class__ == BreakingReturn:
            prev = c.previous or c.parent # previous sibling node or parentnode 
            next = c.next or c.parent.next
            if next.isblocknode or prev.isblocknode: 
                node.removeChild(c)
        removeBreakingReturns(c)
        


def buildAdvancedTree(root): # DO NOT USE WITHOUT CARE
    """
    extends and cleans parse trees
    do not use this funcs without knowing whether these 
    Node modifications fit your problem
    """
    extendClasses(root) 
    fixTagNodes(root)
    removeNodes(root)
    removeNewlines(root)
    fixStyles(root) 
    removeBreakingReturns(root) 



def main():
    import sys
    from mwlib import parser
    from mwlib.dummydb import DummyDB
    import xhtmlwriter
    db = DummyDB()
    
    from mwlib.dummydb import DummyDB
    from mwlib.uparser import parseString
    db = DummyDB()
    
    for x in sys.argv[1:]:
        input = unicode(open(x).read(), 'utf8')
        r = parseString(title=x, raw=input, wikidb=db)
        #parser.show(sys.stderr, r, 0)
        buildAdvancedTree(r)
        parser.show(sys.stderr, r, 0)
        
        """
        x =  r.getClassInChildren(BreakingReturn)
        print x
        """
        
        dbw = xhtmlwriter.MWXHTMLWriter()
        dbw.write(r)
        xhtmlwriter.indent(dbw.root)
        print dbw.asstring()
        


if __name__=="__main__":
    main()
