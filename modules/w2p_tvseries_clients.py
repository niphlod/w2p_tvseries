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
import subprocess
import re
import sys

from gluon.storage import Storage

class w2p_tvseries_client(object):
    def __init__(self):
        pass

    def get_status(self):
        """list of dicts
        id, hash, filename, perc, status, addinfo
        """

class Amule(w2p_tvseries_client):

    def __init__(self):
        self.executable = "amulecmd"
        self.commands = ["-c", "show dl"]
        self.firstr = re.compile(r' > ([A-Z0-9]{32}) (.*)')
        self.secondr = re.compile(r' >?[^-]*\[(.*)%\]?[^-]* - ([^-]*) - ')

    def get_status(self):
        cmds = [self.executable]
        cmds.extend(self.commands)
        p = subprocess.Popen(cmds, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output = p.stdout.read()
        lines = output.split('\n')
        res = []
        while True:
            try:
                line = lines.pop(0)
            except:
                break
            if '>' not in line:
                continue
            fmatch = self.firstr.match(line)
            if fmatch:
                line = lines.pop(0)
                smatch = self.secondr.match(line)
            if fmatch and smatch:
                hash = fmatch.group(1)
                filename = fmatch.group(2)
                perc = smatch.group(1)
                status = smatch.group(2)
                res.append(
                    Storage(
                        hash=hash,
                        filename=filename,
                        perc=float(perc),
                        status=status
                    )
                )
        return res

class Utorrent(w2p_tvseries_client):
    def __init__(self):
        pass

    def get_status(self):
        pass

if __name__ == '__main__':
    amule = Amule()
    print amule.get_status()