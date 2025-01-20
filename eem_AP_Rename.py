import argparse
import re
from cli import cli
from datetime import datetime
import eem
import time
import sys

old_stdout = sys.stdout
sys.stdout = open('/flash/guest-share/eem_AP_Rename.log', 'a+')
current_dateTime = datetime.now()
sys.stdout.write('\n')
sys.stdout.write('#' * 50)
sys.stdout.write('\n')
sys.stdout.write(str(current_dateTime))
sys.stdout.write('\n')

ap_dct = {}

# Create the parser for extracting the expiry time
parser = argparse.ArgumentParser()
parser.add_argument('-d', '--days', type=int, required=False,
                    help='specify the days any AP below threshold would reboot')
args = parser.parse_args()

# get the AP list from the WLC
ap_summ = cli("show ap summary")
ap_list = re.findall('(^\S+)\s+(\d)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)', ap_summ, re.MULTILINE)

for ap_name,ap_slots,ap_model,ap_MACenet,apMACradio,ap_CC,ap_RD,ap_ip,ap_state in ap_list:
    ap_inc_serial = cli("sh ap name {} config general | inc AP Serial Number".format(ap_name))
    try:
        ap_serial = re.search('^(AP Serial Number\s+):\s+(\S+)', ap_inc_serial)
        ap_dct[ap_serial.group(2)] = ap_name
        sys.stdout.write('{} is serial {}\n'.format(ap_dct[ap_serial.group(2)],ap_serial.group(2)))
    except:
        sys.stdout.write('failed to process {}\n'.format(ap_name))

