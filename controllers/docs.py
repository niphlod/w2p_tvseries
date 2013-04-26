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

def index():
    session.forget(response)
    redirect(URL('page', args=['index']))

def page():
    session.forget(response)
    content = ''
    path = path_to_file(request)
    if os.path.exists(path) and os.path.isfile(path):
        with open(path) as g:
            content = g.read()
    else:
        raise HTTP(404)
    def url2(*a,**b):
        b['host'] = False
        b['scheme'] = False
        b['args'] = [q for q in b['args'] if q <> 'def']
        return URL(*a,**b)

    return dict(content=MARKMIN(content, url=url2, extra=dict(images=lambda x : '')), path=path)

def path_to_file(request):
    folders = request.args
    if not request.args:
        folders = ['index']
    return "%s.markmin" % os.path.join(request.folder, 'private', 'docs', *folders)
