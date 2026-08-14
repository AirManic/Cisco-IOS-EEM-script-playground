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

my_name = os.path.basename(sys.argv[0])

# determine if running under IOS-XE guestshell
is_guestshell = os.uname().nodename == 'guestshell'

DEFAULT_INFILE = str(PurePath(my_name).parents) + PurePath(my_name).stem + '.csv'

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
    SIM_FILE_EEM_AP_ENET = f"./experimental/exp_eem_AP_ethernet_stats.txt"
    SIM_FILE_EEM_AP_CONF = f"./exp_eem_AP_config_general.txt"
    SIM_FILE_EEM_AP_CDP_DETAIL = f"./experimental/exp_eem_AP_CDP_neighbors_detail.txt.txt"
    SIM_FILE_EEM_AP_CDP = f"./experimental/exp_eem_AP_CDP_neighbors.txt"

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

def send_ios_syslog(message, severity=l_INFO):
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
            log_string = f"{my_name} {line}"
            if is_guestshell:
                # Construct the standard Cisco log prefix
                log_string = f"{magic}{my_name} {line}"
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
    cli_ap_cdp = None

    if is_guestshell:
        # Retrieve the AP list from the WLC
        if args.name != None and args.name != "None":
            command = f"show ap summary | inc {args.name}"
            send_ios_syslog(severity=l_INFO, message=f"Looking for {command}" )
            cli_ap_summary = cli(command)
            if args.debug: send_ios_syslog(severity=l_DEBUG,message=f"{cli_ap_summary}")
            time.sleep(210.001)  # Allow time for AP CDP to roll in.. take about 3 1/2 mins
            command = f"show ap cdp neighbor | inc {args.name}"
            send_ios_syslog(severity=l_INFO, message=f"Looking for {command}" )
            cli_ap_cdp = cli(command)
            if args.debug: send_ios_syslog(severity=l_DEBUG,message=f"{cli_ap_cdp}")
        else:
            command = f"show ap summary"
            send_ios_syslog(severity=l_INFO, message=f"Looking for {command}" )
            cli_ap_summary = cli(command)
            if args.debug: send_ios_syslog(severity=l_DEBUG,message=f"{cli_ap_summary}")
            command = f"show ap cdp neighbor"
            send_ios_syslog(severity=l_INFO, message=f"Looking for {command}" )
            cli_ap_cdp = cli(command)
            if args.debug: send_ios_syslog(severity=l_DEBUG,message=f"{cli_ap_cdp}")
    else:
        with open(SIM_FILE_EEM_AP_SUMM) as file:
            cli_ap_summary = file.read()
        with open(SIM_FILE_EEM_AP_CDP) as file:
            cli_ap_cdp = file.read()

    ONLINE_APs = []

    for line in cli_ap_summary.splitlines():

        online_ap = AccessPoint()
        # look for Ether to be in the line to filter off other misc lines
        match_cli_ap_summ = re.search(r'^(\S+)\s+(\S+)\s+(\S+)\s+.*(Registered)', line)

        if match_cli_ap_summ:
            online_ap['AP_NAME'] = match_cli_ap_summ.group(1)
            online_ap['AP_MODEL'] = match_cli_ap_summ.group(3)

            for cdp_line in cli_ap_cdp.splitlines():
                # look for Ether to be in the line to filter off other misc lines
                f_regex = f"^({online_ap['AP_NAME']})\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+Ether\S+)"
                pattern = re.compile(f_regex)
                match_cli_cdp = re.search(pattern, cdp_line)
                if match_cli_cdp:
                    online_ap['AP_CDP_SWITCH'] = match_cli_cdp.group(3).split(".")[0]
                    online_ap['AP_CDP_SWITCH_PORT'] = match_cli_cdp.group(5)
                    if args.debug: send_ios_syslog(severity=l_DEBUG, message=f"CDP Neighbor detected {online_ap}")
            ONLINE_APs.append(online_ap)

    sorted_ONLINE_APs = sorted(ONLINE_APs, key=lambda x: x['AP_NAME'])

    if args.debug:
        send_ios_syslog(severity=l_DEBUG, message=f"{len(ONLINE_APs)} online APs in ONLINE_APs")
        for ap in sorted_ONLINE_APs:
            send_ios_syslog(severity=l_DEBUG, message=f"ONLINE_APs has {ap}")

    for online_ap in sorted_ONLINE_APs:

        # First look for a full match of all the criteria that is present
        criteria = ['AP_MODEL', 'AP_SERIAL', 'AP_MAC_ENET', 'AP_MAC_RADIO', 'AP_CDP_SWITCH', 'AP_CDP_SWITCH_PORT']
        if args.debug:
            search_ap = "{"
            for item in criteria:
                if item in online_ap and online_ap[item]:
                    search_ap = search_ap + f"'{item}: {online_ap[item]}', "
            if args.debug:
                send_ios_syslog(severity=l_DEBUG,
                                message=f"MATCH_AP Looking match of ONLINE {online_ap['AP_NAME']} in the NEW_APs list criteria {search_ap}")
        match_ap = online_ap.matching_ap(criteria=criteria, ap_list=NEW_APs)

        do_rename_ap = False
        if match_ap:
            if args.debug: send_ios_syslog(severity=l_DEBUG, message=f"MATCH_AP Found match NEW_AP {match_ap} as ONLINE {online_ap}")
            if match_ap['AP_NAME'] != online_ap['AP_NAME']:
                do_rename_ap = match_ap

        # TODO cripppled for now
        match_ap = False
        if match_ap:
            if match_ap['AP_DUAL_5GHZ'] == "Enabled":
                # Check based on AP_MODEL and if dual 5GHz is not enabled, enable it respectively
                if match_ap['AP_MODEL'] == "CW9178I":
                    pass
                if match_ap['AP_MODEL'] == "CW9176D1":
                    pass

        if do_rename_ap:
            send_ios_syslog(severity=l_INFO, message=f"RENAME_AP Change name {do_rename_ap['AP_NAME']} for {online_ap}")
            command = f"enable ; ap name {online_ap['AP_NAME']} name {do_rename_ap['AP_NAME']}"
            if args.debug:
                # if debugging, don't actually make the change .. comment out command but send
                # TODO cripppled for now
                command = "! CRIPPLED " + command
                send_ios_syslog(severity=l_INFO, message=f"RENAME_AP Sending {command}")
            cli("enable ; " + command)

# for CW9176D1
# ap name AP dot11 dual-band shutdown
# ap name AP dot11 dual-band radio role manual client-serving
# ap name AP dot11 dual-band band 5ghz
# ap name AP no dot11 dual-band shutdown

# for CW9178I
# ap name AP dot11 5ghz dual-radio mode enable
# ap name AP no dot11 5ghz slot 2 shutdown

if __name__ == "__main__":
    send_ios_syslog(severity=l_INFO, message=f"Starting ...")
    main()
    send_ios_syslog(severity=l_INFO, message=f"Finished ...")
