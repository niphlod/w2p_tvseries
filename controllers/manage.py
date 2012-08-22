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

import datetime
import time
from gluon.serializers import json
from gluon.contrib import simplejson as sj
from gluon.storage import Storage
import urllib
import os
from w2p_tvseries_feed import w2p_tvseries_feed_loader
from w2p_tvseries_tvdb import w2p_tvseries_tvdb_loader
from w2p_tvseries_utils import tvdb_scooper_loader, w2p_tvseries_settings

def index():
    session.forget()
    redirect(URL('series', 'index'))

def add():
    gs = w2p_tvseries_settings().global_settings()
    language = gs.language or 'en'
    error = None
    res = []
    form = SQLFORM.factory(Field("series_name", requires=IS_NOT_EMPTY()), showid=False)
    if form.process(hideerror=True).accepted:
        try:
            tvdb = w2p_tvseries_tvdb_loader()
            res = tvdb.search_series(form.vars.series_name, language)
        except:
            res = []
            error = 'Sorry, timeout on thetvdb.com, try again later'
            response.flash = ''
    return dict(res=res, form=form, error=error)

def delete():
    if not request.args(0):
        return ''
    rec = False
    rec = db(db.series.id == request.args(0)).select().first()
    if not rec:
        return dict(rec=rec, message="Series not found")
    if not request.vars.confirm:
        return dict(rec=rec, message="Are you sure ?")
    try:
        #retrieve_eplist
        eplist = db(db.episodes.seriesid == rec.seriesid).select(db.episodes.id)

        eplist = [row.id for row in eplist]

        #delete downloads
        down =  db(db.downloads.episode_id.belongs(eplist)).delete()

        #delete episodes_metadata

        meta = db(db.episodes_metadata.episode_id.belongs(eplist)).delete()

        #delete episodes_banners

        ep_ba = db(db.episodes_banners.episode_id.belongs(eplist)).delete()

        #delete episodes

        eps = db(db.episodes.id.belongs(eplist)).delete()

        #delete seasons_settings

        ss = db(db.seasons_settings.series_id == rec.id).delete()

        #delete series
        db(db.series.id == rec.id).delete()
    except:
        return dict(rec=rec, message="Series couldn't be deleted")

    return dict(rec=rec, message="Series deleted correctly")

def add_series():
    seriesid = request.args(0)
    language = request.args(1)
    if not (seriesid and language):
        return ''

    if not request.vars.task_id:
        db2(db2.scheduler_task.task_name == request.cid).delete()
        task_id = db2.scheduler_task.insert(task_name=request.cid, function_name='add_series', args=json([seriesid, language]))
        return json(dict(task_id=task_id))

    res = db2(
        (db2.scheduler_run.scheduler_task == request.vars.task_id) &
        (db2.scheduler_run.status == 'COMPLETED')
        ).select(limitby=(0,1), orderby=db2.scheduler_run.id).first()

    if not res:
        rtn = json(dict(message='working on it...'))
    if res:
        rtn = json(dict(message='added'))
        location = URL('series', 'index', args=[sj.loads(res.result)], vars=dict(settings=1))
        response.js = "handle.stop(); window.location = '%s';" % (location)

    return rtn

def preview_torrents():
    vars = Storage()
    for k,v in request.vars.iteritems():
        vars[k.replace('tor_','',1)] = v
    try:
        vars.minsize = vars.minsize and int(vars.minsize) or 20
        vars.maxsize = vars.maxsize and int(vars.maxsize) or 4780
        vars.regex = vars.regex and vars.regex == '' and None or vars.regex
    except:
        return ''
    if vars.season <> 'ALL':
        try:
            vars.season = int(vars.season)
        except:
            return ''

    ez = w2p_tvseries_feed_loader(vars.feed)
    res = ez.search(vars.show_name, vars.season, vars.quality, vars.minsize, vars.maxsize, vars.regex, vars.lower_attention)

    return dict(res=res)

def preview_scooper():
    scoop = tvdb_scooper_loader()
    scoop.scoop()
    res = {}
    vars = request.vars.scooper_strings
    if not isinstance(vars, list):
        vars = [vars]
    vars = [a for a in vars if a <> '']
    for a in vars:
        res[a] = scoop.preview(a)

    examples = scoop.find_patterns()
    return dict(form='', res=res, examples=examples)



def series_settings():
    series_id = request.args(0)
    if not series_id:
        return ''

    validate_seasons(series_id)

    settings = w2p_tvseries_settings()
    seasons_settings = db(db.seasons_settings.series_id == series_id).select()
    series = db.series(series_id)
    series_name = series.name

    forms = []
    active_tab = 0
    i = 0

    global_settings = db(db.global_settings.id>0).select()
    starts = 'torrent_default_'
    tor_global_settings = dict([(row.kkey.replace(starts,''), row.value) for row in global_settings if row.kkey.startswith(starts)])
    starts = 'subtitles_default_'
    sub_global_settings = dict([(row.kkey.replace(starts,''), row.value) for row in global_settings if row.kkey.startswith(starts)])

    season_number = {}

    for row in seasons_settings:
        key = "season_%s" % row.id
        season_number[i] = row.seasonnumber
        torrent_settings = settings.torrent_settings()
        #update defaults with globals
        torrent_settings.defaults.update(tor_global_settings)
        #update defaults with season settings
        season_settings = sj.loads(row.torrent_settings)
        torrent_settings.defaults.update(season_settings)
        if not torrent_settings.defaults.show_name:
            torrent_settings.defaults.show_name = series_name
        if not torrent_settings.defaults.season:
            torrent_settings.defaults.season = row.seasonnumber
        torrent_fi = [
            Field("tor_%s" % k, torrent_settings.types.get(k, 'string'), comment=torrent_settings.comments[k]
                  , default=torrent_settings.defaults[k], widget=torrent_settings.widgets[k]
                  , requires=torrent_settings.requires[k]
                  , label = torrent_settings.labels.get(k, k.replace('_', ' ').title())
                  ) for k in torrent_settings.fields
            ]

        subtitles_settings = settings.subtitle_settings()
        #update defaults with globals
        subtitles_settings.defaults.update(sub_global_settings)
        #update defaults with season settings
        season_settings = sj.loads(row.subtitle_settings)
        subtitles_settings.defaults.update(season_settings)
        subtitle_fi = [
            Field("sub_%s" % k, subtitles_settings.types.get(k, 'string'), comment=subtitles_settings.comments[k]
                  , default=subtitles_settings.defaults[k], widget=subtitles_settings.widgets[k]
                  , requires=subtitles_settings.requires[k]
                  ) for k in subtitles_settings.fields
        ]

        tracking_fi = [
            Field('tracking',
                  'boolean',
                  default=row.tracking
                  ,label="Season tracking"
                  ),
            Field('torrent_tracking',
                  'boolean',
                  default=row.torrent_tracking
                  ),
            Field('subtitle_tracking',
                  'boolean',
                  default=row.subtitle_tracking
                  )
        ]

        others_fi = [
            Field("ref_urls",
                'list:string',
                default=row.ref_urls,
                label="Reference urls"
                ),
            Field("scooper_strings",
                  'list:string',
                  default=row.scooper_strings,
                  label="Scooper masks"
            )
        ]

        all_fields = torrent_fi + subtitle_fi + tracking_fi + others_fi

        form = SQLFORM.factory(*all_fields, table_name=key, hidden=dict(ss_id=row.id),
                               buttons=[
                                BUTTON("Save Changes", _class="btn btn-primary"),
                                BUTTON("Preview torrents", _class="btn btn-info pre_torrents",
                                  _href=URL('manage', 'preview_torrents.load')),
                                BUTTON("Preview scooper", _class="btn btn-info pre_scooper",
                                  _href=URL('manage', 'preview_scooper.load'))
                                ]
                               )
        form.wells = [
            dict(
            title="General Settings",
            fields=['tracking', 'torrent_tracking', 'subtitle_tracking', 'ref_urls']
            ),
            dict(
                title="Subtitles",
                fields=["sub_%s" % a for a in subtitles_settings.fields]
            ),
            dict(
                title="Torrents",
                fields=["tor_%s" % a for a in torrent_settings.fields]
            ),
            dict(
                title="Scooper Settings",
                fields=['scooper_strings']
            )
        ]
        if form.process(formname=key, hideerror=True, onvalidation=series_settings_validate).accepted:
            tor_fields = ["tor_%s" % a for a in torrent_settings.fields]
            tor_vars = Storage([(a.replace('tor_','',1), form.vars[a]) for a in tor_fields])

            if tor_vars.regex == '':
                tor_vars.regex = None

            sub_fields = ["sub_%s" % a for a in subtitles_settings.fields]
            sub_vars = Storage([(a.replace('sub_','',1), form.vars[a]) for a in sub_fields])
            season_fields = ['tracking', 'torrent_tracking', 'subtitle_tracking', 'ref_urls', 'scooper_strings']
            season_vars = Storage([(a, form.vars[a]) for a in season_fields])
            for k,v in season_vars.iteritems():
                if k in ['ref_urls', 'scooper_strings']:
                    if not isinstance(v, list):
                        season_vars[k] = [v]

            sub_fields = sj.dumps(sub_vars)
            tor_fields = sj.dumps(tor_vars)
            row.update_record(**season_vars)
            if row.torrent_tracking:
                row.update_record(torrent_settings=tor_fields)
            if row.subtitle_tracking:
                row.update_record(subtitle_settings=sub_fields)

            session.flash = 'Settings for season %s accepted' % (row.seasonnumber)
            redirect(URL(r=request, args=request.args, vars=dict(active_tab=i)))

        elif form.errors:
            response.flash = 'errors in form, please check'
        i += 1
        forms.append(
            form
        )

    suggested = None

    if series.basepath == '' or series.basepath == None:
        suggested = "w2p_tvseries guessed this path. Please press on save if you're okay with that"
    db.series.basepath.widget = myfolderwidget

    form_series = SQLFORM(db.series, series, fields=['basepath'], showid=False, submit_button = 'Save folder')
    if suggested:
        form_series.vars.basepath = get_series_path(series.id)
    if form_series.process(formname='series', hideerror=True, onvalidation=series_basefolder_validate).accepted:
        session.flash = 'settings saved'
        redirect(URL(r=request, args=request.args, vars=dict(active_tab=request.vars.active_tab or active_tab)))
    elif form_series.errors:
        response.flash = 'errors in form, please check'
    return dict(form_series=form_series, forms=forms, suggested=suggested, series=series, season_number=season_number)

def series_basefolder_validate(form):
    form.vars.basepath = form.vars.basepath.strip() ##FIXME

def series_settings_validate(form):
    for a in form.vars:
        if a.startswith('ref_urls') and form.vars[a] <> '':
            errors = []
            if isinstance(form.vars[a], list):
                for b in form.vars[a]:
                    if b == '':
                        continue
                    value, err = IS_URL()(b)
                    if err:
                        errors.append("%s is not a valid URL" % b)
                form.vars[a] = [IS_URL()(b)[0] for b in form.vars[a]]
                if len(errors) > 0:
                    form.errors[a] = UL(errors)
            else:
                value, err = IS_URL()(form.vars[a])
                if err:
                    form.errors[a] = err
                form.vars[a] = IS_URL()(form.vars[a])[0]
    if form.vars.sub_method == 'itasa' and form.vars.sub_language <> 'ita':
        form.errors.sub_language = "Itasa is available only for ITA"
    if form.vars.tor_season and form.vars.tor_season <> 'ALL':
        try:
            int(form.vars.tor_season)
        except:
            form.errors.tor_season = 'You must enter a number or "ALL"'


    all_strings = db(
                (db.seasons_settings.id <> request.vars.ss_id) &
                (db.seasons_settings.series_id == db.series.id)
                ).select(db.series.name, db.seasons_settings.seasonnumber, db.seasons_settings.scooper_strings)
    all = []
    masks = form.vars.scooper_strings
    if isinstance(form.vars.scooper_strings, str):
        masks = [masks]
    masks = [mask for mask in masks if mask <> '']
    single_masks = dict([(k,1) for k in masks])
    masks = single_masks.keys()
    form.vars.scooper_strings = masks
    status = 0
    for row in all_strings:
        if row.seasons_settings.scooper_strings and len(row.seasons_settings.scooper_strings)>0:
            for a in row.seasons_settings.scooper_strings:
                for b in masks:
                    if b in a:
                        form.errors.scooper_strings = 'String "%s" present for series %s, season %s will prevail on "%s"' % (a, row.series.name, row.seasons_settings.seasonnumber, b)
                        return

def stop_operations():
    db2(db2.scheduler_task.status <> 'RUNNING').delete()
    db(db.global_settings.kkey == 'operation_key').delete()
    return 1

def episode_tracking():
    ep_id = request.args(0)
    if not ep_id:
        return ''
    rec = db.episodes(ep_id)
    trackingid = "episode_tracking_%s" % rec.id
    if rec.tracking:
        rec.update_record(tracking=False)
        rtnclass = 'btn btn-danger'
        rtntext = 'Episode Tracking: Off'
        title = 'Click to track'
    else:
        rec.update_record(tracking=True)
        rtnclass = 'btn btn-success'
        rtntext = 'Episode Tracking: On'
        title = 'Click to not track'

    return A(rtntext, callback=URL('manage', 'episode_tracking', args=[rec.id]), target=trackingid, _class=rtnclass, _title=title)

def bit():

    cond_series = db(db.series.id>0)
    cond_path = db(db.rename_log.id>0)
    vars = request.get_vars
    if vars.series_name and vars.series_name <> '':
        cond_series = cond_series(db.series.id == vars.series_name)
    if vars.seasonnumber and vars.seasonnumber <> '':
        cond_series = cond_series(db.seasons_settings.seasonnumber == vars.seasonnumber)
    if vars.paths and vars.paths <> '':
        cond_path = cond_path(db.rename_log.file_to.startswith(vars.paths))
    if vars.date_from and vars.date_from <> '':
        vars.date_from = datetime.datetime.strptime(vars.date_from, T('%Y-%m-%d %H:%M:%S', lazy=False))
        cond_path = cond_path(db.rename_log.dat_insert > vars.date_from)
    if vars.date_to and vars.date_to <> '':
        vars.date_to = datetime.datetime.strptime(vars.date_to, T('%Y-%m-%d %H:%M:%S', lazy=False))
        cond_path = cond_path(db.rename_log.dat_insert < vars.date_to)

    #all folders
    folders = cond_series((db.seasons_settings.tracking == True) & (db.seasons_settings.series_id == db.series.id))
    folders = folders.select()

    all_folders = []
    for row in folders:
        folder = get_season_path(row.seasons_settings.series_id, row.seasons_settings.seasonnumber)
        if folder:
            all_folders.append(folder)

    all_files = {}
    for folder in all_folders:
        all_files[folder] = [os.path.join(folder, a) for a in os.listdir(folder) if os.path.isfile(os.path.join(folder, a))]

    all_files_records = {}
    for k,v in all_files.iteritems():
        contents = cond_path(db.rename_log.file_to.belongs(v)).select(orderby=~db.rename_log.id)
        if contents.first():
            all_files_records[k] = cond_path(db.rename_log.file_to.belongs(v)).select(orderby=~db.rename_log.id)

    form = SQLFORM.factory(
        Field('paths', default=vars['paths'], requires=IS_IN_SET(all_folders)),
        Field('seasonnumber', default=vars['seasonnumber'], requires=IS_IN_SET(set([row.seasons_settings.seasonnumber for row in folders]))),
        Field('series_name', default=vars['series_name'], requires=IS_IN_SET(dict([(row.series.id, row.series.name) for row in folders]))),
        Field('date_from', 'datetime', default=vars['date_from']),
        Field('date_to', 'datetime', default=vars['date_to']),
        buttons=[
                BUTTON(w2p_icon('filter', variant='white'), "Filter Results", _class="btn btn-primary"),
                A(w2p_icon('reset', variant='white'), "Reset Filters", _class="btn btn-info",
                  _href=URL('bit', vars={}))
        ],
        _method = 'GET',
        _enctype = 'application/x-www-form-urlencoded'
    )

    return dict(all_files_records=all_files_records, all_files=all_files, form=form)
