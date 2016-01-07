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

response.title = 'w2p_tvseries'
response.subtitle = 'Another TV Series Organizer!'

## read more at http://dev.w3.org/html5/markup/meta.name.html
response.meta.author = 'Niphlod'
response.meta.description = 'TV Series Organizer!'
response.meta.keywords = 'TV Series Organizer!'
response.meta.generator = 'Web2py Web Framework'
response.meta.copyright = 'Copyright 2014'

MIGRATE = True
LAZY_TABLES = False

response.generic_patterns = ['*'] if request.is_local else []
response.static_version = '1.3.26'

db = DAL(
    "sqlite://storage.db",
    migrate=MIGRATE,
    attempts=10,
    lazy_tables=LAZY_TABLES,
    driver_args= {'timeout': 30}
    )
db2 = DAL(
    "sqlite://storage_scheduler.db",
    migrate=MIGRATE,
    attempts=10,
    lazy_tables=LAZY_TABLES,
    driver_args= {'timeout': 30}
    )

from gluon.storage import Storage
from gluon import current
current.w2p_tvseries = Storage(database = db, database2 = db2)

from gluon.tools import Auth, Crud, Service, PluginManager, prettydate
crud, service, plugins = Crud(db), Service(), PluginManager()


STATIC_FOLDER = os.path.join(request.folder, 'static', 'deposit')

#from gluon.custom_import import track_changes; track_changes(True)

db.define_table("series",
    Field("seriesid", "integer"),
    Field("language", length=3),
    Field("overview", 'text'),
    Field("name"),
    Field("genre", "list:string"),
    Field("status"),
    Field("lastupdated", 'integer'),
    Field("basepath", 'text', unique=True),
    format='%(id)s - %(name)s'
)

db.define_table("episodes",
    Field("seriesid", "integer", requires=IS_IN_DB(db, 'series.seriesid', 'series.name')),
    Field("seasonid", "integer"),
    Field("episodeid", "integer"),
    Field("language", length=3),
    Field("seasonnumber", "integer"),
    Field("name"),
    Field("epnumber", "integer"),
    Field("tracking", "boolean", default=True),
    Field("absolute_number", "integer"),
    Field("overview", 'text'),
    Field("firstaired", 'date'),
    Field("lastupdated", "integer"),
    Field("filename"),
    Field("inserted_on", 'datetime', default=request.utcnow),
    format='S%(seasonnumber).2dE%(number).2d - %(name)s'
)

db.define_table("global_settings",
    Field("kkey"),
    Field("value")
)

db.define_table("seasons_settings",
    Field("series_id", "integer", requires=IS_IN_DB(db, 'series.id', 'series.name')),
    Field("ref_urls", "list:string"),
    Field("seasonnumber", "integer"),
    Field("tracking", "boolean", default=False),
    Field("subtitle_tracking", "boolean", default=False),
    Field("subtitle_settings", "text", default="{}"),
    Field("season_status", "text", default='{}'),
    Field("torrent_settings", "text", default='{}'),
    Field("torrent_tracking", "boolean", default=False),
    Field("scooper_strings", "list:string"),
    Field("updated_on", 'datetime')
)

db.define_table("rename_log",
    Field("series_id", "integer"),
    Field("seasonnumber", "integer"),
    Field("file_from", 'text'),
    Field("file_to", "text"),
    Field("dat_insert", 'datetime', default=request.utcnow, update=request.utcnow)
)

db.define_table("global_log",
    Field("log_module"),
    Field("log_function"),
    Field("log_operation", 'text'),
    Field("log_error", 'text'),
    Field("dat_insert", 'datetime', default=request.utcnow)
)

db.define_table("urlcache",
    Field("kkey", length=512),
    Field("value", 'blob'),
    Field("inserted_on", 'datetime')
)

db.define_table("episodes_banners",
    Field("episode_id", requires=IS_IN_DB(db, 'episodes.id', 'episodes.name')),
    Field("banner", "upload", uploadseparate=True, uploadfolder=STATIC_FOLDER, autodelete=True),
    Field("url", length=150)
)

db.define_table("series_banners",
    Field("series_id", "integer", requires=IS_IN_DB(db, 'series.id', 'series.name')),
    Field("banner", "upload", uploadseparate=True, uploadfolder=STATIC_FOLDER, autodelete=True),
    Field("url", length=150)
)

db.define_table("episodes_metadata",
    Field("episode_id", "integer"), #leave room for episodes not in list
    Field("series_id", "integer"),
    Field("seasonnumber", "integer"),
    Field("filename"),
    Field("guid"),
    Field("ed2k"),
    Field("md5"),
    Field("sha1"),
    Field("osdb"),
    Field("filesize", 'integer'),
    Field("infos", 'text')
)

db.define_table("downloads",
    Field("category", default="torrent"),
    Field("episode_id", requires=IS_IN_DB(db, 'episodes.id', 'episodes.name')),
    Field("series_id", "integer"),
    Field("seasonnumber", "integer"),
    Field("guid", length=150),
    Field("link"),
    Field("magnet"),
    Field("down_file", "blob"),
    Field("queued", "boolean", default=False),
    Field("queued_at", "datetime", default=request.utcnow, update=request.utcnow)
)
