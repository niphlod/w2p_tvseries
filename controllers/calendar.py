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
from gluon.storage import Storage
import datetime

def index():
    session.forget()
    return dict()

def events():
    session.forget()
    start = request.vars.start
    end = request.vars.end

    try:
        start = datetime.datetime.fromtimestamp(int(start))
    except:
        start = request.now - datetime.timedelta(days=15)
    try:
        end = datetime.datetime.fromtimestamp(int(end))
    except:
        end = request.now + datetime.timedelta(days=15)

    evts = []

    all_episodes = db(
        (db.episodes.seriesid == db.series.seriesid) &
        (db.episodes.firstaired < end) &
        (db.episodes.firstaired > start) &
        (db.seasons_settings.series_id == db.series.id) &
        (db.episodes.seasonnumber == db.seasons_settings.seasonnumber)
        ).select(db.series.ALL, db.seasons_settings.ALL, db.episodes.ALL)

    missing = {}

    for row in all_episodes:
        series_id, seasonnumber = row.seasons_settings.series_id, row.seasons_settings.seasonnumber
        key = "%s_%s" % (series_id, seasonnumber)
        if key not in missing:
            try:
                missing[key] = sj.loads(row.seasons_settings.season_status)
            except:
                pass
        try:
            icon = row.episodes.epnumber in missing[key]['missing'] and 'icon-remove' or 'icon-ok'
        except:
            icon = 'icon-remove'
        if icon == 'icon-remove':
            #check if we have a record in db.downloads
            rec = db(db.downloads.episode_id == row.episodes.id).select(limitby=(0,1), orderby=~db.downloads.id).first()
            if not rec:
                rec = Storage()
            if rec.episode_id:
                icon = 'icon-magnet'
        evts.append(
            dict(
                id=row.episodes.id,
                title="%s - S%.2dE%.2d - %s" % (row.series.name, row.episodes.seasonnumber, row.episodes.epnumber, row.episodes.name),
                start=row.episodes.firstaired.strftime('%Y-%m-%dT%H:%M:%SZ'),
                url=URL('series', 'index', args=[row.series.id], anchor="episode_%s" % (row.episodes.id)),
                icon = str(XML(A(I(_class="%s icon-white" % icon),_rel="tooltip", _href=rec.magnet, _title=rec.magnet)))
            )
        )
    return sj.dumps(evts)
