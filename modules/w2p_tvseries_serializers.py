#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2012 Niphlod <niphlod@gmail.com>
#
# This file is part of w2p_tvseries.
#
# w2p_tvseries is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# w2p_tvseries is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with w2p_tvseries. If not, see <http://www.gnu.org/licenses/>.

from gluon.storage import Storage

import datetime

try:
  from lxml import etree
except ImportError:
  try:
    # Python 2.5
    import xml.etree.cElementTree as etree
  except ImportError:
    try:
      # Python 2.5
      import xml.etree.ElementTree as etree
    except ImportError:
      try:
        # normal cElementTree install
        import cElementTree as etree
      except ImportError:
        try:
          # normal ElementTree install
          import elementtree.ElementTree as etree
        except ImportError:
          print("Failed to import ElementTree from any known place")

from gluon.contrib import simplejson as sj
from w2p_tvseries_utils import tvdb_logger, w2p_tvseries_settings
import os
import shutil

from gluon import current
import thread

locker = thread.allocate_lock()

def w2p_tvseries_serializers_loader(*args, **vars):
    locker.acquire()
    try:
        if not hasattr(w2p_tvseries_serializers_loader, 'w2p_tvseries_serializers_loader_instance'):
            w2p_tvseries_serializers_loader.w2p_tvseries_serializers_loader_instance = w2p_tvseries_xbmc(*args, **vars)
    finally:
        locker.release()

    return w2p_tvseries_serializers_loader.w2p_tvseries_serializers_loader_instance


class w2p_tvseries_xbmc(object):

    def __init__(self):
        self.logger = tvdb_logger('xbmc')

    def log(self, function, message):
        log = self.logger
        log.log(function, message)

    def error(self, function, message):
        log = self.logger
        log.error(function, message)

    def get_season_path(self, series_id, seasonnumber):
        db = current.database
        gs = w2p_tvseries_settings().global_settings()
        path_format = gs.season_path or '%(seasonnumber).2d'

        #season_setting
        rec = db(
            (db.series.id == db.seasons_settings.series_id) &
            (db.seasons_settings.seasonnumber == seasonnumber) &
            (db.series.id == series_id) &
            (db.seasons_settings.tracking == True)
            ).select().first()

        if not rec:
            return None
        path = os.path.join(rec.series.basepath, path_format % dict(seasonnumber=seasonnumber))
        if os.path.exists(path):
            return path
        else:
            return None

    def season_metadata(self, seriesid, seasonnumber):
        fname = 'metadata'
        db = current.database
        ep_tb = db.episodes
        se_tb = db.series
        ss_tb = db.seasons_settings

        missing = db(
            (ss_tb.series_id == seriesid) &
            (ss_tb.seasonnumber == seasonnumber)
            ).select(ss_tb.season_status).first()
        missing = missing and missing.season_status or sj.dumps({})
        missing = sj.loads(missing).get('missing', [])

        xbmc_nfo = db(
            (se_tb.seriesid == ep_tb.seriesid) &
            (se_tb.id == seriesid) &
            (ep_tb.seasonnumber == seasonnumber) &
            (ep_tb.tracking == True) &
            (~ep_tb.epnumber.belongs(missing))
            )

        season_path = self.get_season_path(seriesid, seasonnumber)
        if not season_path:
            err = "Path not found for series %s, number %s" % (seriesid, seasonnumber)
            self.error(fname, err)
            return err

        self.series_nfo(seriesid)

        groups = xbmc_nfo.select(ep_tb.ALL).group_by_value(ep_tb.filename)
        for file, eps in groups.iteritems():
            if len(eps) > 1:
                root = etree.Element('xbmcmultiepisode')
                multi = 1
            else:
                root = etree.Element('episodedetails')
                multi = 0
            for ep in eps:
                if multi:
                    eproot = etree.SubElement(root, 'episodedetails')
                else:
                    eproot = root
                etree.SubElement(eproot, 'title').text = ep.name
                etree.SubElement(eproot, 'season').text = "%s" % ep.seasonnumber
                etree.SubElement(eproot, 'episode').text = "%s" % ep.epnumber
                etree.SubElement(eproot, 'plot').text = ep.overview
                etree.SubElement(eproot, 'aired').text = "%s" % ep.firstaired

            ep_nfo = os.path.join(season_path, "%s.nfo" % os.path.splitext(ep.filename)[0])
            if os.path.exists(ep_nfo) and os.stat(ep_nfo).st_mtime < ep.lastupdated:
                return
            #for multi-eps banner is from last ep only
            banner_img = "%s.tbn" % os.path.splitext(ep_nfo)[0]
            eb_tb = db.episodes_banners
            banner_rec = db(eb_tb.episode_id == ep.id).select().first()
            if banner_rec:
                etree.SubElement(eproot, 'thumb').text = 'thumb://Local'
                filename, stream = eb_tb.banner.retrieve(banner_rec.banner)
                with open(banner_img, 'wb') as g:
                    shutil.copyfileobj(stream, g)

            with open(ep_nfo, 'w') as g:
                self.indent(root)
                content = etree.tostring(root, encoding='utf-8',xml_declaration=True)
                g.write(content)
            self.log(fname, "Written ep info to %s" % (ep_nfo))



    def series_nfo(self, seriesid):
        db = current.database
        infos = db(db.series.id == seriesid).select().first()
        if not infos:
            self.error('series_nfo', "Unable to retrieve infos for series %s" % (seriesid))
            return

        series_nfo = os.path.join(infos.basepath, 'tvshow.nfo')
        if os.path.exists(series_nfo) and os.stat(series_nfo).st_mtime > infos.lastupdated:
            return

        root = etree.Element('tvshow')
        etree.SubElement(root, 'title').text = infos.name
        etree.SubElement(root, 'plot').text = infos.overview
        etree.SubElement(root, 'genre').text = " / ".join(infos.genre)
        etree.SubElement(root, 'status').text = infos.status
        self.indent(root)
        with open(series_nfo, 'w') as g:
            content = etree.tostring(root, encoding='utf-8', xml_declaration=True)
            g.write(content)
        self.log('series_nfo', "Written series info to %s" % (series_nfo))
        sb_tb = db.series_banners
        banner_img = os.path.join(infos.basepath, 'folder.tbn')
        banner_rec = db(sb_tb.series_id == seriesid).select().first()
        if banner_rec:
            filename, stream = sb_tb.banner.retrieve(banner_rec.banner)
            with open(banner_img, 'wb') as g:
                shutil.copyfileobj(stream,g)

    def indent(self, elem, level=0):
        i = "\n" + level*"  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                self.indent(elem, level+1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i