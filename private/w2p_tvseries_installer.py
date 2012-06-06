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
import shutil
import urllib
import sys
import zipfile
import hashlib
import datetime

#adapted from http://code.activestate.com/recipes/465649-file-unzip-lite/
def extract( filename, dir ):
    zf = zipfile.ZipFile( filename )
    namelist = zf.namelist()
    filelist = filter( lambda x: not x.endswith( '/' ), namelist )
    # make base
    pushd = os.getcwd()
    if not os.path.isdir( dir ):
        os.mkdir( dir )
    os.chdir( dir )
    filelist.sort()
    for fn in filelist:
        try:
            finalpath = os.path.normpath(os.path.join(dir, fn))
            dirname = os.path.dirname(finalpath)
            if not dirname.startswith(dir):
                continue
            else:
                if not os.path.exists(dirname):
                    os.makedirs(dirname)
                out = open( finalpath, 'wb' )
                out.write(zf.read(fn))
                out.close()
        finally:
            print fn
    os.chdir( pushd )

def download(url, file):
    zipball = open(file, 'wb')
    try:
        handle = urllib.urlopen(url)
        while True:
            block = handle.read(1024*64)
            zipball.write(block)
            if len(block) == 0:
                break
            print '.',
        print 'Downloaded'
        return 1
    except:
        zipball.close()
    return 0

if __name__ == '__main__':
    basefolder = os.getcwd()
    w2p_folder = os.path.join(basefolder, 'web2py')
    w2p_archive = os.path.join(basefolder, 'web2py_src.zip')
    zipball = os.path.join(basefolder, 'w2p_tvseries_tarball.zip')
    ARCHIVE_MD5 = 'a478f3091620612ceb86e193502967fa'
    if not os.path.exists(w2p_folder):
        if raw_input('There is no web2py in this path. Download it from internet (y/n)?').lower() in ['y', 'yes']:
            web2py_url = 'http://www.web2py.com/examples/static/web2py_src.zip'
            if not download(web2py_url, w2p_archive):
                print 'problems downloading from web2py.com, try again later'
                sys.exit(1)
            if os.path.exists(w2p_archive):
                with open(w2p_archive, 'rb') as g:
                    calc_md5 = hashlib.md5(g.read()).hexdigest()
                if calc_md5 != ARCHIVE_MD5:
                    print calc_md5
                    print "Downloaded archive corrupted, exiting..."
                    sys.exit(1)
                extract(w2p_archive, basefolder)
    if not os.path.exists(w2p_folder):
        print 'web2py folder undetected, exiting...'
        sys.exit(1)

    if w2p_folder not in sys.path:
        sys.path.insert(0, w2p_folder)
    os.chdir(w2p_folder)
    from gluon import main
    from gluon.fileutils import fix_newlines, recursive_unlink
    from gluon.shell import run
    from gluon.admin import app_compile
    from gluon.compileapp import remove_compiled_application
    from gluon.storage import Storage


if raw_input('update/download app from internet (y/n)?').lower() in ['y', 'yes']:
    w2p_tvseries_url = 'https://github.com/niphlod/w2p_tvseries/zipball/master'

    destfolder = os.path.normpath(os.path.abspath(os.path.join(w2p_folder, 'deposit', '%s' % datetime.datetime.now().strftime('%f'))))
    if not os.path.exists(destfolder):
        os.makedirs(destfolder)
    if not download(w2p_tvseries_url, zipball):
        print 'problems downloading from github, please try again later'
        sys.exit(1)

    print 'unzipping into %s' % destfolder
    extract(zipball, destfolder)
    if not os.listdir(destfolder):
        print 'Problems downloading or extracting, Aborting auto-install'
        sys.exit(1)
    sourcefolder = os.path.abspath(os.path.join(destfolder, os.listdir(destfolder)[0]))
    appbckfolder = os.path.abspath(os.path.join(w2p_folder, 'applications', 'w2p_tvseries_bck'))
    finalfolder = os.path.abspath(os.path.join(w2p_folder, 'applications', 'w2p_tvseries'))

    if os.path.exists(appbckfolder):
        print 'cleaning %s' % appbckfolder
        recursive_unlink(appbckfolder)

    if os.path.exists(finalfolder):
        print 'backupping current from %s to %s' % (finalfolder, appbckfolder)
        shutil.move(finalfolder, appbckfolder)

    print 'overwriting %s with %s' % (finalfolder, sourcefolder)
    shutil.copytree(sourcefolder, finalfolder)

    print 'cleaning %s' % (destfolder)
    recursive_unlink(destfolder)

    print 'fixing newlines in %s' % (destfolder)
    fix_newlines(destfolder)


if raw_input('w2p_tvseries needs a patched scheduler to work as a cron script. Can I overwrite it (y/n)?'
            ).lower() in ['y', 'yes']:
    new_scheduler = os.path.join(w2p_folder, 'applications', 'w2p_tvseries', 'private', 'scheduler.py')
    old_scheduler = os.path.join(w2p_folder, 'gluon', 'scheduler.py')
    shutil.copy(new_scheduler, old_scheduler)

if raw_input("let's create/migrate our database.... (y/n)?").lower() in ['y', 'yes']:
    remove_compiled_application(os.path.join(w2p_folder, 'applications', 'w2p_tvseries'))
    model_file = os.path.join(w2p_folder, 'applications', 'w2p_tvseries', 'models', 'db.py')
    print 'setting migrate to True, just to be sure'
    with open(model_file) as g:
        content = g.read().replace("MIGRATE = False", "MIGRATE = True")
    with open(model_file, 'w') as g:
        g.write(content)

    run('w2p_tvseries/manage/stop_operations')
    print 'migration occurred, setting migrate to False'

    with open(model_file) as g:
        content = g.read().replace("MIGRATE = True", "MIGRATE = False")
    with open(model_file, 'w') as g:
        g.write(content)

    print 'migrate set to False'

if raw_input("(re)compile application (y,n) ?").lower() in ['y','yes']:
    request = Storage(folder=os.path.abspath(os.path.join(w2p_folder, 'applications', 'w2p_tvseries')))
    remove_compiled_application(os.path.join(w2p_folder, 'applications', 'w2p_tvseries'))
    app_compile('w2p_tvseries', request)

if raw_input("copy default redirection (if this is the only app installed, it's safe to say yes) (y/n)?"
            ).lower() in ['y', 'yes']:
    routes_src = os.path.abspath(os.path.join(w2p_folder, 'applications', 'w2p_tvseries', 'private', 'routes.py'))
    routes_dst = os.path.abspath(os.path.join(w2p_folder, 'routes.py'))
    if not os.path.exists(routes_dst):
        shutil.copy(routes_src, routes_dst)

if raw_input("Create start scripts (y/n)?").lower() in ['y', 'yes']:
    startfiledos = """
cd web2py
start "%(executable)s" web2py.py -K w2p_tvseries
start "%(executable)s" web2py.py -a w2p_tvseries
""" % dict(executable=sys.executable)

    startfilelinux = """
cd web2py
"%(executable)s" web2py.py -a w2p_tvseries &
"%(executable)s" web2py.py -K w2p_tvseries
""" % dict(executable=sys.executable)

    cronscript = """
"%(executable)s" "%(cronfile)s"
"""  % dict(executable=sys.executable, cronfile=os.path.join(w2p_folder, 'applications', 'w2p_tvseries', 'private', 'w2p_tvseries.py'))

    if sys.platform.startswith('win'):
        with open(os.path.join(basefolder, 'start_web_and_scheduler.bat'), 'w') as g:
            g.write(startfiledos)
        with open(os.path.join(basefolder, 'cronscript.bat'), 'w') as g:
            g.write(cronscript)

    elif sys.platform.startswith('linux'):
        with open(os.path.join(basefolder, 'start_web_and_scheduler.sh'), 'w') as g:
            g.write(startfilelinux)
        with open(os.path.join(basefolder, 'cronscript.sh'), 'w') as g:
            g.write(cronscript)

print "Enjoy w2p_tvseries"
for file in [w2p_archive, zipball]:
    if os.path.exists(file):
        os.unlink(file)
