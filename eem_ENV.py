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

!
conf t
!
no event manager applet eem_SYSLOG
   event manager applet eem_SYSLOG
 event timer cron cron-entry "*/1 * * * *" maxrun 60
 action 0.0 syslog msg "Started"
 action 2.5 cli command "copy tftp://192.168.201.210/eem/eem_SYSLOG.py bootflash:/guest-share/" pattern "]"
 action 2.6 cli command "" pattern "[confirm]"
 action 2.7 cli command "y"
 action 3.0 cli command "guestshell run python3 /flash/guest-share/eem_SYSLOG.py"
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

import eem
import time

c = eem.env_reqinfo()

print("EEM Environment Variables")
for k, v in c.iteritems():
    print ("KEY : " + k + str(" ---> ") + v)

print ("Built in Variables")
for i, j in a.iteritems():
    print ("KEY : " + i + str(" ---> ") + j)
