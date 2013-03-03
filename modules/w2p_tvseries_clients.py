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

import os
import subprocess
import re
import sys
import base64
try:
    import requests as req
except:
    raise ImportError , "requests module is needed: http://docs.python-requests.org"

from gluon.contrib import simplejson as sj
from gluon.storage import Storage
from w2p_tvseries_utils import tvdb_logger, w2p_tvseries_settings
UTORRENT_TOKEN = re.compile("<div id='token' style='display:none;'>(.+?)</div>")


from gluon import current
import thread

locker = thread.allocate_lock()

def w2p_tvseries_torrent_client_loader(*args, **vars):
    locker.acquire()
    type = args[0]
    args = args[1:]
    try:
        if not hasattr(w2p_tvseries_torrent_client_loader, 'instance_%s' % (type)):
            types = dict(
                utorrent=w2p_Utorrent,
                deluge=w2p_Deluge,
                transmission=w2p_Transmission,
            )
            setattr(w2p_tvseries_torrent_client_loader, 'instance_%s' % (type),  types[type](*args, **vars))
    finally:
        locker.release()
    return getattr(w2p_tvseries_torrent_client_loader, 'instance_%s' % (type))


class w2p_tvseries_client(object):
    def __init__(self, gsettings=None):
        self.gsettings = gsettings

    def access_settings(self):
        if not self.gsettings:
            self.gsettings = w2p_tvseries_settings().global_settings()
        self.url = self.gsettings.turl
        self.username = self.gsettings.tusername
        self.password = self.gsettings.tpassword

    def get_status(self):
        """list of dicts
        id, hash, filename, perc, status, addinfo
        """

    def log(self, function, message):
        log = self.logger
        log.log(function, message)

    def error(self, function, message):
        log = self.logger
        log.error(function, message)

class w2p_Amule(w2p_tvseries_client):

    def __init__(self):
        self.executable = "amulecmd"
        self.commands = ["-c", "show dl"]
        self.firstr = re.compile(r' > ([A-Z0-9]{32}) (.*)')
        self.secondr = re.compile(r' >?[^-]*\[(.*)%\]?[^-]* - ([^-]*) - ')

    def get_status(self):
        cmds = [self.executable]
        cmds.extend(self.commands)
        p = subprocess.Popen(cmds, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = p.stdout.read()
        lines = output.split('\n')
        res = []
        while True:
            try:
                line = lines.pop(0)
            except:
                break
            if '>' not in line:
                continue
            fmatch = self.firstr.match(line)
            if fmatch:
                line = lines.pop(0)
                smatch = self.secondr.match(line)
            if fmatch and smatch:
                hash = fmatch.group(1)
                filename = fmatch.group(2)
                perc = smatch.group(1)
                status = smatch.group(2)
                res.append(
                    Storage(
                        hash=hash,
                        filename=filename,
                        perc=float(perc),
                        status=status
                    )
                )
        return res

class w2p_Utorrent(w2p_tvseries_client):
    def __init__(self, *args, **vars):
        self.logger = tvdb_logger('utclient')
        super(w2p_Utorrent, self).__init__(*args, **vars)
        self.access_settings()
        self.req = req.Session()
        self.req.headers = {'User-Agent' : 'w2p_tvdb'}

    def get_token(self):
        token_url = self.url + 'token.html'
        content = ''
        try:
            r = self.req.get(token_url, auth=(self.username, self.password), timeout=3)
            r.raise_for_status()
            content = r.content
        except:
            self.error('get_token', 'failed to connect')
            return None
        match = UTORRENT_TOKEN.search(content)
        if match:
            return match.group(1)

    def decode_status(self, parsed):
        stcode = parsed['status']
        percent = parsed['percent']
        statuses = {1:'Started',
                    2:'Checking',
                    4:'Start after check',
                    8:'Checked',
                    16:'Error',
                    32:'Paused',
                    64:'Queued',
                    128:'Loaded'}
        fstatus = []
        for k,v in statuses.iteritems():
            if k & stcode:
                fstatus.append(v)
        if 'Loaded' not in fstatus:
            return 'Not Loaded'
        if 'Error' in fstatus:
            return 'Error'
        if 'Checking' in fstatus:
            return 'Checking'
        if 'Paused' in fstatus:
            if 'Queued' in fstatus:
                return 'Paused'
            else:
                return 'Forced Pause'
        if percent == 100:
            if 'Queued' in fstatus:
                if 'Started' in fstatus:
                    return 'Seeding'
                else:
                    return 'Queued Seed'
            else:
                if 'Started' in fstatus:
                    return 'Forced Seed'
                else:
                    return 'Finished'
        else:
            if 'Queued' in fstatus:
                if 'Started' in fstatus:
                    return 'Downloading'
                if 'Queued' in fstatus:
                    if 'Started' in fstatus:
                        return 'Dowloading'
                    else:
                        return 'Queued'
                else:
                    if 'Started' in fstatus:
                        return 'Forced Download'

    def get_status(self):
        self.token = self.get_token()
        if not self.token:
            return None
        list_url = "%s?token=%s&list=1" % (self.url, self.token)
        try:
            r = self.req.get(list_url, auth=(self.username, self.password), timeout=3)
            r.raise_for_status()
        except:
            self.error('get_status', 'unable to retrieve status')
            return None
        list = sj.loads(r.content)
        filemap = {0 : 'hash',1:'status', 2:'name',3:'size',4:'percent',
                   7:'ratio',8:'up', 9:'down', 10:'eta'}
        files = []
        for file in list['torrents']:
            parsed = {}
            for i, chunk in enumerate(file):
                if i in filemap:
                    parsed[filemap[i]] = chunk
            parsed['status'] = self.decode_status(parsed)
            files.append(Storage(parsed))
        return files

    def add_magnet(self, magnet):
        self.token = self.get_token()
        if not self.token:
            self.error('add_magnet', 'Unable to add magnet')
            return None
        payload = {'token': self.token, 'action' : 'add-url', 's' : magnet}
        try:
            r = self.req.get(self.url, params=payload, auth=(self.username, self.password), timeout=3)
            r.raise_for_status()
        except:
            self.error('add_magnet', 'Unable to add magnet')
            return None
        return True

    def add_torrent(self, filename):
        self.token = self.get_token()
        if not self.token:
            self.error('add_torrent', 'Unable to add torrent')
            return None
        payload = {'token': self.token, 'action' : 'add-file'}
        files = {'torrent_file': open(filename, 'rb')}
        try:
            r = self.req.post(self.url, params=payload, files=files, auth=(self.username, self.password), timeout=3)
            r.raise_for_status()
        except:
            self.error('add_torrent', 'Unable to add torrent')
            return None
        return True

class w2p_Deluge(w2p_tvseries_client):
    def __init__(self, *args, **vars):
        self.logger = tvdb_logger('declient')
        super(w2p_Deluge, self).__init__(*args, **vars)
        self.access_settings()
        self.req = req.Session()
        self.req.headers =  {'User-Agent' : 'w2p_tvdb',
                       'Content-Type' : 'application/json'
                       }

    def init_session(self):
        data = dict(id=1, method='auth.login', params=[self.password])
        try:
            r = self.req.post(self.url, data=sj.dumps(data), timeout=3)
            r.raise_for_status()
        except:
            self.error('auth', 'Unable to login')
            return None
        content = sj.loads(r.content)['result']
        if content == False:
            self.error('auth', 'Unable to login')
            return None
        return content

    def normalize(self, parsed):
        mapping = dict(
            hash='hash',
            state='status',
            name='name',
            total_size='size',
            progress='percent',
            eta='eta',
            download_payload_rate='down',
            upload_payload_rate='up',
            ratio='ratio'
            )
        file = {}
        for k,v in mapping.iteritems():
            file[v] = parsed[k]
        return Storage(file)

    def get_status(self):
        #put the cookie in
        if not self.init_session():
            return None
        retrieve_keys = ['hash', 'ratio', 'total_size','state', 'progress',
                         'name', 'eta', 'upload_payload_rate',
                         'total_payload_upload', 'download_payload_rate',
                         'total_payload_download']
        data = dict(id=2, method='web.update_ui', params=[retrieve_keys, {}])
        try:
            r = self.req.post(self.url, data=sj.dumps(data), timeout=3)
            r.raise_for_status()
        except:
            self.error('get_status', 'Unable to retrieve status')
            return None
        stats = sj.loads(r.content)
        stats = stats['result']
        files = []
        if not stats.get('torrents'):
            return files
        for file in stats['torrents']:
            parsed = stats['torrents'][file]
            files.append(self.normalize(parsed))
        return files

    def add_magnet(self, magnet):
        data = {"method": "core.add_torrent_magnet", "params": [magnet, {}], "id": 1}
        while True:
            try:
                r = self.req.post(self.url, data=sj.dumps(data))
                r.raise_for_status()
                content = sj.loads(r.content)
            except:
                self.error('add_magnet', 'Unable to add magnet')
                break
            err = content.get('error')
            if err and err.get('message'):
                if self.init_session():
                    continue
                else:
                    self.error('add_magnet', 'Unable to add magnet')
                    break
            else:
                break
        return True

    def add_torrent(self, filename):
        data = {"method": "web.add_torrents", "params": [[{'path' : filename, 'options': {}}]], "id": 1}
        while True:
            try:
                r = self.req.post(self.url, data=sj.dumps(data), timeout=3)
                r.raise_for_status()
                content = sj.loads(r.content)
            except:
                self.error('add_torrent', 'Unable to add torrent')
                break
            err = content.get('error')
            if err and err.get('message'):
                if self.init_session():
                    continue
                else:
                    self.error('add_torrent', 'Unable to add torrent')
                    break
            else:
                break
        return True

class w2p_Transmission(w2p_tvseries_client):
    def __init__(self, *args, **vars):
        self.logger = tvdb_logger('trclient')
        super(w2p_Transmission, self).__init__(*args, **vars)
        self.access_settings()

    def decode_status(self, statuscode,rpc_version):
        if rpc_version >= 14:
            mapping = {
                0: 'stopped',
                1: 'check pending',
                2: 'checking',
                3: 'download pending',
                4: 'downloading',
                5: 'seed pending',
                6: 'seeding'
                }
        else:
            mapping = {
                (1<<0): 'check pending',
                (1<<1): 'checking',
                (1<<2): 'downloading',
                (1<<3): 'seeding',
                (1<<4): 'stopped'
                }
        return mapping.get(statuscode, 'Unknown')

    def normalize(self, parsed,rpc_version):
        mapping = {
            'name' : 'name',
            'hash' : 'hashString',
            'eta' : 'eta',
            'ratio' : 'uploadRatio',
            'up' : 'rateUpload',
            'down' : 'rateDownload',
            'size' : 'totalSize',
            'status' : 'status',
            'percent' : 'percentDone'
        }
        file = {}
        for k,v in mapping.iteritems():
            file[k] = parsed[v]
        file['status'] = self.decode_status(file['status'],rpc_version)
        return Storage(file)

    def get_status(self):
        sess = req.Session()
        sess.headers = {'User-Agent' : 'w2p_tvdb',
                                      'Content-Type' : 'application/json'
                                      }
        fields = ['eta', 'hashString', 'name', 'rateDownload', 'rateUpload', 'totalSize', 'status', 'uploadRatio', 'percentDone']
        #get transmission-id header and rpc version (status decoding needs it)
        data = dict(method='session-get', arguments=[])
        while True:
            try:
                r = sess.post(self.url, data=sj.dumps(data), timeout=3,
                           auth=(self.username, self.password))
            except:
                self.error('get_status', 'Unable to retrieve status')
                return None
            if r.status_code == 409:
                sess.headers['X-Transmission-Session-Id'] = r.headers['X-Transmission-Session-Id']
            else:
                break
        try:
            r.raise_for_status()
        except:
            self.error('get_status', 'Unable to retrieve status')
            return None
        content = sj.loads(r.content)
        rpc_version = content['arguments']['rpc-version']
        data = dict(method='torrent-get', arguments={'fields' : fields})
        while True:
            r = sess.post(self.url, data=sj.dumps(data), timeout=3,
                           auth=(self.username, self.password))
            if r.status_code == 409:
                sess.headers['X-Transmission-Session-Id'] = r.headers['X-Transmission-Session-Id']
            else:
                break
        try:
            r.raise_for_status()
        except:
            self.error('get_status', 'Unable to retrieve status')
            return None
        content = r.content
        content = sj.loads(content)
        files = []
        for file in content['arguments']['torrents']:
            files.append(self.normalize(file, rpc_version))
        return files

    def add_magnet(self, magnet):
        sess = req.Session()
        sess.headers = {'User-Agent' : 'w2p_tvdb',
                                      'Content-Type' : 'application/json'
                                      }
        data = dict(method='torrent-add', arguments={'filename' : magnet})
        while True:
            try:
                r = sess.post(self.url, data=sj.dumps(data), timeout=3,
                           auth=(self.username, self.password))
            except:
                self.error('add_magnet', 'Unable to add magnet')
                return None
            if r.status_code == 409:
                sess.headers['X-Transmission-Session-Id'] = r.headers['X-Transmission-Session-Id']
            else:
                break
        try:
            r.raise_for_status()
        except:
            self.error('add magnet', 'Unable to add magnet')
            return None
        content = sj.loads(r.content)
        if content['result'] == 'success':
            return True
        else:
            return False

    def add_torrent(self, filename):
        sess = req.Session()
        sess.headers = {'User-Agent' : 'w2p_tvdb',
                                      'Content-Type' : 'application/json'
                                      }
        with open(filename, 'rb') as g:
            content = base64.b64encode(g.read())
        data = dict(method='torrent-add', arguments={'metainfo' : content})
        while True:
            try:
                r = sess.post(self.url, data=sj.dumps(data), timeout=3,
                           auth=(self.username, self.password))
            except:
                self.error('add_torrent', 'Unable to add torrent')
                return None
            if r.status_code == 409:
                sess.headers['X-Transmission-Session-Id'] = r.headers['X-Transmission-Session-Id']
            else:
                break
        try:
            r.raise_for_status()
        except:
            self.error('add_torrent', 'Unable to add torrent')
            return None
        content = sj.loads(r.content)
        if content['result'] == 'success':
            return True
        else:
            return False


if __name__ == '__main__':
    amule = Amule()
    print amule.get_status()
