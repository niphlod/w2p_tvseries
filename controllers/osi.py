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
import time
from gluon.serializers import json
from gluon.contrib import simplejson as sj
from w2p_tvseries_tvdb import w2p_tvseries_ren_loader
import shutil

def check():
    session.forget()
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
    session.forget()
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
        task_id = db2.scheduler_task.insert(task_name=request.cid, function_name='bit_actualizer', args=json([rename_log_id]))
        return json(dict(task_id=task_id))

    res = db2(
        (db2.scheduler_run.scheduler_task == request.vars.task_id) &
        (db2.scheduler_run.status == 'COMPLETED')
        ).select(limitby=(0,1), orderby=db2.scheduler_run.id).first()
    if not res:
        rtn = json(dict(message='working on it...'))
    if res:
        rtn = json(dict(content=sj.loads(res.result)))

    return rtn


def check_season():
    session.forget()
    series_id, seasonnumber = request.args(0), request.args(1)
    if not (series_id and seasonnumber):
        return json({})

    status = db(
       (db.seasons_settings.series_id == series_id) &
       (db.seasons_settings.seasonnumber == seasonnumber)
       ).select(db.seasons_settings.season_status).first()

    return status.season_status


def check_path():
    session.forget()
    series_id, seasonnumber = request.args(0), request.args(1)

    if not (series_id and seasonnumber):
        return ''

    if not request.vars.task_id:
        db2(db2.scheduler_task.task_name == request.cid).delete()
        task_id = db2.scheduler_task.insert(task_name=request.cid, function_name='create_path', args=json([series_id, seasonnumber]))
        return json(dict(task_id=task_id))

    res = db2(db2.scheduler_run.scheduler_task == request.vars.task_id).select(limitby=(0,1), orderby=db2.scheduler_run.id).first()
    if not res:
        rtn = json(dict(message='working on it...'))
    if res:
        rtn = res.result

    return rtn
