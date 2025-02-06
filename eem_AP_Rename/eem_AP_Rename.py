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
  -c CSV_INFILE, --csv_infile CSV_INFILE
                        specify csv infile, defaults to eem_AP_Rename.csv
  -l, --location        treat 2nd csv field as location data for AP, defaults
                        to false
  -n NAME, --name NAME  check AP name for this specific MAC address


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
 event tag CRON timer cron cron-entry "*/20 * * * *"
 event tag NONE none maxrun 1800
 event tag SYS syslog pattern "CAPWAPAC_SMGR_TRACE_MESSAGE-5-AP_JOIN_DISJOIN.*AP Name:\s+([^\s]+)\s+.*Joined"
 trigger
  correlate event NONE or event CRON or event SYS
 action 000.000   syslog msg "Started event was $_event_type_string"
 action 000.000.1 cli command "enable"
 action 200.000   if $_event_type_string eq "syslog"
 action 200.040.1  set find_ap_name "TBD"
 action 200.040.2  regexp "CAPWAPAC_SMGR_TRACE_MESSAGE-5-AP_JOIN_DISJOIN.*AP Name:\s+([^\s]+)\s+.*Joined" "$_syslog_msg" match find_ap_name
 action 200.070.1  cli command "guestshell run python3 /flash/guest-share/eem_AP_Rename.py -l -c custom.csv -n $find_ap_name"
 action 200.070.8  syslog msg "Finished"
 action 200.070.9  exit
 action 200.090   end
 action 300.020.1 cli command "copy tftp://192.168.201.210/eem/eem_AP_Rename.csv bootflash:/guest-share/custom.csv" pattern "]"
 action 300.020.2 cli command "" pattern "[confirm]"
 action 300.020.3 cli command "y"
 action 300.020.5 cli command "copy tftp://192.168.201.210/eem/eem_AP_Rename.py bootflash:/guest-share/" pattern "]"
 action 300.020.6 cli command "" pattern "[confirm]"
 action 300.020.7 cli command "y"
 action 300.070.1 cli command "guestshell run python3 /flash/guest-share/eem_AP_Rename.py -l -c custom.csv"
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
from cli import cli
import eem
import time

my_name = os.path.basename(sys.argv[0])
DEFAULT_INFILE = Path(my_name).stem + '.csv'

#Create the parser for extracting the expiry time
parser = argparse.ArgumentParser()
parser.add_argument('-c', '--csv_infile',type=str, required=False,
                    default=f"{DEFAULT_INFILE}",
                    help=f"specify csv infile, defaults to {DEFAULT_INFILE}")
parser.add_argument('-l', '--location', required=False, action='store_true',
                    help=f"treat 2nd csv field as location data for AP, defaults to false")
parser.add_argument('-n', '--name', required=False,
                    help=f"check AP name for this specific MAC address")
args = parser.parse_args()

# eem.action_syslog() appears to be not supported in 9800 IOS-XE
# eem.action_syslog("SAMPLE SYSLOG MESSAGE")

# doing open on IOXMAN /dev/ttyS2 must be 'w' else os.open WRONLY
# looks time.sleep(1.001) delay must be met between my_syslog.write() calls
# TODO given that writing to /dev/ttyS2 will drop frames if writing faster than 2-3 messages per sec,
#   need to be careful to my_syslog.write() only when minimally required.
my_syslog = open('/dev/ttyS2', 'w')
# for syslogd magic number is a123b234 with version 1
s_DEBUG  = f"[a123b234,1,7]{my_name} "
s_INFO   = f"[a123b234,1,6]{my_name} "
s_NOTICE = f"[a123b234,1,5]{my_name} "
s_WARN   = f"[a123b234,1,4]{my_name} "
s_ERR    = f"[a123b234,1,3]{my_name} "
s_CRIT   = f"[a123b234,1,2]{my_name} "

# Initialize the reverse lookup dictionary
ap_csv_dct = {}
ap_csv_location_dct = {}
ap_infile_csv_fieldnames = ['ap_csv_name']
if args.location: ap_infile_csv_fieldnames.append('ap_csv_location')

# Open the CSV file for the desired AP mapping
with open(f"/flash/guest-share/{args.csv_infile}") as csvfile:
    # Using DictReader to read CSV with specified fieldnames
    infile_csv_dct = csv.DictReader(csvfile, fieldnames=ap_infile_csv_fieldnames, restkey='ap_csv_details', restval=[])

    for row in infile_csv_dct:
        # Extract the AP name and details
        ap_csv_name = row['ap_csv_name'].strip()

        if args.location:
            ap_csv_location = row.get('ap_csv_location')
            ap_csv_location_dct[ap_csv_name] = ap_csv_location.strip()

        ap_csv_details = row.get('ap_csv_details', [])
        # Build the reverse lookup dictionary
        for csv_aspect in ap_csv_details:
            csv_aspect = csv_aspect.upper().strip()
            # see if this looks like a MAC address.. if yes, then distill down to only upper case hex digits
            if all(c in '0123456789abcdefABCDEF.:-\s' for c in csv_aspect):
                csv_aspect = re.sub('[^0-9a-fA-F]','',csv_aspect)
            ap_csv_dct[csv_aspect.strip()] = ap_csv_name.strip()

# Retrieve the AP list from the WLC
if args.name:
    my_syslog.write(f"{s_NOTICE}Looking for {args.name}\n")
    ap_summary = cli(f"show ap summary | inc {args.name}")
    time.sleep(1.001)
else:
    ap_summary = cli(f"show ap summary")

ap_list = re.findall(r'(^\S+)\s+\d\s+(\S+)\s+(\S+)\s+(\S+)\s+.*Registered\s+(.*)', ap_summary, re.MULTILINE)

# Create list of aspect from the csv file to match against
ap_csv_aspect_list = ap_csv_dct.keys()

# Step across the AP-s online
for ap_cur_name, ap_cur_model, ap_cur_MACenet, ap_cur_MACradio, ap_cur_location in ap_list:

    # Retrieve the AP serial number
    ap_cur_serial = None
    ap_cur_inc_serial = cli(f"show ap name {ap_cur_name} config general | inc AP Serial Number")
    ap_cur_serial_match = re.search(r'^AP Serial Number\s+:\s+(\S+)', ap_cur_inc_serial)
    if ap_cur_serial_match: ap_cur_serial = ap_cur_serial_match.group(1)

    # little extra sanity.. as it is neede at least for ap_cur_location
    ap_cur_name = ap_cur_name.strip()
    ap_cur_model = ap_cur_model.strip()
    ap_cur_MACenet = ap_cur_MACenet.strip()
    ap_cur_MACradio = ap_cur_MACradio.strip()
    ap_cur_location = ap_cur_location.strip()
    ap_cur_serial = ap_cur_serial.strip()

    ap_new_aspect = None
    ap_new_name = None
    ap_new_location = None

    # Determine is there is an csv AP that matches one of the ap_cur_aspect items
    for ap_cur_aspect in [ap_cur_MACradio, ap_cur_MACenet, ap_cur_serial]:
        # if this looks like a MAC address.. distill down to only upper case hex digits
        if all(c in '0123456789abcdefABCDEF.:-\s' for c in ap_cur_aspect):
            ap_cur_aspect = re.sub(r'[^0-9a-fA-F]', '', ap_cur_aspect).upper()

        # Determine is this ap_cur_name matches one of the aspect items
        if ap_cur_aspect in ap_csv_aspect_list:
            # Based on this aspect match, check the ap name
            ap_new_aspect = ap_cur_aspect
            if ap_cur_name != ap_csv_dct[ap_new_aspect]:
                ap_new_name = ap_csv_dct[ap_new_aspect]
            # Based on this aspect match, check the location information
            if args.location and ap_cur_location != ap_csv_location_dct[ap_csv_dct[ap_new_aspect]].strip('"'):
                ap_new_location = ap_csv_location_dct[ap_csv_dct[ap_new_aspect]].strip('"')
                if " " in ap_new_location: ap_new_location = f'"{ap_new_location}"'

    # Change location if determined ap_new_location detected
    if ap_new_aspect and ap_new_location:
        my_syslog.write(f"{s_NOTICE}Changing {ap_cur_name} match {ap_new_aspect} to location {ap_new_location}\n")
        time.sleep(1.001)
        cli(f"ap name {ap_cur_name} location {ap_new_location}")

    # Always Rename the AP last .. if a new name is detected
    if ap_new_aspect and ap_new_name:
        my_syslog.write(f"{s_NOTICE}Renaming {ap_cur_name} match {ap_new_aspect} to {ap_new_name}\n")
        cli(f"ap name {ap_cur_name} name {ap_new_name}")
        time.sleep(10)
        # TODO workaround for AP Priming not fully triggering on name change
        cli(f"ap tag-sources revalidate")
        # TODO workaround for MWAR changes to AP not being updated at WLC, 10 sec is about what 9120 needs
        # TODO workaround for CSCwk77862 as well
        time.sleep(10)
        cli(f"ap name {ap_new_name} reset capwap")


my_syslog.close()
time.sleep(1.001)  # Allow syslog to output before returning to the EEM applet