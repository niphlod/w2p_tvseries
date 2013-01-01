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
import datetime
import time

def wait_and_exit(rtncode=0):
    time.sleep(5)
    sys.exit(rtncode)

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
            pass
    os.chdir( pushd )

def download(url, file):
    zipball = open(file, 'wb')
    try:
        handle = urllib.urlopen(url)
        x = 0
        while True:
            x += 1
            block = handle.read(1024*64)
            zipball.write(block)
            if len(block) == 0:
                break
            if x % 3 == 0:
                print '... %s KB' % (x*64)
        print 'Downloaded'
        return 1
    except:
        zipball.close()
    return 0

def overwrite(src, dst):
    for src_dir, dirs, files in os.walk(src):
        dst_dir = src_dir.replace(src, dst)
        if not os.path.exists(dst_dir):
            os.mkdir(dst_dir)
        for file_ in files:
            src_file = os.path.join(src_dir, file_)
            dst_file = os.path.join(dst_dir, file_)
            if os.path.exists(dst_file):
                os.remove(dst_file)
            shutil.move(src_file, dst_dir)

def parse_tvseries_version(version_file):
    with open(version_file) as g:
        version = g.read().replace('\n', '').strip()
    version = version.split('.')
    return [int(a) for a in version]


def update_w2p_tvseries(w2p_folder, version):
    if raw_input('Q:    Update/download app from internet ([Y]/n)?').lower() in ['y', 'yes']:
        version = '.'.join([str(a) for a in version])
        print '  INFO: Downloading version %s' % version
        w2p_tvseries_url = 'https://github.com/niphlod/w2p_tvseries/zipball/%s' % version

        destfolder = os.path.normpath(os.path.abspath(os.path.join(w2p_folder, 'deposit', '%s' % datetime.datetime.now().strftime('%f'))))
        if not os.path.exists(destfolder):
            os.makedirs(destfolder)
        if not download(w2p_tvseries_url, zipball):
            print '  ERROR: Problems downloading from github, please try again later'
            wait_and_exit(1)

        print '  INFO: unzipping into %s' % destfolder
        extract(zipball, destfolder)
        if not os.listdir(destfolder):
            print '  ERROR: Problems downloading or extracting, Aborting auto-install'
            wait_and_exit(1)
        sourcefolder = os.path.abspath(os.path.join(destfolder, os.listdir(destfolder)[0]))
        appbckfolder = os.path.abspath(os.path.join(w2p_folder, 'applications', 'w2p_tvseries_bck'))
        finalfolder = os.path.abspath(os.path.join(w2p_folder, 'applications', 'w2p_tvseries'))

        if os.path.exists(appbckfolder):
            print '  INFO: cleaning %s' % appbckfolder
            recursive_unlink(appbckfolder)

        if os.path.exists(finalfolder):
            print '  INFO: backupping current from %s to %s' % (finalfolder, appbckfolder)
            shutil.copytree(finalfolder, appbckfolder)

        print '  INFO: overwriting %s with %s' % (finalfolder, sourcefolder)
        overwrite(sourcefolder, finalfolder)

        print '  INFO: cleaning %s' % (destfolder)
        recursive_unlink(destfolder)

        print '  INFO: fixing newlines in %s' % (finalfolder)
        fix_newlines(finalfolder)

        print '  INFO: updating static files with latest version'
        sourcefile = os.path.abspath(os.path.join(w2p_folder, 'applications', 'welcome' , 'static', 'js', 'web2py.js'))
        destfile = os.path.abspath(os.path.join(finalfolder, 'static', 'js', 'web2py.js'))
        os.unlink(destfile)
        shutil.copy(sourcefile, destfile)

if __name__ == '__main__':
    if sys.executable.endswith('web2py.exe'):
        basefolder = os.path.normpath(os.path.join(os.getcwd(), '..'))
        __file__ = os.path.join(basefolder, 'w2p_tvseries_installer.py')
    else:
        basefolder = os.getcwd()
    w2p_folder = os.path.join(basefolder, 'web2py')
    w2p_archive = os.path.join(basefolder, 'web2py_src.zip')
    zipball = os.path.join(basefolder, 'w2p_tvseries_tarball.zip')
    w2p_git_version_url = 'https://raw.github.com/niphlod/w2p_tvseries/master/private/VERSION'
    w2p_git_version_file = os.path.join(basefolder, 'VERSION')
    current_version_file = os.path.join(w2p_folder, 'applications', 'w2p_tvseries', 'private', 'VERSION')
    this_file_path = os.path.abspath(__file__)
    updater_url = 'https://raw.github.com/niphlod/w2p_tvseries/master/private/w2p_tvseries_installer.py'
    if not os.path.exists(w2p_folder):
        if raw_input('Q:    There is no web2py in this path. Download it from internet ([Y]/n)?').lower() in ['y', 'yes']:
            web2py_url = 'http://www.web2py.com/examples/static/web2py_src.zip'
            if not download(web2py_url, w2p_archive):
                print '  INFO: problems downloading from web2py.com, try again later'
                wait_and_exit(1)
            if os.path.exists(w2p_archive):
                extract(w2p_archive, basefolder)
    if not os.path.exists(w2p_folder):
        print '  INFO: web2py folder undetected, exiting...'
        wait_and_exit(1)

    try:
        version_mtime = os.stat(w2p_git_version_file).st_mtime
    except:
        version_mtime = 0
    check_version = version_mtime < time.time() - 60
    if check_version:
        print '  INFO: Retrieving version from github'
        if not download(w2p_git_version_url, w2p_git_version_file):
            print '  ERROR: Unable to contact github. Please try again in a few minutes'
            wait_and_exit(1)
    git_version = parse_tvseries_version(w2p_git_version_file)
    if not os.path.isfile(current_version_file):
        cur_version = None
    else:
        cur_version = parse_tvseries_version(current_version_file)

    if cur_version and cur_version < git_version and check_version:
        print '  INFO: Downloading new installer'
        tmp_path = this_file_path + '____tmp'
        if not download(updater_url, tmp_path):
            print '  INFO: Unable to download updated installer, exiting'
            wait_and_exit(1)
        os.remove(this_file_path)
        os.rename(tmp_path, this_file_path)
        print '  INFO: Updated installer, please restart the script'
        wait_and_exit(1)

    if w2p_folder not in sys.path:
        sys.path.insert(0, w2p_folder)
    os.chdir(w2p_folder)
    from gluon import main
    from gluon.fileutils import fix_newlines, recursive_unlink
    from gluon.shell import run
    from gluon.admin import app_compile
    from gluon.compileapp import remove_compiled_application
    from gluon.storage import Storage


    if cur_version >= git_version:
        print '  INFO: You have the latest version of w2p_tvseries'
        wait_and_exit(0)

    update_w2p_tvseries(w2p_folder, git_version)

if raw_input("Q:    Let's create/migrate our database.... ([Y]/n)?").lower() in ['y', 'yes']:
    remove_compiled_application(os.path.join(w2p_folder, 'applications', 'w2p_tvseries'))
    model_file = os.path.join(w2p_folder, 'applications', 'w2p_tvseries', 'models', 'db.py')
    print '  INFO: setting migrate to True, just to be sure'
    with open(model_file) as g:
        content = g.read()
        content = content.replace("MIGRATE = False", "MIGRATE = True")
        content = content.replace("LAZY_TABLES = True", "LAZY_TABLES = False")
    with open(model_file, 'w') as g:
        g.write(content)

    run('w2p_tvseries/manage/stop_operations')
    print '  INFO: migration occurred, setting migrate to False'

    with open(model_file) as g:
        content = g.read().replace("MIGRATE = True", "MIGRATE = False")
        content = content.replace("LAZY_TABLES = False", "LAZY_TABLES = True")
    with open(model_file, 'w') as g:
        g.write(content)

    print '  INFO: migrate set to False'
"""
if raw_input("(re)compile application (y,n) ?").lower() in ['y','yes']:
    request = Storage(folder=os.path.abspath(os.path.join(w2p_folder, 'applications', 'w2p_tvseries')))
    remove_compiled_application(os.path.join(w2p_folder, 'applications', 'w2p_tvseries'))
    app_compile('w2p_tvseries', request)
"""
routes_dst = os.path.abspath(os.path.join(w2p_folder, 'routes.py'))
if not os.path.isfile(routes_dst):
    if raw_input("Q:    Copy default redirection (if this is the only app installed, it's safe to say yes) ([Y]/n)?"
                ).lower() in ['y', 'yes']:
        routes_src = os.path.abspath(os.path.join(w2p_folder, 'applications', 'w2p_tvseries', 'private', 'routes.py'))
        routes_dst = os.path.abspath(os.path.join(w2p_folder, 'routes.py'))
        if not os.path.exists(routes_dst):
            shutil.copy(routes_src, routes_dst)

if raw_input("Q:    Create start scripts ([Y]/n)?").lower() in ['y', 'yes']:
    is_binary_version = sys.executable.endswith('web2py.exe')
    executable = sys.executable
    if is_binary_version:
        executable = os.path.basename(executable)
    startfiledos = """
pushd web2py
start "%(executable)s" web2py.py -K w2p_tvseries
start "%(executable)s" web2py.py -a w2p_tvseries
popd
""" % dict(executable=executable)
    updaterfile = """
"%(executable)s" w2p_tvseries_installer.py
""" % dict(executable=executable)
    if is_binary_version:
        startfiledos = """
pushd web2py
start %(executable)s -K w2p_tvseries
start %(executable)s -a w2p_tvseries
popd
""" % dict(executable=executable)
        updaterfile = """
pushd web2py
%(executable)s -S admin -R ..\w2p_tvseries_installer.py
popd
""" % dict(executable=executable)
    startfilelinux = """
pushd web2py
"%(executable)s" web2py.py -a w2p_tvseries &
"%(executable)s" web2py.py -K w2p_tvseries
popd
""" % dict(executable=executable)
    cronscript = """
"%(executable)s" "%(cronfile)s"
"""  % dict(executable=sys.executable, cronfile=os.path.join(w2p_folder, 'applications', 'w2p_tvseries', 'private', 'w2p_tvseries.py'))


    if is_binary_version:
        cronscript = """
"%(executable)s" -M -S w2p_tvseries -R "%(cronfile)s"
""" % dict(executable=sys.executable, cronfile=os.path.join(w2p_folder, 'applications', 'w2p_tvseries', 'private', 'w2p_tvseries.py'))

    if sys.platform.startswith('win'):
        with open(os.path.join(basefolder, 'start_web_and_scheduler.template.bat'), 'w') as g:
            g.write(startfiledos)
        with open(os.path.join(basefolder, 'cronscript.template.bat'), 'w') as g:
            g.write(cronscript)
        with open(os.path.join(basefolder, 'updater.bat'), 'w') as g:
            g.write(updaterfile)

    elif sys.platform.startswith('linux'):
        with open(os.path.join(basefolder, 'start_web_and_scheduler.template.sh'), 'w') as g:
            g.write(startfilelinux)
        with open(os.path.join(basefolder, 'cronscript.template.sh'), 'w') as g:
            g.write(cronscript)
        with open(os.path.join(basefolder, 'updater.sh'), 'w') as g:
            g.write(updaterfile)

print "    Enjoy w2p_tvseries!, Exiting from the updater"
for file in [w2p_archive, zipball]:
    if os.path.exists(file):
        os.unlink(file)
wait_and_exit(0)
