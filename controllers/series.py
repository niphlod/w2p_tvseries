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
from w2p_tvseries_utils import Brewer
import time


def index():
    session.forget()
    if not request.args(0):
        redirect(URL('default', 'index'))

    series_id = request.args(0)

    episode_list = db(
                 (db.episodes.seriesid == db.series.seriesid) &
                 (db.series.id == series_id) &
                 (db.seasons_settings.series_id == db.series.id) &
                 (db.seasons_settings.tracking == True) &
                 (db.seasons_settings.seasonnumber == db.episodes.seasonnumber)
                 ).select(db.series.name, db.series.overview, db.seasons_settings.ref_urls,
                          db.episodes.id, db.episodes.epnumber, db.episodes.seasonnumber,
                          db.episodes.firstaired,
                          orderby=db.episodes.seasonnumber|db.episodes.epnumber)

    episodes = {}
    now = request.utcnow.date()
    for ep in episode_list:
        tba = ep.episodes.firstaired > now and 'tba' or ''
        if not episodes.get(ep.episodes.seasonnumber):
            episodes[ep.episodes.seasonnumber] = dict(ref_urls=ep.seasons_settings.ref_urls,
                                                      eps=[dict(id=ep.episodes.id, number=ep.episodes.epnumber, tba=tba)]
                                                      )
        else:
            episodes[ep.episodes.seasonnumber]['eps'].append(dict(id=ep.episodes.id, number=ep.episodes.epnumber, tba=tba))

    banner = db(db.series_banners.series_id == series_id).select()
    banner = banner.first() and banner.first().banner or ''

    if len(episode_list) == 0:
        rec = db(db.series.id == series_id).select()
        name = rec.first() and rec.first().name or ''
    else:
        name = episode_list[0].series.name

    if request.vars.settings:
        episodes = {}

    return dict(episodes=episodes, name=name, banner=banner)

def episodes():
    session.forget()
    if not request.args(0):
        return ''

    episode = db(db.episodes.id == request.args(0)).select().first()
    episode.lastupdated = datetime.datetime.fromtimestamp(episode.lastupdated).isoformat()

    banner = db((db.episodes_banners.episode_id == episode.id) & (db.episodes_banners.banner <> '')).select().first()
    metadata = db(db.episodes_metadata.episode_id == episode.id).select().first()
    download = db(db.downloads.episode_id == episode.id).select(db.downloads.link, db.downloads.magnet).first()
    if metadata and metadata.infos:
        info = sj.loads(metadata.infos)
        if len(info) > 0:
            metadata = Brewer(info).build_graphics()
        else:
            metadata = None

    return dict(episode=episode, banner=banner, metadata=metadata, download=download)

def season():
    session.forget()
    if not (request.args(0) and request.args(1)):
        return ''

    season = db(
                (db.seasons_settings.series_id == request.args(0)) &
                (db.seasons_settings.seasonnumber == request.args(1))
                ).select().first()

    return dict(a=season.season_status)

def sidebar():
    return wp2tv_sidebar(request.vars.genre)

def search():
    term = request.vars.q
    series = db(db.series.name.contains(term)).select(db.series.id, db.series.name)
    rtn = []
    for row in series:
        rtn.append(dict(id="se_%s" % row.id, text=row.name, t="series", url=URL('series', 'index', args=[row.id], extension='')))
    eps = db(
        (db.episodes.name.contains(term)) &
        (db.series.seriesid == db.episodes.seriesid) &
        (db.episodes.tracking == True)
        ).select(db.episodes.id, db.episodes.seasonnumber, db.episodes.epnumber, db.episodes.name, db.series.id, db.series.name)
    for row in eps:
        banner = db((db.episodes_banners.episode_id == row.episodes.id) & (db.episodes_banners.banner <> '')).select().first()
        rtn.append(dict(id="ep_%s" % row.episodes.id,
                        text="%s - S%.2dE%.2d - %s" % (
                            row.series.name, row.episodes.seasonnumber,
                            row.episodes.epnumber, row.episodes.name
                            ),
                        t="episodes",
                        url=URL('series', 'index',
                                args=[row.series.id],
                                anchor="episode_%s" % row.episodes.id,
                                extension=''),
                        src=banner and w2p_deposit(banner.banner) or None
                        )
                   )
    return sj.dumps(rtn)
