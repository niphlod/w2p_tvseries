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

from gluon.contrib import simplejson as sj
from gluon.serializers import json
from w2p_tvseries_tvdb import w2p_tvseries_ren_loader
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
        missing = db(
                     (db.episodes.seriesid == row.series.seriesid) &
                     (db.episodes.seasonnumber == row.seasons_settings.seasonnumber) &
                     (db.episodes.number.belongs(data['missing']))
                     ).select()
        missing = ["E%.2d - %s" % (rec.number, rec.name) for rec in missing]
        if len(missing) == 0:
            continue
        if row.series.id not in rtn:
            rtn[row.series.id] = dict(
                                      name=row.series.name,
                                      seasons=[dict(
                                                    number=row.seasons_settings.seasonnumber,
                                                    missing=missing,
                                                    missingsubs=data.get('missingsubs', []),
                                                    )
                                               ]
                                      )
        else:
            rtn[row.series.id]['seasons'].append(
                                                 dict(
                                                      number=row.seasons_settings.seasonnumber,
                                                      missing=missing,
                                                      missingsubs=data.get('missingsubs', []),
                                                     )
                                                 )

    return dict(rtn=rtn)


#web2py/web2py.py -S "w2p_tvseries/organize/queue_ops" -M -N
def queue_ops():
    operation_key = db(db.global_settings.key=='operation_key').select().first()
    operation_key = operation_key and operation_key.value or None
    if not operation_key:
        db.global_settings.insert(key='operation_key', value='now_or_never')
        operation_key = 'now_or_never'

    se_tb = db.series
    ss_tb = db.seasons_settings

    all_to_check = db(
                      (ss_tb.series_id == se_tb.id) &
                      (ss_tb.tracking == True)
                    ).select()

    validvideos = []
    validsubs = []
    validtorrents = []
    validscooper = []

    for row in all_to_check:
        if row.series.basepath == '' or row.series.basepath == None:
            continue
        else:
            validvideos.append((row.seasons_settings.series_id, row.seasons_settings.seasonnumber))
            if row.seasons_settings.subtitle_tracking:
                validsubs.append((row.seasons_settings.series_id, row.seasons_settings.seasonnumber))
            if row.seasons_settings.torrent_tracking:
                validtorrents.append((row.seasons_settings.series_id, row.seasons_settings.seasonnumber))
            if row.seasons_settings.scooper_strings:
                validscooper.append((row.seasons_settings.series_id, row.seasons_settings.seasonnumber))

    st = db2.scheduler_task
    sr = db2.scheduler_run
    tasks_to_delete = db2(st.id>0)
    db2(sr.scheduler_task.belongs(tasks_to_delete._select(st.id))).delete()
    tasks_to_delete.delete()

    st.insert(task_name='%s:theBoss' % (operation_key), function_name='the_boss',repeats=0, period=10)

    uniquename = "%s:maintenance" % (operation_key)
    st.insert(task_name=uniquename, function_name='maintenance', enabled=False, timeout=15)

    uniquename = "%s:update" % (operation_key)
    st.insert(task_name=uniquename, function_name='update', enabled=False, timeout=120)

    uniquename = "%s:down_sebanners" % (operation_key)
    st.insert(task_name=uniquename, function_name='down_sebanners', enabled=False, timeout=180)

    uniquename = "%s:down_epbanners" % (operation_key)
    st.insert(task_name=uniquename, function_name='down_epbanners', enabled=False, timeout=300)

    for a in validvideos:
        function_name = 'check_season'
        unique_name = "%s:%s:%s:%s" % (operation_key, function_name, a[0], a[1])
        st.insert(task_name=unique_name, function_name=function_name, args=json(a), enabled=False)
        function_name = 'ep_metadata'
        unique_name = "%s:%s:%s:%s" % (operation_key, function_name, a[0], a[1])
        st.insert(task_name=unique_name, function_name=function_name, args=json(a), enabled=False, timeout=300)

    for a in validscooper:
        function_name = 'scoop_season'
        unique_name = "%s:%s:%s:%s" % (operation_key, function_name, a[0], a[1])
        st.insert(task_name=unique_name, function_name=function_name, args=json(a), enabled=False, timeout=300)

    for a in validsubs:
        function_name = 'check_subs'
        unique_name = "%s:%s:%s:%s" % (operation_key, function_name, a[0], a[1])
        st.insert(task_name=unique_name, function_name=function_name, args=json(a), enabled=False)
        function_name = 'down_subs'
        unique_name = "%s:%s:%s:%s" % (operation_key, function_name, a[0], a[1])
        st.insert(task_name=unique_name, function_name=function_name, args=json(a), enabled=False, timeout=300)

    for a in validtorrents:
        function_name = 'queue_torrents'
        unique_name = "%s:%s:%s:%s" % (operation_key, function_name, a[0], a[1])
        st.insert(task_name=unique_name, function_name=function_name, args=json(a), enabled=False)
        function_name = 'down_torrents'
        unique_name = "%s:%s:%s:%s" % (operation_key, function_name, a[0], a[1])
        st.insert(task_name=unique_name, function_name=function_name, args=json(a), enabled=False)

    db2.commit()
    db.commit()

    return 'started'
