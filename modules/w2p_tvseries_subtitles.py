#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2013 Niphlod <niphlod@gmail.com>
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

try:
    import requests as req
except:
    raise ImportError , "requests module is needed: http://docs.python-requests.org"

import hashlib
import datetime
import os
from gluon.contrib import simplejson
import re
try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO
import zipfile
import gzip
from w2p_tvseries_utils import tvdb_logger, w2p_tvseries_settings
from xmlrpclib import ServerProxy
import thread
locker = thread.allocate_lock()

from gluon import current


def w2p_tvseries_sub_loader(*args, **vars):
    locker.acquire()
    type = args[0]
    args = args[1:]
    try:
        if not hasattr(w2p_tvseries_sub_loader, '_instance_%s' % (type)):
            types = dict(
                itasa=ItasaDownloader,
                opensubtitles=OpenSubtitlesDownloader,
            )
            setattr(w2p_tvseries_sub_loader, '_instance_%s' % (type),  types[type](*args, **vars))
    finally:
        locker.release()
    return getattr(w2p_tvseries_sub_loader, '_instance_%s' % (type))


class SubDownloader(object):
    def __init__(self, verbose=False):
        self.logger = tvdb_logger('subs')
        self.req = req.session(headers = {'User-Agent' : 'w2p_tvdb'}, config= {'max_retries': 5}, timeout=3)
        self.verbose = verbose

    def log(self, function, message):
        log = self.logger
        log.log(function, message)

    def error(self, function, message):
        log = self.logger
        log.error(function, message)

    def put_in_cache(self, url, content, mode='insert'):
        db = current.w2p_tvseries.database
        ct = db.urlcache
        cachekey = hashlib.md5(url).hexdigest()
        if mode == 'insert':
            ct.update_or_insert(ct.kkey==cachekey, value=content, inserted_on=datetime.datetime.utcnow(), kkey=cachekey)
        else:
            db(ct.kkey == cachekey).delete()
        db.commit()

    def downloader(self, url, hours=3):
        db = current.w2p_tvseries.database
        ct = db.urlcache
        cachekey = hashlib.md5(url).hexdigest()
        timelimit = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
        cached = db((ct.kkey == cachekey) & (ct.inserted_on > timelimit)).select().first()
        if cached:
            if self.verbose:
                self.log('downloader', "Cache (%s): Getting url: %s" % (cachekey, url))
            return cached.value
        else:
            r = self.req.get(url)
            r.raise_for_status()
            content = r.content
            self.put_in_cache(url, content)
        if self.verbose:
            self.log('downloader', "Internet: Getting url: %s" % (url))
        return content

    def get_missing(self, seriesid, seasonnumber):
        db = current.w2p_tvseries.database
        fname = 'get_missing'
        ss_tb = db.seasons_settings
        se_tb = db.series
        gs = w2p_tvseries_settings().global_settings()

        path_format = gs.path_format or '%(seasonnumber).2d'

        season = db(
           (ss_tb.series_id == seriesid) &
           (ss_tb.seasonnumber == seasonnumber) &
           (se_tb.id == ss_tb.series_id)
            ).select().first()

        bpath = season and season.series.basepath or ''

        if bpath == '':
            return dict(err='No basepath found')

        path = os.path.join(bpath, path_format % dict(seasonnumber = season.seasons_settings.seasonnumber))

        tracking = season and season.seasons_settings.subtitle_tracking or None
        sub_settings = season and season.seasons_settings.subtitle_settings or None
        quality = simplejson.loads(sub_settings).get('quality', 'Normal')
        language = simplejson.loads(sub_settings).get('language', 'eng')
        name = season and season.series.name or None
        id = season and season.seasons_settings.id or None
        if tracking and name and id:
            data = simplejson.loads(season.seasons_settings.season_status)
            missingsubs = data.get('missingsubs', [])
            if len(missingsubs) == 0:
                message="No missing subs for %s, season %s, type %s, in path %s" % (name, seasonnumber, quality, path)
                self.log(fname, message)
                return dict(message=message)
            errs = ''
            subtitles_list, errs = self.search_subtitles(id, name, seasonnumber, missingsubs, quality, language)
            if errs <> '':
                return dict(err=errs)
            else:
                res = self.download_subtitles(subtitles_list, path)
                found = [a['number'] for a in subtitles_list]
                not_found = []
                for a in missingsubs:
                    if a not in found:
                        not_found.append(a)
                data['missingsubs'] = not_found
                data = simplejson.dumps(data)
                db(ss_tb.id == season.seasons_settings.id).update(season_status=data)
                db.commit()
                message="Searching subs for %s, season %s, type %s, in path %s, were %s, are %s" % (name, seasonnumber, quality, path, missingsubs, not_found)
                self.log(fname, message)
                return dict(message=message)
        else:
            err = 'settings deny to download subtitles'
            self.error('fetch_subtitles', err)
            return dict(err=err)

    def download_subtitles(self, subtitles_list, season_path):
        """download subtitles_list to season_path folder"""
        pass

    def search_subtitles(self, id, tvshow, seasonnumber, missingsubs, quality, language):
        """
        returns subtitles_list, errors
        every subtitle is a dict containing
        {'number': episode, 'season': season, 'filename': filename, 'id' : id, 'type' : type, 'link' : downloadlink)}
        """
        pass



class OpenSubtitlesDownloader(SubDownloader):
    def __init__(self, verbose=False):
        super(OpenSubtitlesDownloader, self).__init__(verbose)


    def rpc_call(self, searchlist):
        base_api = "http://api.opensubtitles.org/xml-rpc"
        key = '&'.join(["hash=%s&size=%s&language=%s" % (a['moviehash'], a['moviebytesize'], a['sublanguageid']) for a in searchlist])
        key = base_api + '?' + key
        db = current.w2p_tvseries.database
        ct = db.urlcache
        cachekey = hashlib.md5(key).hexdigest()
        timelimit = datetime.datetime.utcnow() - datetime.timedelta(hours=3)
        cached = db((ct.kkey == cachekey) & (ct.inserted_on > timelimit)).select().first()
        if cached:
            if self.verbose:
                self.log('rpc_call', "Cache (%s): Getting url: %s" % (cachekey, key))
            return cached.value
        else:
            server = ServerProxy(base_api)
            session =  server.LogIn("","","en","OS Test User Agent")
            token = session["token"]
            moviesList = server.SearchSubtitles(token, searchlist)
            content = simplejson.dumps(moviesList)
            self.put_in_cache(key, content)
            server.Logout(token)
        if self.verbose:
            self.log('rpc_call', "Internet: Getting url: %s" % (key))
        return content

    def search_subtitles(self, id, tvshow, seasonnumber, missingsubs, quality, language='eng'):
        fname = 'search'
        db = current.w2p_tvseries.database
        me_tb = db.episodes_metadata
        ep_tb = db.episodes
        ss_tb = db.seasons_settings
        errors = []
        #can download only the one I know the hash of
        avail = db(
            (ss_tb.id == id) &
            (me_tb.series_id == ss_tb.series_id) &
            (me_tb.seasonnumber == ss_tb.seasonnumber) &
            (me_tb.episode_id == ep_tb.id) &
            (ep_tb.tracking == True) &
            (me_tb.osdb <> '') &
            (me_tb.osdb != None)
            ).select()

        searchlist = []
        matches = {}
        for row in avail:
            if not os.path.exists(row.episodes_metadata.filename):
                continue
            matches[row.episodes_metadata.osdb] = dict(
                    seasonnumber=seasonnumber,
                    number=row.episodes.epnumber,
                )
            searchlist.append(
                dict(
                    moviehash = row.episodes_metadata.osdb,
                    moviebytesize = str(row.episodes_metadata.filesize),
                    sublanguageid = language
                )
            )

        res = self.rpc_call(searchlist)
        data = simplejson.loads(res)
        if not data['data']:
            err = "No subs found"
            errors.append(err)
            self.error(fname, err)
            return [], errors

        sublist = data['data']
        res = []
        for k,v in matches.iteritems():
            for sub in sublist:
                if sub['MovieHash'] == k:
                    if int(sub['SeriesEpisode']) == v['number'] and int(sub['SeriesSeason']) == v['seasonnumber']:
                        """{'number': episode, 'season': season, 'filename': filename, 'id' : id, 'type' : type, 'link' : downloadlink)}"""
                        res.append(
                            dict(
                                number = v['number'],
                                season = v['seasonnumber'],
                                filename = sub['SubFileName'],
                                id = sub['IDSubtitle'],
                                type = type,
                                link = sub['SubDownloadLink']
                            )
                        )
                        #take the first, usually it's the better
                        break

        return res, ''

    def download_subtitles(self, subtitles_list, seasonpath):
        fname = 'download'
        for subtitle in subtitles_list:
            content = self.downloader(subtitle['link'])
            if content is not None:
                try:
                    inm_file = StringIO(content)
                    archive = gzip.GzipFile(fileobj=inm_file)
                    path = os.path.join(seasonpath, subtitle['filename'])
                    i = 0
                    while i<100:
                        if not os.path.exists(path):
                            break
                        i += 1
                        filesplit = os.path.splitext(path)
                        if filesplit[1] == '':
                            filesplit[1] = '.srt'
                        path = "%s.%s%s" % (filesplit[0], i, filesplit[1])
                    self.log(fname, 'Extracting to %s' % (path))
                    subtext = archive.read()
                    with open(path, 'wb') as g:
                        g.write(subtext)
                    inm_file.close()
                    archive.close()
                except:
                    self.error(fname, "Error downloading sub")
            else:
                self.error(fname, "No content returned, no sub :(")


class ItasaDownloader(SubDownloader):
    def __init__(self, verbose=False):
        super(ItasaDownloader, self).__init__(verbose)
        db = current.w2p_tvseries.database
        self.main_url = "http://www.italiansubs.net/"
        self.req = req.session(headers={'Referer': self.main_url, 'User-Agent' : 'w2p_tvdb'}, config={'max_retries': 5}, timeout=3) #{'verbose': sys.stderr})
        gs = w2p_tvseries_settings().global_settings()
        self.username = gs.itasa_username
        self.password = gs.itasa_password

        self.logged_in = False

        #<input type="hidden" name="return" value="aHR0cDovL3d3dy5pdGFsaWFuc3Vicy5uZXQv" /><input type="hidden" name="c10b48443ee5730c9b5a0927736bd09f" value="1" />
        self.unique_pattern = '<input type="hidden" name="return" value="([^\n\r\t ]+?)" /><input type="hidden" name="([^\n\r\t ]+?)" value="([^\n\r\t ]+?)" />'
        #<a href="http://www.italiansubs.net/index.php?option=com_remository&amp;Itemid=6&amp;func=select&amp;id=1170"> Castle</a>
        self.show_pattern = '<a href="http://www\.italiansubs\.net/(index.php\?option=com_remository&amp;Itemid=\d+&amp;func=select&amp;id=[^\n\r\t ]+?)"> %s</a>'
        #href="http://www.italiansubs.net/index.php?option=com_remository&amp;Itemid=6&amp;func=select&amp;id=1171"> Stagione 1</a>
        self.season_pattern = '<a href="http://www\.italiansubs\.net/(index.php\?option=com_remository&amp;Itemid=\d+?&amp;func=select&amp;id=[^\n\r\t ]+?)"> Stagione %s</a>'
        #<img src='http://www.italiansubs.net/components/com_remository/images/folder_icons/category.gif' width=20 height=20><a name="1172"><a href="http://www.italiansubs.net/index.php?option=com_remository&amp;Itemid=6&amp;func=select&amp;id=1172"> 720p</a>
        self.category_pattern = '<img src=\'http://www\.italiansubs\.net/components/com_remository/images/folder_icons/category\.gif\' width=20 height=20><a name="[^\n\r\t ]+?"><a href="http://www\.italiansubs\.net/(index.php\?option=com_remository&amp;Itemid=\d+?&amp;func=select&amp;id=[^\n\r\t ]+?)"> ([^\n\r\t]+?)</a>'
        #<a href="http://www.italiansubs.net/index.php?option=com_remository&amp;Itemid=6&amp;func=fileinfo&amp;id=7348">Dexter 3x02</a>
        self.subtitle_pattern = '<a href="http://www\.italiansubs\.net/(index.php\?option=com_remository&amp;Itemid=\d+?&amp;func=fileinfo&amp;id=([^\n\r\t ]+?))">(%s %sx%02d.*?)</a>'
        #<a href='http://www.italiansubs.net/index.php?option=com_remository&amp;Itemid=6&amp;func=download&amp;id=7228&amp;chk=5635630f675375afbdd6eec317d8d688&amp;no_html=1'>
        self.subtitle_download_pattern = '<a href=\'http://www\.italiansubs\.net/(index\.php\?option=com_remository&amp;Itemid=\d+?&amp;func=download&amp;id=%s&amp;chk=[^\n\r\t ]+?&amp;no_html=1\')>'
        self.verbose = verbose
        if not self.username or not self.password:
            self.error('No username or password found in settings, please check them')

    def login(self):
        if self.logged_in:
            self.log('login', "Logged already")
            return 1
        self.log('login', " Logging in with username '%s' ..." % (self.username))
        response = self.req.get(self.main_url + 'index.php')
        content = response.content
        if content is not None:
            match = re.search('logouticon.png', content, re.IGNORECASE | re.DOTALL)
            if match:
                self.log('login', "Logged already")
                self.logged_in = True
                return 1
            else:
                match = re.search(self.unique_pattern, content, re.IGNORECASE | re.DOTALL)
                if match:
                    return_value = match.group(1)
                    unique_name = match.group(2)
                    unique_value = match.group(3)
                    login_postdata = {'username': self.username, 'passwd': self.password, 'remember': 'yes', 'Submit': 'Login', 'remember': 'yes', 'option': 'com_user', 'task': 'login', 'silent': 'true', 'return': return_value, unique_name: unique_value}
                    request = self.req.post(self.main_url + 'index.php',data=login_postdata,allow_redirects=True)
                    self.log('login', 'posting for login')
                    response = request.content
                    #self.put_in_cache(self.main_url + 'index.php', response)
                    match = re.search('logouticon.png', response, re.IGNORECASE | re.DOTALL)
                    if match:
                        self.logged_in = True
                        return 1
                    else:
                        return 0
        else:
            return 0

    def search_subtitles(self, id, tvshow, season, episodes, quality='Normal', language='ita', retry=0):
        fname = "search_subs"
        if language <> 'ita':
            err = "Italiansubs supports only italian subtitles"
            self.error(fname, err)
            return [], err
        if retry >= 5:
            err = "Retried 5 times, try later"
            self.error(fname, err)
            return [], err
        subtitles_list = []
        msg = ""
        if not tvshow:
            err = 'no tv show specified'
            self.error(fname, err)
            return [], err
        if self.login():
            content = self.downloader(self.main_url + 'index.php?option=com_remository&Itemid=6')
            if content is not None:
                match = re.search(self.show_pattern % tvshow, content, re.IGNORECASE | re.DOTALL)
                if match is None and tvshow[-1] == ")":
                    tvshow = tvshow[:-7]
                    match = re.search(self.show_pattern % tvshow, content, re.IGNORECASE | re.DOTALL)
                if match:
                    content= self.downloader(self.main_url + match.group(1))
                    if content is not None:
                        match = re.search(self.season_pattern % season, content, re.IGNORECASE | re.DOTALL)
                        if match:
                            categorypage = match.group(1)
                            content = self.downloader(self.main_url + categorypage)
                            if content is not None:
                                for episode in episodes:
                                    for matches in re.finditer(self.subtitle_pattern % (tvshow, int(season), int(episode)), content, re.IGNORECASE | re.DOTALL):
                                        filename = matches.group(3)
                                        id = matches.group(2)
                                        if quality == 'Normal':
                                            match_down = re.search(self.subtitle_download_pattern % id, content, re.IGNORECASE | re.DOTALL)
                                            if match_down:
                                                subtitles_list.append({'number': episode, 'season': season, 'filename': filename, 'id' : id, 'type' : quality, 'link' : match_down.group(1)})
                                            else:
                                                self.log(fname, 'must re-login')
                                                self.logged_in = False
                                                self.put_in_cache(self.main_url + categorypage, '', 'delete')
                                                return self.search_subtitles(tvshow, season, episodes, quality, retry+1)
                                for matches in re.finditer(self.category_pattern, content, re.IGNORECASE | re.DOTALL):
                                    categorypage = matches.group(1)
                                    category = matches.group(2)
                                    if category <> quality:
                                        self.log(fname, "Skipping category %s" % (category))
                                        continue
                                    content = self.downloader(self.main_url + categorypage)
                                    if content is not None:
                                        for episode in episodes:
                                            for matches in re.finditer(self.subtitle_pattern % (tvshow, int(season), int(episode)), content, re.IGNORECASE | re.DOTALL):
                                                id = matches.group(2)
                                                filename = matches.group(3)
                                                match_down = re.search(self.subtitle_download_pattern % id, content, re.IGNORECASE | re.DOTALL)
                                                if match_down:
                                                    subtitles_list.append({'number': episode, 'season': season, 'filename': "%s (%s)" % (filename, category), 'id' : id, 'type' : quality, 'link' : match_down.group(1)})
                                                else:
                                                    self.log(fname, 'must re-login')
                                                    self.logged_in = False
                                                    self.put_in_cache(self.main_url + categorypage, '', 'delete')
                                                    return self.search_subtitles(tvshow, season, episodes, quality, retry+1)
                        else:
                            msg = "Season %s of tv show '%s' not found" % (season, tvshow)
                            self.error(fname, msg)
                else:
                    msg = "Tv show '%s' not found" % tvshow
                    self.error(fname, msg)
        else:
            msg = "Login to Itasa failed. Check your username/password at the addon configuration."
            self.error(fname, msg)

        return subtitles_list, msg

    def download_subtitles(self, subtitles_list, season_path):
        fname = 'down_subs'
        if self.login():
            self.log(fname, " Login successful")
            for subtitle in subtitles_list:
                content = self.downloader(self.main_url + subtitle['link'])
                if content is not None:
                    if content[:2] == 'PK':
                        try:
                            inm_file = StringIO()
                            inm_file.write(content)
                            archive = zipfile.ZipFile(inm_file)
                            i = 0
                            for a in archive.namelist():
                                if not os.path.split(a)[1] == '':
                                    i += 1
                                    a_ = os.path.split(a)[1]
                                    #stupid hidden files by MACOSX sometimes
                                    if a_.startswith('.'):
                                        continue
                                    file = os.path.join(season_path, a_)
                                    if os.path.exists(file):
                                        filesplit = os.path.splitext(file)
                                        file = "%s.%s%s" % (filesplit[0], i, filesplit[1])
                                    self.log(fname, "Extracting to %s" % (file))
                                    subtext = archive.open(a).read()
                                    with open(file, 'wb') as g:
                                        g.write(subtext)
                            inm_file.close()
                            archive.close()
                        except:
                            self.error(fname, "Extracting sub %s failed" % (subtitle['filename']))
        else:
            self.error(fname, " Login to Itasa failed. Check your username/password at the addon configuration.")
