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
from gluon.contrib import simplejson as sj
from gluon.serializers import json
from w2p_tvseries_tvdb import w2p_tvseries_ren_loader
from w2p_tvseries_clients import w2p_tvseries_torrent_client_loader
from w2p_tvseries_utils import w2p_tvseries_settings
import os

def index():
    all_to_check = db(
        (db.seasons_settings.series_id == db.series.id) &
        (db.seasons_settings.tracking == True)
        ).select()

    invalid = dict(path=[])
    invpath = {}
    validvideos = []
    validsubs = []
    for row in all_to_check:
        if row.series.basepath == '' or row.series.basepath == None:
            if row.series.name not in invpath:
                invpath[row.series.name] = 1
                invalid['path'].append(A(row.series.name, _href=URL('series', 'index', args=[row.series.id], vars=dict(settings=1))))
        else:
            validvideos.append((row.seasons_settings.series_id, row.seasons_settings.seasonnumber))
            if row.seasons_settings.subtitle_tracking <> 'No':
                validsubs.append((row.seasons_settings.series_id, row.seasons_settings.seasonnumber))

    return dict(a=validvideos, b=invalid, c=validsubs, d=missing)

def check_missing_path():
    all_to_check = db(
                      (db.seasons_settings.series_id == db.series.id) &
                      (db.seasons_settings.tracking == True) &
                      (db.series.basepath <> '') &
                      (db.series.basepath != None)
                    ).select()

    ren = w2p_tvseries_ren_loader()
    results = []
    for row in all_to_check:
        res = ren.check_path(row.seasons_settings.series_id, row.seasons_settings.seasonnumber)
        if res.get('message'):
            results.append(res)

    return dict(results=results)

def missing():
    all_to_check = db(
                      (db.seasons_settings.series_id == db.series.id) &
                      (db.series.basepath <> '') &
                      (db.seasons_settings.tracking == True)
                    ).select(orderby=db.seasons_settings.series_id|db.seasons_settings.seasonnumber)

    rtn = {}
    for row in all_to_check:
        data = sj.loads(row.seasons_settings.season_status)
        missing_eps = db(
                     (db.episodes.seriesid == row.series.seriesid) &
                     (db.episodes.seasonnumber == row.seasons_settings.seasonnumber) &
                     (db.episodes.tracking == True) &
                     (db.episodes.firstaired < request.now.date()) &
                     (db.episodes.epnumber.belongs(data.get('missing', [])))
                     ).select()
        missing = []
        #check if we have a record in db.downloads
        for mep in missing_eps:
            rec = db(db.downloads.episode_id == mep.id).select(limitby=(0,1), orderby=~db.downloads.id).first()
            icon = rec and 'icon-magnet' or 'icon-remove'
            if not rec:
                rec = Storage()
            icon = A(I(_class=icon),_rel="tooltip", _href=rec.magnet, _title=rec.magnet)
            missing.append(
                SPAN(icon,
                    A("Disable Tracking",
                    _href=URL('manage', 'episode_tracking', args=[mep.id]), _class='ep_tracking')
                    ," E%.2d - %s" % (mep.epnumber, mep.name)
                )
            )

        if len(missing) == 0:
            continue
        if row.series.id not in rtn:
            rtn[row.series.id] = dict(
                                      name=row.series.name,
                                      seasons=[dict(
                                                    number=row.seasons_settings.seasonnumber,
                                                    missing=missing,
                                                    missingsubs=data.get('missingsubs', []),
                                                    link=URL('series', 'index', args=[row.series.id],
                                                             anchor="episode_%s" % (missing_eps[0].id),
                                                             extension='')
                                                    )
                                               ]
                                      )
        else:
            rtn[row.series.id]['seasons'].append(
                                                 dict(
                                                      number=row.seasons_settings.seasonnumber,
                                                      missing=missing,
                                                      missingsubs=data.get('missingsubs', []),
                                                      link=URL('series', 'index', args=[row.series.id],
                                                               anchor="episode_%s" % (missing_eps[0].id)
                                                               ,extension='')
                                                     )
                                                 )
    return dict(rtn=rtn)


#web2py/web2py.py -S "w2p_tvseries/organize/queue_ops" -M -N
def queue_ops():
    series_id, seasonnumber = request.args(0), request.args(1)
    operation_key = 'spec'
    if not (series_id and seasonnumber):
        operation_key = db(db.global_settings.kkey=='operation_key').select().first()
        operation_key = operation_key and operation_key.value or None
        if not operation_key:
            db.global_settings.insert(kkey='operation_key', value='now_or_never')
            operation_key = 'now_or_never'
            db.commit()

    se_tb = db.series
    ss_tb = db.seasons_settings

    series_metadata = db(db.global_settings.kkey=='series_metadata').select().first()
    series_metadata = series_metadata and series_metadata.value or 'N'
    hash_gen_mode = db(db.global_settings.kkey=='hash_gen').select().first()
    hash_gen_mode = hash_gen_mode and hash_gen_mode.value or 'Simple'

    basecond = db(ss_tb.series_id == se_tb.id)
    if series_id and seasonnumber:
        basecond = basecond(se_tb.id == series_id)(ss_tb.seasonnumber == seasonnumber)

    all_to_check = basecond(ss_tb.tracking == True).select()

    st = db2.scheduler_task
    sr = db2.scheduler_run

    if not (series_id and seasonnumber):
        enabled = False
        tasks_to_delete = db2(st.id>0)
        db2(sr.scheduler_task.belongs(tasks_to_delete._select(st.id))).delete()
        tasks_to_delete.delete()
        uniquename = "%s:maintenance" % (operation_key)
        st.insert(task_name=uniquename, function_name='maintenance', enabled=True, timeout=15, vars=json(dict(cb='update')))

        uniquename = "%s:update:" % (operation_key)
        st.insert(task_name=uniquename, function_name='update', enabled=False, timeout=300, vars=json(dict(cb='down_sebanners')))

        uniquename = "%s:down_sebanners:" % (operation_key)
        st.insert(task_name=uniquename, function_name='down_sebanners', enabled=False, timeout=180, vars=json(dict(cb='down_epbanners')))

        uniquename = "%s:down_epbanners:" % (operation_key)
        st.insert(task_name=uniquename, function_name='down_epbanners', enabled=False, timeout=300, vars=json(dict(cb='check_season')))

    else:
        enabled = True
        tasks_to_delete = db2(
            (st.task_name.startswith(operation_key)) &
            (st.task_name.endswith("%s:%s" % (series_id, seasonnumber)))
            ).delete()

    st.insert(task_name='%s:theBoss' % (operation_key), function_name='the_boss',repeats=0, period=10)

    for row in all_to_check:
        if row.series.basepath == '' or row.series.basepath == None:
            continue
        else:
            path_for_one_season(row.seasons_settings, series_metadata, hash_gen_mode, operation_key, enabled)

    db2.commit()
    db.commit()

    return 'started'

def path_for_one_season(seasons_settings, series_metadata, hash_gen_mode, op_key, enabled):
    series_id, seasonnumber = seasons_settings.series_id, seasons_settings.seasonnumber
    path = []
    if seasons_settings.scooper_strings:
        path.append('scoop_season')
    path.append('check_season')
    path.append('ep_metadata')
    if series_metadata <> 'N':
        path.append('series_metadata')
    if seasons_settings.subtitle_tracking:
        path.append('check_subs')
    if seasons_settings.torrent_tracking:
        path.append('queue_torrents')
        path.append('down_torrents')

    params = Storage()
    params['ep_metadata'] = dict(timeout=300)
    params['check_subs'] = dict(timeout=300, retry_failed=2)
    params['scoop_season'] = dict(timeout=300)
    params['queue_torrents'] = dict(retry_failed=2)
    params['down_torrents'] = dict(retry_failed=2)

    st = db2.scheduler_task

    path_count = len(path)

    for i, op in enumerate(path):
        unique_name = "%s:%s:%s:%s" % (op_key, op, series_id, seasonnumber)
        pr = params[op] or dict()
        pr = Storage(pr)
        pr.update(
            dict(
                task_name=unique_name,
                function_name=op,
                args=json((series_id, seasonnumber)))
            )
        if i != 0 or enabled==False:
            pr['enabled'] = False
        vars = dict()
        if op == 'ep_metadata':
            vars['mode'] = hash_gen_mode
        if i != path_count-1:
            vars['cb'] = path[i+1]
        pr['vars'] = json(vars)
        st.insert(**pr)

def torrents():
    session.forget()
    settings_ = w2p_tvseries_settings()
    gsettings = settings_.global_settings()
    if gsettings.tclient == 'None' or not gsettings.tclient:
        session.flash = 'no client configured'
        redirect(URL('default', 'client_settings'))
    return dict()

def torrents_status():
    session.forget()
    settings_ = w2p_tvseries_settings()
    gsettings = settings_.global_settings()
    tclient = w2p_tvseries_torrent_client_loader(gsettings.tclient)
    res = tclient.get_status()
    if res is None:
        response.flash = 'Unable to connect'
        res = []
    #res = []
    return dict(res=res)
