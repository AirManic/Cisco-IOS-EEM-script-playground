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
example file contents:
 ap-c9130-VRF , KWC233303FP, 04eb.409e.2cd0, 04:eb:40-9f-cc-e0
 ap-c9120-VRF , c828.e56e.7740,c828.e5a4.c740, FJC27061YW1


!
conf t
!
no event manager applet eem_AP_Rename
   event manager applet eem_AP_Rename
 event timer cron cron-entry "*/15 * * * *" maxrun 60
 action 0.0 syslog msg "Started"
 action 1.0 cli command "enable"
 action 2.1 cli command "copy tftp://192.168.201.210/eem/eem_AP_Rename.csv bootflash:/guest-share/" pattern "]"
 action 2.2 cli command "" pattern "[confirm]"
 action 2.3 cli command "y"
 action 2.5 cli command "copy tftp://192.168.201.210/eem/eem_AP_Rename.py bootflash:/guest-share/" pattern "]"
 action 2.6 cli command "" pattern "[confirm]"
 action 2.7 cli command "y"
 action 3.0 cli command "guestshell run python3 /flash/guest-share/eem_AP_Rename.py"
 action 9.0 syslog msg "Finished"
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

import re
import csv
import string
from cli import cli
import eem
import time

my_name = "eem_AP_Rename.py"

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
ap_new_dct = {}

# Open the CSV file for the desired AP mapping
with open('/flash/guest-share/eem_AP_Rename.csv') as csvfile:
    # Using DictReader to read CSV with specified fieldnames
    ap_csv_dct = csv.DictReader(csvfile, fieldnames=['ap_name'], restkey='ap_details', restval=[])

    for row in ap_csv_dct:
        # Extract the AP name and details
        ap_name = row['ap_name'].strip()
        ap_details = row.get('ap_details', [])

        # Build the reverse lookup dictionary
        for aspect in ap_details:
            aspect = aspect.upper().strip()
            # see if this looks like a MAC address.. if yes, then distill down to only upper case hex digits
            if all(c in '0123456789abcdefABCDEF.:-\s' for c in aspect):
                aspect = re.sub('[^0-9a-fA-F]','',aspect)
            ap_new_dct[aspect.strip()] = ap_name.strip()

# Retrieve the AP list from the WLC
ap_summary = cli("show ap summary")
ap_list = re.findall(r'(^\S+)\s+\d\s+(\S+)\s+(\S+)\s+(\S+)', ap_summary, re.MULTILINE)

ap_key_list = ap_new_dct.keys()

for ap_name, ap_model, ap_MACenet, ap_MACradio in ap_list:
    ap_new_name = None

    # Retrieve the AP serial number
    ap_inc_serial = cli(f"show ap name {ap_name} config general | inc AP Serial Number")
    ap_serial_match = re.search(r'^AP Serial Number\s+:\s+(\S+)', ap_inc_serial)

    if ap_serial_match:
        ap_serial = ap_serial_match.group(1)

        # Determine the new aspect and name
        for aspect in [ap_MACradio, ap_MACenet, ap_serial]:
            # if this looks like a MAC address.. distill down to only upper case hex digits
            if all(c in '0123456789abcdefABCDEF.:-\s' for c in aspect):
                aspect = re.sub(r'[^0-9a-fA-F]', '', aspect).upper()

            if aspect in ap_key_list and ap_name != ap_new_dct[aspect]:
                ap_new_name = ap_new_dct[aspect]

    # Rename the AP if a new name is determined
    if ap_new_name:
        my_syslog.write(f"{s_NOTICE}Renaming {ap_name} to {ap_new_name} based on {aspect} check\n")
        time.sleep(1.001)
        cli(f"ap name {ap_name} name {ap_new_name}")

my_syslog.close()
time.sleep(1.001)  # Allow syslog to output before returning to the EEM applet