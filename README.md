w2p_tvseries
============

TV Series Organizer, built with web2py

This app was born to accomplish some objectives:
- use as much web2py codebase as possible
- use extensively the scheduler
- test if Twitter Bootstrap (as opposed to jquery-ui that I used for all my previous projects) is "enough" for all the functionality required
- use AJAX wherever is possible: async stuff will take place probably in places where it was not necessary, but I decided to give it a shot whenever (and wherever) possible
- make it a multi-platform app
- combine some useful piece of scripts lying around my machine
- play and test the requests (https://github.com/kennethreitz/requests) library for all the HTTP communications. I grew fond of urllib3 (http://code.google.com/p/urllib3/) in the past and requests is it's natural successor

Some considerations:
- use this at your own risk (that is: I'm NOT responsible if your world will be trashed with this application, if you'll be arrested and/or you'll find your house burnt to the grounds....)
- all operations are "divided" into "logical" groups
- operations that can take a considerable amount of time
- operations that need read access to the filesystem
- operations that need write access to the filesystem

Operations that are "potentially harmful" will be passed to the scheduler (long ones and the ones that need write access):
the idea behind is that you can "mount" the web part to a webserver of your choice and give the process only read permission
on the filesystem, and then let the scheduler run with a user with write permission to do the "dirty parts" of the work.
Still, ideally the scheduler will have take the burden of do the "read the filesystem" part, for the complete decoupling of operations: this is not implemented yet.

## Loose ends
Loose ends in such an application are likely to happen. I'll be more than glad to receive patches and accomodate everybody, just remember that I'm definitely NOT
a full-time python programmer guru.

##Install
There is a script in private folder, w2p_tvseries_installer.py, to put in an empty directory.
It tries to:
- download the last stable web2py release
- download the source of w2p_tvseries
- ease default redirection (http://127.0.0.1:8000/ instead of http://127.0.0.1:8000/w2p_tvseries/)
- create template scripts to run w2p_tvseries and the cron task

While it becomes stable (needs testing), here's how install w2p_tvseries manually

- Install web2py (downloading the archive and unzipping it in a directory)
- Download this app and place it under web2py/applications/w2p_tvseries
- Start web2py with
<pre>
python web2py.py -a "yourdesiredpassword"
</pre>
- go to http://127.0.0.1:8000/w2p_tvseries/
- now, for the actual stuff to happen, you must start the worker too
<pre>
python web2py.py -K w2p_tvseries
</pre>

Once you have finished, you can stop both processes.

In the private folder there is a patched scheduler, allowing it to be put in cron.
For further details, please refer to the embedded docs that you can find at

http://127.0.0.1:8000/w2p_tvseries/docs/page/using

