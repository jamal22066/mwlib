"""api.php client, url guessing"""

import urlparse
import urllib
from twisted.internet import reactor, defer
from twisted.web import client 
from twisted.python import failure




try:
    import json
except ImportError:
    import simplejson as json

def loads(s):
    """Potentially remove UTF-8 BOM and call json.loads()"""

    if s and isinstance(s, str) and s[:3] == '\xef\xbb\xbf':
        s = s[3:]
    return json.loads(s)


def merge_data(dst, src):
    todo = [(dst, src)]
    while todo:
        dst, src = todo.pop()
        assert type(dst)==type(src), "cannot merge %r with %r" % (type(dst), type(src))
        
        if isinstance(dst, list):
            dst.extend(src)
        elif isinstance(dst, dict):
            for k, v in src.items():
                if k in dst:
                    todo.append((dst[k], v))
                else:
                    dst[k] = v
    
def guess_api_urls(url):
    """
    @param url: URL of a MediaWiki article
    @type url: str
    
    @returns: list of possible api.php urls
    @rtype: list
    """
    
    try:
        scheme, netloc, path, params, query, fragment = urlparse.urlparse(url)
    except ValueError:
        return []
    
    if not (scheme and netloc):
        return []
    

    path_prefix = ''
    if '/wiki/' in path:
        path_prefix = path[:path.find('/wiki/')]
    elif '/w/' in path:
        path_prefix = path[:path.find('/w/')]
    
    prefix = '%s://%s%s' % (scheme, netloc, path_prefix)

    retval = []
    for path in ('/w/', '/wiki/', '/'):
        base_url = '%s%sapi.php' % (prefix, path)
        retval.append(base_url)
    return retval

def try_api_urls(urls):
    urls = list(urls)
    urls.reverse()

    
    d = defer.Deferred()

    def doit(_):
        if not urls:
            d.callback(None)
            return
        
        url = urls.pop()
        m = mwapi(url)
        old_retry_count = m.max_retry_count
        m.max_retry_count = 1
        
        def got_api(si):
            m.max_retry_count = old_retry_count
            d.callback(m)

        m.ping().addCallbacks(got_api,  doit)
        
    doit(None)
    return d

def find_api_for_url(url):
    return try_api_urls(guess_api_urls(url))

class mwapi(object):
    api_result_limit = 500 # 5000 for bots
    api_request_limit = 20 # at most 50 titles at once

    max_connections = 20
    siteinfo = None
    max_retry_count = 2
    
    def __init__(self, baseurl, script_extension='.php'):
        self.baseurl = baseurl
        self.script_extension = script_extension
        self._todo = []
        self.num_running = 0
        self.qccount = 0
        self.cookies = {}

    def __repr__(self):
        return "<mwapi %s at %s>" % (self.baseurl, hex(id(self)))
    
    def idle(self):
        """Return whether another connection is possible at the moment"""

        return self.num_running < self.max_connections

    def login(self, username, password, domain=None):
        args = dict(action="login",
                    lgname=username.encode("utf-8"), 
                    lgpassword=password.encode("utf-8"), 
                    format="json", 
                    )
        
        if domain is not None:
            args['lgdomain'] = domain.encode('utf-8')
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        postdata = urllib.urlencode(args)
        
        def got_page(res):
            res = loads(res)
            if res["login"]["result"]=="Success":
                return self
            raise RuntimeError("login failed: %r" % (res, ))
            
        return client.getPage(self.baseurl, method="POST",  postdata=postdata, headers=headers,  cookies=self.cookies).addCallback(got_page)
            
    def _fetch(self, url):
        errors = []
        d = defer.Deferred()
        
        def done(val):
            if isinstance(val, failure.Failure):
                errors.append(val)
                if len(errors)<self.max_retry_count:
                    print "retrying: could not fetch %r" % (url,)
                    client.getPage(url, cookies=self.cookies).addCallbacks(done, done)
                else:
                    # print "error: could not fetch %r" % (url,)
                    d.callback(val)
            else:
                d.callback(val)
            
                
        client.getPage(url, cookies=self.cookies).addCallbacks(done, done)
        return d
    
    def _maybe_fetch(self):
        def decref(res):
            self.num_running -= 1
            reactor.callLater(0.0, self._maybe_fetch)
            return res
        
        while self.num_running<self.max_connections and self._todo:
            url, d = self._todo.pop()
            self.num_running += 1
            # print url
            self._fetch(url).addCallbacks(decref, decref).addCallback(loads).chainDeferred(d)


    def _build_url(self,  **kwargs):
        args = {'format': 'json'}
        args.update(**kwargs)
        for k, v in args.items():
            if isinstance(v, unicode):
                args[k] = v.encode('utf-8')
        q = urllib.urlencode(args)
        q = q.replace('%3A', ':') # fix for wrong quoting of url for images
        q = q.replace('%7C', '|') # fix for wrong quoting of API queries (relevant for redirects)

        url = "%s?%s" % (self.baseurl, q)
        return url
    
    def _request(self, **kwargs):
        url = self._build_url(**kwargs)
        
        d=defer.Deferred()
        self._todo.append((url, d))
        reactor.callLater(0.0, self._maybe_fetch)
        return d
        
    def do_request(self, **kwargs):
        retval = {}
        last_qc = [None]
        
        def got_result(data):
            
            try:
                error = data.get("error")
            except:
                print "ERROR:", data, kwargs
                raise
            
            if error:
                return failure.Failure(RuntimeError(error.get("info", "")))

            merge_data(retval, data["query"])
            
            qc = data.get("query-continue", {}).values()
            
            if qc: 
                kw = kwargs.copy()
                for d in qc:
                    for k,v in d.items(): # dict of len(1)
                        kw[str(k)] = v

                if qc == last_qc[0]:
                    print "warning: cannot continue this query:",  self._build_url(**kw)
                    return retval

                last_qc[0] = qc
                        
                self.qccount += 1
                return self._request(**kw).addCallback(got_result)
            return retval
        
        return self._request(**kwargs).addCallback(got_result)

    def ping(self):
        return self._request(action="query", meta="siteinfo",  siprop="general")
        
    def get_siteinfo(self):
        if self.siteinfo is not None:
            return defer.succeed(self.siteinfo)

        siprop = "general namespaces interwikimap namespacealiases magicwords".split()

        def got_err(r):
            siprop.pop()
            if len(siprop)<3:
                return r
            return doit()
        
        def got_it(siteinfo):
            self.siteinfo = siteinfo
            return siteinfo
        
        def doit():
            return self.do_request(action="query", meta="siteinfo", siprop="|".join(siprop)).addCallbacks(got_it, got_err)

        return doit()

    def _update_kwargs(self, kwargs, titles, revids):
        assert titles or revids and not (titles and revids), 'either titles or revids must be set'

        if titles:
            kwargs["titles"] = "|".join(titles)
        if revids:
            kwargs["revids"] = "|".join([str(x) for x in revids])
        
    def fetch_used(self, titles=None, revids=None):
        kwargs = dict(prop="revisions|templates|images",
                      rvprop='ids',
                      imlimit=self.api_result_limit,
                      tllimit=self.api_result_limit)
        if titles:
            kwargs['redirects'] = 1

        self._update_kwargs(kwargs, titles, revids)
        return self.do_request(action="query", **kwargs)
        
    def fetch_pages(self, titles=None, revids=None):        
        kwargs = dict(prop="revisions",
                      rvprop='ids|content',
                      imlimit=self.api_result_limit,
                      tllimit=self.api_result_limit)
        if titles:
            kwargs['redirects'] = 1

        self._update_kwargs(kwargs, titles, revids)
        return self.do_request(action="query", **kwargs)

    def fetch_imageinfo(self, titles, iiurlwidth=800):
        kwargs = dict(prop="imageinfo",
                      iiprop="url|user|comment|url|sha1|metadata|size",
                      iiurlwidth=iiurlwidth)
        
        self._update_kwargs(kwargs, titles, [])
        return self.do_request(action="query", **kwargs)
    
    def get_edits(self, title, revision, rvlimit=500):
        kwargs = {
            'titles': title,
            'redirects': 1,
            'prop': 'revisions',
            'rvprop': 'ids|user|flags|comment|size',
            'rvlimit': rvlimit,
            'rvdir': 'older',
        }
        if revision is not None:
            kwargs['rvstartid'] = revision

        return self.do_request(action="query", **kwargs)
        
    def get_categorymembers(self, cmtitle):
        return self.do_request(action="query", list="categorymembers", cmtitle=cmtitle)
