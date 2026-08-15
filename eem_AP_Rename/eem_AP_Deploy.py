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
 action 200.000.1 set find_ap_name "None"
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
from pathlib import PurePath
import sys
import re
import csv
import time
import copy
import random
import string

my_name = os.path.basename(sys.argv[0])

# determine if running under IOS-XE guestshell
is_guestshell = os.uname().nodename == 'guestshell'

DEFAULT_INFILE = str(PurePath(my_name).parents) + PurePath(my_name).stem + '.csv'
DEFAULT_INFILE = PurePath(my_name).stem + '.csv'

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
    DEFAULT_INFILE = "./experimental/exp_" + PurePath(my_name).stem + '.csv'
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

if is_guestshell:
    # /dev/ttyS2 format for for syslogd magic number is a123b234 with version 1 then level
    s_DEBUG  = f"[a123b234,1,{l_DEBUG}]"
    s_INFO   = f"[a123b234,1,{l_INFO}]"
    s_NOTICE = f"[a123b234,1,{l_NOTICE}]"
    s_WARN   = f"[a123b234,1,{l_WARN}]"
    s_ERR    = f"[a123b234,1,{l_ERR}]"
    s_CRIT   = f"[a123b234,1,{l_CRIT}]"
else:
    # Use this for local testing
    s_DEBUG  = f"DEBUG"
    s_INFO   = f"INFO"
    s_NOTICE = f"NOTICE"
    s_WARN   = f"WARN"
    s_ERR    = f"ERR"
    s_CRIT   = f"CRIT"

global run_string
run_string = ''.join(random.choices(string.digits, k=5))
def send_ios_syslog(message=None, severity=l_INFO):
    my_name = os.path.basename(sys.argv[0])
    magic = ""
    if severity == l_DEBUG:  magic = s_DEBUG
    if severity == l_INFO:   magic = s_INFO
    if severity == l_NOTICE: magic = s_NOTICE
    if severity == l_WARN:   magic = s_WARN
    if severity == l_ERR:    magic = s_ERR
    if severity == l_CRIT:   magic = s_CRIT

    # TODO still working to figure out how to write to IOS-XE logging/syslog
    try:
        for line in message.splitlines():
            log_string = f"{my_name} RunID {run_string} {line}"
            if is_guestshell:
                # Construct the standard Cisco log prefix
                log_string = f"{magic}{log_string}\n"
                # Open the specific IOx serial pipe
                with open("/dev/ttyS2", "w", encoding="utf-8") as syslog_pipe:
                    syslog_pipe.write(log_string)
                    syslog_pipe.flush()
                    time.sleep(1.001)  # IOS-XE syslogd will limit to one message a sec, drops faster
            else:
                print(f"{log_string}")
    except FileNotFoundError:
        print(f"Error: /dev/ttyS2 not found. Ensure this is executed inside Guestshell.")


csv_fields = ['AP_NAME', 'AP_MODEL', 'AP_SERIAL', 'AP_MAC_ENET', 'AP_MAC_RADIO',
              'AP_LOCATION', 'AP_CDP_SWITCH', 'AP_CDP_SWITCH_PORT',
              'AP_DUAL_5GHZ']  # Define fields to strip
class AccessPoint(dict):

    def __init__(self, *args, **kwargs):
        # Make sure these attributes exist
        for field in csv_fields: self[field] = None
        super().__init__(*args, **kwargs)
        for field in csv_fields:
            if isinstance(self[field],str): self[field] = self[field].strip()

    def __setitem__(self, key, value):
        new_value = value
        if isinstance(value,str): new_value = value.strip()
        super().__setitem__(key, new_value)

    def match_ap_criteria(self, criteria=None, ap=None):
        # self is expected to be a real AP, and ap is an AP that might/might not exist but has the key criteria
        # track if there is at least one criteria item called out that matches
        is_ap_criteria = False
        # seed the match with True, as it will go False if there is a criteria item that does not match
        match_ap = True
        for aspect in criteria:
            # make sure both devices being compared have valid aspect values, else will get error on fullmatch
            this_criteria_ap = ap[aspect] is not None and ap[aspect] != ''
            this_criteria_self = self[aspect] is not None and self[aspect] != ''
            # make note once have at least one criteria to match of value of ONLY the AP trying to match
            is_ap_criteria = is_ap_criteria or this_criteria_ap

            # both AP-s being compared must have valid criteria to check, else fullmatch will error
            if this_criteria_ap and this_criteria_self:
                # now check it for a match, where anything that does not match will make it go False
                match_ap = match_ap and ( (ap[aspect] is None or ap[aspect] == '')
                                          or ( ap[aspect] and re.fullmatch(rf"{ap[aspect]}", self[aspect]) ) )
            # if one of the AP records being checked has this criteria, but the other one does not.. then false the match
            if ( (not this_criteria_ap and this_criteria_self)
                or (this_criteria_ap and not this_criteria_self) ):
                match_ap = False

        # if had at least one item to match on.. and if all the items called out did match
        got_a_solid_match = is_ap_criteria and match_ap
        if got_a_solid_match:
            if args.debug:
                send_ios_syslog(severity=l_DEBUG,
                                message=f"match_ap_criteria() matching {self['AP_NAME']} matches {ap['AP_NAME']} based on criteria {criteria}")
                send_ios_syslog(severity=l_DEBUG,
                                message=f"match_ap_criteria() matching {self} matches {ap}")
        return got_a_solid_match

    def matching_ap(self, criteria=None, ap_list=None):
        # self is expected to be a real AP, and ap is an AP that might/might not exist but has the key criteria
        for aspect in criteria:
            if self[aspect] is None or self[aspect] == '':
                if args.debug:
                    send_ios_syslog(severity=l_DEBUG,
                                    message=f"matching_ap() missing {aspect} {self['AP_NAME']}")
        match_ap = next( (ap for ap in ap_list if
                         self.match_ap_criteria(criteria=criteria, ap=ap) ), None )
        return match_ap


def main():

    # make args global so we can use outside this scope
    global args

    # Create the parser for extracting the expiry time
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--infile_csv', type=str, required=False,
                        default=f"{DEFAULT_INFILE}",
                        help=f"specify infile csv, defaults to {DEFAULT_INFILE}")
    parser.add_argument('-j', '--junk', type=str, required=False)
    parser.add_argument('-n', '--name', type=str, required=False,
                        default=None,
                        help=f"check only this specific AP name")
    parser.add_argument('-d', '--debug', required=False, action='store_true',
                        help=f"print debug message")
    args = parser.parse_args()

    NEW_APs = []

    # Open the CSV file for the desired AP mapping
    with open(f"{args.infile_csv}",mode='r', encoding='utf-8') as csvfile:
        # Read and clean the first row (header) keys
        header_line = csvfile.readline()
        raw_headers = next(csv.reader([header_line]))
        cleaned_headers = [h.strip() for h in raw_headers]

        for ap in csv.DictReader(csvfile, fieldnames=cleaned_headers, delimiter=',', quotechar='"', restkey='details', restval=None):
            NEW_APs.append(AccessPoint(ap))

    if args.debug:
        send_ios_syslog(severity=l_DEBUG, message=f"{len(NEW_APs)} APs from infile_csv {args.infile_csv}")
        for ap in NEW_APs:
            send_ios_syslog(severity=l_DEBUG, message=f"NEW_APs has {ap['AP_NAME']} {ap}")

    cli_ap_summary = None
    cli_ap_cdp_detail = None
    cli_ap_ether_stats = None
    cli_ap_config_slot = None

    if is_guestshell:
        # Retrieve the AP list from the WLC
        if args.name is not None and args.name != "None":
            command = f"show ap summary | inc {args.name}"
            send_ios_syslog(severity=l_INFO, message=f"Looking for {command}" )
            cli_ap_summary = cli(command)
            time.sleep(210.001)  # Allow time for AP CDP to roll in.. take about 3 1/2 mins
            command = f"show ap name {args.name} cdp neighbor detail"
            send_ios_syslog(severity=l_INFO, message=f"Looking for {command}" )
            cli_ap_cdp_detail = cli(command)
            command = f"show ap name {args.name} ethernet statistics"
            send_ios_syslog(severity=l_INFO, message=f"Looking for {command}" )
            cli_ap_ether_stats = cli(command)
            # for a single AP, have to loop thru the potential slots
            cli_ap_config_slot = ""
            for i in range(0, 4):
                command = f"show ap name {args.name} config slot {i}"
                send_ios_syslog(severity=l_INFO, message=f"Looking for {command}" )
                cli_ap_config_slot = cli_ap_config_slot + cli(command)
        else:
            command = f"show ap summary"
            send_ios_syslog(severity=l_INFO, message=f"Looking for {command}" )
            cli_ap_summary = cli(command)
            command = f"show ap cdp neighbor detail"
            send_ios_syslog(severity=l_INFO, message=f"Looking for {command}" )
            cli_ap_cdp_detail = cli(command)
            command = f"show ap ethernet statistics"
            send_ios_syslog(severity=l_INFO, message=f"Looking for {command}" )
            cli_ap_ether_stats = cli(command)
            command = f"show ap config slot"
            send_ios_syslog(severity=l_INFO, message=f"Looking for {command}" )
            cli_ap_config_slot = cli(command)
    else:
        with open(SIM_FILE_EEM_AP_SUMM) as file:
            cli_ap_summary = file.read()
        with open(SIM_FILE_EEM_AP_CDP_DETAIL) as file:
            cli_ap_cdp_detail = file.read()
        with open(SIM_FILE_EEM_AP_ETHER_STATS) as file:
            cli_ap_ether_stats = file.read()
        with open(SIM_FILE_EEM_AP_CONFIG_SLOT) as file:
            cli_ap_config_slot = file.read()



    ONLINE_APs = []

    for line in cli_ap_summary.splitlines():

        online_ap = AccessPoint()
        # look for Ether to be in the line to filter off other misc lines
        match_cli_ap_summ = re.search(r'^(\S+)\s+(\S+)\s+(\S+)\s+.*(Registered)', line)

        if match_cli_ap_summ:
            online_ap['AP_NAME'] = match_cli_ap_summ.group(1)
            online_ap['AP_MODEL'] = match_cli_ap_summ.group(3)

            # assume we have a longer summary, as this will work for short or long output then
            # as we are expecting some AP-s to be dual-enet, so need to find all matches
            f_regex = rf"^AP Name\s+:\s+(\S+)"
            pattern_AP_NAME = re.compile(f_regex)
            f_regex = rf"^Device ID\s+:\s+(\S+)\."
            pattern_AP_DEVICEID = re.compile(f_regex)
            f_regex = rf"^Interface\s+:\s+(\S+),.*:\s+(\S+)"
            pattern_INTERFACE = re.compile(f_regex)

            this_ap_name = None
            for cdp_line in cli_ap_cdp_detail.splitlines():
                # find the line that matches this AP
                match_cli_cdp_ap = re.search(pattern_AP_NAME, cdp_line)
                if match_cli_cdp_ap:
                    this_ap_name = match_cli_cdp_ap.group(1)
                # now process this block, but only for the AP looking for
                if this_ap_name == online_ap['AP_NAME']:
                    # Now continue to fetch the attached neighbor device basename
                    match_cli_cdp_deviceid = re.search(pattern_AP_DEVICEID, cdp_line)
                    if match_cli_cdp_deviceid:
                        online_ap['AP_CDP_SWITCH'] = match_cli_cdp_deviceid.group(1).split(".")[0]
                    match_cli_cdp_interface = re.search(pattern_INTERFACE, cdp_line)
                    if match_cli_cdp_interface:
                        online_ap['AP_CDP_SWITCH_PORT'] = match_cli_cdp_interface.group(2)
                        online_ap['AP_CDP_SWITCH_PORT_LOCAL'] = match_cli_cdp_interface.group(1)

                        if args.debug: send_ios_syslog(severity=l_DEBUG, message=f"CDP Neighbor detected {online_ap}")
                        # create a new object for appending
                        append_online_ap = copy.deepcopy(online_ap)
                        ONLINE_APs.append(append_online_ap)

            # see if we already added this AP per a CDP hit, if not then added with CDP neighbor not known
            match_ap = online_ap.matching_ap(criteria=['AP_NAME'], ap_list=[ online_ap ])
            if not match_ap:
                ONLINE_APs.append(online_ap)

    sorted_ONLINE_APs = sorted(ONLINE_APs, key=lambda x: x['AP_NAME'])

    if args.debug:
        send_ios_syslog(severity=l_DEBUG, message=f"{len(ONLINE_APs)} online APs in ONLINE_APs")
        for ap in sorted_ONLINE_APs:
            send_ios_syslog(severity=l_DEBUG, message=f"ONLINE_APs has {ap}")

    for online_ap in sorted_ONLINE_APs:
        # in this loop, will only look for AP-s that need to be renamed, so match does not include AP_NAME itself
        # First look for a full match of all the criteria that is present
        criteria = ['AP_MODEL', 'AP_SERIAL', 'AP_MAC_ENET', 'AP_MAC_RADIO', 'AP_CDP_SWITCH', 'AP_CDP_SWITCH_PORT']
        if args.debug:send_ios_syslog(severity=l_DEBUG,
                                      message=f"MATCH_AP Looking match of ONLINE {online_ap['AP_NAME']} in the NEW_APs list criteria {criteria} {online_ap}")
        match_ap = online_ap.matching_ap(criteria=criteria, ap_list=NEW_APs)

        do_rename_ap = None
        if match_ap:
            if args.debug: send_ios_syslog(severity=l_DEBUG, message=f"MATCH_AP Found match NEW_AP {match_ap} as ONLINE {online_ap}")
            if match_ap['AP_NAME'] != online_ap['AP_NAME']:
                do_rename_ap = match_ap

        if do_rename_ap:
            send_ios_syslog(severity=l_INFO, message=f"RENAME_AP Renaming to name {do_rename_ap['AP_NAME']} for {online_ap}")
            command = f"enable ; ap name {online_ap['AP_NAME']} name {do_rename_ap['AP_NAME']}"
            # TODO cripppled for now
            command = "! CRIPPLED " + command
            send_ios_syslog(severity=l_INFO, message=f"RENAME_AP Sending cli([{command}])")
            cli("enable ; " + command)

    for online_ap in sorted_ONLINE_APs:
        # in this loop, will only look for AP-s HAVE BEEN named/renamed correctly.. so include AP_NAME
        # First look for a full match of all the criteria that is present
        criteria = ['AP_NAME', 'AP_MODEL', 'AP_SERIAL', 'AP_MAC_ENET', 'AP_MAC_RADIO', 'AP_CDP_SWITCH', 'AP_CDP_SWITCH_PORT']
        if args.debug: send_ios_syslog(severity=l_DEBUG,
                                       message=f"DUAL_5GHZ Looking match of ONLINE {online_ap['AP_NAME']} in the NEW_APs list criteria {criteria} {online_ap}")
        match_ap = online_ap.matching_ap(criteria=criteria, ap_list=NEW_APs)
        if match_ap:
            if match_ap['AP_MODEL'] in ['CW9178I', 'CW9176D1'] and match_ap['AP_DUAL_5GHZ'] == "Enable":
                # Check based on AP_MODEL and if dual 5GHz is not enabled, enable it respectively
                if args.debug: send_ios_syslog(severity=l_DEBUG,
                                               message=f"DUAL_5GHZ Checking dual-5GHz of ONLINE {online_ap['AP_NAME']} as AP_MODEL {match_ap['AP_MODEL']}")
                if match_ap['AP_MODEL'] == "CW9178I":

                    # Attributes for Slot 1
                    #   Dual Radio Mode                               : Disabled
                    #
                    # Attributes for Slot 1
                    #   Dual Radio Mode                               : Enabled
                    #

                    # assume we have a longer summary, as this will work for short or long output then
                    hit_ap = None
                    this_ap_name = None
                    this_ap_slot = None
                    this_ap_slot_dual_mode = None
                    for slot_line in cli_ap_config_slot.splitlines():
                        f_regex = rf"^Cisco AP Name\s+:\s+(\S+)"
                        pattern_AP_NAME = re.compile(f_regex)
                        f_regex = rf"^Attributes for Slot (1)"
                        pattern_AP_SLOT = re.compile(f_regex)
                        f_regex = rf"^\s+Dual Radio Mode\s+:\s+(.*)"
                        pattern_AP_SLOT_DUAL_ROLE = re.compile(f_regex)

                        # find the line that matches this AP
                        match_cli_ap_name = re.search(pattern_AP_NAME, slot_line)
                        match_cli_ap_slot = re.search(pattern_AP_SLOT, slot_line)
                        match_cli_ap_slot_dual_role = re.search(pattern_AP_SLOT_DUAL_ROLE, slot_line)
                        if match_cli_ap_name:
                            this_ap_name = match_cli_ap_name.group(1)
                        # now process this block, but only for the AP looking for
                        if this_ap_name == online_ap['AP_NAME'] and match_cli_ap_slot:
                            this_ap_slot = match_cli_ap_slot.group(1)
                        if this_ap_name == online_ap['AP_NAME'] and match_cli_ap_slot_dual_role:
                            this_ap_slot_dual_mode = match_cli_ap_slot_dual_role.group(1).strip()

                        # once we have the details, break out of the for loop
                        hit_ap = this_ap_name == online_ap['AP_NAME'] and this_ap_slot and this_ap_slot_dual_mode
                        if hit_ap:
                            if args.debug: send_ios_syslog(severity=l_DEBUG,
                                                           message=f"DUAL_5GHZ Found dual-5GHz of ONLINE {online_ap['AP_NAME']} as {this_ap_slot} / {this_ap_slot_dual_mode}")
                            break
                    if hit_ap and this_ap_slot_dual_mode != "Enabled":
                        send_ios_syslog(severity=l_INFO,
                                        message=f"DUAL_5GHZ Changing to dual-5GHz of ONLINE {online_ap['AP_NAME']} as {this_ap_slot} / {this_ap_slot_role} / {this_ap_slot_method} / {this_ap_slot_band}")
                        command = " ! CRIPPLED ;"
                        command = command + f" ! ap name {online_ap['AP_NAME']} dot11 5ghz slot 2 shutdown ;"
                        command = command + f" ! ap name {online_ap['AP_NAME']} dot11 5ghz dual-radio mode enable ;"
                        command = command + f" ! ap name {online_ap['AP_NAME']} no dot11 5ghz slot 2 shutdown ;"

                        # for CW9178I
                        # ap name AP dot11 5ghz dual-radio mode enable
                        # ap name AP no dot11 5ghz slot 2 shutdown
                        send_ios_syslog(severity=l_INFO, message=f"DUAL_5GHZ Sending cli([{command}])")
                        cli("enable ; " + command)
                elif match_ap['AP_MODEL'] == "CW9176D1":
                    # assume we have a longer summary, as this will work for short or long output then
                    hit_ap = None
                    this_ap_name = None
                    this_ap_slot = None
                    this_ap_slot_role = None
                    this_ap_slot_method = None
                    this_ap_slot_band = None
                    for slot_line in cli_ap_config_slot.splitlines():
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
                        match_cli_ap_name = re.search(pattern_AP_NAME, slot_line)
                        match_cli_ap_slot = re.search(pattern_AP_SLOT, slot_line)
                        match_cli_ap_slot_role = re.search(pattern_AP_SLOT_ROLE, slot_line)
                        match_cli_ap_slot_method = re.search(pattern_AP_SLOT_METHOD, slot_line)
                        match_cli_ap_slot_band = re.search(pattern_AP_SLOT_BAND, slot_line)
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
                                                           message=f"DUAL_5GHZ Found dual-5GHz of ONLINE {online_ap['AP_NAME']} as {this_ap_slot} / {this_ap_slot_role} / {this_ap_slot_method} / {this_ap_slot_band}")
                            break
                    if hit_ap and this_ap_slot_band != "5 GHz":
                        send_ios_syslog(severity=l_INFO,
                                        message=f"DUAL_5GHZ Changing to dual-5GHz of ONLINE {online_ap['AP_NAME']} as {this_ap_slot} / {this_ap_slot_role} / {this_ap_slot_method} / {this_ap_slot_band}")
                        command = " ! CRIPPLED ;"
                        command = command + f" ! ap name {online_ap['AP_NAME']} dot11 dual-band shutdown ;"
                        command = command + f" ! ap name {online_ap['AP_NAME']} dot11 dual-band radio role manual client-serving ;"
                        command = command + f" ! ap name {online_ap['AP_NAME']} dot11 dual-band band 5ghz ;"
                        command = command + f" ! ap name {online_ap['AP_NAME']} no dot11 dual-band shutdown"
                        send_ios_syslog(severity=l_INFO, message=f"DUAL_5GHZ Sending cli([{command}])")
                        cli("enable ; " + command)

if __name__ == "__main__":
    send_ios_syslog(severity=l_INFO, message=f"Starting ... {sys.argv}")
    main()
    send_ios_syslog(severity=l_INFO, message=f"Finished ... {sys.argv}")
