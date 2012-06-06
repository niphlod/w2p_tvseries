#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

if '__file__' in globals():
    path = os.path.dirname(os.path.abspath(__file__))

    if not os.path.exists(os.path.join(path,'web2py.py')):
        i = 0
        while i<10:
            i += 1
            if os.path.exists(os.path.join(path,'web2py.py')):
                break
            path = os.path.abspath(os.path.join(path, '..'))
    os.chdir(path)
else:
    path = os.getcwd() # Seems necessary for py2exe


sys.path = [path]+[p for p in sys.path if not p==path]

from gluon.widget import start
from gluon.shell import run
from gluon import main
import shutil
import logging

logging.getLogger().setLevel(logging.INFO)

def start_schedulers():
    apps = ['w2p_tvseries']
    try:
        from multiprocessing import Process
    except:
        sys.stderr.write('Sorry, -K only supported for python 2.6-2.7\n')
        return
    processes = []
    code = "from gluon import current; current._scheduler.max_empty_runs=10; current._scheduler.loop()"
    for app in apps:
        logging.info('starting scheduler for "%s"...' % app)
        args = (app,True,True,None,False,code)
        p = Process(target=run, args=args)
        processes.append(p)
        logging.info("Currently running %s scheduler processes" % (len(processes)))
        p.start()
        logging.info("Processes started")
    for p in processes:
        try:
            p.join()
        except KeyboardInterrupt:
            p.terminate()
            p.join()


# Queue ops and start Scheduler
if __name__ == '__main__':
    args = sys.argv
    if '-h' in args or '--help' in args:
        print """Use this to enqueue and process tasks with a cron job
    -s to disable operations. Available operations are
        - 'maintenance'
        - 'update'
        - 'down_sebanners'
        - 'scoop_season'
        - 'check_season'
        - 'ep_metadata'
        - 'down_epbanners'
        - 'check_subs'
        - 'down_subs'
        - 'queue_torrents'
        - 'down_torrents'
e.g.  Set this to maintenance,update to skip maintenance and update jobs

"""
        sys.exit(0)
    run('w2p_tvseries/organize/queue_ops', True)
    disabled_operations = []
    if '-s' in args:
        available_ops = ['maintenance', 'update', 'down_sebanners', 'scoop_season', 'check_season', 'ep_metadata', 'down_epbanners', 'check_subs', 'down_subs', 'queue_torrents', 'down_torrents']
        disabled_operations = args[2].split(',')
        code = ''
        for a in disabled_operations:
            if a in available_ops:
                logging.info('Skipping %s tasks' % a)
                code += "db2(db2.scheduler_task.function_name == '%s').delete();" % a
        code += "db2.commit();"
        run('w2p_tvseries/organize', True, True, None, False, code)
    from multiprocessing import Process
    start_schedulers()
