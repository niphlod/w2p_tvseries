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
import struct
import shutil
import thread
import re
import enzyme
import datetime
from gluon.storage import Storage
import hashlib
from gluon.html import URL, A, IMG, UL, LI, H5, INPUT, SCRIPT, TAG, LABEL, DIV, SPAN, I
from gluon.sqlhtml import SQLFORM
from gluon.validators import *
locker = thread.allocate_lock()

from gluon import current


def myfolderwidget(field, value, **attributes):
    _id = "%s_%s" % (field._tablename, field.name)
    attr = attributes
    attributes['_class'] = "%sfolders span10" % attributes.get('_class', ' ')
    _style = "display: inline-block;"
    attributes['_style'] = _style
    default_input = SQLFORM.widgets.string.widget(field, value, **attributes)
    return DIV(SPAN(I(_class="icon-folder-open"),_class="add-on"),default_input, _class="input-prepend span9", _style=_style)

def myfolderwidgetmultiple(field, value, **attributes):
    _id = '%s_%s' % (field._tablename, field.name)
    _name = field.name
    _class = 'string folders span10'
    _style="display: inline-block;"
    requires = field.requires if isinstance(field.requires, (IS_NOT_EMPTY, IS_LIST_OF)) else None
    items=[LI(DIV(
                SPAN(I(_class="icon-folder-open"),_class="add-on"),
                  INPUT(_class=_class, _name=_name, value=v, hideerror=True, requires=requires, _style=_style)
                  , _class="input-prepend span9", _style=_style))
               for v in value or ['']]
    script=SCRIPT("""
// from http://refactormycode.com/codes/694-expanding-input-list-using-jquery
(function(){
jQuery.fn.grow_input_fold = function() {
return this.each(function() {
var ul = this;
jQuery(ul).find(":text").after('<a href="javascript:void(0)">+</a>').keypress(function (e) { return (e.which == 13) ? pe(ul) : true; }).next().click(function(){ pe(ul) });
});
};
function pe(ul) {
var new_line = ml(ul);
rel(ul);
new_line.appendTo(ul);
new_line.find(":text").focus().after('<a href="javascript:void(0)">+</a>').keypress(function (e) { return (e.which == 13) ? pe(ul) : true; }).next().click(function(){ pe(ul) });
new_line.find(":text").scanfolders();
return false;
}
function ml(ul) {
var line = jQuery(ul).find("li:first").clone();
line.find(':text').val('');
line.find('a').remove();
return line;
}
function rel(ul) {
return;
jQuery(ul).find("li").each(function() {
var trimmed = jQuery.trim(jQuery(this.firstChild).val());
if (trimmed=='') jQuery(this).remove(); else jQuery(this.firstChild).val(trimmed);
});
}
})();
jQuery(document).ready(function(){
    jQuery('#%s_grow_input').grow_input_fold();
    });
""" % _id)
    attributes['_id']=_id+'_grow_input'
    return TAG[''](UL(*items,_class="unstyled", **attributes),script)

def myradiowidgetvertical(field,value,**attributes):
    attributes['type'] = ''
    return myradiowidget(field, value, **attributes)

def myradiowidget(field, value, **attributes):
    """
    <div class="control-group">
            <label for="inlineCheckboxes" class="control-label">Inline checkboxes</label>
            <div class="controls">
              <label class="checkbox inline">
                <input type="checkbox" value="option1" id="inlineCheckbox1"> 1
              </label>
              <label class="checkbox inline">
                <input type="checkbox" value="option2" id="inlineCheckbox2"> 2
              </label>
              <label class="checkbox inline">
                <input type="checkbox" value="option3" id="inlineCheckbox3"> 3
              </label>
            </div>
          </div>
    """
    _id = "%s_%s" % (field._tablename, field.name)
    #print 'aaa', value
    #if not value:
    #    value = field.default
    #print 'bbb', value

    requires = field.requires
    if not isinstance(requires, (list, tuple)):
        requires = [requires]
    if requires:
        if hasattr(requires[0], 'options'):
            options = requires[0].options()
        else:
            raise SyntaxError, 'widget cannot determine options of %s' \
                % field
    options = [(k, v) for k, v in options if str(v)]
    labels_and_inputs = []
    for i, a in options:
        checked={'_checked':'checked'} if i==value else {}
        labels_and_inputs.extend([
            LABEL(a,
                INPUT(_type="radio", _name=field.name, _value=i, _id="%s%s" % (_id, i), **checked),
                _class="radio%s" % (attributes.get('type', ' inline')))
            ])

    return TAG[''](
        *labels_and_inputs
    )


def tvdb_logger_loader(*args, **vars):
    locker.acquire()
    try:
        if not hasattr(tvdb_logger_loader, 'tvdb_logger_instance'):
            tvdb_logger_loader.tvdb_logger_instance = tvdb_logger(*args, **vars)
    finally:
        locker.release()
    return tvdb_logger_loader.tvdb_logger_instance

def tvdb_scooper_loader(*args, **vars):
    locker.acquire()
    try:
        if not hasattr(tvdb_scooper_loader, 'tvdb_scooper_instance'):
            tvdb_scooper_loader.tvdb_scooper_instance = Scooper(*args, **vars)
    finally:
        locker.release()
    return tvdb_scooper_loader.tvdb_scooper_instance

class w2p_tvseries_settings(object):
    def __init__(self):
        self.sub_langs = ['aar', 'abk', 'afr', 'aka', 'alb', 'amh', 'ara', 'arg', 'arm', 'asm',
             'ava', 'ave', 'aym', 'aze', 'bak', 'bam', 'baq', 'bel', 'ben', 'bih',
             'bis', 'bos', 'bul', 'bur', 'cat', 'cha', 'che', 'chi', 'chu', 'chv',
             'cor', 'cos', 'cre', 'cze', 'dan', 'div', 'dut', 'dzo', 'eng', 'epo',
             'est', 'ewe', 'fao', 'fij', 'fin', 'fre', 'fry', 'ful', 'geo', 'ger',
             'gla', 'gle', 'glg', 'glv', 'ell', 'grn', 'guj', 'hat', 'hau', 'heb',
             'her', 'hin', 'hmo', 'hrv', 'hun', 'ibo', 'ice', 'ido', 'iii', 'iku',
             'ile', 'ina', 'ind', 'ipk', 'ita', 'jav', 'jpn', 'kal', 'kan', 'kas',
             'kau', 'kaz', 'khm', 'kik', 'kin', 'kir', 'kom', 'kon', 'kor', 'kua',
             'kur', 'lao', 'lat', 'lav', 'lim', 'lin', 'lit', 'ltz', 'lub', 'lug',
             'mac', 'mah', 'mal', 'mao', 'mar', 'may', 'mlg', 'mlt', 'mon', 'nau',
             'nav', 'nbl', 'nde', 'ndo', 'nep', 'nno', 'nob', 'nor', 'nya', 'oci',
             'oji', 'ori', 'orm', 'oss', 'pan', 'per', 'pli', 'pob', 'pol', 'por',
             'pus', 'que', 'roh', 'rum', 'run', 'rus', 'sag', 'san', 'sin', 'slo',
             'slv', 'smo', 'sna', 'snd', 'som', 'sot', 'spa', 'srd', 'ssw', 'sun',
             'swa', 'swe', 'tah', 'tam', 'tat', 'tel', 'tgk', 'tgl', 'tha', 'tib',
             'tir', 'ton', 'tsn', 'tso', 'tuk', 'tur', 'twi', 'uig', 'ukr', 'unk',
             'urd', 'uzb', 'ven', 'vie', 'vol', 'wel', 'wln', 'wol', 'xho', 'yid',
             'yor', 'zha', 'zul']

        self.langs = [
            ('de', 'Deutsch'),
            ('it', 'Italiano'),
            ('es','Español'),
            ('fr' , 'Français'),
            ('en' , 'English'),
            ('da' , 'Dansk'),
            ('fi' , 'Suomeksi'),
            ('nl' , 'Nederlands'),
            ('pl' , 'Polski'),
            ('hu' , 'Magyar'),
            ('el' , 'Ελληνικά'),
            ('tr' , 'Türkçe'),
            ('ru' , 'русский язык'),
            ('he' , ' עברית'),
            ('ja' , '日本語'),
            ('pt' , 'Português'),
            ('zh' , '中文'),
            ('cs' , 'čeština'),
            ('sl' , 'Slovenski'),
            ('hr' , 'Hrvatski'),
            ('ko' , '한국어'),
            ('sv' , 'Svenska'),
            ('no' , 'Norsk')
        ]

        self.magnet_options = [
            ('N', "Dont' handle them, try to download torrent files instead"),
            ('SF', "Create a catalog.magnet file into into torrent folder, with a line for every link"),
            ('MF', "Download into torrent folder, create a .magnet file for every link")
        ]

    def general_settings(self):
        settings = Storage()

        settings.fields = ['series_basefolder', 'series_language', 'season_path', 'itasa_username', 'itasa_password',
            'torrent_path', 'torrent_magnet', 'scooper_path', 'subtitles_default_method',
            'subtitles_default_quality', 'subtitles_default_language',
            'torrent_default_feed', 'torrent_default_quality',
            'torrent_default_feed', 'torrent_default_quality', 'torrent_default_minsize',
            'torrent_default_maxsize']

        settings.defaults = Storage()
        settings.comments = Storage()
        settings.types = Storage()
        settings.widgets = Storage()
        settings.requires = Storage()

        settings.defaults.series_basefolder = ''
        settings.defaults.series_language = 'en'
        settings.defaults.season_path = '%(seasonnumber).2d'
        settings.defaults.itasa_username = ''
        settings.defaults.itasa_password = ''
        settings.defaults.torrent_path = ''
        settings.defaults.scooper_path = []
        settings.defaults.torrent_magnet = 'N'
        settings.defaults.subtitles_default_method = 'opensubtitles'
        settings.defaults.subtitles_default_quality = 'Normal'
        settings.defaults.subtitles_default_language = 'ita'
        settings.defaults.torrent_default_feed = 'Eztv_feed'
        settings.defaults.torrent_default_quality = ''
        settings.defaults.torrent_default_minsize = 100
        settings.defaults.torrent_default_maxsize = 4780

        settings.comments.series_basefolder = 'w2p_tvseries will suggest a default folder for new added series in this path'
        settings.comments.series_language = 'w2p_tvseries will download series definitions from thetvdb.com using this language'
        settings.comments.season_path = 'Standard subpath format for every season (python formatting allowed)'
        settings.comments.itasa_username = 'username for logging into www.italiansubs.net'
        settings.comments.itasa_password = 'password for logging into www.italiansubs.net'
        settings.comments.torrent_path = 'save torrents in this folder'
        settings.comments.scooper_path = 'where to find finished downloads'
        settings.comments.subtitles_default_method = 'Default method to download subtitles'
        settings.comments.subtitles_default_quality = 'Default quality to pick for subtitles'
        settings.comments.subtitles_default_language = 'Default language to pick for subtitles'
        settings.comments.torrent_default_feed = 'Default method to download torrents'
        settings.comments.torrent_default_quality = 'Like HD,DSRIP,TVRIP,PDTV,DVD,HR,HDTV,720p, etc, prefix with NO_ to discard (NO_720p)'
        settings.comments.torrent_default_minsize = 'Minimum allowed size for torrents, in MB'
        settings.comments.torrent_default_maxsize = 'Maximum allowed size for torrents, in MB'
        settings.comments.torrent_magnet = 'How should I handle magnet links ?'

        settings.types.itasa_password = 'password'
        settings.types.torrent_default_minsize = 'integer'
        settings.types.torrent_default_maxsize = 'integer'

        settings.widgets.series_basefolder = myfolderwidget
        settings.widgets.torrent_path = myfolderwidget
        settings.widgets.scooper_path = myfolderwidgetmultiple
        settings.widgets.subtitles_default_method = myradiowidget
        settings.widgets.subtitles_default_quality = myradiowidget
        settings.widgets.torrent_default_feed = myradiowidget
        settings.widgets.torrent_magnet = myradiowidgetvertical

        settings.requires.series_language = IS_IN_SET(self.langs)
        settings.requires.subtitles_default_method = IS_IN_SET(('itasa', 'opensubtitles'))
        settings.requires.subtitles_default_quality = IS_IN_SET(('Normal', 'WEB-DL', '720p'))
        settings.requires.torrent_default_feed = IS_IN_SET(('Eztv_feed', 'Torrentz_feed'))
        settings.requires.subtitles_default_language = IS_IN_SET(self.sub_langs)
        settings.requires.torrent_magnet = IS_IN_SET(self.magnet_options)

        return settings

    def torrent_settings(self):
        settings = Storage()

        settings.fields = ['feed', 'show_name', 'season', 'quality', 'minsize', 'maxsize', 'regex', 'lower_attention']
        settings.defaults = Storage()
        settings.labels = Storage()
        settings.comments = Storage()
        settings.types = Storage()
        settings.widgets = Storage()
        settings.requires = Storage()

        #labels
        settings.labels.lower_attention = "Search type"

        #defaults
        settings.defaults.lower_attention = 'Verified'

        #comments
        settings.comments.quality = "Like HD,DSRIP,TVRIP,PDTV,DVD,HR,HDTV,720p, etc, prefix with NO_ to discard (NO_720p)"
        settings.comments.minsize = "MB"
        settings.comments.maxsize = "MB"
        settings.comments.season = 'set this to ALL to skip season validation, else the seasonnumber'
        settings.comments.lower_attention = 'Search type for torrents (works only for torrentz.eu)'

        #type
        settings.types.minsize = 'integer'
        settings.types.maxsize = 'integer'

        #widgets
        settings.widgets.feed = myradiowidget
        settings.widgets.lower_attention = myradiowidget

        #requires
        settings.requires.feed = IS_IN_SET(('Eztv_feed', 'Torrentz_feed'))
        settings.requires.lower_attention = IS_IN_SET(('Verified', 'Unverified'))

        return settings

    def subtitle_settings(self):
        settings = Storage()

        langs = self.sub_langs

        settings.fields = ['method', 'quality', 'language']
        settings.defaults = Storage()
        settings.comments = Storage()
        settings.types = Storage()
        settings.widgets = Storage()
        settings.requires = Storage()

        settings.defaults.language = 'eng'

        settings.comments.language = 'pick a language'
        settings.comments.quality = 'Default quality to pick for subtitles'

        settings.widgets.method = myradiowidget
        settings.widgets.quality = myradiowidget

        settings.requires.method = IS_IN_SET(('itasa', 'opensubtitles'))
        settings.requires.quality = IS_IN_SET(('Normal', 'WEB-DL', '720p'))
        settings.requires.language = IS_IN_SET(langs)


        return settings


class tvdb_logger(object):
    def __init__(self, module):
        self.module = module

    def log(self, function, message):
        db = current.database
        db.global_log.insert(log_module=self.module, log_function=function, log_operation=message)

    def error(self, function, message):
        db = current.database
        db.global_log.insert(log_module=self.module, log_function=function, log_error=message)

class Scooper(object):
    def __init__(self):
        db = current.database
        self.counter = {}
        self.collector = {}
        self.logger = tvdb_logger('scooper')
        folders = db(db.global_settings.key=='scooper_path').select()
        self.folders = [row.value for row in folders if os.path.exists(row.value)]

    def log(self, function, message):
        log = self.logger
        log.log(function, message)

    def error(self, function, message):
        log = self.logger
        log.error(function, message)

    def scoop(self):
        db = current.database
        #folders to scoop
        filelist = []
        for folder in self.folders:
            filelist.extend(os.listdir(folder))
        self.filelist = filelist

    def preview(self, mask, reload=False):
        if reload:
            self.scoop()
        mask = mask.lower()
        return [file for file in self.filelist if mask in file.lower()]

    def tokenize(self, riga):
        tokens = [riga[:a] for a in range(4, len(riga)/2)]
        for a in tokens:
            if a[:-1] in self.counter:
                filelist = self.counter[a[:-1]]
            else:
                filelist = self.filelist
            for file in filelist:
                if file.startswith(a):
                    if a not in self.counter:
                        self.counter[a] = [file]
                    elif file not in self.counter[a]:
                        self.counter[a].append(file)

    def find_patterns(self):
        if len(self.filelist) == 0:
            self.collector = {}
        for file in self.filelist:
            self.tokenize(file)
        keys = self.counter.keys()
        keys.sort()
        prevk = 0
        prevg = 0
        mid = ''
        for k in keys:
            #skip mask good only for 1 file
            if len(self.counter[k]) == 1:
                continue
            if len(k) < prevk:
                self.collector[mid] = prevg
                mid = ''
            if self.counter[k] > len(self.counter[k]):
                mid = k
            prevk = len(k)
            prevg = len(self.counter[k])

        self.collector[mid] = prevg
        return self.collector

    def move_files(self, seriesid, seasonnumber):
        fname = 'move'
        db = current.database

        se_tb = db.series
        ss_tb = db.seasons_settings
        gs_tb = db.global_settings

        #retrieve strings
        path_format = db(gs_tb.key == 'season_path').select(gs_tb.value).first()
        path_format = path_format and path_format.value or '%(seasonnumber).2d'

        rec = db((se_tb.id == seriesid) &
                       (ss_tb.tracking == True) &
                       (ss_tb.series_id == se_tb.id) &
                       (ss_tb.seasonnumber == seasonnumber)
                ).select().first()

        bpath = rec and rec.series.basepath or ''
        name = rec and rec.series.name or ''

        if bpath == '':
            self.error(fname, "basepath not found (%s season %s)" % (name, seasonnumber))
            return

        path = os.path.join(bpath, path_format % dict(seasonnumber = rec.seasons_settings.seasonnumber))
        if not os.path.exists(path):
            self.error(fname, "%s path not found (%s season %s)" % (path, name, seasonnumber))
            return

        masks = rec and rec.seasons_settings.scooper_strings or []
        masks = [a for a in masks if a <> '']
        for folder in self.folders:
            for filename in os.listdir(folder):
                file = os.path.join(folder, filename)
                source = file
                dest = os.path.join(path, filename)
                for mask in masks:
                    if filename.lower().startswith(mask.lower()):
                        if os.path.isfile(source) and not os.path.exists(dest):
                            try:
                                db.commit()
                                db.rename_log.insert(file_from=source, file_to=dest, series_id=seriesid, seasonnumber=seasonnumber)
                                self.log(fname, 'moving %s --> %s' % (filename, path))
                                shutil.move(source, dest)
                            except:
                                db.rollback()

class Meddler(object):
    def __init__(self):
        self.regexes = [
        # [group] Show - 01-02 [Etc]
        '''^\[.+?\][ ]? # group name
        (?P<seriesname>.*?)[ ]?[-_][ ]? # show name, padding, spaces?
        (?P<episodenumberstart>\d+) # first episode number
        ([-_]\d+)* # optional repeating episodes
        [-_](?P<episodenumberend>\d+) # last episode number
        [^\/]*$''',

        # [group] Show - 01 [Etc]
        '''^\[.+?\][ ]? # group name
        (?P<seriesname>.*) # show name
        [ ]?[-_][ ]?(?P<episodenumber>\d+)
        [^\/]*$''',

        # foo s01e23 s01e24 s01e25 *
        '''
        ^((?P<seriesname>.+?)[ \._\-])? # show name
        [Ss](?P<seasonnumber>[0-9]+) # s01
        [\.\- ]? # separator
        [Ee](?P<episodenumberstart>[0-9]+) # first e23
        ([\.\- ]+ # separator
        [Ss](?P=seasonnumber) # s01
        [\.\- ]? # separator
        [Ee][0-9]+)* # e24 etc (middle groups)
        ([\.\- ]+ # separator
        [Ss](?P=seasonnumber) # last s01
        [\.\- ]? # separator
        [Ee](?P<episodenumberend>[0-9]+)) # final episode number
        [^\/]*$''',

        # foo.s01e23e24*
        '''
        ^((?P<seriesname>.+?)[ \._\-])? # show name
        [Ss](?P<seasonnumber>[0-9]+) # s01
        [\.\- ]? # separator
        [Ee](?P<episodenumberstart>[0-9]+) # first e23
        ([\.\- ]? # separator
        [Ee][0-9]+)* # e24e25 etc
        [\.\- ]?[Ee](?P<episodenumberend>[0-9]+) # final episode num
        [^\/]*$''',

        # foo.1x23 1x24 1x25
        '''
        ^((?P<seriesname>.+?)[ \._\-])? # show name
        (?P<seasonnumber>[0-9]+) # first season number (1)
        [xX](?P<episodenumberstart>[0-9]+) # first episode (x23)
        ([ \._\-]+ # separator
        (?P=seasonnumber) # more season numbers (1)
        [xX][0-9]+)* # more episode numbers (x24)
        ([ \._\-]+ # separator
        (?P=seasonnumber) # last season number (1)
        [xX](?P<episodenumberend>[0-9]+)) # last episode number (x25)
        [^\/]*$''',

        # foo.1x23x24*
        '''
        ^((?P<seriesname>.+?)[ \._\-])? # show name
        (?P<seasonnumber>[0-9]+) # 1
        [xX](?P<episodenumberstart>[0-9]+) # first x23
        ([xX][0-9]+)* # x24x25 etc
        [xX](?P<episodenumberend>[0-9]+) # final episode num
        [^\/]*$''',

        # foo.s01e23-24*
        '''
        ^((?P<seriesname>.+?)[ \._\-])? # show name
        [Ss](?P<seasonnumber>[0-9]+) # s01
        [\.\- ]? # separator
        [Ee](?P<episodenumberstart>[0-9]+) # first e23
        ( # -24 etc
        [\-]
        [Ee]?[0-9]+
        )*
        [\-] # separator
        [Ee]?(?P<episodenumberend>[0-9]+) # final episode num
        [\.\- ] # must have a separator (prevents s01e01-720p from being 720 episodes)
        [^\/]*$''',

        # foo.1x23-24*
        '''
        ^((?P<seriesname>.+?)[ \._\-])? # show name
        (?P<seasonnumber>[0-9]+) # 1
        [xX](?P<episodenumberstart>[0-9]+) # first x23
        ( # -24 etc
        [\-+][0-9]+
        )*
        [\-+] # separator
        (?P<episodenumberend>[0-9]+) # final episode num
        ([\.\-+ ].* # must have a separator (prevents 1x01-720p from being 720 episodes)
        |
        $)''',

        # foo.[1x09-11]*
        '''^(?P<seriesname>.+?)[ \._\-] # show name and padding
        \[ # [
        ?(?P<seasonnumber>[0-9]+) # season
        [xX] # x
        (?P<episodenumberstart>[0-9]+) # episode
        ([\-+] [0-9]+)*
        [\-+] # -
        (?P<episodenumberend>[0-9]+) # episode
        \] # \]
        [^\\/]*$''',

        # foo - [012]
        '''^((?P<seriesname>.+?)[ \._\-])? # show name and padding
        \[ # [ not optional (or too ambigious)
        (?P<episodenumber>[0-9]+) # episode
        \] # ]
        [^\\/]*$''',
        # foo.s0101, foo.0201
        '''^(?P<seriesname>.+?)[ \._\-]
        [Ss](?P<seasonnumber>[0-9]{2})
        [\.\- ]?
        (?P<episodenumber>[0-9]{2})
        [^0-9]*$''',

        # foo.1x09*
        '''^((?P<seriesname>.+?)[ \._\-])? # show name and padding
        \[? # [ optional
        (?P<seasonnumber>[0-9]+) # season
        [xX] # x
        (?P<episodenumber>[0-9]+) # episode
        \]? # ] optional
        [^\\/]*$''',

        # foo.s01.e01, foo.s01_e01, "foo.s01 - e01"
        '''^((?P<seriesname>.+?)[ \._\-]+)?
        \[?
        [Ss](?P<seasonnumber>[0-9]+)[ ]?[\._\- ]?[ ]?
        [Ee]?(?P<episodenumber>[0-9]+)
        \]?
        [^\\/]*$''',

        # foo.2010.01.02.etc
        '''
        ^((?P<seriesname>.+?)[ \._\-])? # show name
        (?P<year>\d{4}) # year
        [ \._\-] # separator
        (?P<month>\d{2}) # month
        [ \._\-] # separator
        (?P<day>\d{2}) # day
        [^\/]*$''',

        # foo - [01.09]
        '''^((?P<seriesname>.+?)) # show name
        [ \._\-]? # padding
        \[ # [
        (?P<seasonnumber>[0-9]+?) # season
        [.] # .
        (?P<episodenumber>[0-9]+?) # episode
        \] # ]
        [ \._\-]? # padding
        [^\\/]*$''',

        # Foo - S2 E 02 - etc
        '''^(?P<seriesname>.+?)[ ]?[ \._\-][ ]?
        [Ss](?P<seasonnumber>[0-9]+)[\.\- ]?
        [Ee]?[ ]?(?P<episodenumber>[0-9]+)
        [^\\/]*$''',

        # Show - Episode 9999 [S 12 - Ep 131] - etc
        '''
        (?P<seriesname>.+) # Showname
        [ ]-[ ] # -
        [Ee]pisode[ ]\d+ # Episode 1234 (ignored)
        [ ]
        \[ # [
        [sS][ ]?(?P<seasonnumber>\d+) # s 12
        ([ ]|[ ]-[ ]|-) # space, or -
        ([eE]|[eE]p)[ ]?(?P<episodenumber>\d+) # e or ep 12
        \] # ]
        .*$ # rest of file
        ''',

        # show.name.e123.abc
        '''^(?P<seriesname>.+?) # Show name
        [ \._\-] # Padding
        (?P<episodenumber>[0-9]+) # 2
        of # of
        [ \._\-]? # Padding
        \d+ # 6
        ([\._ -]|$|[^\\/]*$) # More padding, then anything
        ''',

        # foo.103*
        '''^(?P<seriesname>.+)[ \._\-]
        (?P<seasonnumber>[0-9]{1})
        (?P<episodenumber>[0-9]{2})
        [\._ -][^\\/]*$''',

        # foo.0103*
        '''^(?P<seriesname>.+)[ \._\-]
        (?P<seasonnumber>[0-9]{2})
        (?P<episodenumber>[0-9]{2,3})
        [\._ -][^\\/]*$''',

        # show.name.e123.abc
        '''^(?P<seriesname>.+?) # Show name
        [ \._\-] # Padding
        [Ee](?P<episodenumber>[0-9]+) # E123
        [\._ -][^\\/]*$ # More padding, then anything
        ''',
            ]
        self.regexes = [re.compile(a, re.VERBOSE) for a in self.regexes]

    def analyze(self, name):
        m = Storage()
        for rex in self.regexes:
            match = rex.search(name)
            if match:
                m = Storage(match.groupdict())
                if m.episodenumberstart and m.episodenumberend:
                    m.episodes = range(int(m.episodenumberstart), int(m.episodenumberend)+1)
                    del m['episodenumberstart']
                    del m['episodenumberend']
                elif m.episodenumberstart:
                    m.episodes = [int(m.episodenumberstart)]
                    del m['episodenumberstart']
                elif m.episodenumber:
                    m.episodes = [int(m.episodenumber)]
                    del m['episodenumber']
                break
        if not m.episodes:
            m.reason = "episode not recognized"
        try:
            m.seasonnumber = int(m.seasonnumber)
        except:
            pass
        return m

class Hasher(object):

    def __init__(self, filename):
        self.filename = filename
        self.hashes = Storage()
        self.logger = tvdb_logger('hasher')
        self.gen_stats()

    def log(self, function, message):
        log = self.logger
        log.log(function, message)

    def error(self, function, message):
        log = self.logger
        log.error(function, message)

    def ed2k(self):
        return 'ed2k://|file|%s|%d|%s|/' % (os.path.basename(filename),
                                        os.path.getsize(filename),
                                        self.hashes.ed2k.upper())

    def gen_stats(self):
        self.stats = Storage()
        finfo = os.stat(self.filename)
        self.stats.mtime = finfo.st_mtime
        self.stats.size  = finfo.st_size
        c = hashlib.sha1()
        c.update("%s %s %s" % (self.filename, self.stats.mtime, self.stats.size))
        self.guid = c.hexdigest()

    def gen_hashes(self):
        """
        http://www.radicand.org/blog/orz/2010/2/21/edonkey2000-hash-in-python/
        """
        self.log('generate', 'generating hashes for %s' % self.filename)
        md4 = hashlib.new('md4').copy
        md5 = hashlib.md5()
        sha1 = hashlib.sha1()

        def gen(f):
            while True:
                x = f.read(9728000)
                if x:
                    yield x
                else:
                    return

        def md4_hash(data):
            m = md4()
            m.update(data)
            return m

        with open(self.filename, 'rb') as f:
            a = gen(f)
            ed2k_ = []
            for data in a:
                ed2k_.append(md4_hash(data).digest())
                md5.update(data)
                sha1.update(data)
        self.hashes.md5 = md5.hexdigest()
        self.hashes.sha1 = sha1.hexdigest()
        if len(ed2k_) == 1:
            ed2k = ed2k_[0].encode("hex")
        else:
            ed2k = md4_hash(reduce(lambda a, d: a + d, ed2k_, "")).hexdigest()
        self.hashes.ed2k = ed2k
        self.hashes.osdb = self.opensub_hash()

    def opensub_hash(self):
        """
        http://trac.opensubtitles.org/projects/opensubtitles/wiki/HashSourceCodes
        """

        longlongformat = 'q'  # long long
        bytesize = struct.calcsize(longlongformat)

        f = open(self.filename, "rb")

        filesize = self.stats.size
        hash_value = filesize

        if filesize < 65536 * 2:
            self.error('generate', "SizeError: size is %d, should be > 132K..." % filesize)
            return None

        for x in range(65536 / bytesize):
            buf = f.read(bytesize)
            (l_value,) = struct.unpack(longlongformat, buf)
            hash_value += l_value
            hash_value = hash_value & 0xFFFFFFFFFFFFFFFF #to remain as 64bit number

        f.seek(max(0, filesize - 65536), 0)
        for x in range(65536 / bytesize):
            buf = f.read(bytesize)
            (l_value,) = struct.unpack(longlongformat, buf)
            hash_value += l_value
            hash_value = hash_value & 0xFFFFFFFFFFFFFFFF

        f.close()

        return "%016x" % hash_value

class Brewer(object):
    def __init__(self, reference):
        self.reference = None
        self.logger = tvdb_logger('brewer')
        if isinstance(reference, dict):
            self.reference = reference
        else:
            try:
                self.log('parse', "parsing metadata for %s" % reference)
                self.complete_infos = enzyme.parse(reference).convert()
                self.info = self.cleanup(self.complete_infos)
            except:
                self.complete_infos = {}
                self.info = {}
                self.error('parse', "error parsing metadata for %s" % reference)

    def log(self, function, message):
        log = self.logger
        log.log(function, message)

    def error(self, function, message):
        log = self.logger
        log.error(function, message)

    def cleanup(self, element):
        if isinstance(element, dict):
            new = {}
            for k, v in element.iteritems():
                if v and k not in ('codec_private',):
                    new[k] = self.cleanup(v)
            return new

        elif isinstance(element, (list,tuple)):
            return [self.cleanup(a) for a in element if a]
        elif isinstance(element, (int, str, float)):
            return element
        elif isinstance(element, unicode):
            return element.encode('utf8')
        else:
            return element

    def adapt(self, info):
        aspects = [1.33, 1.66, 1.78, 1.85, 2.20, 2.35]
        resolutions = [480, 540, 576, 720, 1080]
        fourccs = {
            '0x55' : 'mp3',
            '0x20' : 'ac3',
            '0x8' : 'dts',
            8192 : 'ac3',
            8193 : 'dts',
            '0x2001' : 'dts',
            '0x564C' : 'vorbis',
            '0x674F' : 'vorbis',
            '0x6751' : 'vorbis',
            '0x676F' : 'vorbis',
            '0x6770' : 'vorbis',
            '0x6771' : 'vorbis',
        }
        videos = {
            'avc1' : 'avc1',
            'AVC1' : 'avc1',
            'XVID' : 'xvid',
            'XviD MPEG-4' : 'xvid'
        }
        m = Storage()
        try:
            aspect = info['video'][0]['width'] * 1.0 / info['video'][0]['height']
            m.aspect = sorted(aspects, key=lambda d: abs(aspect - d))[0]
        except:
            pass

        try:
            m.channels = info['audio'][0]['channels']
        except:
            pass
        try:
            m.audiocodec = fourccs[info['audio'][0]['fourcc']]
        except:
            try:
                m.audiocodec = fourccs[info['audio'][0]['codec']]
            except:
                pass
        try:
            m.videocodec = videos[info['video'][0]['codec']]
        except:
            pass
        try:
            resolution = info['video'][0]['width']
            m.resolution = sorted(resolutions, key=lambda d: abs(resolution -d))[0]
        except:
            pass
        try:
            m.length = str(datetime.timedelta(seconds=info['length'])).split('.')[0]
        except:
            pass

        return m

    def build_graphics(self):
        if self.reference:
            m_ = self.reference
            m = self.adapt(m_)
        else:
            m = self.adapt(self.info)
        ul = UL(_class="brewer")
        if m.resolution:
            ul.append(
                A(IMG(_alt=m.resolution, _src=URL('static', 'images/flagging/video/%s.png' % m.resolution, extension=False)))
            )
        if m.videocodec:
            ul.append(
                A(IMG(_alt=m.videocodec, _src=URL('static', 'images/flagging/video/%s.png' % m.videocodec, extension=False)))
            )
        if m.audiocodec:
            ul.append(
                A(IMG(_alt=m.audiocodec, _src=URL('static', 'images/flagging/audio/%s.png' % m.audiocodec, extension=False)))
            )
        if m.channels:
            ul.append(
                A(IMG(_alt=m.channels, _src=URL('static', 'images/flagging/audio/%s.png' % m.channels, extension=False)))
            )
        if m.aspect:
            ul.append(
                A(IMG(_alt=m.aspect, _src=URL('static', 'images/flagging/aspectratio/%s.png' % m.aspect, extension=False)))
            )
        #if m.length:
        #    ul.append(
        #        H5(m.length)
        #    )
        return ul
