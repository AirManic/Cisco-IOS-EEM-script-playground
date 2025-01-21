import eem

# appears to be buggy to use eem.action_syslog()
eem.action_syslog("SAMPLE SYSLOG MESSAGE")


# no event manager applet eem_SYSLOG
#    event manager applet eem_SYSLOG
#  event timer cron cron-entry "*/1 * * * *" maxrun 60
#  action 0.0 syslog msg "Started"
#  action 1.0 cli command "enable"
#  action 2.5 cli command "copy tftp://192.168.201.210/eem/eem_SYSLOG.py bootflash:/guest-share/" pattern "]"
#  action 2.6 cli command "" pattern "[confirm]"
#  action 2.7 cli command "y"
#  action 3.0 cli command "guestshell run python3 /flash/guest-share/eem_SYSLOG.py"
#  action 9.0 syslog msg "Finished"