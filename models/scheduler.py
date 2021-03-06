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
from gluon.storage import Storage
from gluon.scheduler import Scheduler
from gluon.contrib import simplejson as sj
from w2p_tvseries_tvdb import w2p_tvseries_ren_loader, w2p_tvseries_tvdb_loader
from w2p_tvseries_subtitles import w2p_tvseries_sub_loader
from w2p_tvseries_feed import w2p_tvseries_torrent_loader
from w2p_tvseries_utils import tvdb_scooper_loader, Hasher, Brewer
from w2p_tvseries_serializers import w2p_tvseries_serializers_loader
import datetime
import shutil

def check_season_worker(series_id , seasonnumber, mode):
    renamer = w2p_tvseries_ren_loader()

    res = renamer.check(series_id, seasonnumber, mode)

    prev_status = db(
       (db.seasons_settings.series_id == series_id) &
       (db.seasons_settings.seasonnumber == seasonnumber)
       ).select(db.seasons_settings.season_status).first()

    prev_status = prev_status and prev_status.season_status or sj.dumps({})
    prev_status = sj.loads(prev_status)

    if mode == 'subs':
        res['missingsubs'] = res['missing']
        del res['missing']

    for k,v in res.iteritems():
        prev_status[k] = v

    rtn = sj.dumps(prev_status)

    db(
       (db.seasons_settings.series_id == series_id) &
       (db.seasons_settings.seasonnumber == seasonnumber)
       ).update(season_status=rtn)

    renamer.rename(series_id, seasonnumber, mode)

    db.commit()
    return rtn

def check_season(series_id, seasonnumber, cb=None):
    rtn = check_season_worker(series_id, seasonnumber, 'video')
    if cb:
        default_callback(cb, series_id, seasonnumber)
    return rtn

def check_season_subs(series_id, seasonnumber, cb=None):
    check_season_worker(series_id, seasonnumber, 'subs')
    rtn = down_subs(series_id, seasonnumber)
    if rtn.get('err') is None:
        check_season_worker(series_id, seasonnumber, 'subs')
    if cb:
        default_callback(cb, series_id, seasonnumber)
    rtn = ''
    return rtn

def down_subs(series_id, seasonnumber):
    rec = db(
            (db.seasons_settings.series_id == series_id) &
            (db.seasons_settings.seasonnumber == seasonnumber)
            ).select().first()
    if not rec:
        return

    settings = rec.subtitle_settings
    method = sj.loads(settings).get('method')
    downloader = w2p_tvseries_sub_loader(method, verbose=False)

    rtn = downloader.get_missing(series_id, seasonnumber)
    return rtn

def down_epbanners(cb=None):
    tvdb = w2p_tvseries_tvdb_loader()
    res = tvdb.episodes_banner_update_global()
    db.commit()
    if cb:
        default_callback(cb)
    return res

def down_sebanners(cb=None):
    tvdb = w2p_tvseries_tvdb_loader()
    res = tvdb.series_banner_update_global()
    db.commit()
    if cb:
        default_callback(cb)
    return res

def update(cb=None):
    tvdb = w2p_tvseries_tvdb_loader()
    res = tvdb.global_update()
    res = dict(message='Update done (%s)' % (res))
    db.commit()
    if cb:
        default_callback(cb)
    return sj.dumps(res)

def update_single_series(series_id):
    tvdb = w2p_tvseries_tvdb_loader()
    se_tb = db.series
    series = db(se_tb.id == series_id).select(se_tb.seriesid, se_tb.language).first()
    if not series:
        return
    db(se_tb.id == series_id).update(lastupdated = se_tb.lastupdated - 10000)
    res = tvdb.add_series(series.seriesid, series.language)
    db.commit()
    return sj.dumps(res)

def maintenance(cb=None):
    unparsed_date = datetime.datetime(2000, 1, 1)
    max_date = datetime.datetime(2050, 1, 1)
    now = datetime.datetime.utcnow()
    limit = now - datetime.timedelta(days=5)
    db(db.urlcache.inserted_on < limit).delete()
    db(db.global_log.dat_insert < (limit - datetime.timedelta(days=25))).delete()
    db(db.episodes.firstaired == unparsed_date).update(firstaired = max_date)
    db(db.episodes.inserted_on == None).update(inserted_on=now)
    db(db.seasons_settings.updated_on == None).update(updated_on=now)
    db.commit()
    if cb:
        default_callback(cb)
    db.commit()

def down_torrents(series_id, seasonnumber, cb=None):
    l = w2p_tvseries_torrent_loader()
    l.download_torrents(series_id, seasonnumber)
    db.commit()
    if cb:
        default_callback(cb, series_id, seasonnumber)

def queue_torrents(series_id, seasonnumber, cb=None):
    l = w2p_tvseries_torrent_loader()
    l.queue_torrents(series_id, seasonnumber)
    db.commit()
    if cb:
        default_callback(cb, series_id, seasonnumber)

def scoop_season(series_id, seasonnumber, cb=None):
    scooper = tvdb_scooper_loader()
    scooper.move_files(series_id, seasonnumber)
    db.commit()
    if cb:
        default_callback(cb, series_id, seasonnumber)

def ep_metadata(series_id, seasonnumber, mode='simple', cb=None):
    ep_tb = db.episodes
    se_tb = db.series
    me_tb = db.episodes_metadata
    episodes_to_check = db(
                (se_tb.id == series_id) &
                (ep_tb.seriesid == se_tb.seriesid) &
                (ep_tb.seasonnumber == seasonnumber) &
                (ep_tb.filename <> '') &
                (ep_tb.filename <> None)
            ).select()
    path = get_season_path(series_id, seasonnumber)
    for row in episodes_to_check:
        filename = os.path.join(path, row.episodes.filename)
        if os.path.exists(filename):
            h = Hasher(filename)
            #file yet in metadata ?
            rec = db(me_tb.guid == h.guid).select().first()
            if not rec:
                b = Brewer(filename).info
                #not exists, let's insert...
                newr = Storage()
                h.gen_hashes(mode=mode)
                newr.episode_id = row.episodes.id
                newr.series_id = series_id
                newr.seasonnumber = seasonnumber
                newr.filename = filename
                newr.guid = h.guid
                newr.ed2k = h.hashes.ed2k
                newr.sha1 = h.hashes.sha1
                newr.md5 = h.hashes.md5
                newr.osdb = h.hashes.osdb
                newr.filesize = h.stats.size
                newr.infos = sj.dumps(b)
                me_tb.update_or_insert(me_tb.episode_id == newr.episode_id, **newr)
                db.commit()
    if cb:
        default_callback(cb, series_id, seasonnumber)
    return 1

def series_metadata(series_id, seasonnumber, cb=None):
    xbmc = w2p_tvseries_serializers_loader()
    xbmc.season_metadata(series_id, seasonnumber)
    db.commit()
    if cb:
        default_callback(cb, series_id, seasonnumber)
    return 1

def add_series(seriesid, language):
    tvdb = w2p_tvseries_tvdb_loader()
    rtn = tvdb.add_series(seriesid, language)
    db.commit()
    return rtn

def bit_actualizer(rename_log_id):
    record = db.rename_log(rename_log_id)

    if not record:
        return str(TAG[''](TD(), TD('Invalid rename'), TD()))

    if not os.path.exists(record.file_from):
        shutil.move(record.file_to, record.file_from)
        record = db((db.rename_log.file_to == record.file_to) & (db.rename_log.id < record.id)).select(orderby=~db.rename_log.id, limitby=(0,1)).first()
        if not record:
            return str(TAG[''](TD(), TD(), TD()))
        return str(TAG[''](
            TD(A('Revert last rename', _href=URL('osi', 'bit_actualizer', args=[record.id]), _class="revert btn btn-danger")),
            TD(record.file_from),
            TD(record.file_to)
        ))
    else:
        return str(TAG[''](TD(), TD('Invalid rename'), TD()))

def task_group_finished(group, operation_key):
    st = db2.scheduler_task
    #still to run
    still_to_run = db2(
       (st.task_name.startswith("%s:%s" % (operation_key, group))) &
       (st.times_run == 0) &
       (~st.status.belongs(('FAILED', 'TIMEOUT')))
       ).count()
    if still_to_run == 0:
        return True
    return False

def default_callback(operation, series_id=None, seasonnumber=None):
    st = db2.scheduler_task
    if series_id and seasonnumber:
        pattern = "%s:%s:%s" % (operation, series_id, seasonnumber)
        try:
            db2(st.task_name.endswith(pattern)).update(enabled=True)
            db2.commit()
        except:
            db2.rollback()
    else:
        pattern = ":%s:" % (operation)
        try:
            db2(st.task_name.contains(pattern)).update(enabled=True)
            db2.commit()
        except:
            db2.rollback()

def create_path(series_id, seasonnumber):
    ren = w2p_tvseries_ren_loader()
    rtn = ren.check_path(series_id, seasonnumber, True)
    return rtn

def the_boss():
    operation_key = db(db.global_settings.kkey=='operation_key').select().first()
    operation_key = operation_key and operation_key.value or None
    st = db2.scheduler_task
    sr = db2.scheduler_run
    sw = db2.scheduler_worker
    if not operation_key:
        operation_key = "spec"

    rtn = []
    steps = ['maintenance', 'update', 'down_sebanners', 'scoop_season', 'check_season', 'ep_metadata',
             'down_epbanners', 'series_metadata', 'check_subs', 'down_subs', 'queue_torrents', 'down_torrents']
    res = []

    try:
        for a in steps:
            res.append((a, task_group_finished(a, operation_key)))
    except:
        rtn.append('exception')
        return rtn
    steps_todo = [a[0] for a in res if not a[1]]

    if len(steps_todo) > 0:
        step = steps_todo[0]
        rtn.append('activating %s' % (step))
        try:
            db2(st.task_name.startswith("%s:%s" % (operation_key, step))).update(enabled=True)
            db2(sw.is_ticker == True).update(status="PICK")
            db2.commit()
        except:
            rtn.append('exception')
            db2.rollback()
    else:
        try:
            tasks_to_delete = (st.task_name.startswith("%s:" % (operation_key)))
            db2(sr.task_id.belongs(db2(tasks_to_delete)._select(st.id))).delete()
            db2(tasks_to_delete).delete()
            db(db.global_settings.kkey=='operation_key').delete()
            db.commit()
            db2.commit()
        except:
            rtn.append('exception')
            db.rollback()
            db2.rollback()

    return rtn

myscheduler = Scheduler(db2,
    dict(
        check_season=check_season,
        create_path=create_path,
        add_series=add_series,
        update_single_series=update_single_series,
        bit_actualizer=bit_actualizer,
        check_subs=check_season_subs,
        down_epbanners=down_epbanners,
        down_sebanners=down_sebanners,
        update=update,
        maintenance=maintenance,
        ep_metadata=ep_metadata,
        queue_torrents=queue_torrents,
        down_torrents=down_torrents,
        scoop_season=scoop_season,
        series_metadata=series_metadata,
        the_boss=the_boss
    ),
    migrate=MIGRATE
)
