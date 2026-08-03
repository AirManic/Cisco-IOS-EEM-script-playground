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
 event tag CRON timer cron cron-entry "*/5 */4 * * *"
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

# determine if running under IOS-XE guestshell
is_guestshell = os.uname().nodename == 'guestshell'

if is_guestshell:
    from cli import cli, clip, configure, configurep, execute, executep
    from eem import action_syslog
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
    def action_syslog(message, level, facility):
        return ''

my_name = os.path.basename(sys.argv[0])
if is_guestshell:
    DEFAULT_INFILE = "/flash/guest-share/" + PurePath(my_name).stem + '.csv'
else:
    DEFAULT_INFILE = "./dev_" + PurePath(my_name).stem + '.csv'

l_DEBUG  = 7
l_INFO   = 6
l_NOTICE = 5
l_WARN   = 4
l_ERR    = 3
l_CRIT   = 2

if is_guestshell:
    # /dev/tty32 format for for syslogd magic number is a123b234 with version 1 then level
    s_DEBUG  = f"[a123b234,1,l_DEBUG]"
    s_INFO   = f"[a123b234,1,l_INFO]"
    s_NOTICE = f"[a123b234,1,l_NOTICE]"
    s_WARN   = f"[a123b234,1,l_WARN]"
    s_ERR    = f"[a123b234,1,l_ERR]"
    s_CRIT   = f"[a123b234,1,l_CRIT]"
else:
    # Use this for local testing
    s_DEBUG  = f"DEBUG"
    s_INFO   = f"INFO"
    s_NOTICE = f"NOTICE"
    s_WARN   = f"WARN"
    s_ERR    = f"ERR"
    s_CRIT   = f"CRIT"

def send_ios_syslog(message, facility=my_name, severity=l_INFO, mnemonic=None):
    if  mnemonic is None:
        if severity == l_DEBUG: mnemonic = s_DEBUG
        if severity == l_INFO: mnemonic = s_INFO
        if severity == l_NOTICE: mnemonic = s_NOTICE
        if severity == l_WARN: mnemonic = s_WARN
        if severity == l_ERR: mnemonic = s_ERR
        if severity == l_CRIT: mnemonic = s_CRIT
    # Construct the standard Cisco log prefix
    log_string = f"%{facility}-{severity}-{mnemonic}: {message}"
    if is_guestshell:
        # TODO still working to figure out how to write to IOS-XE logging/syslog
        try:
            # Open the specific IOx serial pipe
            # TODO does not seem to work
            with open("/dev/ttyS3", "w") as syslog_pipe:
                syslog_pipe.write(log_string)
            # TODO Let's try this approach
            action_syslog(message, severity, facility)
            # TODO this only logs in the native bash shell running manually
            print(log_string)
        except FileNotFoundError:
            print(f"Error: /dev/ttyS3 not found. Ensure this is executed inside Guestshell.")
    else:
        print(f"{log_string}")

csv_fields = ['AP_NAME', 'AP_MODEL', 'AP_SERIAL', 'AP_MAC_ENET', 'AP_MAC_RADIO', 'AP_LOCATION', 'AP_CDP_SWITCH', 'AP_CDP_SWITCH_PORT']  # Define fields to strip
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


class StrippedDict:
    def __init__(self, data):
        self.data = data

    def __getitem__(self, key):
        value = self.data[key]
        # Automatically strip if the value is a text string
        if isinstance(value, str):
            return value.strip()
        return value

def main():

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
    with open(f"{args.infile_csv}") as csvfile:
        for ap in csv.DictReader(csvfile, delimiter=',', quotechar='"', restkey='details', restval=None):
            NEW_APs.append(AccessPoint(ap))

    if args.debug:
        send_ios_syslog(severity=l_DEBUG, message=f"{len(NEW_APs)} APs from infile_csv {args.infile_csv}")
        for ap in NEW_APs:
            send_ios_syslog(severity=l_DEBUG, message=f"NEW_APs has {ap['AP_NAME']} {ap}")

    cli_ap_summary = None
    cli_ap_cdp = None
    if is_guestshell:
        # Retrieve the AP list from the WLC
        if args.name != "None":
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
        with open(f"./dev_AP_summary.txt") as file:
            cli_ap_summary = file.read()
        with open(f"./dev_AP_CDP.txt") as file:
            cli_ap_cdp = file.read()
    time.sleep(1.001)  # Allow syslog to output before returning to the EEM applet

    ONLINE_APs = []

    for line in cli_ap_summary.splitlines():

        online_ap = AccessPoint()
        # look for Ether to be in the line to filter off other misc lines
        match_cli_ap_summ = re.search(r'^(\S+)\s+(\S+)\s+(\S+)\s+.*(Registered)', line)

        if match_cli_ap_summ:
            online_ap['AP_NAME'] = match_cli_ap_summ.group(1)
            online_ap['AP_MODEL'] = match_cli_ap_summ.group(3)

            for line in cli_ap_cdp.splitlines():
                # look for Ether to be in the line to filter off other misc lines
                f_regex = f"^({online_ap['AP_NAME']})\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+Ether\S+)"
                pattern = re.compile(f_regex)
                match_cli_cdp = re.search(pattern, line)
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


    do_rename_ap = False

    for online_ap in sorted_ONLINE_APs:

        match_ap = next((ap for ap in NEW_APs
                         if (
                             # at least on of these criteria exist, then step across them
                                ap['AP_MODEL']
                             or ap['AP_SERIAL']
                             or ap['AP_CDP_SWITCH']
                             or ap['AP_CDP_SWITCH_PORT']
                            )
                         and (
                             # if this not our criteria, move on.. or check it
                                 (ap['AP_MODEL'] is None)
                              or (ap['AP_MODEL'] and ap['AP_MODEL'] in online_ap['AP_MODEL'])
                             )
                        and (
                             # if this not our criteria, move on.. or check it
                                 (ap['AP_SERIAL'] is None)
                              or (ap['AP_SERIAL'] and ap['AP_SERIAL'] in online_ap['AP_SERIAL'])
                             )
                         and (
                             # if this not our criteria, move on.. or check it
                                 (ap['AP_CDP_SWITCH'] is None)
                              or (ap['AP_CDP_SWITCH'] and ap['AP_CDP_SWITCH'] in online_ap['AP_CDP_SWITCH'])
                             )
                         and (
                             # if this not our criteria, move on.. or check it
                                 (ap['AP_CDP_SWITCH_PORT'] is None)
                              or (ap['AP_CDP_SWITCH_PORT'] and ap['AP_CDP_SWITCH_PORT'] == online_ap['AP_CDP_SWITCH_PORT'])
                             )
                         ), None)
        if match_ap:
            if args.debug: send_ios_syslog(severity=l_DEBUG, message=f"Found match NEW_AP {match_ap} as ONLINE {online_ap}")
            if match_ap['AP_NAME'] != online_ap['AP_NAME']:
                do_rename_ap = True

        if do_rename_ap:
            send_ios_syslog(severity=l_INFO, message=f"Changing to new name {match_ap['AP_NAME']} for {online_ap}")
            command = f"enable ; ap name {online_ap['AP_NAME']} name {match_ap['AP_NAME']}"
            if args.debug: send_ios_syslog(severity=l_INFO, message=f"Sending {command}")
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
