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

import os
import re
from gluon.storage import Storage
try:
    import requests as req
except:
    raise ImportError , "requests module is needed: http://docs.python-requests.org"

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

import hashlib
import os
import zipfile
import urllib
try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO
import re
import datetime
import time
from gluon.contrib import simplejson
from w2p_tvseries_utils import tvdb_logger_loader, Meddler, w2p_tvseries_settings

import thread

locker = thread.allocate_lock()

from gluon import current

def w2p_tvseries_tvdb_loader(*args, **vars):
    locker.acquire()
    try:
        if not hasattr(w2p_tvseries_tvdb_loader, '_instance'):
            w2p_tvseries_tvdb_loader._instance = w2p_tvseries_tvdb(*args, **vars)
    finally:
        locker.release()
    return w2p_tvseries_tvdb_loader._instance

def w2p_tvseries_ren_loader(*args, **vars):
    locker.acquire()
    try:
        if not hasattr(w2p_tvseries_ren_loader, '_instance'):
            w2p_tvseries_ren_loader._instance = w2p_tvseries_tvren(*args, **vars)
    finally:
        locker.release()
    return w2p_tvseries_ren_loader._instance


class w2p_tvseries_tvdb(object):
    def __init__(self):
        db = current.w2p_tvseries.database
        self.logger = tvdb_logger_loader('tvdb')
        self.req = req.session(headers = {'User-Agent' : 'w2p_tvdb'}, config= {'max_retries': 5}, timeout=10)
        self.apikey = 'C833E23D89D5FD35'
        self.mirrors_url = "http://thetvdb.com/api/%s/mirrors.xml" % (self.apikey)
        self.languages = {
            'de' : ('Deutsch', 14),
            'it': ('Italiano', 15),
            'es' : ('Español', 16),
            'fr' : ('Français', 17),
            'en' : ('English', 7),
            'da' : ('Dansk', 10),
            'fi' : ('Suomeksi', 11),
            'nl' : ('Nederlands', 13),
            'pl' : ('Polski', 18),
            'hu' : ('Magyar', 19),
            'el' : ('Ελληνικά', 20),
            'tr' : ('Türkçe', 21),
            'ru' : ('русский язык', 22),
            'he' : (' עברית', 24),
            'ja' : ('日本語', 25),
            'pt' : ('Português', 26),
            'zh' : ('中文', 27),
            'cs' : ('čeština', 28),
            'sl' : ('Slovenski', 30),
            'hr' : ('Hrvatski', 31),
            'ko' : ('한국어', 32),
            'sv' : ('Svenska', 8),
            'no' : ('Norsk', 9)
            }
        self.mappers = tvdb_mappers()
        self.mirrors = []
        self.choose_mirror()

    def log(self, function, message):
        log = self.logger
        log.log(function, message)

    def error(self, function, message):
        log = self.logger
        log.error(function, message)

    def downloader(self, url, raw=False, verbose=False):
        db = current.w2p_tvseries.database
        ct = db.urlcache
        cachekey = hashlib.md5(url).hexdigest()
        timelimit = datetime.datetime.utcnow() - datetime.timedelta(hours=3)
        cached = db((ct.kkey == cachekey) & (ct.inserted_on > timelimit)).select().first()
        if cached:
            if verbose:
                self.log('downloader', '%s fetched from cache' % (url))
            return cached.value
        else:
            r = self.req.get(url)
            r.raise_for_status()
            if not raw:
                content = r.text
            else:
                content = r.content
            ct.update_or_insert(ct.kkey==cachekey, value=content, inserted_on=datetime.datetime.utcnow(), kkey=cachekey)
            db.commit()
        if not raw:
            content = content.encode('utf-8')
        if verbose:
            self.log('downloader', '%s fetched from internet' % (url))
        return content

    def retrieve_mirrors(self):
        url = self.mirrors_url
        content = self.downloader(url)
        self.map_mirrors(content)

    def map_mirrors(self, xml):
        root = etree.fromstring(xml)
        mirrors = root.findall('Mirror')
        self.mirrors = {}
        for mirr in mirrors:
            mirpath = mirr.findtext('mirrorpath')
            typemask = mirr.findtext('typemask')
            self.mirrors[mirpath] = int(typemask)

    def choose_mirror(self, operation=''):
        if not self.mirrors:
            self.retrieve_mirrors()
        for a in self.mirrors:
            if self.mirrors[a] == 7:
                self.target_mirror = a

    def search_series(self, seriesname, language='all'):
        self.log('search_series', "Season search (%s)" % (seriesname))
        vars = {'seriesname' : seriesname, 'language' : language}
        vars = urllib.urlencode(vars)
        url = "%s/api/GetSeries.php?%s" % (self.target_mirror, vars)
        content = self.downloader(url)

        return self.mappers.search_series_mapper(content)

    def add_series(self, seriesid, language='en'):
        self.log('add_series', 'updating series %s' % (seriesid))
        url = "%s/api/%s/series/%s/all/%s.zip" % (self.target_mirror, self.apikey, seriesid, language)
        content = self.downloader(url, raw=True)
        return self.mappers.add_series_mapper(content, language)

    def global_reset(self):
        db = current.w2p_tvseries.database
        self.log('global_reset', "Instantiated")
        gs_tb = db.global_settings
        #series I own
        se_tb = db.series
        series = db(se_tb.id>0).select(se_tb.seriesid, se_tb.language)
        series = [(row.seriesid, row.language) for row in series]
        db(se_tb.id>0).update(lastupdated = se_tb.lastupdated - 10000)
        for id, language in series:
            self.log('global_reset', "Re-add Series (%s)" % (id))
            self.add_series(id, language)
        now = int(time.mktime(datetime.datetime.utcnow().timetuple()))
        db(gs_tb.kkey == 'update_time').update(value=now)
        self.log('global_reset', "Finished")

    def global_update(self, mode='auto'):
        db = current.w2p_tvseries.database
        self.log('global_update', "Global update (%s)" % (mode))
        gs_tb = db.global_settings
        lastupdate = db(gs_tb.kkey == 'update_time').select().first()
        lastupdate = lastupdate and int(lastupdate.value) or None
        if lastupdate == None:
            gs_tb.insert(kkey='update_time', value=0)
            lastupdate = 0
        #guess what update is more suited (day, week, month)
        daydur = 24*60*60
        weekdur = daydur * 7
        monthdur = daydur * 30
        elapsed = int(time.mktime(datetime.datetime.utcnow().timetuple())) - lastupdate
        if mode == 'auto':
            if elapsed < daydur:
                mode = 'day'
                self.log('global_update', 'update with mode day')
            elif daydur <= elapsed < weekdur:
                mode = 'week'
                self.log('global_update', 'update with mode week')
            elif weekdur <= elapsed < monthdur:
                mode = 'month'
                self.log('global_update', 'update with mode month')
            elif elapsed > monthdur:
                self.log('global_update', 'update with mode all')
                self.global_reset()
                return 'all'

        url = "%s/api/%s/updates/updates_%s.zip" % (self.target_mirror, self.apikey, mode)
        content = self.downloader(url, raw=True)
        lastupdated, se_up, ep_up, ba_up = self.mappers.global_update_mapper(content)
        #series that I own
        se_tb = db.series
        myseries = db(se_tb.id>0).select(se_tb.seriesid, se_tb.lastupdated)
        myseries = dict([(row.seriesid, row.lastupdated) for row in myseries])
        #series that were updated
        se_updated = {}
        for series in se_up:
            id = series.findtext('id')
            utime = series.findtext('time')
            se_updated[int(id)] = int(utime)

        #find all series that I own that are in updates
        se_updated_set = set(se_updated.keys())
        myseries_set = set(myseries.keys())
        for a in se_updated_set & myseries_set:
            #if lastupdate from updates file is greater, I have to update the series
            if se_updated[a] > myseries[a]:
                self.series_update(a)

        #episodes that I own
        ep_tb = db.episodes
        myepisodes = db(ep_tb.id>0).select(ep_tb.episodeid, ep_tb.lastupdated)
        myepisodes = dict([(row.episodeid, row.lastupdated) for row in myepisodes])
        #episodes that were updated
        ep_updated = {}
        for a in ep_up:
            id = a.findtext('id')
            utime = a.findtext('time')
            ep_updated[int(id)] = int(utime)

        ep_updated_set = set(ep_updated.keys())
        myepisodes_set = set(myepisodes.keys())

        for a in ep_updated_set & myepisodes_set:
            #if lastupdate from updates file is greater, I have to update the episode
            if ep_updated[a] > myepisodes[a]:
                self.episode_update(a)

        self.log('global_update', 'updating update_time')
        db(gs_tb.kkey == 'update_time').update(value=lastupdated)
        db.commit()
        return mode

    def series_update(self, seriesid):
        db = current.w2p_tvseries.database
        self.log('series_update', 'updating series %s' % (seriesid))
        se_tb = db.series
        #detect language of my series
        language = db(se_tb.seriesid == seriesid).select(se_tb.language).first()
        if language:
            language = language.language
        else:
            language = 'en'
        url = "%s/api/%s/series/%s/%s.xml" % (self.target_mirror, self.apikey, seriesid, language)
        content = self.downloader(url)
        node = etree.fromstring(content)
        node = node.find('Series')
        self.mappers.series_mapper(node, language)

    def episode_update(self, episodeid):
        db = current.w2p_tvseries.database
        self.log('episode_update', 'updating episode %s' % (episodeid))
        ep_tb = db.episodes
        #detect language of my episode
        language = db(ep_tb.episodeid == episodeid).select(ep_tb.language).first()
        if language:
            language = language.language
        else:
            language = 'en'
        url = "%s/api/%s/episodes/%s/%s.xml" % (self.target_mirror, self.apikey, episodeid, language)
        content = self.downloader(url)
        node = etree.fromstring(content)
        self.mappers.episode_mapper(node, language)

    def episodes_banner_update_global(self):
        db = current.w2p_tvseries.database
        ep_tb = db.episodes
        eb_tb = db.episodes_banners
        se_tb = db.series
        ss_tb = db.seasons_settings
        banners_to_check = db(
            (ss_tb.tracking == True) &
            (ss_tb.series_id == se_tb.id) &
            (ss_tb.seasonnumber == ep_tb.seasonnumber) &
            (se_tb.seriesid == ep_tb.seriesid) &
            (eb_tb.episode_id == ep_tb.id) &
            (eb_tb.url <> '') &
            (
                (eb_tb.banner == '') |
                (eb_tb.banner == None)
            )
            ).select(eb_tb.id)

        for row in banners_to_check:
            self.episode_banner_update(row.id)

    def series_banner_update_global(self):
        db = current.w2p_tvseries.database
        sb_tb = db.series_banners
        series_to_check = db(
            (sb_tb.url <> '') &
            (
                (sb_tb.banner == '') |
                (sb_tb.banner == None)
            )
        ).select()
        for row in series_to_check:
            self.series_banner_update(row.id)

    def episode_banner_update(self, episodeid):
        db = current.w2p_tvseries.database
        eb_tb = db.episodes_banners
        rec = db(eb_tb.id == episodeid).select().first()
        self.log('ep_banner', "Updating banner for episode %s" % (rec.id))
        url = rec.url
        url = "%s/banners/%s" % (self.target_mirror, url)
        ext = url.split('.')[-1]
        filename = "episode_banner_%s.%s" % (episodeid, ext)
        content = self.downloader(url, raw=True)
        inm_file = StringIO()
        inm_file.write(content)
        inm_file.seek(0)
        db(eb_tb.id == episodeid).update(banner=eb_tb.banner.store(inm_file, filename))

    def series_banner_update(self, banner_id):
        db = current.w2p_tvseries.database
        sb_tb = db.series_banners
        rec = db(sb_tb.id == banner_id).select().first()
        self.log('se_banner', "Updating banner for series %s" % (rec.id))
        url = rec.url
        url = "%s/banners/%s" % (self.target_mirror, url)
        ext = url.split('.')[-1]
        filename = "series_banner_%s.%s" % (banner_id, ext)
        content = self.downloader(url, raw=True)
        inm_file = StringIO()
        inm_file.write(content)
        inm_file.seek(0)
        db(sb_tb.id == banner_id).update(banner=sb_tb.banner.store(inm_file, filename))


class tvdb_mappers(object):

    def __init__(self):
        self.logger = tvdb_logger_loader('tvdb_mappers')

    def log(self, function, message):
        log = self.logger
        log.log(function, message)

    def error(self, function, message):
        log = self.logger
        log.error(function, message)

    def search_series_mapper(self, xml):
        root = etree.fromstring(xml)
        series = []
        for a in root.findall('Series'):
            id = a.findtext('seriesid')
            language = a.findtext('language')
            name = a.findtext('SeriesName')
            overview = a.findtext('Overview')
            series.append((id, language, name, overview))
        return series

    def add_series_mapper(self, archive, language):
        self.log('add_series_mapper', "Mapping Series to Add")
        inm_file = StringIO()
        inm_file.write(archive)
        series_archive = zipfile.ZipFile(inm_file)
        mainfile = series_archive.read("%s.xml" % language)
        root = etree.fromstring(mainfile)
        series_node = root.find('Series')
        rtn = self.series_mapper(series_node, language)
        episodes_node = root.findall('Episode')
        self.episode_mapper(episodes_node, language)
        return rtn

    def series_mapper(self, xmlnode, language):
        db = current.w2p_tvseries.database
        se_tb = db.series
        ba_tb = db.series_banners
        record = Storage()
        record.language = language
        record.seriesid = xmlnode.findtext('id')
        record.genre = xmlnode.findtext('Genre')
        record.overview = xmlnode.findtext('Overview')
        record.name = xmlnode.findtext('SeriesName')
        record.status = xmlnode.findtext('Status')
        record.lastupdated = xmlnode.findtext('lastupdated')
        record.genre = [a for a in record.genre.split('|') if a <> '']
        banner = xmlnode.findtext('banner')
        self.log('series_mapper', 'mapping series %s (%s)' % (record.name, record.seriesid))
        if record.seriesid:
            condition = (se_tb.seriesid == record.seriesid)
            id = se_tb.update_or_insert(condition, **record)
            if not id:
                id = db(condition).select().first().id
            condition = (ba_tb.series_id == id)
            ba_tb.update_or_insert(condition, url=banner, series_id=id)
            db.commit()
            return id

    def episode_mapper(self, xmlnodes, language):
        db = current.w2p_tvseries.database
        ep_tb = db.episodes
        eb_tb = db.episodes_banners
        records = []
        for episode in xmlnodes:
            record = Storage()
            record.firstaired = episode.findtext('FirstAired')
            record.seriesid = episode.findtext('seriesid')
            record.seasonid = episode.findtext('seasonid')
            record.language = language
            record.seasonnumber = episode.findtext('SeasonNumber')
            record.name = episode.findtext('EpisodeName')
            record.epnumber = episode.findtext('EpisodeNumber')
            record.absolute_number = episode.findtext('absolute_number')
            record.overview = episode.findtext('Overview')
            record.lastupdated = episode.findtext('lastupdated')
            record.episodeid = episode.findtext('id')
            banner = episode.findtext('filename')
            self.log('episode_mapper', "Mapping episode %s (%s)" % (record.name, record.episodeid))
            try:
                record.firstaired = datetime.datetime.strptime(record.firstaired, '%Y-%m-%d')
            except ValueError:
                record.firstaired = datetime.datetime(2050, 1, 1)
            condition = (ep_tb.episodeid == record.episodeid)
            id = ep_tb.update_or_insert(condition, **record)
            if not id:
                id = db(condition).select().first().id
            records.append(id)
            condition = eb_tb.episode_id == id
            eb_tb.update_or_insert(condition, url=banner, episode_id=id)

        db.commit()
        return records

    def global_update_mapper(self, archive):
        inm_file = StringIO()
        inm_file.write(archive)
        updates_archive = zipfile.ZipFile(inm_file)
        for file in updates_archive.namelist():
            update_file = updates_archive.read(file)
            update_root = etree.fromstring(update_file)
            update_time = update_root.attrib['time']
            series_to_update = update_root.findall("Series")
            episodes_to_update = update_root.findall("Episode")
            banners_to_update = update_root.findall("Banner")
            return update_time, series_to_update, episodes_to_update, banners_to_update


class w2p_tvseries_tvren(object):

    def __init__(self):
        self.video_ext = ['.avi', '.mkv', '.mp4', '.3gp']
        self.subs_ext = ['.srt', '.ass']
        self.logger = tvdb_logger_loader('tvren')
        self.meddler = Meddler()

    def log(self, function, message):
        log = self.logger
        log.log(function, message)

    def error(self, function, message):
        log = self.logger
        log.error(function, message)

    def slugify(self, value):
        """taken from web2py's urlify"""
        import unicodedata
        s = value
        s = s.decode('utf-8')                 # to utf-8
        s = unicodedata.normalize('NFKD', s)  # normalize eg è => e, ñ => n
        s = s.encode('ASCII', 'ignore')       # encode as ASCII
        s = re.sub('&\w+;', '', s)            # strip html entities
        s = re.sub('[^\w\- ]', '', s)          # strip all but alphanumeric/underscore/hyphen/space
        s = re.sub('[-_][-_]+', '-', s)       # collapse strings of hyphens
        s = s.strip('-')                      # remove leading and trailing hyphens
        return s[:150]                        # 150 chars will be sufficient

    def check(self, seriesid, seasonnumber, mode='video'):
        db = current.w2p_tvseries.database
        se_tb = db.series
        ep_tb = db.episodes
        ss_tb = db.seasons_settings
        gs = w2p_tvseries_settings().global_settings()

        if mode == 'video':
            check_exts = self.video_ext
        elif mode == 'subs':
            check_exts = self.subs_ext

        path_format = gs.path_format or '%(seasonnumber).2d'

        rec = db((se_tb.id == seriesid) &
                       (ss_tb.tracking == True) &
                       (ss_tb.series_id == se_tb.id) &
                       (ss_tb.seasonnumber == seasonnumber)
                ).select().first()

        bpath = rec and rec.series.basepath or ''
        name = rec and rec.series.name or ''

        if bpath == '':
            self.error('check', "basepath not found (%s season %s)" % (name, seasonnumber))
            return dict(seriesid=seriesid, seasonnumber=seasonnumber, rename=[], missing=[], errors='basepath not found')

        path = os.path.join(bpath, path_format % dict(seasonnumber = rec.seasons_settings.seasonnumber))
        if not os.path.exists(path):
            self.error('check', "%s path not found (%s season %s)" % (path, name, seasonnumber))
            return dict(seriesid=seriesid, seasonnumber=seasonnumber, rename=[], missing=[], errors='path not found')

        lista = []

        for a in os.listdir(path):
            file = os.path.join(path, a)
            if os.path.isfile(file):
                if os.path.splitext(file)[1] in check_exts:
                  lista.append(file)

        ep_tb = db.episodes
        se_tb = db.series
        eplist = db(
                (se_tb.id == seriesid) &
                (ep_tb.seriesid == se_tb.seriesid) &
                (ep_tb.seasonnumber == seasonnumber) &
                (ep_tb.firstaired < datetime.datetime.utcnow()) &
                (ep_tb.tracking == True)
                    ).select(ep_tb.seasonnumber, ep_tb.epnumber, ep_tb.name)
        eplist_dict = {}
        for row in eplist:
            eplist_dict[row.epnumber] = row.name
        self.default_format = "%(seriesname)s - S%(seasonnumber).2dE%(number)s - %(name)s%(ext)s"

        to_rename = []
        episodes_matching = []
        matching = []

        for file_ in lista:
            file = os.path.split(file_)[1]
            x = 0
            match = self.meddler.analyze(file)
            if match.reason:
                continue
            matching.append((file_, match))
            if len(match.episodes)>0:
                for ep in match.episodes:
                    episodes_matching.append(("%.2d" % ep))

        missing = []
        errors = []
        for a in eplist_dict:
            if "%.2d" % (int(a)) not in episodes_matching:
                missing.append(a)

        if len(lista) == 0:
            rtn = dict(seriesid=seriesid, seasonnumber=seasonnumber, rename=[], missing=missing, errors=errors)
            return rtn

        for a in matching:
            file, match = a
            origext = os.path.splitext(file)[1]
            origpath, origfile = os.path.split(file)
            name = []
            number = []
            if match.reason:
                errors.append(file)
                continue
            if len(match.episodes)>1:
                for ep in match.episodes:
                    #(we have a episode, we don't have a record for it)
                    name_ = eplist_dict.get(int(ep), 'WEDONTHAVEARECORDFORTHIS')
                    if name == 'WEDONTHAVEARECORDFORTHIS' and file not in errors:
                        errors.append(file)
                        continue
                    name.append(name_)
                    number.append(ep)
                name = '-'.join(name)
                number = '-'.join(["%.2d" % i for i in number])
            else:
                #find name, if not, continue (we have a episode, we don't have a record for it)
                name = eplist_dict.get(int(match.episodes[0]), 'WEDONTHAVEARECORDFORTHIS')
                if name == 'WEDONTHAVEARECORDFORTHIS':
                    errors.append(file)
                    continue
                number = "%.2d" % int(match.episodes[0])
            newname = self.default_format % dict(seriesname = self.slugify(rec.series.name),
                                                 seasonnumber = int(match.seasonnumber),
                                                 number = number,
                                                 name = self.slugify(name),
                                                 ext = origext
                                                 )
            if mode == 'video':
                db(
                    (ep_tb.epnumber.belongs(match.episodes)) &
                    (ep_tb.seasonnumber == seasonnumber) &
                    (ep_tb.seriesid == rec.series.seriesid)
                ).update(filename=newname)
            if newname != origfile:
                to_rename.append((file, os.path.join(origpath, newname)))
        self.log('check', "Completed check for %s season %s" % (rec.series.name, seasonnumber))
        rtn = dict(seriesid=seriesid, seasonnumber=seasonnumber, rename=to_rename, missing=missing, errors=errors)
        return rtn

    def check_path(self, seriesid, seasonnumber, create=False):
        db = current.w2p_tvseries.database
        se_tb = db.series
        ss_tb = db.seasons_settings
        gs = w2p_tvseries_settings().global_settings()

        path_format = gs.path_format or '%(seasonnumber).2d'

        #check path existance and writability
        season = db(
            (se_tb.id == seriesid) &
            (ss_tb.series_id == se_tb.id) &
            (ss_tb.seasonnumber == seasonnumber)
            ).select().first()

        name = season and season.series.name or ''
        series_basepath = season and season.series.basepath or ''
        if series_basepath == '':
            self.error('check_path', "No basepath found for %s season %s" % (name, seasonnumber))
            return dict(err='no basepath', series=season.series.name, seasonnumber=seasonnumber)
        season_path = os.path.join(series_basepath, path_format % dict(seasonnumber=int(seasonnumber)))
        if os.path.exists(season_path) and os.access(season_path, os.W_OK):
            return dict(ok='1')
        else:
            if create:
                try:
                    os.makedirs(season_path)
                    self.log('check_path', 'Created folder %s' % (season_path))
                    return dict(ok='1')
                except OSError, e:
                    self.error('check_path', 'error creating folder %s (%s)' % (season_path, e))
                    return dict(err='error creating folder %s (%s)' % (season_path, e) ,
                                                 series=season.series.name, seasonnumber=seasonnumber )
            return dict(dir=season_path, message="dir %s doesn't exist, can I create it?" % season_path,
                                         series=season.series.name, seasonnumber=seasonnumber, seriesid=seriesid)

    def rename(self, seriesid, seasonnumber):
        db = current.w2p_tvseries.database
        self.log('rename', "Checking for series with id %s and season %s" % (seriesid, seasonnumber))
        bit = db.rename_log
        ss_tb = db.seasons_settings
        datarec = db(
                       (ss_tb.series_id == seriesid) &
                       (ss_tb.seasonnumber == seasonnumber)
                       ).select().first()
        data = datarec and datarec.season_status
        data = simplejson.loads(data)
        if not data:
            return
        rename = data['rename']

        now = datetime.datetime.now()
        db.commit()
        while True:
            try:
                rename_ = rename.pop()
            except:
                break
            source, dest = rename_
            self.log('rename', "trying to do %s --> %s" % (os.path.basename(source), os.path.basename(dest)))
            if os.path.exists(dest) or not os.path.exists(source):
                continue
            try:
                bit.insert(series_id=seriesid,
                           seasonnumber=seasonnumber,
                           file_from=source,
                           file_to=dest)
                os.rename(source, dest)
                db.commit()
            except:
                db.rollback()
        data['rename'] = rename
        datarec.update_record(season_status=simplejson.dumps(data), updated_on=now)
        db.commit()
