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
from w2p_tvseries_utils import w2p_tvseries_settings

def index():
    settings_ = w2p_tvseries_settings()
    gsettings = settings_.global_settings()
    if len(gsettings) < 7:
        session.flash = "Please adjust your preferences"
        redirect(URL('settings'))
    return dict()

def settings():
    settings_ = w2p_tvseries_settings()
    settings = settings_.general_settings()
    gsettings = settings_.global_settings()

    for k,v in gsettings.iteritems():
        settings.defaults[k] = v

    fi = [
        Field(k, settings.types.get(k, 'string'), comment=settings.comments[k],
              default=settings.defaults[k], widget=settings.widgets[k], requires=settings.requires[k])
        for k in settings.fields
    ]

    form = SQLFORM.factory(
        *fi, submit_button="Save Settings"
    )
    form.wells = [
        dict(
            title="General Settings",
            fields=['series_language', 'season_path', 'series_basefolder', 'series_metadata']
        ),
        dict(
            title="Scooper Settings",
            fields=['scooper_path']
        ),
        dict(
            title="Torrent Defaults",
            fields=['torrent_path', 'torrent_magnet', 'torrent_default_feed','torrent_default_quality','torrent_default_minsize', 'torrent_default_maxsize']
        ),
        dict(
            title="Subtitles Settings",
            fields=['itasa_username','itasa_password','subtitles_default_method','subtitles_default_quality', 'subtitles_default_language']
        )
        ]

    if form.process(hideerror=True).accepted:
        for a in form.vars:
            if a == 'itasa_password':
                if form.vars[a] <> 8*('*'):
                    db.global_settings.update_or_insert(db.global_settings.kkey == a, value = form.vars[a], kkey=a)
            elif a == 'series_basefolder':
                db.global_settings.update_or_insert(db.global_settings.kkey == a, value = form.vars[a].strip(), kkey=a) ##FIXME
            elif a == 'scooper_path':
                values = form.vars[a]
                if not isinstance(values, (tuple,list)):
                    values = [values]
                values = [a.strip() for a in values] #FIXME
                db(
                    (db.global_settings.kkey=='scooper_path') &
                    (~db.global_settings.value.belongs(values))
                  ).delete()
                for b in values:
                    if b and b not in settings.defaults['scooper_path']:
                        db.global_settings.insert(kkey='scooper_path', value=b)
            else:
                db.global_settings.update_or_insert(db.global_settings.kkey == a, value = form.vars[a], kkey=a)

        settings_.global_settings(refresh=True)
        session.flash = 'settings updated correctly'
        redirect(URL(r=request, args=request.args))
    elif form.errors:
        response.flash = 'errors in form, please check'

    return dict(form=form)
