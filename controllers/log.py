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

from gluon.serializers import json
import datetime

def index():
    last_time = session.refresh_log
    if not last_time or request.vars.refresh == '1':
        last_records = db(db.global_log.id>0).select(orderby=~db.global_log.id, limitby=(0,20))
        session.refresh_log_lastid = last_records.first() and last_records.first().id or 0
    else:
        last_records = db(db.global_log.id>session.refresh_log_lastid).select(orderby=~db.global_log.id, limitby=(0,20))
        session.refresh_log_lastid = last_records.first() and last_records.first().id or session.refresh_log_lastid

    rtn = []
    for row in last_records:
        type = 'ok'
        trclass = 'info'
        if row.log_error:
            type = 'ko'
            trclass = 'error'
            row.log_operation = row.log_error
        rtn.append(
            str(TR(
                TD(
                    SPAN(w2p_icon(type), "%s: %s - %s " % (row.dat_insert, row.log_module, row.log_function)),
                    ),
                TD(
                    SPAN(row.log_operation)
                    ),
                _class=trclass)
                )
            )
    rtn = json(rtn)
    session.refresh_log = 1
    return rtn

def op_status():
    session.forget(response)
    st = db2.scheduler_task
    sw = db2.scheduler_worker
    operations = db2(
                    (st.task_name.startswith('now_or_never')) |
                    (st.task_name.startswith('spec'))
                    ).select()

    timelimit = request.now - datetime.timedelta(seconds=10)
    worker = db2(sw.last_heartbeat > timelimit).select(sw.id).first()

    if not operations.first():
        rtn = dict(status='complete', text='0/0', perc=0, worker=worker)
        return json(rtn)

    todo = operations.find(lambda row: (row.times_run == 0 and row.status not in ('RUNNING', 'FAILED')))

    todo = len(todo)
    operations = len(operations)

    text = "%s/%s" % (operations-todo,operations)
    perc = "%s%%" % ((operations - todo) * 1.0 / operations * 100)
    rtn = dict(status='loading', text=text, perc=perc, worker=worker)
    return json(rtn)

def show():
    start = request.utcnow - datetime.timedelta(days=1)
    if request.vars.start:
        start = datetime.datetime.strptime(request.vars.start, T('%Y-%m-%d %H:%M:%S', lazy=False))
    end = request.utcnow
    if request.vars.end:
        end = datetime.datetime.strptime(request.vars.end, T('%Y-%m-%d %H:%M:%S', lazy=False))
    form = SQLFORM.factory(
        Field('start', 'datetime', default=start),
        Field('end', 'datetime', default=end),
        Field('module', default=request.vars.module),
        Field('function', default=request.vars.function),
        buttons=[
                BUTTON(w2p_icon('filter', variant='white'), " Filter Results", _class="btn btn-primary"),
                A(w2p_icon('reset', variant='white'), " Reset Filters", _class="btn btn-info",
                  _href=URL('show', vars={}))
        ],
        _method = 'GET',
        _enctype = 'application/x-www-form-urlencoded'
    )
    gl = db.global_log
    recs = db((gl.dat_insert >= start) & (gl.dat_insert <= end))
    if request.vars.module:
        recs = recs(gl.log_module.contains(request.vars.module))
    if request.vars.function:
        recs = recs(gl.log_function.contains(request.vars.function))
    recs = recs.select(orderby=~gl.dat_insert)
    return dict(recs=recs, form=form)
