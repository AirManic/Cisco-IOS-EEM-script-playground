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

from iosxe_guestshell_logging import configure_guestshell_logging
import argparse
import os
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


logger = configure_guestshell_logging(__name__)

l_DEBUG  = 7
l_INFO   = 6
l_NOTICE = 5
l_WARN   = 4
l_ERR    = 3
l_CRIT   = 2

args_global = argparse.Namespace()

cli_results = defaultdict(str)
ONLINE_APs = []
NEW_APs = []

def show_ap(command:Union[str,list]=None):
    command_loop = []
    if type(command) is str:
        command_loop.append(command)
    elif type(command) is list:
        command_loop = command_loop + command
    command_seq = []
    for cmd in command_loop:
        command_seq.append(f"{cmd}")
    if args_global.debug: logger.info(f"fetching cli([{command}])")
    results = cli(command)
    return results

def change_ap(command:Union[str,list]=None):
    command_loop = [f"enable"]
    if type(command) is str:
        command_loop.append(f"{command}")
    elif type(command) is list:
        command_loop = command_loop + command
    cripple = ""
    if args_global.Xchange: cripple = f"! Xchange crippled "
    command_seq = ""
    for cmd in command_loop:
        if command_seq != "": command_seq += ";"
        command_seq = command_seq + (f"{cripple}{cmd}")
    logger.info(f"sending cli('{command_seq}')")
    results = cli(command)
    return results

def fetch_file(file:str=None):
    results = ''
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

    def match_ap_criteria(self, criteria:list=None, ap=None):
        criteria_loop = []
        if type(criteria) is str:
            criteria_loop.append(criteria)
        if type(criteria) is list:
            criteria_loop = criteria_loop + criteria
        # self is expected to be a real AP, and ap is an AP that might/might not exist but has the key criteria
        # track if there is at least one criteria item called out that matches
        # seed the match with True, as it will go False if there is a criteria item that does not match
        ap_return = None
        match_ap = True
        miss_match_ap = False
        is_ap_criteria = False
        for aspect in criteria_loop:
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

    def matching_ap(self, criteria:list=None, ap_list:list=None):
        # self is expected to be reference to find, and ap might/might not exist but has the key criteria
        ap_loop = []
        if type(ap_list) is str:
            ap_loop.append(ap_list)
        if type(ap_list) is list:
            ap_loop = ap_loop + ap_list
        criteria_loop = []
        if type(criteria) is str:
            criteria_loop.append(criteria)
        if type(criteria) is list:
            criteria_loop = criteria_loop + criteria
        match_ap = next( (ap for ap in ap_loop if
                         self.match_ap_criteria(criteria=criteria_loop, ap=ap) ), None )
        return match_ap

def get_ap_cdp(chk_ap=None):
    global cli_results
    global ONLINE_APs
    if chk_ap is None: return
    if args_global.name is not None and args_global.name != "ALL":
        wait_time = 300
        logger.info(f"{args_global.name} waiting up to {wait_time} seconds for CDP information")
        start_time = time.time()
        if is_guestshell:
            while len(cli_results['show_cdp_neighbor']) < 10 and time.time() - start_time < wait_time:
                cli_results['show_cdp_neighbor'] = show_ap(command=f"show ap name {chk_ap['AP_NAME']} cdp neighbor detail")
        logger.info(f"{args_global.name} got CDP information after {(time.time() - start_time):.3f} seconds")
    cli_results['show_cdp_neighbor'] = show_ap(command=f"show ap name {chk_ap['AP_NAME']} cdp neighbor detail")
    if not is_guestshell:
        cli_results['show_cdp_neighbor'] = fetch_file(file=SIM_FILE_EEM_AP_CDP_DETAIL)
    # clear and start a new objects
    cli_ap = AccessPoint()
    pattern = defaultdict(lambda : re.compile(rf'~'))
    pattern['AP_NAME'] =        re.compile(rf"^AP Name\s+:\s+(\S+)")
    pattern['AP_CDP_SWITCH'] =    re.compile(rf"^Device ID\s+:\s+(\S+)\.")
    pattern['AP_INTERFACE'] =   re.compile(rf"^Interface\s+:\s+(\S+),.*:\s+(\S+)")
    cli_match = defaultdict(lambda : re.search(pattern['~'],'BLANK'))
    for line in cli_results['show_cdp_neighbor'].splitlines():
        # find the line that matches this AP
        cli_match['AP_NAME'] = re.search(pattern['AP_NAME'], line)
        cli_match['AP_CDP_SWITCH'] = re.search(pattern['AP_CDP_SWITCH'], line)
        cli_match['AP_INTERFACE'] = re.search(pattern['AP_INTERFACE'], line)
        if (cli_ap['AP_NAME'] is None
                and cli_match['AP_NAME']
                and chk_ap['AP_NAME'] == cli_match['AP_NAME'].group(1)):
            # clear and start a new cli_ap object
            cli_ap = AccessPoint()
            cli_ap['AP_NAME'] = cli_match['AP_NAME'].group(1)
        if (cli_ap['AP_NAME']
                and cli_ap['AP_CDP_SWITCH'] is None
                and cli_match['AP_CDP_SWITCH']):
            cli_ap['AP_CDP_SWITCH'] = cli_match['AP_CDP_SWITCH'].group(1).split(".")[0]
        if (cli_ap['AP_CDP_SWITCH']
                and cli_ap['AP_CDP_SWITCH_PORT'] is None
                and cli_ap['AP_CDP_SWITCH_PORT_LOCAL'] is None
                and cli_match['AP_INTERFACE']):
            cli_ap['AP_CDP_SWITCH_PORT'] = cli_match['AP_INTERFACE'].group(2)
            cli_ap['AP_CDP_SWITCH_PORT_LOCAL'] = cli_match['AP_INTERFACE'].group(1)
        cli_match['HIT'] = (cli_ap['AP_NAME']
                            and cli_ap['AP_CDP_SWITCH'] and cli_ap['AP_CDP_SWITCH_PORT']
                            and cli_ap['AP_CDP_SWITCH_PORT_LOCAL'])

        if cli_match['HIT']:
            if args_global.debug: logger.debug(f"CDP detected {cli_ap}")
            # most likely, this is the only AP entry and this is first AP_CDP_SWITCH_PORT_LOCAL need to track
            if (chk_ap['AP_CDP_SWITCH_PORT_LOCAL'] is None
                    or chk_ap['AP_CDP_SWITCH_PORT_LOCAL'] == cli_ap['AP_CDP_SWITCH_PORT_LOCAL']):
                match_ap = chk_ap
            else:
                # see if we already added this AP, if not then add it
                match_ap = cli_ap.matching_ap(criteria=['AP_NAME', 'AP_CDP_SWITCH_PORT_LOCAL'],
                                                      ap_list=ONLINE_APs)
                if not match_ap:
                    # create a new object for checking and potentially appending
                    match_ap = copy.deepcopy(chk_ap)
                    ONLINE_APs.append(match_ap)
            match_ap['AP_CDP_SWITCH']            = cli_ap['AP_CDP_SWITCH']
            match_ap['AP_CDP_SWITCH_PORT']       = cli_ap['AP_CDP_SWITCH_PORT']
            match_ap['AP_CDP_SWITCH_PORT_LOCAL'] = cli_ap['AP_CDP_SWITCH_PORT_LOCAL']
            # clear and start a new cli_ap object
            cli_ap = AccessPoint()

def get_ap_serial(chk_ap=None):
    global cli_results
    global ONLINE_APs
    if chk_ap is None: return
    cli_ap_serial_detail = show_ap(command=f"show ap name {chk_ap['AP_NAME']} inventory")
    # clear and start a new cli_ap object
    cli_ap = AccessPoint()
    pattern = defaultdict(lambda : re.compile(rf'~'))
    pattern['AP_SERIAL'] = re.compile(rf"^PID:.*SN:\s+(\S+)")
    cli_match = defaultdict(lambda : re.search(pattern['~'],'BLANK'))
    for line in cli_ap_serial_detail.splitlines():
        cli_match['AP_SERIAL'] = re.search(pattern['AP_SERIAL'], line)
        if cli_match['AP_SERIAL']:
            chk_ap['AP_SERIAL'] = cli_match['AP_SERIAL'].group(1)
    if args_global.debug: logger.debug(f"chk_ap {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']}"
                                       f" is {chk_ap['AP_SERIAL']}")

def get_tilt(chk_ap=None):
    global cli_results
    global ONLINE_APs
    if chk_ap is None: return
    cli_ap_tile_detail = show_ap(command=f"show ap name {chk_ap['AP_NAME']} accelerometer")
    # clear and start a new cli_ap object
    cli_ap = AccessPoint()
    pattern = defaultdict(lambda : re.compile(rf'~'))
    pattern['AP_TILT'] = re.compile(rf"^Tilt angle\s+:\s+(.*)")
    cli_match = defaultdict(lambda : re.search(pattern['~'],'BLANK'))
    for line in cli_ap_tile_detail.splitlines():
        cli_match['AP_TILT'] = re.search(pattern['AP_TILT'], line)
        if cli_match['AP_TILT']:
            chk_ap['AP_TILT'] = cli_match['AP_TILT'].group(1)
    if args_global.accel: logger.debug(f"chk_ap {chk_ap['AP_MODEL']} {chk_ap['AP_NAME']} is {chk_ap['AP_TILT']}")

def get_speed_duplex(chk_ap=None):
    global cli_results
    global ONLINE_APs
    if chk_ap is None: return
    cli_results['show_ap_ether_stats'] = show_ap(command=f"show ap name {chk_ap['AP_NAME']} ethernet statistics")
    if not is_guestshell:
        cli_results['show_ap_ether_stats'] = fetch_file(file=SIM_FILE_EEM_AP_ETHER_STATS)
    # clear and start a new objects
    cli_ap = AccessPoint()
    pattern = defaultdict(lambda : re.compile(rf'~'))
    pattern['AP_NAME'] =            re.compile(rf"^(?:AP Name\s+:|Ethernet Stats for AP)\s+(\S+)")
    # Ethernet Stats for AP BLAH
    pattern['AP_SPEED_DUPLEX'] =    re.compile(rf"^(GigabitEthernet\d)\s+(\S+)\s+(\d+)\s+(Mbps)\s+(\S+)")
    cli_match = defaultdict(lambda : re.search(pattern['~'],'BLANK'))
    for line in cli_results['show_ap_ether_stats'].splitlines():
        # find the line that matches this AP
        cli_match['AP_NAME'] = re.search(pattern['AP_NAME'], line)
        cli_match['AP_SPEED_DUPLEX'] = re.search(pattern['AP_SPEED_DUPLEX'], line)
        if cli_match['AP_NAME']:
            # clear start a new cli_ap object
            cli_ap = AccessPoint()
            if cli_match['AP_NAME'].group(1) == chk_ap['AP_NAME']:
                cli_ap['AP_NAME'] = cli_match['AP_NAME'].group(1)
        if cli_ap['AP_NAME'] and cli_match['AP_SPEED_DUPLEX']:
            cli_ap['AP_CDP_SWITCH_PORT_LOCAL'] = cli_match['AP_SPEED_DUPLEX'].group(1)
            cli_ap['AP_CDP_SWITCH_PORT_SPEED'] = cli_match['AP_SPEED_DUPLEX'].group(3)
            cli_ap['AP_CDP_SWITCH_PORT_DUPLEX'] = cli_match['AP_SPEED_DUPLEX'].group(5)
        cli_match['HIT'] = (cli_ap['AP_NAME']
                            and cli_ap['AP_CDP_SWITCH_PORT_LOCAL']
                            and cli_ap['AP_CDP_SWITCH_PORT_SPEED'] and cli_ap['AP_CDP_SWITCH_PORT_DUPLEX'])

        if cli_match['HIT']:
            if args_global.debug: logger.debug(f"detected cli_ap {cli_ap}")

            # most likely, this is the only AP entry and this is first AP_CDP_SWITCH_PORT_LOCAL need to track
            if (chk_ap['AP_CDP_SWITCH_PORT_LOCAL'] is None
                    or chk_ap['AP_CDP_SWITCH_PORT_LOCAL'] == cli_ap['AP_CDP_SWITCH_PORT_LOCAL']):
                match_ap = chk_ap
            else:
                # see if we already added this AP, if not then add it
                match_ap = cli_ap.matching_ap(criteria=['AP_NAME', 'AP_CDP_SWITCH_PORT_LOCAL'],
                                               ap_list=ONLINE_APs)
                if match_ap is None:
                    # create a new object for checking and potentially appending
                    match_ap = copy.deepcopy(chk_ap)
                    ONLINE_APs.append(match_ap)
                    match_ap['AP_CDP_SWITCH']            = None
                    match_ap['AP_CDP_SWITCH_PORT']       = None
            # now set the items ..
            match_ap['AP_CDP_SWITCH_PORT_LOCAL']  = cli_ap['AP_CDP_SWITCH_PORT_LOCAL']
            match_ap['AP_CDP_SWITCH_PORT_SPEED']  = cli_ap['AP_CDP_SWITCH_PORT_SPEED']
            match_ap['AP_CDP_SWITCH_PORT_DUPLEX'] = cli_ap['AP_CDP_SWITCH_PORT_DUPLEX']
            # clear the cli_ap speed/duplex aspects to look for another interface match
            cli_ap['AP_CDP_SWITCH_PORT_LOCAL']  = None
            cli_ap['AP_CDP_SWITCH_PORT_SPEED']  = None
            cli_ap['AP_CDP_SWITCH_PORT_DUPLEX'] = None
            if args_global.debug:
                logger.debug(f"match_ap {match_ap['AP_NAME']}"
                             f" using {match_ap['AP_CDP_SWITCH_PORT_LOCAL']}"
                             f" HIT on {match_ap['AP_CDP_SWITCH_PORT_SPEED']} / {match_ap['AP_CDP_SWITCH_PORT_DUPLEX']}")
            # check to see if this has correct speed max
            switch_port_speed_max = None
            if match_ap['AP_CDP_SWITCH_PORT']:
                if   match_ap['AP_CDP_SWITCH_PORT'].startswith('TenGigabitEthernet'): switch_port_speed_max = '10000'
                elif match_ap['AP_CDP_SWITCH_PORT'].startswith('FiveGigabitEthernet'):  switch_port_speed_max = '5000'
                elif match_ap['AP_CDP_SWITCH_PORT'].startswith('TwoGigabitEthernet'):  switch_port_speed_max = '2500'
                elif match_ap['AP_CDP_SWITCH_PORT'].startswith('GigabitEthernet'):  switch_port_speed_max = '1000'
            ap_speed_max = switch_port_speed_max
            if match_ap['AP_MODEL']:
                # assume AP models not explicitly listed can do max speed of switchport to start
                # TODO categorize more AP_MODEL-s
                if match_ap['AP_MODEL'].startswith('CW917'): ap_speed_max = '10000'
                if match_ap['AP_MODEL'].startswith('AIR-AP38'):  ap_speed_max = '5000'
            expected_speed = None
            if switch_port_speed_max and ap_speed_max:
                expected_speed = str(min(int(switch_port_speed_max), int(ap_speed_max)))
            if expected_speed and match_ap['AP_CDP_SWITCH_PORT_SPEED'] != expected_speed:
                logger.notice(f"match_ap {match_ap['AP_NAME']} {match_ap['AP_MODEL']}"
                               f" check {match_ap['AP_CDP_SWITCH_PORT_SPEED']} Mbps against expected {expected_speed} Mbps"
                               f" on {match_ap['AP_CDP_SWITCH']} {match_ap['AP_CDP_SWITCH_PORT']}")

def do_ap_rename(chk_ap=None):
    global cli_results
    global ONLINE_APs
    global NEW_APs
    if chk_ap is None: return
    # First look for a full match of all the criteria that is present
    # only look for AP-s that need to be renamed, so match does not include AP_NAME itself
    criteria = ['AP_MODEL', 'AP_SERIAL', 'AP_MAC_ENET', 'AP_MAC_RADIO', 'AP_CDP_SWITCH', 'AP_CDP_SWITCH_PORT']
    if args_global.debug:logger.debug(f"chk_ap {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']} "
                                          f"doing NEW_APs match criteria {criteria}")
    if args_global.debug:logger.debug(f"chk_ap is {chk_ap}")
    match_ap = chk_ap.matching_ap(criteria=criteria, ap_list=NEW_APs)
    if match_ap:
        if args_global.debug: logger.debug(f"chk_ap {chk_ap} in as NEW_APs {match_ap}")
        if match_ap['AP_NAME'] != chk_ap['AP_NAME']:
            logger.info(f"chk_ap {chk_ap['AP_NAME']} renaming NEW_APs match_ap {match_ap['AP_NAME']} for chk_ap {chk_ap}")
            change_ap(command=f"ap name {chk_ap['AP_NAME']} name {match_ap['AP_NAME']}")

def do_dual_5ghz(chk_ap=None):
    global cli_results
    global ONLINE_APs
    global NEW_APs
    if chk_ap is None: return
    cli_results['show_ap_config_slot'] = ""
    for i in range(0, 4):
        cli_results['show_ap_config_slot'] = (cli_results['show_ap_config_slot']
                    + show_ap(command=f"show ap name {args_global.name} config slot {i}"))
    if not is_guestshell:
        cli_results['show_ap_config_slot'] = fetch_file(file=SIM_FILE_EEM_AP_CONFIG_SLOT)
    # First look for a full match of all the criteria that is present
    # only look for AP-s HAVE BEEN named/renamed correctly.. so include AP_NAME
    criteria = ['AP_NAME', 'AP_MODEL', 'AP_SERIAL', 'AP_MAC_ENET', 'AP_MAC_RADIO', 'AP_CDP_SWITCH', 'AP_CDP_SWITCH_PORT']
    if args_global.debug: logger.debug(f"chk_ap {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']} "
                                       f"matching in NEW_APs criteria {criteria} {chk_ap} ")
    match_ap = chk_ap.matching_ap(criteria=criteria, ap_list=NEW_APs)
    if match_ap:
        if args_global.debug: logger.debug(f"chk_ap {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']} "
                                           f"HIT as {match_ap['AP_NAME']} {match_ap['AP_MODEL']}")

        # TODO deal with explicit Disabled
        if match_ap['AP_MODEL'] in ['CW9178I', 'CW9176D1']:
            # Check based on AP_MODEL and if dual 5GHz is not enabled, enable it respectively
            if args_global.debug: logger.debug(f"match_ap {match_ap['AP_NAME']} {match_ap['AP_MODEL']}"
                                               f" checking status")
            if match_ap['AP_MODEL'] == "CW9178I":
                # assume we have a longer summary, as this will work for short or long output then
                # Check Slot 1 first
                # clear and start a new objects
                cli_ap = AccessPoint()
                pattern = defaultdict(lambda: re.compile('~'))
                pattern['AP_NAME'] = re.compile(rf"^Cisco AP Name\s+:\s+({chk_ap['AP_NAME']})")
                pattern['AP_SLOT'] = re.compile(rf"^Attributes for Slot (1)")
                pattern['AP_SLOT_DUAL_ROLE'] = re.compile(rf"^\s+Dual Radio Mode\s+:\s+(.*)")
                pattern['AP_SLOT_ADMIN'] = re.compile(rf"^\s+Administrative State\s+:\s+(.*)")
                cli_match = defaultdict(lambda: re.search(pattern['NULL'],'NEVER'))
                for line in cli_results['show_ap_config_slot'].splitlines():
                    # find the respective patterns
                    for p in pattern:
                        cli_match[p] = re.search(pattern[p],line)
                    if (cli_ap['AP_NAME'] is None
                        and cli_match['AP_NAME']):
                        # clear and start a new cli_ap object
                        cli_ap = AccessPoint()
                        cli_ap['AP_NAME'] = cli_match['AP_NAME'].group(1)
                    if (cli_ap['AP_NAME']
                            and cli_ap['AP_SLOT'] is None
                            and cli_match['AP_SLOT']):
                        cli_ap['AP_SLOT'] = cli_match['AP_SLOT'].group(1)
                    if (cli_ap['AP_SLOT']
                            and cli_ap['AP_SLOT_DUAL_ROLE'] is None
                            and cli_match['AP_SLOT_DUAL_ROLE']):
                        cli_ap['AP_SLOT_DUAL_ROLE'] = cli_match['AP_SLOT_DUAL_ROLE'].group(1)
                    if (cli_ap['AP_SLOT_DUAL_ROLE']
                            and cli_ap['AP_SLOT_ADMIN'] is None
                            and cli_match['AP_SLOT_ADMIN']):
                        cli_ap['AP_SLOT_ADMIN'] = cli_match['AP_SLOT_ADMIN'].group(1)

                    cli_match['HIT'] = (cli_ap['AP_NAME']
                                        and cli_ap['AP_SLOT']
                                        and cli_ap['AP_SLOT_DUAL_ROLE']
                                        and cli_ap['AP_SLOT_ADMIN'])

                    if cli_match['HIT'] and args_global.debug:
                        logger.debug(f"match_ap {match_ap['AP_NAME']}"
                                     f" {match_ap['AP_MODEL']} Slot {match_ap['AP_SLOT']}"
                                     f" HIT as mode {match_ap['AP_SLOT_DUAL_ROLE']} / admin {match_ap['AP_SLOT_ADMIN']}")

                    # no need to keep looking, so break the loop checking line
                    if cli_match['HIT']:
                        # update chk_ap
                        chk_ap['AP_DUAL_5GHZ'] = f"Slot {cli_ap['AP_SLOT']} dual_radio {cli_ap['AP_SLOT_DUAL_ROLE']} admin {cli_ap['AP_SLOT_ADMIN']}"
                        break

                if cli_match['HIT'] and cli_ap['AP_SLOT_DUAL_ROLE'] != "Enabled" and match_ap['AP_DUAL_5GHZ'] == "Enabled":
                    logger.info(f"chk_ap {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']}"
                                f" Slot {chk_ap['AP_SLOT']}"
                                f" changing to dual_mode for mode {cli_ap['AP_SLOT_DUAL_ROLE']} / admin {cli_ap['AP_SLOT_ADMIN']}")
                    change_ap(command=f"ap name {chk_ap['AP_NAME']} dot11 5ghz slot 2 shutdown")
                    change_ap(command=f"ap name {chk_ap['AP_NAME']} dot11 5ghz dual-radio mode enable")
                    change_ap(command=f"ap name {chk_ap['AP_NAME']} no dot11 5ghz slot 2 shutdown")

                if cli_match['HIT'] and cli_ap['AP_SLOT_ADMIN'] != "Enabled" and match_ap['AP_DUAL_5GHZ'] == "Enabled":
                    logger.info(f"chk_ap {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']}"
                                f" slot {cli_ap['AP_SLOT']}"
                                f" changing to dual-5GHz to admin enable per existing"
                                f" dual_mode {cli_ap['AP_SLOT_DUAL_ROLE']} / admin {cli_ap['AP_SLOT_ADMIN']}")
                    change_ap(command=f"ap name {chk_ap['AP_NAME']} no dot11 5ghz slot {cli_ap['AP_SLOT']} shutdown")

                # assume we have a longer summary, as this will work for short or long output then
                # Now check Slot 2
                # clear and start a new objects
                cli_ap = AccessPoint()
                pattern = defaultdict(lambda : re.compile(rf'~'))
                pattern['AP_NAME'] = re.compile(rf"^Cisco AP Name\s+:\s+({chk_ap['AP_NAME']})")
                pattern['AP_SLOT'] = re.compile(rf"^Attributes for Slot (2)")
                pattern['AP_SLOT_ADMIN'] = re.compile(rf"^\s+Administrative State\s+:\s+(.*)")
                cli_match = defaultdict(lambda : re.search(pattern['~'],'BLANK'))
                for line in cli_results['show_ap_config_slot'].splitlines():
                    # find the respective patterns
                    for p in pattern:
                        cli_match[p] = re.search(pattern[p],line)
                    if (cli_ap['AP_NAME'] is None
                        and cli_match['AP_NAME']):
                        # clear and start a new cli_ap object
                        cli_ap = AccessPoint()
                        cli_ap['AP_NAME'] = cli_match['AP_NAME'].group(1)
                    if (cli_ap['AP_NAME']
                            and cli_ap['AP_SLOT'] is None
                            and cli_match['AP_SLOT']):
                        cli_ap['AP_SLOT'] = cli_match['AP_SLOT'].group(1)
                    if (cli_ap['AP_SLOT']
                            and cli_ap['AP_SLOT_ADMIN'] is None
                            and cli_match['AP_SLOT_ADMIN']):
                        cli_ap['AP_SLOT_ADMIN'] = cli_match['AP_SLOT_ADMIN'].group(1)
                    cli_match['HIT'] = (cli_ap['AP_NAME']
                                        and cli_ap['AP_SLOT']
                                        and cli_ap['AP_SLOT_ADMIN'])
                    if cli_match['HIT'] and args_global.debug:
                        logger.debug(f"chk_ap {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']}"
                                     f" slot {cli_ap['AP_SLOT']}"
                                     f" HIT admin {cli_ap['AP_SLOT_ADMIN']}")

                    # no need to keep looking, so break the loop checking line
                    if cli_match['HIT']:
                        # update chk_ap
                        chk_ap['AP_DUAL_5GHZ'] = f"{chk_ap['AP_DUAL_5GHZ']} / Slot {cli_ap['AP_SLOT']} admin {cli_ap['AP_SLOT_ADMIN']}"
                        break

                if (cli_match['HIT']
                        and cli_ap['AP_SLOT_ADMIN'] != "Enabled" and match_ap['AP_DUAL_5GHZ'] == "Enabled"):
                    logger.info(f"chk_ap {chk_ap['AP_MODEL']} {chk_ap['AP_NAME']}"
                                f" slot {cli_ap['AP_SLOT']}"
                                f" changing to dual-5GHz to admin enable per existing admin {cli_ap['AP_SLOT_ADMIN']}")
                    change_ap(command=f"ap name {chk_ap['AP_NAME']} no dot11 5ghz slot {cli_ap['AP_SLOT']} shutdown")

            elif match_ap['AP_MODEL'] == "CW9176D1":
                # assume we have a longer summary, as this will work for short or long output then
                # clear and start a new objects
                cli_ap = AccessPoint()
                pattern = defaultdict(lambda : re.compile(rf'~'))
                pattern['AP_NAME'] = re.compile(rf"^Cisco AP Name\s+:\s+({chk_ap['AP_NAME']})")
                pattern['AP_SLOT'] = re.compile(rf"^Attributes for Slot (0)")
                pattern['AP_SLOT_ROLE'] = re.compile(rf"^\s+Radio Role\s+:\s+(.*)")
                pattern['AP_SLOT_METHOD'] = re.compile(rf"^\s+Assignment Method\s+:\s+(.*)")
                pattern['AP_SLOT_BAND'] = re.compile(rf"^\s+Band\s+:\s+(\S+\s+GHz)")
                pattern['AP_SLOT_ADMIN'] = re.compile(rf"^\s+Administrative State\s+:\s+(.*)")
                cli_match = defaultdict(lambda : re.search(pattern['~'],'BLANK'))
                for line in cli_results['show_ap_config_slot'].splitlines():
                    # find the respective patterns
                    for p in pattern:
                        cli_match[p] = re.search(pattern[p],line)
                    if (cli_ap['AP_NAME'] is None
                        and cli_match['AP_NAME']):
                        # clear and start a new cli_ap object
                        cli_ap = AccessPoint()
                        cli_ap['AP_NAME'] = cli_match['AP_NAME'].group(1)
                    if (cli_ap['AP_NAME']
                            and cli_ap['AP_SLOT'] is None
                            and cli_match['AP_SLOT']):
                        cli_ap['AP_SLOT'] = cli_match['AP_SLOT'].group(1)
                    if (cli_ap['AP_SLOT']
                            and cli_ap['AP_SLOT_ROLE'] is None
                            and cli_match['AP_SLOT_ROLE']):
                        cli_ap['AP_SLOT_ROLE'] = cli_match['AP_SLOT_ROLE'].group(1)
                    if (cli_ap['AP_SLOT_ROLE']
                            and cli_ap['AP_SLOT_METHOD'] is None
                            and cli_match['AP_SLOT_METHOD']):
                        cli_ap['AP_SLOT_METHOD'] = cli_match['AP_SLOT_METHOD'].group(1)
                    if (cli_ap['AP_SLOT_METHOD']
                            and cli_ap['AP_SLOT_BAND'] is None
                            and cli_match['AP_SLOT_BAND']):
                        cli_ap['AP_SLOT_BAND'] = cli_match['AP_SLOT_BAND'].group(1)
                    if (cli_ap['AP_SLOT']
                            and cli_ap['AP_SLOT_ADMIN'] is None
                            and cli_match['AP_SLOT_ADMIN']):
                        cli_ap['AP_SLOT_ADMIN'] = cli_match['AP_SLOT_ADMIN'].group(1)

                    cli_match['HIT'] = (cli_ap['AP_NAME']
                                        and cli_ap['AP_SLOT']
                                        and cli_ap['AP_SLOT_ROLE']
                                        and cli_ap['AP_SLOT_METHOD']
                                        and cli_ap['AP_SLOT_BAND']
                                        and cli_ap['AP_SLOT_ADMIN'])
                    if cli_match['HIT'] and args_global.debug:
                        logger.debug(f"chk_ap {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']}"
                                     f" slot {cli_ap['AP_SLOT']}"
                                     f" has role {cli_ap['AP_SLOT_ROLE']} / method {cli_ap['AP_SLOT_METHOD']} / band {cli_ap['AP_SLOT_BAND']}")
                    # no need to keep looking, so break the loop checking line
                    if cli_match['HIT']:
                        # update chk_ap
                        chk_ap['AP_DUAL_5GHZ'] = f"Slot {cli_ap['AP_SLOT']} band {cli_ap['AP_SLOT_BAND']} admin {cli_ap['AP_SLOT_ADMIN']}"
                        break

                if cli_match['HIT'] and cli_ap['AP_SLOT_BAND'] != "5 GHz" and match_ap['AP_DUAL_5GHZ'] == "Enabled":
                    logger.info(f"chk_ap {chk_ap['AP_NAME']} {chk_ap['AP_MODEL']}"
                                f" slot {cli_ap['AP_SLOT']}"
                                f" changing to enable dual-5GHz for existing"
                                f" role {cli_ap['AP_SLOT_ROLE']} / method {cli_ap['AP_SLOT_METHOD']} / band {cli_ap['AP_SLOT_BAND']}")
                    change_ap(command=f"ap name {chk_ap['AP_NAME']} dot11 dual-band shutdown")
                    change_ap(command=f"ap name {chk_ap['AP_NAME']} dot11 dual-band radio role manual client-serving")
                    change_ap(command=f"ap name {chk_ap['AP_NAME']} dot11 dual-band band 5ghz")
                    change_ap(command=f"ap name {chk_ap['AP_NAME']} no dot11 dual-band shutdown")

def process_ap(chk_ap=None):
    try:
        get_ap_serial(chk_ap)
        get_ap_cdp(chk_ap)
        do_ap_rename(chk_ap)
        get_speed_duplex(chk_ap)
        get_tilt(chk_ap)
        do_dual_5ghz(chk_ap)
    except Exception:
        pass

def main():
    global cli_results
    global ONLINE_APs
    global NEW_APs

    # make args global so we can use outside this scope
    global args_global

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
    parser.add_argument('-S', '--speed', required=False, action='store_true',
                        help=f"print speed & duplex for each AP")
    parser.add_argument('-a', '--accel', required=False, action='store_true',
                        help=f"print accelerometer for each AP")
    parser.add_argument('-d', '--debug', required=False, action='store_true',
                        help=f"print debug message")
    parser.add_argument('-X', '--Xchange', required=False, action='store_true',
                        help=f"don't actually make change")
    args_global, args_unknown = parser.parse_known_args()

    logger.info(f"Starting ... {sys.argv}")

    # Open the CSV file for the desired AP mapping
    # basically, we want all loops to still work.. so we can at least collect what we can collect despite lacking information
    if Path(args_global.infile_csv).is_file():
        with open(args_global.infile_csv, "r") as csvfile:
            # Read and clean the first row (header) keys
            header_line = csvfile.readline()
            raw_headers = next(csv.reader([header_line]))
            cleaned_headers = [h.strip() for h in raw_headers]
            for ap in csv.DictReader(csvfile, fieldnames=cleaned_headers, delimiter=',', quotechar='"', restkey='details', restval=None):
                append_ap = AccessPoint(**ap)
                NEW_APs.append(append_ap)
                if args_global.debug: logger.debug(f"infile_csv {args_global.infile_csv} has {append_ap['AP_NAME']} {append_ap}")
    else:
        print(f"{args_global.infile_csv} not found.")

    if args_global.debug:
        logger.debug(f"NEW_APs has {len(NEW_APs)} APs from infile_csv {args_global.infile_csv}")
        for ap in NEW_APs:
            logger.debug(f"NEW_APs has {ap['AP_NAME']} {ap}")

    if args_global.name is not None and args_global.name != "ALL":
        cli_results['show_ap_summary'] = show_ap(command=f"show ap summary | inc {args_global.name}")
    else:
        cli_results['show_ap_summary'] = show_ap(command=f"show ap summary")
    if not is_guestshell:
        cli_results['show_ap_summary'] = fetch_file(file=SIM_FILE_EEM_AP_SUMM)

    # build list of online AP from show ap summary
    pattern = defaultdict(lambda : re.compile(rf'~'))
    pattern['AP_SUMMARY'] = re.compile(rf"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(Registered)\s+(.*)")
    cli_match = defaultdict(lambda : re.search(pattern['~'],'BLANK'))
    for line in cli_results['show_ap_summary'].splitlines():
        # clear and start a new objects
        online_ap = AccessPoint()
        cli_match['AP_SUMMARY'] = re.search(pattern['AP_SUMMARY'], line)
        # clear and start a new cli_ap object
        if cli_match['AP_SUMMARY']:
            online_ap['AP_NAME'] = cli_match['AP_SUMMARY'].group(1)
            online_ap['AP_MODEL'] = cli_match['AP_SUMMARY'].group(3)
            online_ap['AP_MAC_ENET'] = cli_match['AP_SUMMARY'].group(4)
            online_ap['AP_MAC_RADIO'] = cli_match['AP_SUMMARY'].group(5)
            online_ap['AP_LOCATION'] = cli_match['AP_SUMMARY'].group(10)
            ONLINE_APs.append(online_ap)

    # Sort them for added sanity to process loops in a way most humans think
    sorted_ONLINE_APs = sorted(ONLINE_APs, key=lambda x: (x['AP_NAME'], x['AP_CDP_SWITCH_PORT_LOCAL']))

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Start the load operations and mark each future with its URL
        iterator = executor.map(process_ap, sorted_ONLINE_APs, timeout=120)
        # Convert to list to force execution and wait until ALL are completed
        results = list(iterator)

    if args_global.debug: logger.info(f"ONLINE_APs length is {len(ONLINE_APs)}")

    # only dump if doing ALL AP-s
    if args_global.list and (args_global.name is None or args_global.name == "ALL"):
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

        with open(args_global.outfile_csv, 'w', newline='') as f:
            writer = csv.writer(f)
            # restval handles missing keys by filling them with an empty string
            writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
            # Write the column headers row
            writer.writeheader()
            # Write all rows at once
            writer.writerows(sorted_ONLINE_APs)
        logger.info(f"sorted_ONLINE_APs of {len(sorted_ONLINE_APs)} items is written to {args_global.outfile_csv}")

    logger.info(f"Finished ... {sys.argv}")


if __name__ == "__main__":
    main()
