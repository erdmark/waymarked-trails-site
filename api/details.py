# This file is part of waymarkedtrails.org
# Copyright (C) 2015 Sarah Hoffmann
#
# This is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.

from collections import OrderedDict
from datetime import datetime
import urllib.parse
import urllib.request
import json as jsonlib
import cherrypy
import sqlalchemy as sa
from osgende.tags import TagStore

import config.defaults
import api.common

def _add_names(relinfo, dbres):
    relinfo['id'] = dbres['id']
    # name
    for l in cherrypy.request.locales:
        if l in dbres['intnames']:
            relinfo['name'] = dbres['intnames'][l]
            if relinfo['name'] != dbres['name']:
                relinfo['local_name'] = dbres['name']
            break
    else:
        relinfo['name'] = dbres['name']


@cherrypy.popargs('oid')
class RelationInfo(object):

    def _hierarchy_list(self, rid, subs):
        mapdb = cherrypy.request.app.config['DB']['map']
        r = mapdb.tables.routes.data
        h = mapdb.tables.hierarchy.data

        if subs:
            w = sa.select([h.c.child], distinct=True).where(h.c.parent == rid)
        else:
            w = sa.select([h.c.parent], distinct=True).where(h.c.child == rid)

        sections = sa.select([r.c.id, r.c.name, r.c.intnames, r.c.level])\
                   .where(r.c.id != rid).where(r.c.id.in_(w))

        return [api.common.RouteDict(x)
                 for x in cherrypy.request.db.execute(sections)]


    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self, oid, **params):
        cfg = cherrypy.request.app.config
        mapdb = cfg['DB']['map']
        r = mapdb.tables.routes.data
        o = mapdb.osmdata.relation.data
        sel = sa.select([r.c.id, r.c.name, r.c.intnames, r.c.symbol, r.c.level,
                         o.c.tags,
                         sa.func.ST_length2d_spheroid(sa.func.ST_Transform(r.c.geom,4326),
                             'SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]]').label("length")])

        res = cherrypy.request.db.execute(sel.where(r.c.id==oid)
                                             .where(o.c.id==oid)).first()
        if res is None:
            raise cherrypy.NotFound()

        loctags = TagStore.make_localized(res['tags'], cherrypy.request.locales)

        ret = api.common.RouteDict(res)
        ret['type'] = 'relation'
        ret['symbol_url'] = '%s/symbols/%s/%s.png' % (cfg['Global']['MEDIA_URL'],
                                                      cfg['Global']['BASENAME'],
                                                      str(res['symbol']))
        ret['mapped_length'] = int(res['length'])
        ret.add_if('official_length',
                   loctags.get_length('distance', 'length', unit='m'))
        for tag in ('operator', 'note', 'description'):
            ret.add_if(tag, loctags.get(tag))
        ret.add_if('url', loctags.get_url())
        ret.add_if('wikipedia', loctags.get_wikipedia_tags())

        for name, val in (('subroutes', True), ('superroutes', False)):
            ret.add_if(name, self._hierarchy_list(ret['id'], val))

        ret['tags'] = res['tags']

        return ret

    @cherrypy.expose
    def geom(self, oid):
        return "TODO: geometry of relation %s" % oid

    @cherrypy.expose
    def wikilink(self, oid, **params):
        r = cherrypy.request.app.config['DB']['map'].osmdata.relation.data
        res = cherrypy.request.db.execute(sa.select([r.c.tags]).where(r.c.id==oid)).first()

        if res is None:
            raise cherrpy.NotFound()

        wikientries = TagStore(res['tags']).get_wikipedia_tags()

        if not wikientries:
            raise Http404

        outinfo = None # tuple of language/title
        wikilink = 'http://%s.wikipedia.org/wiki/%s'
        for lang in cherrypy.request.locales:
            if lang in wikientries:
                raise cherrypy.HTTPRedirect(wikilink % (lang, wikientries[lang]))

            for k,v in wikientries.items():
                url = "http://%s.wikipedia.org/w/api.php?action=query&prop=langlinks&titles=%s&llprop=url&&lllang=%s&format=json" % (k,urllib.parse.quote(v.encode('utf8')),lang)
                try:
                    req = urllib.request.Request(url, headers={
                        'User-Agent' : 'Python-urllib/2.7 Routemaps'
                        })
                    data = urllib.request.urlopen(req).read().decode('utf-8')
                    data = jsonlib.loads(data)
                except:
                    continue # oh well, we tried
                (pgid, data) = data["query"]["pages"].popitem()
                if 'langlinks' in data:
                    raise cherrypy.HTTPRedirect(data['langlinks'][0]['url'])
        else:
            # given up to find a requested language
            raise cherrypy.HTTPRedirect(wikilink % wikientries.popitem())

        raise cherrypy.HTTPRedirect('http://%s.wikipedia.org/wiki/%s' % outlinfo)


    @cherrypy.expose
    def gpx(self, oid):
        return "TODO: GPX of relation %s" % oid

