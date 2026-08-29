import argparse
import os
import logging
import textwrap
from pathlib import Path
import sys
import inspect
from collections import defaultdict
from typing import Union
import re
import csv
import time
import copy
import random
import string
import concurrent.futures
import pprint
import textwrap

cli_results = defaultdict(str)
FRAMEWORK = defaultdict(list)
pattern = defaultdict(lambda: re.compile(rf'~'))

def fetch_file(file:str=None):
    results = ''
    if Path(file).is_file():
        with open(file) as f:
            results = f.read()
    else:
        print(f"{file} not found.")
    return results

def main():
    global cli_results
    global FRAMEWORK
    global pattern

    cli_results['config_txt'] = fetch_file(file=f'./config.txt')

    # look for these sections of configuration
    find_sec_loop = [
        ('TAG_POLICY_BLOCK', rf"wireless\s+tag\s+policy"),
        ('PROFILE_WLAN_BLOCK', rf"wlan"),
        ('PROFILE_POLICY_BLOCK', rf"wireless\s+profile\s+policy"),
        ('TAG_SITE_BLOCK', rf"wireless\s+tag\s+site"),
        ('TAG_RF_BLOCK', rf"wireless\s+tag\s+rf"),
        ('PROFILE_AP_DOT11_6GHZ', rf"ap\s+dot11\s+6ghz\s+rf-profile"),
        ('PROFILE_AP_DOT11_5GHZ', rf"ap\s+dot11\s+5ghz\s+rf-profile"),
    ]

    # now go find those sections and store them in FRAMEWORK
    for sec,sec_pat in find_sec_loop:
        pattern[sec] = rf"(?:(^{sec_pat}.*?$)\n)((?:\s+.*?$\n)*)(?=^{sec_pat}|^\S)"
        list_me = re.findall(pattern[sec], cli_results['config_txt'], flags=re.MULTILINE)
        for hit in list_me:
            entry = defaultdict(str)
            entry['NAME'] = hit[0]
            entry['BLOCK'] = hit[1]
            # remove lines: description / psk
            entry['BLOCK'] = re.sub(r'^\s*description\s+.*?$\n', r'', entry['BLOCK'], flags=re.MULTILINE)
            entry['BLOCK'] = re.sub(r'^\s*security\s+wpa\s+psk\s+set-key\s+ascii\s+0\s+.*?$\n', r'', entry['BLOCK'], flags=re.MULTILINE)
            FRAMEWORK[sec].append(entry)

    # TODO syslog debugs
    # pprint.pp(f"FRAMEWORK is ")
    # pprint.pp(FRAMEWORK, width=200, compact=True)

    # go across the sections of configuration in FRAMEWORK and see what is the SAME & DIFFERENT (ignoring the "description")
    collect_set = defaultdict(set)

    # step across the various config sections collected
    for sec in FRAMEWORK:
        collect_set['BLOCK_UNIQUE'] = set()
        collect_set['BLOCK_LINES_OVERALL'] = set()

        # step across the entries in each configuration section
        for entry in FRAMEWORK[sec]:
            # create a set of all the specific BLOCK entries
            # basically figure out what the specific unique combination of common lines by using a "set"
            collect_set['BLOCK_UNIQUE'].add(entry['BLOCK'])
            # create an overall per line set of all the subordinate lines in each BLOCK and call it set BLOCK_LINES_OVERALL
            for line in entry['BLOCK'].splitlines(): collect_set['BLOCK_LINES_OVERALL'].add(line.strip())

        print(f"=" * 120)
        print(f"collect_set {sec}['BLOCK_LINES_OVERALL'] is ")
        pp_BLOCK_LINES_OVERALL = pprint.pformat(collect_set['BLOCK_LINES_OVERALL'])
        pp_BLOCK_LINES_OVERALL = textwrap.indent(pp_BLOCK_LINES_OVERALL, ' ' * 2)
        print(f"{pp_BLOCK_LINES_OVERALL}")

        # Step across the instances of the BLOCK_UNIQUE entries
        for this_block_unique in collect_set['BLOCK_UNIQUE']:
            same = []

            for entry in FRAMEWORK[sec]:
                if entry['BLOCK'] == this_block_unique:
                    same.append(entry['NAME'])
            pp_same = pprint.pformat(same)
            pp_same = textwrap.indent(pp_same, ' ' * 2)

            print(f"SAME\n{pp_same}")
            pp_instance = pprint.pformat(this_block_unique)
            pp_instance = textwrap.indent(pp_instance, ' ' * 4)
            print(f"{pp_instance}")

            # let's figure out what is missing from the BLOCK_LINES_OVERALL
            missing = []
            for line in collect_set['BLOCK_LINES_OVERALL']:
                if line not in this_block_unique:
                    missing.append(line)
            pp_missing = pprint.pformat(missing)
            pp_missing = textwrap.indent(pp_missing, ' ' * 4)
            print(f"   MISSING\n{pp_missing}")



if __name__ == "__main__":
    main()