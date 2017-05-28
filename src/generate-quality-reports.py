#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2017 Jordi Mas i Hernandez <jmas@softcatala.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import datetime
import configparser
import polib
import os
import shutil
import re
import time
from collections import OrderedDict
from optparse import OptionParser
from builder.findfiles import FindFiles


def read_parameters():
    parser = OptionParser()

    parser.add_option(
        "-s",
        "--source",
        action="store",
        type="string",
        dest="source_dir",
        default="",
        help="Source directory of po files")

    
    (options, args) = parser.parse_args()

    if len(options.source_dir) == 0:
        parser.print_help()
        exit(1)

    return options.source_dir


def read_config():
    SECTION_LT = "lt"
    SECTION_POLOGY = "pology"

    config = configparser.ConfigParser()
    config.read("../cfg/quality/parameters.conf")
    lt = OrderedDict()
    pology = OrderedDict()

    for option in config.options(SECTION_LT):
        lt[option] = config.get(SECTION_LT, option)

    for option in config.options(SECTION_POLOGY):
        pology[option] = config.get(SECTION_POLOGY, option)
          
    return lt, pology

def transonly_po_and_extract_text(po_file, po_transonly, text_file):
    try:
        input_po = polib.pofile(po_file)
    except Exception as e:
        print("Unable to open PO file {0}: {1}".format(po_file, str(e)))
        return False

    text_file = open(text_file, "w")
    for entry in input_po.translated_entries():
        text = entry.msgstr
        text = re.sub('[\t]', ' ', entry.msgstr)
        text = re.sub('[_&~]', '', text)
        #text = re.sub('^([^.]*,[^.]*){8,}$', '', text)  #comma-separated word list
        text += "\n\n"
        text_file.write(text)

    input_po.save(po_transonly)
    text_file.close()
    return True

def run_lt(lt, txt_file, json_file):

    cmd = lt['command'].format(lt['enabled-rules'], lt['disabled-rules'],
          txt_file, lt['server'], json_file)
    os.system(cmd)

def generate_lt_report(lt_html_dir, json_file, file_report):

    subdir = "output/individual_pos/"
    curdir = os.getcwd()
    cwd = os.path.join(curdir, subdir)
    if cwd == json_file[:len(cwd)]:
        json_file = json_file[len(cwd):]
    elif subdir == json_file[:len(subdir)]:
        json_file = json_file[len(subdir):]

    cmd = 'cd {0} && python {1}/lt-json-to-html.py -i "{2}" -o "{3}"'.format(
           subdir, os.path.join(curdir, lt_html_dir), json_file, file_report)

    os.system(cmd)

def run_pology(pology, po_transonly, html):

    posieve = pology['python2'] + " " + pology['posieve']

    cmd = pology['header-fix'].format(posieve, po_transonly)
    os.system(cmd)

    cmd = pology['command'].format(posieve, pology['rules-dir'], po_transonly, html)
    os.system(cmd)

def create_project_report(header_dir, lt_output, project_html):
    header_filename = os.path.join(header_dir, "header.html")
    report_filename = os.path.join(lt_output, project_html)
    shutil.copyfile(header_filename, report_filename)
    return open(report_filename, "a")

def add_string_to_project_report(text_file, text):
    text_file.write(text + "\n")

def add_file_to_project_report(text_file, filename):
    pology_file = open(filename, "r")
    text_file.write(pology_file.read())
    pology_file.close()

def main():

    print("Quality report generator")

    source_dir = read_parameters()
    lt, pology = read_config()
    print("Source directory: " + source_dir)

    report_filename = os.path.basename(os.path.normpath(source_dir)) + ".html"
    project_file = create_project_report(lt['lt-html-dir'], lt['lt_output'], report_filename)

    for po_file in FindFiles().find_recursive(source_dir, "*.po"):
        txt_file = po_file + ".txt"
        json_file = po_file + ".json"
        po_transonly = po_file + "-translated-only.po"
        pology_report = po_file + "-pology.html"
        file_report = po_file + "-report.html"
 
        start_time = time.time()
        rslt = transonly_po_and_extract_text(po_file, po_transonly, txt_file)
        if not rslt:
            continue

        if os.stat(txt_file).st_size == 0:
            print("No translations in file:" + txt_file)
            continue

        start_time = time.time()
        run_lt(lt, txt_file, json_file)
        print("LT runned PO {0} {1}".format(po_file, str(time.time() - start_time)))
        
        start_time = time.time()
        generate_lt_report(lt['lt-html-dir'], json_file, file_report)
        
        if os.path.isfile(file_report):
            add_file_to_project_report(project_file, file_report)
        else:
            print("Unable to add:" + file_report)
            continue

        start_time = time.time()
        run_pology(pology, po_transonly, pology_report)
        print("Pology runned PO {0} {1}".format(po_file, str(time.time() - start_time)))

        if os.path.isfile(pology_report):
            add_file_to_project_report(project_file, pology_report)
            os.remove(pology_report)
        else:
            add_string_to_project_report(project_file, 'El Pology no ha detectat cap error.')

        os.remove(txt_file)
        os.remove(json_file)
        os.remove(po_transonly)
        os.remove(file_report)

    dt = datetime.date.today().strftime("%d/%m/%Y")
    report_date = '<p><i>Informe generat el {0} </i></p>'.format(dt)
    add_string_to_project_report(project_file, report_date)
    footer_filename = os.path.join(lt['lt-html-dir'], "footer.html")
    add_file_to_project_report(project_file, footer_filename)
    project_file.close()

if __name__ == "__main__":
    main()