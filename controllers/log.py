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

from gluon.serializers import json

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
        rtn.append(str(TR(
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
    session.forget()
    operation_key = db(db.global_settings.kkey=='operation_key').select().first()
    operation_key = operation_key and operation_key.value or None
    if not operation_key:
        rtn = dict(status='complete', text='0/0', perc=0)
        return json(rtn)

    operations = db2(
                    (db2.scheduler_task.task_name.startswith(operation_key))
                    ).select()

    if not operations.first():
        rtn = dict(status='complete', text='0/0', perc=0)
        return json(rtn)

    todo = operations.find(lambda row: (row.times_run == 0 and row.status not in ('RUNNING', 'FAILED')))

    todo = len(todo)
    operations = len(operations)

    text = "%s/%s" % (operations-todo,operations)
    perc = "%s%%" % ((operations - todo) * 1.0 / operations * 100)
    rtn = dict(status='loading', text=text, perc=perc)
    return json(rtn)
