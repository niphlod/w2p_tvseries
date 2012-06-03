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

import thread
from w2p_tvseries_utils import tvdb_logger
#from w2p_tvseries_feed import w2p_tvseries_torrent#, w2p_tvseries_feed, Eztv_feed, Torrentz_feed
from gluon import current


locker = thread.allocate_lock()

def w2p_tvseries_loader(*args, **vars):
    locker.acquire()
    type = args[0]
    args = args[1:]
    try:
        if not hasattr(w2p_tvseries_loader, 'w2p_tvseries_loader_instance_%s' % (type)):
            types = dict(
                #w2p_tvseries_torrent=w2p_tvseries_torrent,
                #w2p_tvseries_feed=w2p_tvseries_feed,
                #Eztv_feed=Eztv_feed,
                #Torrentz_feed=Torrentz_feed,
                tvdb_logger=tvdb_logger
            )
            setattr(w2p_tvseries_loader, 'w2p_tvseries_loader_instance_%s' % (type),  types[type](*args, **vars))
    finally:
        locker.release()
    return getattr(w2p_tvseries_loader, 'w2p_tvseries_loader_instance_%s' % (type))
