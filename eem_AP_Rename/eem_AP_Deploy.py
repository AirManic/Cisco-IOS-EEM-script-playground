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
            log_string = f"{my_name} RandRunID {run_string} {line}"
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


class AccessPoint(dict):

    # Define fields to make sure exist
    csv_fields = ['AP_NAME', 'AP_MODEL', 'AP_SERIAL', 'AP_MAC_ENET', 'AP_MAC_RADIO',
                  'AP_LOCATION', 'AP_CDP_SWITCH', 'AP_CDP_SWITCH_PORT',
                  'AP_DUAL_5GHZ']

    def __init__(self, *args, **kwargs):
        # Make sure these attributes exist first
        for field in self.csv_fields: self[field] = None
        # now load any fields passed in the instantiator call
        super().__init__(*args, **kwargs)
        # make sure all fields are strip(), this esp helps when reading csv file headers and values
        for field in self.csv_fields:
            if isinstance(self[field],str): self[field] = self[field].strip()

    def __setitem__(self, key, value):
        new_value = value
        if isinstance(value,str): new_value = value.strip()
        super().__setitem__(key, new_value)

    def make_exist(self,key):
        key_loop = []
        if type(key) is str:
            key_loop.append(key)
        elif type(key) is list:
            key_loop = key
        for item in key_loop:
            if item not in self:
                self[item] = None

    def match_ap_criteria(self, criteria=None, ap=None,):
        # self is expected to be a real AP, and ap is an AP that might/might not exist but has the key criteria
        # track if there is at least one criteria item called out that matches
        is_ap_criteria = False
        # seed the match with True, as it will go False if there is a criteria item that does not match
        ap_return = None
        match_ap = True
        miss_match_ap = False
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
                # no need to check any further, break loop
                break

        # if had at least one item to match on.. and if all the items called out did match
        got_a_solid_match = is_ap_criteria and match_ap and not miss_match_ap
        # TODO concurrent
        if got_a_solid_match:
            ap_return = ap

        return ap_return

    def matching_ap(self, criteria=None, ap_list=None):
        # self is expected to be a real AP, and ap is an AP that might/might not exist but has the key criteria
        # TODO concurrent
        match_ap = next( (ap for ap in ap_list if
                         self.match_ap_criteria(criteria=criteria, ap=ap) ), None )
        return match_ap


args = None
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
                        help=f"fetch accelerometer for each AP")
    parser.add_argument('-s', '--speed', required=False, action='store_true',
                        help=f"fetch speed/duplex and check for each AP")
    parser.add_argument('-d', '--debug', required=False, action='store_true',
                        help=f"print debug message")
    parser.add_argument('-X', '--Xchange', required=False, action='store_true',
                        help=f"don't actually make change")
    args = parser.parse_args()

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
                NEW_APs.append(AccessPoint(ap))
    else:
        print(f"{args.infile_csv} not found.")

    if args.debug:
        send_ios_syslog(severity=l_DEBUG, message=f"NEW_APs has {len(NEW_APs)} APs from infile_csv {args.infile_csv}")
        for ap in NEW_APs:
            send_ios_syslog(severity=l_DEBUG, message=f"NEW_APs has {ap['AP_NAME']} {ap}")

    # using dummy "blank line" to keep for loop splitline() happy later
    # basically, we want all loops to still work.. so we can at least collect what we can collect despite lacking information
    cli_ap_summary = "blank line"
    cli_ap_cdp_detail = "blank line"
    cli_ap_ether_stats = "blank line"
    cli_ap_config_slot = "blank line"

    if is_guestshell:
        # Retrieve the AP list from the WLC
        if args.name is not None and args.name != "ALL":
            command = f"show ap summary | inc {args.name}"
            if args.debug: send_ios_syslog(severity=l_INFO, message=f"Fetching cli([{command}])" )
            cli_ap_summary = cli(command) ; command = ""
            # TODO fix sleep
            if args.debug: send_ios_syslog(severity=l_INFO, message=f"Sleeping 210 sec on {args.name} to wait for CDP information" )
            time.sleep(210.001)  # Allow time for AP CDP to roll in.. take about 3 1/2 mins
            command = f"show ap name {args.name} cdp neighbor detail"
            if args.debug: send_ios_syslog(severity=l_INFO, message=f"Fetching cli([{command}])" )
            cli_ap_cdp_detail = cli(command) ; command = ""
            command = f"show ap name {args.name} ethernet statistics"
            if args.debug:send_ios_syslog(severity=l_INFO, message=f"Fetching cli([{command}])" )
            cli_ap_ether_stats = cli(command) ; command = ""
            # for a single AP, have to loop thru the potential slots
            cli_ap_config_slot = ""
            for i in range(0, 4):
                command = f"show ap name {args.name} config slot {i}"
                if args.debug: send_ios_syslog(severity=l_INFO, message=f"Fetching cli([{command}])" )
                cli_ap_config_slot = cli_ap_config_slot + cli(command) ; command =""
        else:
            command = f"show ap summary"
            if args.debug: send_ios_syslog(severity=l_INFO, message=f"Fetching cli([{command}])" )
            cli_ap_summary = cli(command) ; command = ""
            command = f"show ap cdp neighbor detail"
            if args.debug: send_ios_syslog(severity=l_INFO, message=f"Fetching cli([{command}])" )
            cli_ap_cdp_detail = cli(command) ; command = ""
            command = f"show ap ethernet statistics"
            if args.debug: send_ios_syslog(severity=l_INFO, message=f"Fetching cli([{command}])" )
            cli_ap_ether_stats = cli(command) ; command = ""
            command = f"show ap config slot"
            if args.debug: send_ios_syslog(severity=l_INFO, message=f"Fetching cli([{command}])" )
            cli_ap_config_slot = cli(command) ; command = ""
    else:
        if Path(SIM_FILE_EEM_AP_SUMM).is_file():
            with open(SIM_FILE_EEM_AP_SUMM) as file:
                cli_ap_summary = file.read()
        else:
            print(f"{SIM_FILE_EEM_AP_SUMM} not found.")

        if Path(SIM_FILE_EEM_AP_CDP_DETAIL).is_file():
            with open(SIM_FILE_EEM_AP_CDP_DETAIL) as file:
                cli_ap_cdp_detail = file.read()
        else:
            print(f"{SIM_FILE_EEM_AP_CDP_DETAIL} not found.")

        if Path(SIM_FILE_EEM_AP_ETHER_STATS).is_file():
            with open(SIM_FILE_EEM_AP_ETHER_STATS) as file:
                cli_ap_ether_stats = file.read()
        else:
            print(f"{SIM_FILE_EEM_AP_ETHER_STATS} not found.")

        if Path(SIM_FILE_EEM_AP_CONFIG_SLOT).is_file():
            with open(SIM_FILE_EEM_AP_CONFIG_SLOT) as file:
                cli_ap_config_slot = file.read()
        else:
            print(f"{SIM_FILE_EEM_AP_CONFIG_SLOT} not found.")

    ONLINE_APs = []

    # build list of online AP from show ap summary
    for line in cli_ap_summary.splitlines():
        online_ap = AccessPoint()
        f_regex = rf"^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(Registered)\s+(.*)"
        match_cli_ap_summ = re.search(f_regex, line)
        if match_cli_ap_summ:
            online_ap['AP_NAME'] = match_cli_ap_summ.group(1)
            online_ap['AP_MODEL'] = match_cli_ap_summ.group(3)
            online_ap['AP_MAC_ENET'] = match_cli_ap_summ.group(4)
            online_ap['AP_MAC_RADIO'] = match_cli_ap_summ.group(5)
            online_ap['AP_LOCATION'] = match_cli_ap_summ.group(10)
            ONLINE_APs.append(online_ap)

    # Sort them for added sanity to process loops in a way most humans think
    sorted_ONLINE_APs = sorted(ONLINE_APs, key=lambda x: x['AP_NAME'])

    def get_ap_cdp(online_ap=None):
        if online_ap is None: return
        if 'AP_CDP_SWITCH' not in online_ap.keys():
            online_ap['AP_CDP_SWITCH'] = None
        if 'AP_CDP_SWITCH_PORT' not in online_ap.keys():
            online_ap['AP_CDP_SWITCH_PORT'] = None
        if 'AP_CDP_SWITCH_PORT_LOCAL' not in online_ap.keys():
            online_ap['AP_CDP_SWITCH_PORT_LOCAL'] = None
        # assume we have a longer summary, as this will work for short or long output then
        # as we are expecting some AP-s to be dual-enet, so need to find all matches
        f_regex = rf"^AP Name\s+:\s+(\S+)"
        pattern_AP_NAME = re.compile(f_regex)
        f_regex = rf"^Device ID\s+:\s+(\S+)\."
        pattern_AP_DEVICEID = re.compile(f_regex)
        f_regex = rf"^Interface\s+:\s+(\S+),.*:\s+(\S+)"
        pattern_INTERFACE = re.compile(f_regex)

        this_ap_name = None
        this_ap_cdp_switch = None
        this_ap_cdp_switch_port = None
        this_ap_cdp_switch_port_local = None
        for line in cli_ap_cdp_detail.splitlines():
            # find the line that matches this AP
            match_cli_cdp_ap = re.search(pattern_AP_NAME, line)
            if match_cli_cdp_ap:
                this_ap_name = match_cli_cdp_ap.group(1)
                this_ap_cdp_switch = None
                this_ap_cdp_switch_port = None
                this_ap_cdp_switch_port_local = None
            # now process this block, but only for the AP looking for
            if this_ap_name == online_ap['AP_NAME']:
                # Now continue to fetch the attached neighbor device basename
                match_cli_cdp_deviceid = re.search(pattern_AP_DEVICEID, line)
                if match_cli_cdp_deviceid:
                    this_ap_cdp_switch = match_cli_cdp_deviceid.group(1).split(".")[0]
                match_cli_cdp_interface = re.search(pattern_INTERFACE, line)
                if match_cli_cdp_interface:
                    this_ap_cdp_switch_port = match_cli_cdp_interface.group(2)
                    this_ap_cdp_switch_port_local = match_cli_cdp_interface.group(1)
            hit_ap = this_ap_name == online_ap['AP_NAME'] and this_ap_cdp_switch and this_ap_cdp_switch_port and this_ap_cdp_switch_port_local

            # create a new object for checking and potentially appending
            prep_online_ap = copy.deepcopy(online_ap)
            prep_online_ap['AP_CDP_SWITCH'] = this_ap_cdp_switch
            prep_online_ap['AP_CDP_SWITCH_PORT'] = this_ap_cdp_switch_port
            prep_online_ap['AP_CDP_SWITCH_PORT_LOCAL'] = this_ap_cdp_switch_port_local

            if hit_ap:
                if args.debug: send_ios_syslog(severity=l_DEBUG, message=f"CDP detected {prep_online_ap}")
                # see if we already added this AP per a CDP hit, if not then added with CDP neighbor not known
                match_ap = online_ap.matching_ap(criteria=['AP_NAME', 'AP_CDP_SWITCH_PORT_LOCAL'], ap_list=[prep_online_ap])
                if match_ap:
                    match_ap['AP_CDP_SWITCH'] = this_ap_cdp_switch
                    match_ap['AP_CDP_SWITCH_PORT'] = this_ap_cdp_switch_port
                    match_ap['AP_CDP_SWITCH_PORT_LOCAL'] = this_ap_cdp_switch_port_local
                elif not online_ap['AP_CDP_SWITCH_PORT_LOCAL']:
                    online_ap['AP_CDP_SWITCH'] = this_ap_cdp_switch
                    online_ap['AP_CDP_SWITCH_PORT'] = this_ap_cdp_switch_port
                    online_ap['AP_CDP_SWITCH_PORT_LOCAL'] = this_ap_cdp_switch_port_local
                else:
                    ONLINE_APs.append(prep_online_ap)
                # reset this_ap_name to look for the next hit
                this_ap_name = None

    def get_ap_serial(online_ap:AccessPoint=None):
        if online_ap is None: return
        online_ap.make_exist("AP_SERIAL")
        command = f"show ap name {online_ap['AP_NAME']} inventory"
        if args.debug: send_ios_syslog(severity=l_INFO, message=f"Fetching cli([{command}])")
        cli_ap_serial_detail = cli(command)
        command = ""
        for line in cli_ap_serial_detail.splitlines():
            f_regex = rf"^PID:.*SN:\s+(\S+)"
            pattern_AP_SERIAL = re.compile(f_regex)
            match_cli_ap_serial = re.search(pattern_AP_SERIAL, line)
            if match_cli_ap_serial:
                online_ap['AP_SERIAL'] = match_cli_ap_serial.group(1)
        if args.debug: send_ios_syslog(severity=l_DEBUG,
                                       message=f"SERIAL ONLINE {online_ap['AP_MODEL']} {online_ap['AP_NAME']} is {online_ap['AP_SERIAL']}")

    def get_tilt(online_ap=None):
        if online_ap is None: return
        online_ap.make_exist("AP_TILT")
        command = f"show ap name {online_ap['AP_NAME']} accelerometer"
        if args.debug: send_ios_syslog(severity=l_INFO, message=f"Fetching cli([{command}])")
        cli_ap_accel_detail = cli(command)
        command = ""
        for line in cli_ap_accel_detail.splitlines():
            f_regex = rf"^Tilt angle\s+:\s+(.*)"
            pattern_AP_TILT = re.compile(f_regex)
            match_cli_ap_tilt = re.search(pattern_AP_TILT, line)
            if match_cli_ap_tilt:
                online_ap['AP_TILT'] = match_cli_ap_tilt.group(1).strip()
        if args.accel: send_ios_syslog(severity=l_DEBUG,
                        message=f"TILT ONLINE {online_ap['AP_MODEL']} {online_ap['AP_NAME']} is {online_ap['AP_TILT']}")

    def get_speed_duplex(online_ap=None):
        if online_ap is None: return
        online_ap.make_exist(["AP_CDP_SWITCH", "AP_CDP_SWITCH_PORT", "AP_CDP_SWITCH_PORT_LOCAL", "AP_SPEED_DUPLEX"])

        # AP Name : WAP039-115
        # GigabitEthernet0    UP       5000 Mbps   Full    187466978     45023229      0

        # assume we have a longer summary, as this will work for short or long output then
        # as we are expecting some AP-s to be dual-enet, so need to find all matches
        f_regex = rf"^AP Name\s+:\s+(\S+)"
        pattern_AP_NAME = re.compile(f_regex)
        f_regex = rf"^(GigabitEthernet\d)\s+(\S+)\s+(\d+)\s+Mbps\s+(\S+)"
        pattern_INTERFACE = re.compile(f_regex)

        this_ap_name = None
        this_ap_cdp_switch_port = None
        this_ap_cdp_switch_port_local = None
        for line in cli_ap_ether_stats.splitlines():
            # find the line that matches this AP
            match_cli_cdp_ap = re.search(pattern_AP_NAME, line)
            if match_cli_cdp_ap:
                this_ap_name = match_cli_cdp_ap.group(1)
                this_ap_cdp_switch = None
                this_ap_cdp_switch_port = None
                this_ap_cdp_switch_port_local = None
            # now process this block, but only for the AP looking for
            if this_ap_name == online_ap['AP_NAME']:
                # Now continue to fetch the attached neighbor device basename
                match_cli_cdp_deviceid = re.search(pattern_AP_DEVICEID, line)
                if match_cli_cdp_deviceid:
                    this_ap_cdp_switch = match_cli_cdp_deviceid.group(1).split(".")[0]
                match_cli_cdp_interface = re.search(pattern_INTERFACE, line)
                if match_cli_cdp_interface:
                    this_ap_cdp_switch_port = match_cli_cdp_interface.group(2)
                    this_ap_cdp_switch_port_local = match_cli_cdp_interface.group(1)
            hit_ap = this_ap_name == online_ap[
                'AP_NAME'] and this_ap_cdp_switch and this_ap_cdp_switch_port and this_ap_cdp_switch_port_local

            # create a new object for checking and potentially appending
            prep_online_ap = copy.deepcopy(online_ap)
            prep_online_ap['AP_CDP_SWITCH'] = this_ap_cdp_switch
            prep_online_ap['AP_CDP_SWITCH_PORT'] = this_ap_cdp_switch_port
            prep_online_ap['AP_CDP_SWITCH_PORT_LOCAL'] = this_ap_cdp_switch_port_local

            if hit_ap:
                if args.debug: send_ios_syslog(severity=l_DEBUG, message=f"CDP detected {prep_online_ap}")
                # see if we already added this AP per a CDP hit, if not then added with CDP neighbor not known
                match_ap = online_ap.matching_ap(criteria=['AP_NAME', 'AP_CDP_SWITCH_PORT_LOCAL'],
                                                 ap_list=[prep_online_ap])
                if match_ap:
                    match_ap['AP_CDP_SWITCH'] = this_ap_cdp_switch
                    match_ap['AP_CDP_SWITCH_PORT'] = this_ap_cdp_switch_port
                    match_ap['AP_CDP_SWITCH_PORT_LOCAL'] = this_ap_cdp_switch_port_local
                elif not online_ap['AP_CDP_SWITCH_PORT_LOCAL']:
                    online_ap['AP_CDP_SWITCH'] = this_ap_cdp_switch
                    online_ap['AP_CDP_SWITCH_PORT'] = this_ap_cdp_switch_port
                    online_ap['AP_CDP_SWITCH_PORT_LOCAL'] = this_ap_cdp_switch_port_local
                else:
                    ONLINE_APs.append(prep_online_ap)
                # reset this_ap_name to look for the next hit
                this_ap_name = None

    def do_ap_rename(online_ap=None):
        if online_ap is None: return
        # First look for a full match of all the criteria that is present
        # only look for AP-s that need to be renamed, so match does not include AP_NAME itself
        criteria = ['AP_MODEL', 'AP_SERIAL', 'AP_MAC_ENET', 'AP_MAC_RADIO', 'AP_CDP_SWITCH', 'AP_CDP_SWITCH_PORT']
        if args.debug:send_ios_syslog(severity=l_DEBUG,
                                      message=f"MATCH_AP ONLINE {online_ap['AP_NAME']} in NEW_APs criteria {criteria} {online_ap}")
        match_ap = online_ap.matching_ap(criteria=criteria, ap_list=NEW_APs)

        do_rename_ap = None
        if match_ap:
            if args.debug: send_ios_syslog(severity=l_DEBUG, message=f"MATCH_AP Found NEW_AP {match_ap} as ONLINE {online_ap}")
            if match_ap['AP_NAME'] != online_ap['AP_NAME']:
                do_rename_ap = match_ap

        if do_rename_ap:
            send_ios_syslog(severity=l_INFO, message=f"RENAME_AP Renaming to name {do_rename_ap['AP_NAME']} for {online_ap}")
            command = f"enable ; "
            if args.Xchange: command = command + f"! Xchange crippled "
            command = command + f"ap name {online_ap['AP_NAME']} name {do_rename_ap['AP_NAME']} ; "
            send_ios_syslog(severity=l_INFO, message=f"RENAME_AP Sending cli([{command}])")
            cli(command) ; command = ""

    def do_dual_5ghz(online_ap=None):
        if online_ap is None: return
        online_ap.make_exist("AP_DUAL_5GHZ")
        # First look for a full match of all the criteria that is present
        # only look for AP-s HAVE BEEN named/renamed correctly.. so include AP_NAME
        criteria = ['AP_NAME', 'AP_MODEL', 'AP_SERIAL', 'AP_MAC_ENET', 'AP_MAC_RADIO', 'AP_CDP_SWITCH', 'AP_CDP_SWITCH_PORT']
        if args.debug: send_ios_syslog(severity=l_DEBUG,
                                      message=f"DUAL_5GHZ ONLINE {online_ap['AP_NAME']} {online_ap['AP_MODEL']} matching in NEW_APs criteria {criteria} {online_ap}")
        match_ap = online_ap.matching_ap(criteria=criteria, ap_list=NEW_APs)
        if match_ap:
            if args.debug: send_ios_syslog(severity=l_DEBUG,
                                           message=f"DUAL_5GHZ ONLINE {online_ap['AP_NAME']} {online_ap['AP_MODEL']} HIT as {match_ap['AP_NAME']} {match_ap['AP_MODEL']}")
            if match_ap['AP_MODEL'] in ['CW9178I', 'CW9176D1'] and match_ap['AP_DUAL_5GHZ'] == "Enabled":
                # Check based on AP_MODEL and if dual 5GHz is not enabled, enable it respectively
                if args.debug: send_ios_syslog(severity=l_DEBUG,
                                               message=f"DUAL_5GHZ ONLINE {online_ap['AP_NAME']} {match_ap['AP_MODEL']} checking status")
                if match_ap['AP_MODEL'] == "CW9178I":
                    # assume we have a longer summary, as this will work for short or long output then
                    # Check Slot 1 first
                    hit_ap = None
                    this_ap_name = None
                    this_ap_slot = None
                    this_ap_slot_dual_mode = None
                    this_ap_slot_admin = None
                    for line in cli_ap_config_slot.splitlines():
                        f_regex = rf"^Cisco AP Name\s+:\s+(\S+)"
                        pattern_AP_NAME = re.compile(f_regex)
                        f_regex = rf"^Attributes for Slot (1)"
                        pattern_AP_SLOT = re.compile(f_regex)
                        f_regex = rf"^\s+Dual Radio Mode\s+:\s+(.*)"
                        pattern_AP_SLOT_DUAL_ROLE = re.compile(f_regex)
                        f_regex = rf"^\s+Administrative State\s+:\s+(.*)"
                        pattern_AP_SLOT_ADMIN = re.compile(f_regex)
                        # find the line that matches this AP
                        match_cli_ap_name = re.search(pattern_AP_NAME, line)
                        match_cli_ap_slot = re.search(pattern_AP_SLOT, line)
                        match_cli_ap_slot_dual_role = re.search(pattern_AP_SLOT_DUAL_ROLE, line)
                        match_cli_ap_slot_admin = re.search(pattern_AP_SLOT_ADMIN, line)
                        if match_cli_ap_name:
                            this_ap_name = match_cli_ap_name.group(1)
                            this_ap_slot = None
                            this_ap_slot_dual_mode = None
                            this_ap_slot_admin = None
                        # now process this block, but only for the AP looking for
                        if this_ap_name == online_ap['AP_NAME'] and match_cli_ap_slot:
                            this_ap_slot = match_cli_ap_slot.group(1)
                            this_ap_slot_dual_mode = None
                            this_ap_slot_admin = None
                        if this_ap_name == online_ap['AP_NAME'] and match_cli_ap_slot_dual_role:
                            this_ap_slot_dual_mode = match_cli_ap_slot_dual_role.group(1).strip()
                            this_ap_slot_admin = None
                        if this_ap_name == online_ap['AP_NAME'] and match_cli_ap_slot_admin:
                            this_ap_slot_admin = match_cli_ap_slot_admin.group(1).strip()
                        # once we have the details, break out of the for loop
                        hit_ap = this_ap_name == online_ap['AP_NAME'] and this_ap_slot and this_ap_slot_dual_mode and this_ap_slot_admin
                        if hit_ap:
                            if args.debug: send_ios_syslog(severity=l_DEBUG,
                                                           message=f"DUAL_5GHZ ONLINE {online_ap['AP_NAME']} {online_ap['AP_MODEL']} Slot {this_ap_slot} HIT as mode {this_ap_slot_dual_mode} / admin {this_ap_slot_admin}")
                            # update online_ap
                            online_ap['AP_DUAL_5GHZ'] = f"Slot {this_ap_slot} mode {this_ap_slot_dual_mode}"
                            break


                    if hit_ap and this_ap_slot_dual_mode != "Enabled":
                        send_ios_syslog(severity=l_INFO,
                                        message=f"DUAL_5GHZ ONLINE {online_ap['AP_NAME']} {online_ap['AP_MODEL']} Slot {this_ap_slot} changing to dual_mode for mode {this_ap_slot_dual_mode} / admin {this_ap_slot_admin}")
                        command = f"enable ; "
                        if args.Xchange: command = command + f"! Xchange crippled "
                        command = f"ap name {online_ap['AP_NAME']} dot11 5ghz slot 2 shutdown ; "
                        send_ios_syslog(severity=l_INFO, message=f"DUAL_5GHZ sending {online_ap['AP_MODEL']} cli([{command}])")
                        cli(command) ; command = ""
                        if args.Xchange: command = command + f"! Xchange crippled "
                        command = f"ap name {online_ap['AP_NAME']} dot11 5ghz dual-radio mode enable ; "
                        send_ios_syslog(severity=l_INFO, message=f"DUAL_5GHZ sending {online_ap['AP_MODEL']} cli([{command}])")
                        cli(command) ; command = ""
                        if args.Xchange: command = command + f"! Xchange crippled "
                        command = f"ap name {online_ap['AP_NAME']} no dot11 5ghz slot 2 shutdown ; "
                        send_ios_syslog(severity=l_INFO, message=f"DUAL_5GHZ sending {online_ap['AP_MODEL']} cli([{command}])")
                        cli(command) ; command = ""

                    if hit_ap and this_ap_slot_admin != "Enabled":
                        send_ios_syslog(severity=l_INFO,
                                        message=f"DUAL_5GHZ ONLINE {online_ap['AP_NAME']} {online_ap['AP_MODEL']} Slot {this_ap_slot} changing to dual-5GHz to Admin Enable as dual_mode {this_ap_slot_dual_mode} / admin {this_ap_slot_admin}")
                        if args.Xchange: command = command + f"! Xchange crippled "
                        command = f"enable ; "
                        if args.Xchange: command = command + f"! Xchange crippled "
                        command = f"ap name {online_ap['AP_NAME']} no dot11 5ghz slot {this_ap_slot} shutdown ; "
                        send_ios_syslog(severity=l_INFO, message=f"DUAL_5GHZ sending {online_ap['AP_MODEL']} cli([{command}])")
                        cli(command) ; command = ""

                    # assume we have a longer summary, as this will work for short or long output then
                    # Now check Slot 2
                    hit_ap = None
                    this_ap_name = None
                    this_ap_slot = None
                    this_ap_slot_admin = None
                    for line in cli_ap_config_slot.splitlines():
                        f_regex = rf"^Cisco AP Name\s+:\s+(\S+)"
                        pattern_AP_NAME = re.compile(f_regex)
                        f_regex = rf"^Attributes for Slot (2)"
                        pattern_AP_SLOT = re.compile(f_regex)
                        f_regex = rf"^\s+Administrative State\s+:\s+(.*)"
                        pattern_AP_SLOT_ADMIN = re.compile(f_regex)
                        # find the line that matches this AP
                        match_cli_ap_name = re.search(pattern_AP_NAME, line)
                        match_cli_ap_slot = re.search(pattern_AP_SLOT, line)
                        match_cli_ap_slot_admin = re.search(pattern_AP_SLOT_ADMIN, line)
                        if match_cli_ap_name:
                            this_ap_name = match_cli_ap_name.group(1)
                            this_ap_slot = None
                            this_ap_slot_admin = None
                        # now process this block, but only for the AP looking for
                        if this_ap_name == online_ap['AP_NAME'] and match_cli_ap_slot:
                            this_ap_slot = match_cli_ap_slot.group(1)
                            this_ap_slot_admin = None
                        if this_ap_name == online_ap['AP_NAME'] and match_cli_ap_slot_admin:
                            this_ap_slot_admin = match_cli_ap_slot_admin.group(1).strip()
                        # once we have the details, break out of the for loop
                        hit_ap = this_ap_name == online_ap['AP_NAME'] and this_ap_slot and this_ap_slot_admin
                        if hit_ap:
                            if args.debug: send_ios_syslog(severity=l_DEBUG,
                                                           message=f"DUAL_5GHZ ONLINE {online_ap['AP_MODEL']} {online_ap['AP_NAME']} Slot {this_ap_slot} HIT admin {this_ap_slot_admin}")
                            # update online_ap
                            online_ap['AP_DUAL_5GHZ'] = f"{online_ap['AP_DUAL_5GHZ']} / Slot {this_ap_slot} admin {this_ap_slot_admin}"
                            break

                    if hit_ap and this_ap_slot_admin != "Enabled":
                        send_ios_syslog(severity=l_INFO,
                                        message=f"DUAL_5GHZ ONLINE {online_ap['AP_MODEL']} {online_ap['AP_NAME']} Slot {this_ap_slot} changing to dual-5GHz to Admin Enable as admin {this_ap_slot_admin}")
                        command = ""
                        if args.Xchange: command = command + f"! Xchange crippled "
                        command = command + f"enable ; "
                        if args.Xchange: command = command + f"! Xchange crippled "
                        command = command + f"ap name {online_ap['AP_NAME']} no dot11 5ghz slot {this_ap_slot} shutdown ; "
                        send_ios_syslog(severity=l_INFO, message=f"DUAL_5GHZ sending {online_ap['AP_MODEL']} cli([{command}])")
                        cli(command) ; command = ""

                elif match_ap['AP_MODEL'] == "CW9176D1":
                    # assume we have a longer summary, as this will work for short or long output then
                    hit_ap = None
                    this_ap_name = None
                    this_ap_slot = None
                    this_ap_slot_role = None
                    this_ap_slot_method = None
                    this_ap_slot_band = None
                    for line in cli_ap_config_slot.splitlines():
                        f_regex = rf"^Cisco AP Name\s+:\s+(\S+)"
                        pattern_AP_NAME = re.compile(f_regex)
                        f_regex = rf"^Attributes for Slot (0)"
                        pattern_AP_SLOT = re.compile(f_regex)
                        f_regex = rf"^\s+Radio Role\s+:\s+(.*)"
                        pattern_AP_SLOT_ROLE = re.compile(f_regex)
                        f_regex = rf"^\s+Assignment Method\s+:\s+(.*)"
                        pattern_AP_SLOT_METHOD = re.compile(f_regex)
                        f_regex = rf"^\s+Band\s+:\s+(\S+\s+GHz)"
                        pattern_AP_SLOT_BAND = re.compile(f_regex)
                        # find the line that matches this AP
                        match_cli_ap_name = re.search(pattern_AP_NAME, line)
                        match_cli_ap_slot = re.search(pattern_AP_SLOT, line)
                        match_cli_ap_slot_role = re.search(pattern_AP_SLOT_ROLE, line)
                        match_cli_ap_slot_method = re.search(pattern_AP_SLOT_METHOD, line)
                        match_cli_ap_slot_band = re.search(pattern_AP_SLOT_BAND, line)
                        if match_cli_ap_name:
                            this_ap_name = match_cli_ap_name.group(1)
                        # now process this block, but only for the AP looking for
                        if this_ap_name == online_ap['AP_NAME'] and match_cli_ap_slot:
                            this_ap_slot = match_cli_ap_slot.group(1)
                        if this_ap_name == online_ap['AP_NAME'] and match_cli_ap_slot_role:
                            this_ap_slot_role = match_cli_ap_slot_role.group(1).strip()
                        if this_ap_name == online_ap['AP_NAME'] and match_cli_ap_slot_method:
                            this_ap_slot_method = match_cli_ap_slot_method.group(1).strip()
                        if this_ap_name == online_ap['AP_NAME'] and match_cli_ap_slot_band:
                            this_ap_slot_band = match_cli_ap_slot_band.group(1).strip()
                        # once we have the details, break out of the for loop
                        hit_ap = this_ap_name == online_ap['AP_NAME'] and this_ap_slot and this_ap_slot_role and this_ap_slot_method and this_ap_slot_band
                        if hit_ap:
                            if args.debug: send_ios_syslog(severity=l_DEBUG,
                                                           message=f"DUAL_5GHZ ONLINE {online_ap['AP_NAME']} {online_ap['AP_MODEL']} Slot {this_ap_slot} has role {this_ap_slot_role} / method {this_ap_slot_method} / band {this_ap_slot_band}")
                            break

                    # update online_ap
                    online_ap['AP_DUAL_5GHZ'] = f"Slot {this_ap_slot} band {this_ap_slot_band}"

                    if hit_ap and this_ap_slot_band != "5 GHz":
                        send_ios_syslog(severity=l_INFO,
                                        message=f"DUAL_5GHZ ONLINE {online_ap['AP_NAME']} {online_ap['AP_MODEL']} Slot {this_ap_slot} changing to enable dual-5GHz for role {this_ap_slot_role} / method {this_ap_slot_method} / band {this_ap_slot_band}")
                        command = ""
                        if args.Xchange: command = command + f"! Xchange crippled "
                        command = command + f"enable ; "
                        if args.Xchange: command = command + f"! Xchange crippled "
                        command = command + f"ap name {online_ap['AP_NAME']} dot11 dual-band shutdown ; "
                        send_ios_syslog(severity=l_INFO, message=f"DUAL_5GHZ sending {online_ap['AP_MODEL']} cli([{command}])")
                        cli(command) ; command = ""
                        if args.Xchange: command = command + f"! Xchange crippled "
                        command = command + f"enable ; "
                        if args.Xchange: command = command + f"! Xchange crippled "
                        command = command + f"ap name {online_ap['AP_NAME']} dot11 dual-band radio role manual client-serving ; "
                        send_ios_syslog(severity=l_INFO, message=f"DUAL_5GHZ sending {online_ap['AP_MODEL']} cli([{command}])")
                        cli(command) ; command = ""
                        if args.Xchange: command = command + f"! Xchange crippled "
                        command = command + f"enable ; "
                        if args.Xchange: command = command + f"! Xchange crippled "
                        command = command + f"ap name {online_ap['AP_NAME']} dot11 dual-band band 5ghz ; "
                        send_ios_syslog(severity=l_INFO, message=f"DUAL_5GHZ sending {online_ap['AP_MODEL']} cli([{command}])")
                        cli(command) ; command = ""
                        if args.Xchange: command = command + f"! Xchange crippled "
                        command = command + f"enable ; "
                        if args.Xchange: command = command + f"! Xchange crippled "
                        command = command + f"ap name {online_ap['AP_NAME']} no dot11 dual-band shutdown ; "
                        send_ios_syslog(severity=l_INFO, message=f"DUAL_5GHZ sending {online_ap['AP_MODEL']} cli([{command}])")
                        cli(command) ; command = ""

    def process_ap(online_ap):
        get_ap_cdp(online_ap)
        get_ap_serial(online_ap)
        get_tilt(online_ap)
        # get_speed_duplex(online_ap)
        do_ap_rename(online_ap)
        do_dual_5ghz(online_ap)

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
