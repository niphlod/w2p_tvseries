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
import time
from gluon.serializers import json
from gluon.contrib import simplejson as sj
from w2p_tvseries_tvdb import w2p_tvseries_ren_loader
import shutil

def check():
    session.forget(response)
    if not request.vars.directory:
        return 0

    base, hint = os.path.split(request.vars.directory)
    if not base:
        return json([])
    if not os.access(base, os.R_OK):
        return json([])
    res = find_matching_subdir(base, hint)
    if res:
        return res
    else:
        return json([])

def find_matching_subdir(base, hint):
    session.forget(response)
    topdirs = [name for name in os.listdir(base) if os.path.isdir(os.path.join(base, name))]
    res = []
    for a in topdirs:
        if a.startswith(hint):
            res.append(os.path.join(base, a, ''))
    return json(res)

def bit_actualizer():
    rename_log_id = request.args(0)

    if not rename_log_id:
        return ''

    if not request.vars.task_id:
        db2(db2.scheduler_task.task_name == request.cid).delete()
        res = myscheduler.queue_task('bit_actualizer', [rename_log_id], task_name=request.cid, immediate=True)
        task_id = res.id
        return json(dict(task_id=task_id))

    task_id = int(request.vars.task_id)

    res = myscheduler.task_status(task_id, output=True)

    if not res.scheduler_run.status == 'COMPLETED':
        rtn = json(dict(message='working on it...'))
    else:
        rtn = json(dict(content=res.result))

    return rtn


def check_season():
    session.forget(response)
    series_id, seasonnumber = request.args(0), request.args(1)
    if not (series_id and seasonnumber):
        return json({})

    status = db(
       (db.seasons_settings.series_id == series_id) &
       (db.seasons_settings.seasonnumber == seasonnumber)
       ).select(db.seasons_settings.season_status, db.seasons_settings.updated_on).first()

    if not status.updated_on:
        status.updated_on = request.now
    episodes = db(
        (db.series.id == series_id) &
        (db.episodes.seriesid == db.series.seriesid) &
        (db.episodes.seasonnumber == seasonnumber) &
        (db.episodes.inserted_on > status.updated_on)
        ).select(db.episodes.epnumber)

    rtn = status.season_status
    if len(episodes) > 0:
        st_ = sj.loads(status.season_status)
        missing = st_.get('missing', [])
        for ep in episodes:
            missing.append(ep.epnumber)
        st_['missing'] = missing
        rtn = sj.dumps(st_)
    return rtn


def check_path():
    session.forget(response)
    series_id, seasonnumber = request.args(0), request.args(1)

    if not (series_id and seasonnumber):
        return ''

    if not request.vars.task_id:
        db2(db2.scheduler_task.task_name == request.cid).delete()
        res = myscheduler.queue_task('create_path', [series_id, seasonnumber], {}, task_name=request.cid, immediate=True)
        task_id = res.id
        return json(dict(task_id=task_id))

    task_id = int(request.vars.task_id)

    res = myscheduler.task_status(task_id, output=True)

    if not res.scheduler_run.status == 'COMPLETED':
        rtn = json(dict(message='working on it...'))
    else:
        rtn = res.scheduler_run.run_result

    return rtn
