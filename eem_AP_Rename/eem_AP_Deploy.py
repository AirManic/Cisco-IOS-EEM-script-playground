"""
BSD 3-Clause License

Copyright (c) 2024, grogier@cisco.com

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


Cliff Notes ... pending nicer README.md

eem_AP_Rename.csv is simple format.. AP name followed by [in any order] AP details of SerialNum,MACenet, MACradio
  - AP name is case-sensitive, char for char
  - AP details will all be compared as forced upper case, eg serial number and MAC addresses
  - AP details, if it is only hexdigits with optional delimiters of [:.-], the delimiters will be stripped
      and uppercase for comparison to same on WLC AP list.
example file contents (** optional 2nd field to be _location_ if -l  used
 ap-c9130-VRF , basement, KWC233303FP, 04eb.409e.2cd0S, 04:eb:40-9f-cc-e0
 ap-c9120-VRF, "living room",c828.e56e.7740,c828.e5a4.c740, FJC27061YW1

guestshell run python3 /flash/guest-share/eem_AP_Rename.py -h
Please note, this package[eem] is ONLY for EEM Python Scripts
usage: eem_AP_Rename.py [-h] [-c CSV_INFILE] [-l] [-n NAME]

optional arguments:
  -h, --help            show this help message and exit
  -i INFILE_CSV, --infile_csv INFILE_CSV
                        specify infile csv, defaults to eem_AP_Rename.csv
  -n NAME, --name NAME  check only this specific AP name
  -l, --location        set location information
  -m, --model           check only this specific model in regexp format
  -s, --switch          check for this switch & switchport


!
conf t
!
! Basically, only fetch updated csv and python file if running on timer or manual run
! If only getting single AP join, just check existing csv using existing python
!  .. could only look for given syslog AP name.. but found that if a handful join in same second..
!  .. some of the syslog messages are suppressed
!  .. thus a bit brute force, albeit gets the job done to run repeatedly for AP join messages
no event manager applet eem_AP_Rename
   event manager applet eem_AP_Rename
 event tag CRON timer cron cron-entry "5 */4 * * *"
 event tag NONE none maxrun 1800
 event tag SYS1 syslog pattern "CAPWAPAC_SMGR_TRACE_MESSAGE-5-AP_JOIN_DISJOIN.*AP Name:\s+([^\s]+)\s+.*Joined"
 event tag SYS2 syslog pattern "APMGR_TRACE_MESSAGE-4-WLC_APMGR_WARNING_MSG.*is associated with the policy tag"
 trigger
  correlate event NONE or event CRON or event SYS1 or event SYS2
 action 000.000   syslog msg "Started event trigger $_event_type_string"
 action 000.000.1 cli command "enable"
 action 200.000.1 set find_ap_name "ALL"
 action 200.040.1 if $_event_type_string eq "syslog"
 action 200.040.2  regexp "CAPWAPAC_SMGR_TRACE_MESSAGE-5-AP_JOIN_DISJOIN.*AP Name:\s+([^\s]+)\s+.*Joined" "$_syslog_msg" match find_ap_name
 action 200.090   end
 ! action 300.020.1 cli command "copy tftp://192.168.201.210/eem/eem_AP_Rename_new.csv bootflash:/guest-share/eem_AP_Rename_new.csv" pattern "]"
 ! action 300.020.2 cli command "" pattern "[confirm]"
 ! action 300.020.3 cli command "y"
 ! action 300.020.5 cli command "copy tftp://192.168.201.210/eem/eem_AP_Rename_new.py bootflash:/guest-share/" pattern "]"
 ! action 300.020.6 cli command "" pattern "[confirm]"
 ! action 300.020.7 cli command "y"
 action 300.070.1 cli command "guestshell run python3 /flash/guest-share/eem_AP_Rename_new.py -n $find_ap_name"
 action 900.999.9 syslog msg "Finished"
!
end
!

!
config t
iox
app-hosting appid guestshell
 app-vnic management guest-interface 0
end
!
guestshell enable
!
"""

import argparse
import os
from pathlib import Path
import sys
import inspect
from collections import defaultdict
import re
import csv
import time
import copy
import random
import string
import concurrent.futures

my_name = os.path.basename(sys.argv[0])

# determine if running under IOS-XE guestshell
is_guestshell = os.uname().nodename == 'guestshell'

DEFAULT_INFILE  = "/flash/guest-share/" + Path(my_name).stem + '.csv'
DEFAULT_OUTFILE = "/flash/guest-share/" + Path(my_name).stem + '_ONLINE_AP_LIST.csv'

if is_guestshell:
    from cli import cli, clip, configure, configurep, execute, executep
else:
    # if not running in guestshell create placeholder functions so we can exercise the code for development work
    def cli(command: str):
        return ''
    def clip(command):
        return ''
    def configure(configuration: Union[str, list]):
        return []
    def configurep(configuration: Union[str, list]):
        return []
    def execute(command: str):
        return ''
    def executep(command: str):
        return ''
    DEFAULT_INFILE  = "./experimental/exp_" + Path(my_name).stem + '.csv'
    DEFAULT_OUTFILE = "./experimental/exp_" + Path(my_name).stem + '_ONLINE_AP_LIST.csv'
    SIM_FILE_EEM_AP_SUMM = f"./experimental/exp_eem_AP_summary.txt"
    SIM_FILE_EEM_AP_CDP = f"./experimental/exp_eem_AP_CDP_neighbors.txt"
    SIM_FILE_EEM_AP_ETHER_STATS = f"./experimental/exp_eem_AP_ethernet_stats.txt"
    SIM_FILE_EEM_AP_CONF = f"./exp_eem_AP_config_general.txt"
    SIM_FILE_EEM_AP_CDP_DETAIL = f"./experimental/exp_eem_AP_CDP_neighbors_detail.txt"
    SIM_FILE_EEM_AP_CONFIG_SLOT = f"./experimental/exp_eem_AP_config_slot.txt"

l_DEBUG  = 7
l_INFO   = 6
l_NOTICE = 5
l_WARN   = 4
l_ERR    = 3
l_CRIT   = 2

global run_string
run_string = ''.join(random.choices(string.digits, k=5))
def send_ios_syslog(message=None, severity=l_INFO):
    try:
        for line in message.splitlines():
            log_string = f"{my_name} line {inspect.stack()[1][2]:>3} {inspect.stack()[1][3]}() RandRunID {run_string} {line}"
            if is_guestshell:
                # Construct the standard Cisco log prefix
                log_string = f"[a123b234,1,{severity}]{log_string}\n"
                # Open the specific IOx serial pipe
                with open("/dev/ttyS2", "w", encoding="utf-8") as syslog_pipe:
                    syslog_pipe.write(log_string)
                    syslog_pipe.flush()
                    # move faster and drop a few messages if just debugging
                    time.sleep(1.001)  # IOS-XE syslogd will limit to one message a sec, drops faster
            else:
                sev_string = {
                    l_DEBUG : "DEBUG",
                    l_INFO : "INFO",
                    l_NOTICE : "NOTICE",
                    l_WARN : "WARN",
                    l_ERR : "ERR",
                    l_CRIT : "CRIT"
                }
                print(f"{sev_string[severity]} {log_string}")
    except FileNotFoundError:
        print(f"Error: /dev/ttyS2 not found. Ensure this is executed inside Guestshell.")

def show_ap(command=None):
    command_loop = []
    if type(command) is str:
        command_loop.append(command)
    elif type(command) is list:
        command_loop = command_loop + command
    command_seq = []
    for cmd in command_loop:
        command_seq.append(f"{cmd}")
    if args.debug: send_ios_syslog(severity=l_INFO, message=f"fetching cli([{command}])")
    results = cli(command)
    return results

def change_ap(command=None):
    command_loop = [f"enable"]
    if type(command) is str:
        command_loop.append(f"{command}")
    elif type(command) is list:
        command_loop = command_loop + command
    cripple = ""
    if args.Xchange: cripple = f"! Xchange crippled "
    command_seq = ""
    for cmd in command_loop:
        command_seq = command_seq + (f"{cripple}{cmd} ; ")
    send_ios_syslog(severity=l_INFO, message=f"sending cli('{command_seq}')")
    results = cli(command)
    return results

def fetch_file(file=None):
    results = None
    if Path(file).is_file():
        with open(file) as f:
            results = f.read()
    else:
        print(f"{file} not found.")
    return results

class AccessPoint(defaultdict):

    def __init__(self, default_factory=str,  *args, **kwargs):
        super().__init__(default_factory, *args, **kwargs)

    def __getitem__(self, key):
        # First, call standard dict lookup to handle missing keys normally
        try:
            value = super().__getitem__(key)
        except KeyError:
            return None  # Returns None if the key doesn't exist
        # If the key exists but is an empty string, return None
        ret_value = value
        if type(value) is str and value == "":
            ret_value = None
        if type(value) is list and value == []:
            ret_value = None
        if type(value) is dict and value == {}:
            ret_value = None
        return ret_value

    def __setitem__(self, key, value):
        new_value = value
        if isinstance(value,str): new_value = value.strip()
        super().__setitem__(key, new_value)

    def match_ap_criteria(self, criteria=None, ap=None,):
        # self is expected to be a real AP, and ap is an AP that might/might not exist but has the key criteria
        # track if there is at least one criteria item called out that matches
        # seed the match with True, as it will go False if there is a criteria item that does not match
        ap_return = None
        match_ap = True
        miss_match_ap = False
        is_ap_criteria = False
        for aspect in criteria:
            # make sure both devices being compared have valid aspect values, else will get error on fullmatch
            this_criteria_ap = ap[aspect] is not None and ap[aspect] != ''
            this_criteria_self = self[aspect] is not None and self[aspect] != ''
            # make note once have at least one criteria to match of value of ONLY the AP trying to match
            is_ap_criteria = is_ap_criteria or this_criteria_ap
            # see if we are missing a match due to lacking information that "ap" is calling out
            if this_criteria_ap and not this_criteria_self:
                miss_match_ap = True
            # both AP-s being compared must have valid criteria to check, else fullmatch will error
            elif this_criteria_ap and this_criteria_self:
                # now check it for a match, where anything that does not match will make it go False
                match_ap = match_ap and ( not this_criteria_ap
                                          or ( ap[aspect]
                                               and re.fullmatch(rf"{ap[aspect]}", self[aspect]) is not None ) )
            if not match_ap or miss_match_ap:
                # no need to keep looking, so break the loop checking more aspect
                break
        # if had at least one item to match on.. and if all the items called out did match
        got_a_solid_match = is_ap_criteria and match_ap and not miss_match_ap
        if got_a_solid_match:
            ap_return = ap
        return ap_return

    def matching_ap(self, criteria=None, ap_list=None):
        # self is expected to be a real AP, and ap is an AP that might/might not exist but has the key criteria
        match_ap = next( (ap for ap in ap_list if
                         self.match_ap_criteria(criteria=criteria, ap=ap) ), None )
        return match_ap


args = defaultdict(str)
def main():

    # make args global so we can use outside this scope
    global args

    # Create the parser for extracting the expiry time
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--infile_csv', type=str, required=False,
                        default=f"{DEFAULT_INFILE}",
                        help=f"specify infile csv, defaults to {DEFAULT_INFILE}")
    parser.add_argument('-o', '--outfile_csv', type=str, required=False,
                        default=f"{DEFAULT_OUTFILE}",
                        help=f"specify outfile csv to dump ONLINE_AP list, defaults to {DEFAULT_INFILE}")
    parser.add_argument('-l', '--list', required=False, action='store_true',
                        help=f"list the ONLINE_AP in the outfile csv. Only works if -n not used or is ALL")
    parser.add_argument('-n', '--name', type=str, required=False,
                        default=None,
                        help=f"check only this specific AP name")
    parser.add_argument('-a', '--accel', required=False, action='store_true',
                        help=f"print accelerometer for each AP")
    parser.add_argument('-S', '--speed', required=False, action='store_true',
                        help=f"print speed & duplex for each AP")
    parser.add_argument('-d', '--debug', required=False, action='store_true',
                        help=f"print debug message")
    parser.add_argument('-X', '--Xchange', required=False, action='store_true',
                        help=f"don't actually make change")
    args, args_unknown = parser.parse_known_args()

    NEW_APs = []

    # Open the CSV file for the desired AP mapping
    # basically, we want all loops to still work.. so we can at least collect what we can collect despite lacking information
    if Path(args.infile_csv).is_file():
        with open(args.infile_csv, "r") as csvfile:
            # Read and clean the first row (header) keys
            header_line = csvfile.readline()
            raw_headers = next(csv.reader([header_line]))
            cleaned_headers = [h.strip() for h in raw_headers]
            for ap in csv.DictReader(csvfile, fieldnames=cleaned_headers, delimiter=',', quotechar='"', restkey='details', restval=None):
                append_ap = AccessPoint(**ap)
                NEW_APs.append(append_ap)
                if args.debug: send_ios_syslog(message=f"NEW_APs has {append_ap['AP_NAME']} {append_ap}")
    else:
        print(f"{args.infile_csv} not found.")

    if args.debug:
        send_ios_syslog(severity=l_DEBUG, message=f"NEW_APs has {len(NEW_APs)} APs from infile_csv {args.infile_csv}")
        for ap in NEW_APs:
            send_ios_syslog(severity=l_DEBUG, message=f"NEW_APs has {ap['AP_NAME']} {ap}")

    cli_results = defaultdict(str)

    if is_guestshell:
        # Retrieve the AP list from the WLC
        if args.name is not None and args.name != "ALL":
            cli_results['show_ap_summary'] = show_ap(command=f"show ap summary | inc {args.name}")
            # TODO fix sleep
            send_ios_syslog(severity=l_INFO, message=f"Sleeping 210 sec on {args.name} to wait for CDP information" )
            time.sleep(210.001)  # Allow time for AP CDP to roll in.. take about 3 1/2 mins
            cli_results['show_cdp_neighbor'] = show_ap(command=f"show ap name {args.name} cdp neighbor detail")
            cli_results['show_ap_ether_stats'] = show_ap(command=f"show ap name {args.name} ethernet statistics")
            # for a single AP, have to loop thru the potential slots
            cli_results['show_ap_config_slot'] = ""
            for i in range(0, 4):
                cli_results['show_ap_config_slot'] = cli_results['show_ap_config_slot'] + show_ap(command=f"show ap name {args.name} config slot {i}")
        else:
            cli_results['show_ap_summary'] = show_ap(command=f"show ap summary")
            cli_results['show_cdp_neighbor'] = show_ap(command=f"show ap cdp neighbor detail")
            cli_results['show_ap_ether_stats'] = show_ap(command=f"show ap ethernet statistics")
            cli_results['show_ap_config_slot'] = show_ap(command=f"show ap config slot")
    else:
        cli_results['show_ap_summary'] = fetch_file(file=SIM_FILE_EEM_AP_SUMM)
        cli_results['show_cdp_neighbor'] = fetch_file(file=SIM_FILE_EEM_AP_CDP_DETAIL)
        cli_results['show_ap_ether_stats'] = fetch_file(file=SIM_FILE_EEM_AP_ETHER_STATS)
        cli_results['show_ap_config_slot'] = fetch_file(file=SIM_FILE_EEM_AP_CONFIG_SLOT)

    ONLINE_APs = []

    # build list of online AP from show ap summary
    pattern = defaultdict(lambda : re.compile(rf'~'))
    pattern['AP_SUMMARY'] = re.compile(rf"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(Registered)\s+(.*)")
    match_cli = defaultdict(lambda : re.search(pattern['~'],'BLANK'))
    for line in cli_results['show_ap_summary'].splitlines():
        # clear and start a new objects
        online_ap = AccessPoint()
        match_cli['AP_SUMMARY'] = re.search(pattern['AP_SUMMARY'], line)
        # clear and start a new this_ap object
        if match_cli['AP_SUMMARY']:
            online_ap['AP_NAME'] = match_cli['AP_SUMMARY'].group(1)
            online_ap['AP_MODEL'] = match_cli['AP_SUMMARY'].group(3)
            online_ap['AP_MAC_ENET'] = match_cli['AP_SUMMARY'].group(4)
            online_ap['AP_MAC_RADIO'] = match_cli['AP_SUMMARY'].group(5)
            online_ap['AP_LOCATION'] = match_cli['AP_SUMMARY'].group(10)
            ONLINE_APs.append(online_ap)

    # Sort them for added sanity to process loops in a way most humans think
    sorted_ONLINE_APs = sorted(ONLINE_APs, key=lambda x: (x['AP_NAME'], x['AP_CDP_SWITCH_PORT_LOCAL']))

    def get_ap_cdp(chk_ap:AccessPoint=None):
        if chk_ap is None: return
        if chk_ap is None: return
        # clear and start a new objects
        this_ap = AccessPoint()
        pattern = defaultdict(lambda : re.compile(rf'~'))
        pattern['AP_NAME'] =        re.compile(rf"^AP Name\s+:\s+(\S+)")
        pattern['AP_CDP_SWITCH'] =    re.compile(rf"^Device ID\s+:\s+(\S+)\.")
        pattern['AP_INTERFACE'] =   re.compile(rf"^Interface\s+:\s+(\S+),.*:\s+(\S+)")
        match_cli = defaultdict(lambda : re.search(pattern['~'],'BLANK'))
        for line in cli_results['show_cdp_neighbor'].splitlines():
            # find the line that matches this AP
            match_cli['AP_NAME'] = re.search(pattern['AP_NAME'], line)
            match_cli['AP_CDP_SWITCH'] = re.search(pattern['AP_CDP_SWITCH'], line)
            match_cli['AP_INTERFACE'] = re.search(pattern['AP_INTERFACE'], line)
            if (this_ap['AP_NAME'] is None
                    and match_cli['AP_NAME']
                    and chk_ap['AP_NAME'] == match_cli['AP_NAME'].group(1)):
                # clear and start a new this_ap object
                this_ap = AccessPoint()
                this_ap['AP_NAME'] = match_cli['AP_NAME'].group(1)
            if (this_ap['AP_NAME']
                    and this_ap['AP_CDP_SWITCH'] is None
                    and match_cli['AP_CDP_SWITCH']):
                this_ap['AP_CDP_SWITCH'] = match_cli['AP_CDP_SWITCH'].group(1).split(".")[0]
            if (this_ap['AP_CDP_SWITCH']
                    and this_ap['AP_CDP_SWITCH_PORT'] is None
                    and this_ap['AP_CDP_SWITCH_PORT_LOCAL'] is None
                    and match_cli['AP_INTERFACE']):
                this_ap['AP_CDP_SWITCH_PORT'] = match_cli['AP_INTERFACE'].group(2)
                this_ap['AP_CDP_SWITCH_PORT_LOCAL'] = match_cli['AP_INTERFACE'].group(1)
            match_cli['HIT'] = (this_ap['AP_NAME']
                                and this_ap['AP_CDP_SWITCH'] and this_ap['AP_CDP_SWITCH_PORT']
                                and this_ap['AP_CDP_SWITCH_PORT_LOCAL'])

            if match_cli['HIT']:
                # create a new object for checking and potentially appending
                prep_online_ap = copy.deepcopy(chk_ap)
                prep_online_ap['AP_CDP_SWITCH'] = this_ap['AP_CDP_SWITCH']
                prep_online_ap['AP_CDP_SWITCH_PORT'] = this_ap['AP_CDP_SWITCH_PORT']
                prep_online_ap['AP_CDP_SWITCH_PORT_LOCAL'] = this_ap['AP_CDP_SWITCH_PORT_LOCAL']

                if args.debug: send_ios_syslog(severity=l_DEBUG, message=f"CDP detected {prep_online_ap}")
                # see if we already added this AP per a CDP hit, if not then added with CDP neighbor not known
                match_ap = prep_online_ap.matching_ap(criteria=['AP_NAME', 'AP_CDP_SWITCH_PORT_LOCAL'],
                                                      ap_list=ONLINE_APs)
                if match_ap:
                    match_ap['AP_CDP_SWITCH'] = this_ap['AP_CDP_SWITCH']
                    match_ap['AP_CDP_SWITCH_PORT'] = this_ap['AP_CDP_SWITCH_PORT']
                    match_ap['AP_CDP_SWITCH_PORT_LOCAL'] = this_ap['AP_CDP_SWITCH_PORT_LOCAL']
                elif chk_ap['AP_CDP_SWITCH_PORT_LOCAL'] is None:
                    chk_ap['AP_CDP_SWITCH'] = this_ap['AP_CDP_SWITCH']
                    chk_ap['AP_CDP_SWITCH_PORT'] = this_ap['AP_CDP_SWITCH_PORT']
                    chk_ap['AP_CDP_SWITCH_PORT_LOCAL'] = this_ap['AP_CDP_SWITCH_PORT_LOCAL']
                else:
                    ONLINE_APs.append(prep_online_ap)
            if match_cli['HIT']:
                # clear and start a new this_ap object
                this_ap = AccessPoint()

    def get_ap_serial(chk_ap:AccessPoint=None):
        if chk_ap is None: return
        cli_ap_serial_detail = show_ap(command=f"show ap name {chk_ap['AP_NAME']} inventory")
        # clear and start a new this_ap object
        this_ap = AccessPoint()
        pattern = defaultdict(lambda : re.compile(rf'~'))
        pattern['AP_SERIAL'] = re.compile(rf"^PID:.*SN:\s+(\S+)")
        match_cli = defaultdict(lambda : re.search(pattern['~'],'BLANK'))
        for line in cli_ap_serial_detail.splitlines():
            match_cli['AP_SERIAL'] = re.search(pattern['AP_SERIAL'], line)
            if match_cli['AP_SERIAL']:
                chk_ap['AP_SERIAL'] = match_cli['AP_SERIAL'].group(1)
        if args.debug: send_ios_syslog(severity=l_DEBUG,
                                       message=f"SERIAL ONLINE {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']} "
                                               f"is {chk_ap['AP_SERIAL']}")

    def get_tilt(chk_ap:AccessPoint=None):
        if chk_ap is None: return
        cli_ap_tile_detail = show_ap(command=f"show ap name {chk_ap['AP_NAME']} accelerometer")
        # clear and start a new this_ap object
        this_ap = AccessPoint()
        pattern = defaultdict(lambda : re.compile(rf'~'))
        pattern['AP_TILT'] = re.compile(rf"^Tilt angle\s+:\s+(.*)")
        match_cli = defaultdict(lambda : re.search(pattern['~'],'BLANK'))
        for line in cli_ap_tile_detail.splitlines():
            match_cli['AP_TILT'] = re.search(pattern['AP_TILT'], line)
            if match_cli['AP_TILT']:
                chk_ap['AP_TILT'] = match_cli['AP_TILT'].group(1).strip()
        if args.accel: send_ios_syslog(severity=l_DEBUG,
                        message=f"ACCEL ONLINE {chk_ap['AP_MODEL']} {chk_ap['AP_NAME']} is {chk_ap['AP_TILT']}")

    def get_speed_duplex(chk_ap:AccessPoint=None):
        if chk_ap is None: return
        # clear and start a new objects
        this_ap = AccessPoint()
        pattern = defaultdict(lambda : re.compile(rf'~'))
        pattern['AP_NAME'] =        re.compile(rf"^AP Name\s+:\s+(\S+)")
        pattern['AP_SPEED_DUPLEX'] =   re.compile(rf"^(GigabitEthernet\d)\s+(\S+)\s+(\d+)\s+(Mbps)\s+(\S+)")
        match_cli = defaultdict(lambda : re.search(pattern['~'],'BLANK'))
        for line in cli_results['show_ap_ether_stats'].splitlines():
            # find the line that matches this AP
            match_cli['AP_NAME'] = re.search(pattern['AP_NAME'], line)
            if match_cli['AP_NAME']:
                # clear and start a new this_ap object
                this_ap = AccessPoint()
                this_ap['AP_NAME'] = match_cli['AP_NAME'].group(1)
            # now process this block, but only for the AP looking for
            if this_ap['AP_NAME'] == chk_ap['AP_NAME']:
                # Now continue to fetch the attached speed/duplex
                match_cli['AP_SPEED_DUPLEX'] = re.search(pattern['AP_SPEED_DUPLEX'], line)
                if match_cli['AP_SPEED_DUPLEX']:
                    this_ap['AP_CDP_SWITCH_PORT_LOCAL'] = match_cli['AP_SPEED_DUPLEX'].group(1)
                    this_ap['AP_CDP_SWITCH_SPEED'] = match_cli['AP_SPEED_DUPLEX'].group(3)
                    this_ap['AP_CDP_SWITCH_DUPLEX'] = match_cli['AP_SPEED_DUPLEX'].group(5)

            match_cli['HIT'] = (this_ap['AP_NAME'] == chk_ap['AP_NAME']
                                and this_ap['AP_CDP_SWITCH_PORT_LOCAL']
                                and this_ap['AP_CDP_SWITCH_SPEED'] and this_ap['AP_CDP_SWITCH_DUPLEX'])

            if match_cli['HIT']:
                # create a new object for checking and potentially appending
                prep_online_ap = copy.deepcopy(chk_ap)
                prep_online_ap['AP_CDP_SWITCH_PORT_LOCAL'] = this_ap['AP_CDP_SWITCH_PORT_LOCAL']
                prep_online_ap['AP_CDP_SWITCH_PORT_SPEED'] = this_ap['AP_CDP_SWITCH_SPEED']
                prep_online_ap['AP_CDP_SWITCH_PORT_DUPLEX'] = this_ap['AP_CDP_SWITCH_DUPLEX']

                if args.debug: send_ios_syslog(severity=l_DEBUG, message=f"SPEED_DUPLEX detected {prep_online_ap}")
                # see if we already added this AP, if not then add it
                match_ap = prep_online_ap.matching_ap(criteria=['AP_NAME', 'AP_CDP_SWITCH_PORT_LOCAL'],
                                                      ap_list=ONLINE_APs)
                if  match_ap:
                    match_ap['AP_CDP_SWITCH_PORT_LOCAL'] = this_ap['AP_CDP_SWITCH_PORT_LOCAL']
                    match_ap['AP_CDP_SWITCH_PORT_SPEED'] = this_ap['AP_CDP_SWITCH_SPEED']
                    match_ap['AP_CDP_SWITCH_PORT_DUPLEX'] = this_ap['AP_CDP_SWITCH_DUPLEX']
                elif chk_ap['AP_CDP_SWITCH_PORT_LOCAL'] is None:
                     chk_ap['AP_CDP_SWITCH_PORT_LOCAL'] = this_ap['AP_CDP_SWITCH_PORT_LOCAL']
                     chk_ap['AP_CDP_SWITCH_PORT_SPEED'] = this_ap['AP_CDP_SWITCH_SPEED']
                     chk_ap['AP_CDP_SWITCH_PORT_DUPLEX'] = this_ap['AP_CDP_SWITCH_DUPLEX']
                else:
                    ONLINE_APs.append(prep_online_ap)

        if args.speed: send_ios_syslog(severity=l_DEBUG,
                                       message=f"SPEED_DUPLEX ONLINE {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']} "
                                               f"{chk_ap['AP_CDP_SWITCH_PORT_LOCAL']} is "
                                               f"{chk_ap['AP_CDP_SWITCH_PORT_SPEED']} "
                                               f"{chk_ap['AP_CDP_SWITCH_PORT_DUPLEX']}")


    def do_ap_rename(chk_ap:AccessPoint=None):
        if chk_ap is None: return
        # First look for a full match of all the criteria that is present
        # only look for AP-s that need to be renamed, so match does not include AP_NAME itself
        criteria = ['AP_MODEL', 'AP_SERIAL', 'AP_MAC_ENET', 'AP_MAC_RADIO', 'AP_CDP_SWITCH', 'AP_CDP_SWITCH_PORT']
        if args.debug:send_ios_syslog(severity=l_DEBUG,
                                      message=f"MATCH_AP ONLINE {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']} "
                                              f"in NEW_APs criteria {criteria} {chk_ap}")
        match_ap = chk_ap.matching_ap(criteria=criteria, ap_list=NEW_APs)
        if match_ap:
            if args.debug: send_ios_syslog(severity=l_DEBUG, message=f"MATCH_AP Found NEW_AP {match_ap} as ONLINE {this_online_apchk_online_ap}")
            if match_ap['AP_NAME'] != chk_ap['AP_NAME']:
                send_ios_syslog(severity=l_INFO,
                                message=f"RENAME_AP Renaming to name {match_ap['AP_NAME']} for {chk_ap}")
                change_ap(command=f"ap name {chk_ap['AP_NAME']} name {match_ap['AP_NAME']}")

    def do_dual_5ghz(chk_ap:AccessPoint=None):
        if chk_ap is None: return
        # First look for a full match of all the criteria that is present
        # only look for AP-s HAVE BEEN named/renamed correctly.. so include AP_NAME
        criteria = ['AP_NAME', 'AP_MODEL', 'AP_SERIAL', 'AP_MAC_ENET', 'AP_MAC_RADIO', 'AP_CDP_SWITCH', 'AP_CDP_SWITCH_PORT']
        if args.debug: send_ios_syslog(severity=l_DEBUG,
                                      message=f"DUAL_5GHZ ONLINE {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']}"
                                              f" matching in NEW_APs criteria {criteria} {chk_ap}")
        match_ap = chk_ap.matching_ap(criteria=criteria, ap_list=NEW_APs)
        if match_ap:
            if args.debug: send_ios_syslog(severity=l_DEBUG,
                                           message=f"DUAL_5GHZ ONLINE {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']}"
                                                   f" HIT as {match_ap['AP_NAME']} {match_ap['AP_MODEL']}")

            # TODO always collect.. also deal with explicit Disabled
            if match_ap['AP_MODEL'] in ['CW9178I', 'CW9176D1']:
                # Check based on AP_MODEL and if dual 5GHz is not enabled, enable it respectively
                if args.debug: send_ios_syslog(severity=l_DEBUG,
                                               message=f"DUAL_5GHZ ONLINE {chk_ap['AP_NAME']} {match_ap['AP_MODEL']}"
                                                       f" checking status")
                if match_ap['AP_MODEL'] == "CW9178I":
                    # assume we have a longer summary, as this will work for short or long output then
                    # Check Slot 1 first
                    # clear and start a new objects
                    this_ap = AccessPoint()
                    pattern = defaultdict(lambda: re.compile('~'))
                    pattern['AP_NAME'] = re.compile(rf"^Cisco AP Name\s+:\s+({chk_ap['AP_NAME']})")
                    pattern['AP_SLOT'] = re.compile(rf"^Attributes for Slot (1)")
                    pattern['AP_SLOT_DUAL_ROLE'] = re.compile(rf"^\s+Dual Radio Mode\s+:\s+(.*)")
                    pattern['AP_SLOT_ADMIN'] = re.compile(rf"^\s+Administrative State\s+:\s+(.*)")
                    match_cli = defaultdict(lambda: re.search(pattern['NULL'],'NEVER'))
                    for line in cli_results['show_ap_config_slot'].splitlines():
                        # find the line that matches this AP
                        match_cli['AP_NAME'] = re.search(pattern['AP_NAME'], line)
                        match_cli['AP_SLOT'] = re.search(pattern['AP_SLOT'], line)
                        match_cli['AP_SLOT_DUAL_ROLE'] = re.search(pattern['AP_SLOT_DUAL_ROLE'], line)
                        match_cli['AP_SLOT_ADMIN'] = re.search(pattern['AP_SLOT_ADMIN'], line)
                        if (this_ap['AP_NAME'] is None
                            and match_cli['AP_NAME']
                            and match_cli['AP_NAME'].group(1) == chk_ap['AP_NAME']):
                            # clear and start a new this_ap object
                            this_ap = AccessPoint()
                            this_ap['AP_NAME'] = match_cli['AP_NAME'].group(1)
                        if (this_ap['AP_NAME']
                                and this_ap['AP_SLOT'] is None
                                and match_cli['AP_SLOT']):
                            this_ap['AP_SLOT'] = match_cli['AP_SLOT'].group(1)
                        if (this_ap['AP_SLOT']
                                and this_ap['AP_SLOT_DUAL_ROLE'] is None
                                and match_cli['AP_SLOT_DUAL_ROLE']):
                            this_ap['AP_SLOT_DUAL_ROLE'] = match_cli['AP_SLOT_DUAL_ROLE'].group(1).strip()
                        if (this_ap['AP_SLOT_DUAL_ROLE']
                                and this_ap['AP_SLOT_ADMIN'] is None
                                and match_cli['AP_SLOT_ADMIN']):
                            this_ap['AP_SLOT_ADMIN'] = match_cli['AP_SLOT_ADMIN'].group(1).strip()

                        match_cli['HIT'] = (this_ap['AP_NAME']
                                            and this_ap['AP_SLOT']
                                            and this_ap['AP_SLOT_DUAL_ROLE']
                                            and this_ap['AP_SLOT_ADMIN'])

                        if match_cli['HIT'] and args.debug:
                            send_ios_syslog(severity=l_DEBUG,
                                            message=f"DUAL_5GHZ ONLINE {chk_ap['AP_NAME']} "
                                                    f"{chk_ap['AP_MODEL']} Slot {this_ap['AP_SLOT']} "
                                                    f"HIT as mode {this_ap['AP_SLOT_DUAL_ROLE']} / admin {this_ap['AP_SLOT_ADMIN']}")
                            # update online_ap
                            chk_ap['AP_DUAL_5GHZ'] = f"Slot {this_ap['AP_SLOT']} mode {this_ap['AP_SLOT_DUAL_ROLE']}"
                        # no need to keep looking, so break the loop checking line
                        if match_cli['HIT']: break

                    if match_cli['HIT'] and this_ap['AP_SLOT_DUAL_ROLE'] != "Enabled" and match_ap['AP_DUAL_5GHZ'] == "Enabled":
                        send_ios_syslog(severity=l_INFO,
                                        message=f"DUAL_5GHZ ONLINE {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']} "
                                                f"Slot {this_ap['AP_SLOT']} "
                                                f"changing to dual_mode for mode {this_ap['AP_SLOT_DUAL_ROLE']} / admin {this_ap['AP_SLOT_ADMIN']}")
                        change_ap(command=f"ap name {chk_ap['AP_NAME']} dot11 5ghz slot 2 shutdown")
                        change_ap(command=f"ap name {chk_ap['AP_NAME']} dot11 5ghz dual-radio mode enable")
                        change_ap(command=f"ap name {chk_ap['AP_NAME']} no dot11 5ghz slot 2 shutdown")

                    if match_cli['HIT'] and this_ap['AP_SLOT_ADMIN'] != "Enabled" and match_ap['AP_DUAL_5GHZ'] == "Enabled":
                        send_ios_syslog(severity=l_INFO,
                                        message=f"DUAL_5GHZ ONLINE {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']} "
                                                f"Slot {this_ap['AP_SLOT']} "
                                                f"changing to dual-5GHz to Admin Enable as dual_mode {this_ap['AP_SLOT_DUAL_ROLE']} / admin {this_ap['AP_SLOT_ADMIN']}")
                        change_ap(command=f"ap name {chk_ap['AP_NAME']} no dot11 5ghz slot {this_ap['AP_SLOT']} shutdown")

                    # assume we have a longer summary, as this will work for short or long output then
                    # Now check Slot 2
                    # clear and start a new objects
                    this_ap = AccessPoint()
                    pattern = defaultdict(lambda : re.compile(rf'~'))
                    pattern['AP_NAME'] = re.compile(rf"^Cisco AP Name\s+:\s+(\S+)")
                    pattern['AP_SLOT'] = re.compile(rf"^Attributes for Slot (2)")
                    pattern['AP_SLOT_ADMIN'] = re.compile(rf"^\s+Administrative State\s+:\s+(.*)")
                    match_cli = defaultdict(lambda : re.search(pattern['~'],'BLANK'))
                    for line in cli_results['show_ap_config_slot'].splitlines():
                        # find the line that matches this AP
                        match_cli['AP_NAME'] = re.search(pattern['AP_NAME'], line)
                        match_cli['AP_SLOT'] = re.search(pattern['AP_SLOT'], line)
                        match_cli['AP_SLOT_ADMIN'] = re.search(pattern['AP_SLOT_ADMIN'], line)
                        if (this_ap['AP_NAME'] is None
                            and match_cli['AP_NAME']
                            and match_cli['AP_NAME'].group(1) == chk_ap['AP_NAME']):
                            # clear and start a new this_ap object
                            this_ap = AccessPoint()
                            this_ap['AP_NAME'] = match_cli['AP_NAME'].group(1)
                        if (this_ap['AP_NAME']
                                and this_ap['AP_SLOT'] is None
                                and match_cli['AP_SLOT']):
                            this_ap['AP_SLOT'] = match_cli['AP_SLOT'].group(1)
                        if (this_ap['AP_SLOT']
                                and this_ap['AP_SLOT_ADMIN'] is None
                                and match_cli['AP_SLOT_ADMIN']):
                            this_ap['AP_SLOT_ADMIN'] = match_cli['AP_SLOT_ADMIN'].group(1).strip()
                        match_cli['HIT'] = (this_ap['AP_NAME']
                                            and this_ap['AP_SLOT']
                                            and this_ap['AP_SLOT_ADMIN'])
                        if match_cli['HIT'] and args.debug:
                            send_ios_syslog(severity=l_DEBUG,
                                            message=f"DUAL_5GHZ ONLINE {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']} "
                                                    f"Slot {this_ap['AP_SLOT']} HIT admin {this_ap['AP_SLOT_ADMIN']}")
                            # update online_ap
                            chk_ap['AP_DUAL_5GHZ'] = f"{chk_ap['AP_DUAL_5GHZ']} / Slot {this_ap['AP_SLOT']} admin {this_ap['AP_SLOT_ADMIN']}"
                        # no need to keep looking, so break the loop checking line
                        if match_cli['HIT']: break

                    if (match_cli['HIT']
                            and this_ap['AP_SLOT_ADMIN'] != "Enabled" and match_ap['AP_DUAL_5GHZ'] == "Enabled"):
                        send_ios_syslog(severity=l_INFO,
                                        message=f"DUAL_5GHZ ONLINE {chk_ap['AP_MODEL']} {chk_ap['AP_NAME']} "
                                                f"Slot {this_ap['AP_SLOT']} "
                                                f"changing to dual-5GHz to Admin Enable as admin {this_ap['AP_SLOT_ADMIN']}")
                        change_ap(command=f"ap name {chk_ap['AP_NAME']} no dot11 5ghz slot {this_ap['AP_SLOT']} shutdown")

                elif match_ap['AP_MODEL'] == "CW9176D1":
                    # assume we have a longer summary, as this will work for short or long output then
                    # clear and start a new objects
                    this_ap = AccessPoint()
                    pattern = defaultdict(lambda : re.compile(rf'~'))
                    pattern['AP_NAME'] = re.compile(rf"^Cisco AP Name\s+:\s+(\S+)")
                    pattern['AP_SLOT'] = re.compile(rf"^Attributes for Slot (0)")
                    pattern['AP_SLOT_ROLE'] = re.compile(rf"^\s+Radio Role\s+:\s+(.*)")
                    pattern['AP_SLOT_METHOD'] = re.compile(rf"^\s+Assignment Method\s+:\s+(.*)")
                    pattern['AP_SLOT_BAND'] = re.compile(rf"^\s+Band\s+:\s+(\S+\s+GHz)")
                    match_cli = defaultdict(lambda : re.search(pattern['~'],'BLANK'))
                    for line in cli_results['show_ap_config_slot'].splitlines():
                        # find the line that matches this AP
                        match_cli['AP_NAME'] = re.search(pattern['AP_NAME'], line)
                        match_cli['AP_SLOT'] = re.search(pattern['AP_SLOT'], line)
                        match_cli['AP_SLOT_ROLE'] = re.search(pattern['AP_SLOT_ROLE'], line)
                        match_cli['AP_SLOT_METHOD'] = re.search(pattern['AP_SLOT_METHOD'], line)
                        match_cli['AP_SLOT_BAND'] = re.search(pattern['AP_SLOT_BAND'], line)
                        if (this_ap['AP_NAME'] is None
                            and match_cli['AP_NAME']):
                            this_ap['AP_NAME'] = match_cli['AP_NAME'].group(1)
                        if (this_ap['AP_NAME']
                                and this_ap['AP_SLOT'] is None
                                and match_cli['AP_SLOT']):
                            this_ap['AP_SLOT'] = match_cli['AP_SLOT'].group(1)
                        if (this_ap['AP_SLOT']
                                and this_ap['AP_SLOT_ROLE'] is None
                                and match_cli['AP_SLOT_ROLE']):
                            this_ap['AP_SLOT_ROLE'] = match_cli['AP_SLOT_ROLE'].group(1).strip()
                        if (this_ap['AP_SLOT_ROLE']
                                and this_ap['AP_SLOT_METHOD'] is None
                                and match_cli['AP_SLOT_METHOD']):
                            this_ap['AP_SLOT_METHOD'] = match_cli['AP_SLOT_METHOD'].group(1).strip()
                        if (this_ap['AP_SLOT_METHOD']
                                and this_ap['AP_SLOT_BAND'] is None
                                and match_cli['AP_SLOT_BAND']):
                            this_ap['AP_SLOT_BAND'] = match_cli['AP_SLOT_BAND'].group(1).strip()

                        match_cli['HIT'] = (this_ap['AP_NAME'] == chk_ap['AP_NAME']
                                  and this_ap['AP_SLOT'] and this_ap['AP_SLOT_ROLE'] and this_ap['AP_SLOT_METHOD'] and this_ap['AP_SLOT_BAND'])
                        if match_cli['HIT'] and args.debug:
                            send_ios_syslog(severity=l_DEBUG,
                                            message=f"DUAL_5GHZ ONLINE {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']} "
                                                    f"Slot {this_ap['AP_SLOT']} "
                                                    f"has role {this_ap['AP_SLOT_ROLE']} / method {this_ap['AP_SLOT_METHOD']} / band {this_ap['AP_SLOT_BAND']}")
                        # no need to keep looking, so break the loop checking line
                        if match_cli['HIT']: break

                    # update online_ap
                    chk_ap['AP_DUAL_5GHZ'] = f"Slot {this_ap['AP_SLOT']} band {this_ap['AP_SLOT_BAND']}"

                    if match_cli['HIT'] and this_ap['AP_SLOT_BAND'] != "5 GHz" and match_ap['AP_DUAL_5GHZ'] == "Enabled":
                        send_ios_syslog(severity=l_INFO,
                                        message=f"DUAL_5GHZ ONLINE {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']} "
                                                f"Slot {this_ap['AP_SLOT']} "
                                                f"changing to enable dual-5GHz for role {this_ap['AP_SLOT_ROLE']} / method {this_ap['AP_SLOT_METHOD']} / band {this_ap['AP_SLOT_BAND']}")
                        change_ap(command=f"ap name {chk_ap['AP_NAME']} dot11 dual-band shutdown")
                        change_ap(command=f"ap name {chk_ap['AP_NAME']} dot11 dual-band radio role manual client-serving")
                        change_ap(command=f"ap name {chk_ap['AP_NAME']} dot11 dual-band band 5ghz")
                        change_ap(command=f"ap name {chk_ap['AP_NAME']} no dot11 dual-band shutdown")

    def process_ap(chk_ap:AccessPoint=None):
        get_ap_cdp(chk_ap)
        get_ap_serial(chk_ap)
        get_tilt(chk_ap)
        # get_speed_duplex(online_ap)
        do_ap_rename(chk_ap)
        do_dual_5ghz(chk_ap)

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Start the load operations and mark each future with its URL
        iterator = executor.map(process_ap, sorted_ONLINE_APs)
        # Convert to list to force execution and wait until ALL are completed
        results = list(iterator)

    if args.debug: send_ios_syslog(severity=l_INFO, message=f"ONLINE_APs length is {len(ONLINE_APs)}")

    # only dump if doing ALL AP-s
    if args.list and (args.name is None or args.name == "ALL"):
        csv_fields = ['AP_NAME', 'AP_MODEL', 'AP_SERIAL', 'AP_MAC_ENET', 'AP_MAC_RADIO',
                      'AP_LOCATION', 'AP_CDP_SWITCH', 'AP_CDP_SWITCH_PORT',
                      'AP_DUAL_5GHZ']

        # sort again, allowing for repeated AP_NAME for AP_CDP_SWITCH_PORT_LOCAL
        sorted_ONLINE_APs = sorted(ONLINE_APs, key=lambda x: (x['AP_NAME'], x['AP_CDP_SWITCH_PORT_LOCAL']))

        # using a dict to build fieldnames so will be in order inserted, aka csv_fields first followed by other keys used
        fieldnames = dict.fromkeys(csv_fields)
        for item in sorted_ONLINE_APs:
            for key in item.keys():
                fieldnames[key] = None

        with open(args.outfile_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            # restval handles missing keys by filling them with an empty string
            writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
            # Write the column headers row
            writer.writeheader()
            # Write all rows at once
            writer.writerows(sorted_ONLINE_APs)
        send_ios_syslog(severity=l_INFO, message=f"ONLINE_AP of {len(ONLINE_APs)} items is written to {args.outfile_csv}")


if __name__ == "__main__":
    send_ios_syslog(severity=l_INFO, message=f"Starting ... {sys.argv}")
    main()
    send_ios_syslog(severity=l_INFO, message=f"Finished ... {sys.argv}")
