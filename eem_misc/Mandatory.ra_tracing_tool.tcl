# ##############################################################################
# System policy EEM script to automate RA Tracing commands in wireless platforms
# ##############################################################################
# Copyright (c) 2018-2020, 2022 by Cisco Systems, Inc.
# Author  :  Sandeep Gudla, 18 Oct 2018
# Script  :  ra_tracing_tool.tcl
# Version :  v1.3
# ##############################################################################
# v1.0:
#       CLI: [no] debug wireless mac/ip <mac/ip> [monitor-time <time>]
#                                                [ftp-server   <ip> <path>]
#                                                [internal]
# v1.1: Making either one of ftp-server or file-location optional
#       CLI: [no] debug wireless mac/ip <mac/ip> ftp-server <ip> <path>
#                                                [monitor-time <time>]
#                                                [internal]
#            [no] debug wireless mac/ip <mac/ip> to-file <FS:>
#                                                [monitor-time <time>]
#                                                [internal]
# v1.2: Any of below CLIs can be used to stop RA tracing
#           'no debug wireless mac/ip ...' or
#           'undebug wireless mac/ip ...'
# v1.3: Adding log level to the optional parameter
#       CLI: [no] debug wireless mac/ip <mac/ip> ...
#                                [ftp-server <ip> <path> (or) to-file <FS:>]
#                                [monitor-time <time>]
#                                [level <log-level]
#                                [internal]
# ##############################################################################
# Script Usage:
# ### A. CLI event detector (Manual debug CLI trigger for the script)
# ###    Use below exec CLI to start/stop RA tracing on a MAC/IP condition
# ###        CLI: [no] debug wireless mac/ip <mac/ip> ...
# ### B. None event detector (Manual event manager CLI trigger for the script)
# ###    Use below exec CLI to start RA tracing on a MAC/IP condition
# ###     'event manager run Mandatory.ra_tracing_tool.tcl start MAC/IP <> ...'
# ###     'event manager run Mandatory.ra_tracing_tool.tcl stop MAC/IP <> ... '
# ##############################################################################
# Script Agreement:
# ### When condition enable trigger is invoked on given MAC/IP,
# ###      Enable conditional RA tracing on this condition
# ###      Activate tracing (for this condition) upto 'monitor-time'
# ###        or upto Default max time (30min)
# ### Log file name generation:
# ###      'to-file' expected format <dir>:<file-name>
# ###      If 'to-file' not specified or in invalid format,
# ###        Then choose default file path as 'flash:/'
# ###      If <file-name> is not mentioned then generate unique file name:
# ###        'ra_trace_@condition@_@clock_time@.log'
# ### When timer expires or manual stop trigger is invoked,
# ###      Decode RA logs for this condition
# ###        TAC logs by default or all internal logs if 'internal' is specified
# ###      If 'ftp-server' IP is specified,
# ###        Move log file to '<ftp-ip>:/<ftp-path>/' and remove from internal
# ###          storage after confirming FTP copy is successful.
# ###        FTP credentials are expected to be configured before hand as below:
# ###          (config)# ip ftp username <username>
# ###          (config)# ip ftp password <encryption-level> <password>
# ##############################################################################

# ##### Declare Event Triggers here #####
::cisco::eem::event_register_cli tag ev_ra_trace occurs 1 pattern "(no )?debug wireless. *" sync yes maxrun 18000
::cisco::eem::event_register_none tag ev_none
::cisco::eem::trigger {
    ::cisco::eem::correlate event ev_ra_trace or event ev_none
}

# ##### Include namespaces here #####
namespace import ::cisco::eem::*
namespace import ::cisco::lib::*


# ##### Global variables #####

# Set debug flag based on env var, default set to FALSE
set DEBUG_FLAG         0
set DEFAULT_MAX_TIME   1800
set SCRIPT_NAME        "Mandatory.ra_tracing_tool.tcl"
set DEFAULT_DIR        "flash"

# ##### PROCEDURES #####

# ### Always print errors to syslog
proc p_error {str} {
    action_syslog msg "ERROR: $str\n"
}

# ### Put info logs to syslog when info flag is set
proc p_info {str} {
    action_syslog msg "$str\n"
}

# ### Put debug logs to syslog when debug flag is set
proc debug {str} {
    global DEBUG_FLAG
    if {$DEBUG_FLAG == 1} {
        action_syslog msg "$str\n"
    }
}

# ### Directly dump log on the console (this is not syslog message)
proc dump {str} {
    puts "$str"
}

# ### Helper proc to print TCL array
proc print_array {in_arr arr_name} {
    upvar $in_arr arr
    debug "'$arr_name' content:"
    foreach {key value} [array get arr] {
        debug "$key ==> $value"
    }
}

# ### Start new CLI session and move to enable mode
proc cli_session_start {} {
    debug "Opening CLI TTY line"

    if [catch {cli_open} result] {
        p_error "Unable to open a CLI session, Result: $result"
        exit 1
    }
    array set cli_sess $result

    debug "CLI session created - entering enabled mode"

    if [catch {cli_exec $cli_sess(fd) "enable"} result] {
        p_error "Unable to enter enabled mode, Result: $result"
        cli_close $cli_sess(fd) $cli_sess(tty_id)
        exit 1
    }

    return [array get cli_sess]
}

# ### Close CLI session of the given TTY line
proc cli_session_close {sess} {
    upvar $sess cli_sess
    if {![info exists cli_sess(fd)]} {
        p_error "Invalid CLI session input, ignoring close attempt"
        return
    }

    if [catch {cli_close $cli_sess(fd) $cli_sess(tty_id)} result] {
        p_error "Unable to close CLI session"
        exit 1
    }

    debug "CLI session closed OK"
    array set cli_sess {}

    return [array get cli_sess]
}

# ### Parse-proc for debug CLI event trigger,
# ### CLI Syntax: 
# ###     [no] debug wireless mac/IP <mac/ip> [ftp-server <ip> <path>]
# ###                                         [monitor-time <time>]
# ###                                         [internal]
# ###                                         <CR>
proc parse_cli_evd_inputs {ev_info} {
    upvar $ev_info arr_einfo

    set args(trigger)    ""
    set args(cndtn)      ""
    set args(cndtn_val)  ""
    set args(ftp_ip)     ""
    set args(ftp_path)   ""
    set args(time)       0
    set args(internal)   0
    set args(to_file)    ""
    set args(log_level)  ""
    set args(rc)         -1

    debug "Parsing CLI event inputs"

    # Get input CLI entered on console
    if {![info exists arr_einfo(msg)]} {
        p_error "User input CLI is not available in event info"
        exit 1
    }
    set     cmd $arr_einfo(msg)
    debug   "Parsing input command: '$cmd'"

    # Check if we are interested in this CLI, Parse the trigger (start/stop)
    if {[string first "no debug wireless " $cmd] != -1 ||
        [string first "undebug wireless " $cmd] != -1} {
        set args(trigger) "stop"
    } elseif {[string first "debug wireless " $cmd] != -1} {
        set args(trigger) "start"
    } else {
        # NOT interested in this CLI
        debug "Input command: $cmd, neither start nor stop request"
        set args(rc) 0
        return [array get args]
    }

    set mac_index [string first "debug wireless mac "  $cmd]
    set ip_index  [string first "debug wireless ip " $cmd]
    if {$mac_index == -1 && $ip_index == -1} {
        # NOT interested in this CLI
        debug "RA Tracing condition is not set in input command: $cmd"
        set args(rc) 0
        return [array get args]
    }

    # Now extract string containing user inputs from given command
    # inputs: condition: MAC/IP, condition value: <mac/ip> (mandatory)
    #         FTP-server IP and destination path (or) to-file path,
    #         Max monitor time and internal log collect flag

    if {$mac_index != -1} {
        set parse_start [expr $mac_index + [string length "debug wireless "]]
    } else {
        set parse_start [expr $ip_index + [string length "debug wireless "]]
    }
    set strr  [string range $cmd $parse_start end]
    # Split by space
    set listt [regexp -inline -all -- {\S+} $strr]
    set listt_len [llength $listt]

    # Parse & Copy user inputs
    for {set i 0} {$i < $listt_len} {incr i} {
        set pattern [lindex $listt $i]
        switch $pattern {
            "mac" {
                set args(cndtn)     "MAC"
                incr i
                set cndtn_val [lindex $listt $i]
                set args(cndtn_val) [string tolower $cndtn_val]
            }
            "ip" {
                set args(cndtn)     "IP"
                incr i
                set args(cndtn_val) [lindex $listt $i]
            }
            "ftp-server" {
                incr i
                set args(ftp_ip)    [lindex $listt $i]
                incr i
                set args(ftp_path)  [lindex $listt $i]
            }
            "monitor-time" {
                incr i
                set args(time)      [lindex $listt $i]
            }
            "internal" {
                set args(internal) 1
            }
            "to-file" {
                incr i
                set args(to_file)   [lindex $listt $i]
            }
            "level" {
               incr i
               set args(log_level)  [lindex $listt $i]
            }
        }
    }
    
    set args(rc) 0
    return [array get args]
}

# ### Parse-proc for EEM none event trigger
# ### Expected none event: 
# ###     event manager run <> start/stop MAC/IP <> [ftp-server <ftp-ip> <path>]
# ###                                               [monitor-time <time>]
# ###                                               [internal]
# ###                                               <CR>
proc parse_none_evd_inputs {ev_info} {
    upvar $ev_info arr_einfo

    set args(trigger)    ""
    set args(cndtn)      ""
    set args(cndtn_val)  ""
    set args(ftp_ip)     ""
    set args(ftp_path)   ""
    set args(time)       0
    set args(internal)   0
    set args(to_file)    ""
    set args(log_level)  ""
    set args(start_time) 0
    set args(rc)         -1

    debug "Parsing none event arguments"

    if {![info exists arr_einfo(argc)]} {
        p_error "argc argument doesn't exist in none event info"
        return [array get args]
    }
    set argc $arr_einfo(argc)
    debug "Argument count: $argc"

    # Mandatory args: trigger, condition, condition-value
    if {$argc < 3} {
        p_error "Invalid arguments in none event info"
        return [array get args]
    }

    if {$arr_einfo(arg1) == "start"} {
        set args(trigger) "start"
    } elseif {$arr_einfo(arg1) == "stop"} {
        set args(trigger) "stop"
    } else {
        p_error "Invalid trigger argument: '$arr_einfo(arg1)' in none event info"
        return [array get args]
    }

    if {$arr_einfo(arg2) == "MAC"} {
        set args(cndtn) "MAC"
    } elseif {$arr_einfo(arg2) == "IP"} {
        set args(cndtn) "IP"
    } else {
        p_error "Invalid RA tracing condition: '$arr_einfo(arg2)' in none event info"
        return [array get args]
    }
    set args(cndtn_val) [string tolower $arr_einfo(arg3)]

    if {$argc == 3} {
        # No optional arguments given
        set args(rc) 0
        return [array get args]
    }

    # Extract other optional arugments given
    print_array arr_einfo "arr_einfo"
    set listt {}
    for {set i 4} {$i <= $argc} {incr i} {
        set arg $arr_einfo(arg$i)
        switch $arg {
            "ftp-server" {
                incr i
                if {![info exists arr_einfo(arg$i)]} {
                    p_error "FTP server IP is not valid in arguments"
                    return [array get args]
                }
                set args(ftp_ip) $arr_einfo(arg$i)
                incr i
                if {![info exists arr_einfo(arg$i)]} {
                    p_error "FTP Path is not valid in arguments"
                    return [array get args]
                }
                set args(ftp_path) $arr_einfo(arg$i)
            }
            "monitor-time" {
                incr i
                if {![info exists arr_einfo(arg$i)]} {
                    p_error "Monitor time is not valid in arguments"
                    return [array get args]
                }
                set args(time) $arr_einfo(arg$i)
            }
            "internal" {
                set args(internal) 1
            }
            "to-file" {
                incr i
                if {![info exists arr_einfo(arg$i)]} {
                    p_error "to-file option is not valid in arguments"
                    return [array get args]
                }
                set args(to_file) $arr_einfo(arg$i)
            }
            "level" {
                incr i
                if {![info exists arr_einfo(arg$i)]} {
                    p_error "Log level option is not valid in arguments"
                    return [array get args]
                }
                set args(log_level), $arr_einfo(arg$i)
            }
            "start-time" {
                incr i
                if {![info exists arr_einfo(arg$i)]} {
                    p_error "start-time option is not valid in arguments"
                    return [array get args]
                }
                set args(start_time) $arr_einfo(arg$i)
            }
        }
    }

    set args(rc) 0
    return [array get args]
}

# ### Execute commands (non-interactive) present in the given list
proc execute_command_list {sess cmds} {
    upvar $sess cli_sess
    upvar $cmds cmd_list

    set ret(rc)     0
    set ret(rbuf)   ""

    foreach cmd $cmd_list {
        if {[catch {cli_exec $cli_sess(fd) $cmd} result]} {
            append ret(rbuf) "Command: '$cmd', Result:\n$result\n"
            set ret(rc) -1
            return [array get ret]
        } elseif {[string first "Invalid input detected" $result] != -1 ||
                  [string first "Incomplete command" $result] != -1} {
            append ret(rbuf) "Command: '$cmd' is invalid. Result:\n$result\n"
            set ret(rc) -1
            return [array get ret]
        }
        append ret(rbuf) "Command: '$cmd', Result:\n$result\n"
    }

    return [array get ret]
}

# ### Generate unique applet name per RA trace condition
proc generate_timer_applet_name {in_args} {
    upvar $in_args args
    set output(rc)    -1
    set output(name)  ""

    if {![info exists args(cndtn)] || ![info exists args(cndtn_val)]} {
        p_error "get-timer-applet-name: Invalid arguments"
        return [array get output]
    }

    set output(name) "timer_ra-tracing_$args(cndtn)_$args(cndtn_val)"
    set output(rc)   0

    return [array get output]
}

# ### Schdule RA trace stop event from given input conditions
# ###   Creates EEM applet sets a countdown timer of $args(time),
# ###   When timer expires, applet posts below none - EEM event
# ###     event manager stop MAC/IP <mac/ip> [ftp-server <ip> <path>]
# ###                                            [internal]
proc set_ra_trace_stop_timer_applet {cli in_args applet_name} {
    global SCRIPT_NAME
    upvar $cli      cli_sess
    upvar $in_args  args

    # Schedule time should be more than zero seconds
    if {$args(time) <= 0} {
        p_error "time:$args(time)sec is invalid"
        return -1
    }

    debug "Setting countdown timer for RA trace stop condition, time: $args(time) sec"

    set     cmd_list {}
    lappend cmd_list "configure terminal"
    lappend cmd_list "event manager applet $applet_name"
    lappend cmd_list "event timer countdown time $args(time)"
    lappend cmd_list "action 1.0 cli command \"enable\""

    set    msg "RA Tracing countdown timer expired/stopped, "
    append msg "Condition: $args(cndtn), Value: $args(cndtn_val)"

    lappend cmd_list "action 2.0 syslog priority informational msg \"$msg\""
    lappend cmd_list "action 3.0 cli command \"configure terminal\""
    lappend cmd_list "action 4.0 cli command \"no event manager applet $applet_name\""
    lappend cmd_list "action 5.0 cli command \"end\""

    set    run_ev "event manager run $SCRIPT_NAME stop"
    append run_ev " $args(cndtn) $args(cndtn_val)"
    if {$args(ftp_ip) != ""} {
        append run_ev " ftp-server $args(ftp_ip) $args(ftp_path)"
    }
    if {$args(internal) == 1} {
        append run_ev " internal"
    }
    if {$args(to_file) != ""} {
        append run_ev " to-file $args(to_file)"
    }
    if {$args(log_level) != ""} {
        append run_ev " level $args(log_level)"        
    } else {
        append run_ev " level debug"
    }
    append run_ev " start-time $args(start_time)"

    lappend cmd_list "action 6.0 cli command \"$run_ev\""
    lappend cmd_list "end"

    array set ret [execute_command_list cli_sess cmd_list]
    if {$ret(rc) != 0} {
        p_error "Failed to set countdown timer for condition: $args(cndtn) $args(cndtn_val)"
        p_error "Output:\n$ret(rbuf)"
        return $ret(rc)
    }
    debug "\n$ret(rbuf)\n"

    return 0
}

# ### Reschedule given applet countdown timer with new value
# ###   Throw error if applet is not present in running-config
proc reset_ra_trace_stop_timer_applet_time {cli applet_name time} {
    upvar $cli cli_sess

    set applet_cfg "event manager applet $applet_name"
    set cmd "show running-config | section $applet_cfg"
    if {[catch {cli_exec $cli_sess(fd) $cmd} result]} {
        p_error "Failed to execute '$cmd', result:\n$result\n"
        return -1
    }
    debug "Command: '$cmd', Result:\n$result\n"

    # Split output by CR, Last line is always device hostname trim it
    set split_list [lrange [split $result "\n\r"] 0 end-1]
    set applet_found 0
    foreach linee $split_list {
        if {[string first $applet_cfg $linee] != -1} {
            set applet_found 1
            break
        }
    }
    if {$applet_found != 1} {
        p_error "'$applet_cfg' not found in running-config"
        return -1
    }

    set cmd_list ""
    lappend cmd_list "configure terminal"
    lappend cmd_list "$applet_cfg"
    lappend cmd_list "event timer countdown time $time"
    lappend cmd_list "end"
    array set ret [execute_command_list cli_sess cmd_list]
    if {$ret(rc) != 0} {
        p_error "Failed to set countdown timer for condition: $strr"
        p_error "Output:\n$ret(rbuf)\n"
        return -1
    }
    debug "\n$ret(rbuf)\n"

    return 0
}

# ### Enable RA tracing on given input condition
proc set_cndtn_and_start_ra_trace {cli in_args} {
    upvar $cli      cli_sess
    upvar $in_args  args

    # Generate applet name from input arguments
    array set applet [generate_timer_applet_name args]
    if {$applet(rc) != 0} {
        p_error "start-ra-tracing: Failed to generate timer applet name"
        return $applet(rc)
    }

    set cndtn_str "$args(cndtn) $args(cndtn_val)"
    set     cmd_list {}
    lappend cmd_list "debug platform condition feature wireless $cndtn_str"
    lappend cmd_list "debug platform condition start"

    array set ret [execute_command_list cli_sess cmd_list]
    if {$ret(rc) != 0} {
        p_error "Failed to start RA tracing for condition: $cndtn_str"
        p_error "Output:\n$ret(rbuf)"
        return $ret(rc)
    } else {
        debug "\n$ret(rbuf)\n"
    }

    # RA trace shouldn't run forever, schedule stop event
    set rett [set_ra_trace_stop_timer_applet cli_sess args $applet(name)]
    if {$rett != 0} {
        p_error "Failed to schedule RA trace stop for condition: $$cndtn_str"
        return $rett
    }

    return $ret(rc)
}

# ### Parses 'show platform conditions' output and return
# ###   a. global ra tracing condition state
# ###   b. Total number of features enabled
# ###   c. Total number of conditions enabled
# ###   d. Total number of ewlc conditions enabled
# ###   e. Status of target condition (whether already set or not)
proc parse_sh_pl_cndtns_check_cndtn {cli cndtn} {
    upvar $cli cli_sess

    set output(gbl_cndtn_state)      ""
    set output(ewlc_feature_cndtn)   "Disabled"
    set output(ewlc_cndtn_count)     0
    set output(total_cndtn_count)    0
    set output(total_feature_count)  0
    set output(target_cndtn_set)     0
    set output(rc)                   -1

    set cmd "show platform conditions"
    if {[catch {cli_exec $cli_sess(fd) $cmd} result]} {
        p_error "Failed to execute command: '$cmd', Result:\n$result"
        return [array get output]
    }

    # Split output by CR, Last line is always device hostname trim it
    set split_list [lrange [split $result "\n\r"] 0 end-1]
    set line_cnt   [llength $split_list]
    set ewlc_cndtn_cnt     0
    set total_cndtn_cnt    0
    set total_feature_cnt  0

    for {set i 0} {$i < $line_cnt} {incr i} {
        set linee [lindex $split_list $i]
        if {[string length $linee] <= 0} {
            continue
        }
        debug $linee
        set strr "Conditional Debug Global State: "
        set index [string first $strr $linee]
        if {$index != -1} {
            incr  index [string length $strr]
            set   state [string range $linee $index end]
            set   state [string trimright $state " \n\r"]
            set   output(gbl_cndtn_state) $state
            debug "Conditional Debug Global State: $state"
            continue
        }

        set index [string first "Feature Condition" $linee]
        if {$index != -1} {
            debug "Feature Condition found"
            # Count conditions
            for {incr i} {$i < $line_cnt} {incr i} {
                set linee [lindex $split_list $i]
                if {[string length $linee] <= 0 ||
                    [string first "-------" $linee] != -1} {
                    continue
                }
                debug $linee
                if {[string first "Submode" $linee] != -1 &&
                    [string first "Level" $linee] != -1} {
                    debug "Found submodes, exiting conditions count"
                    break
                }
                incr total_cndtn_cnt
                debug "new feature condition"
                if {[string first "ewlc" $linee] != -1} {
                    incr ewlc_cndtn_cnt
                    debug "ewlc feature condition"
                    set newline [string tolower $linee]
                    set tcndtn  [string tolower $cndtn]
                    if {[string first $tcndtn $newline] != -1} {
                        debug "Target condtion: $cndtn found"
                        set output(target_cndtn_set) 1
                    }
                    continue
                }
            }
        }

        if {[string first "Submode" $linee] == -1 ||
            [string first "Level" $linee] == -1} {
                continue
        }
        debug "Submode found"

        for {incr i} {$i < $line_cnt} {incr i} {
            set linee [lindex $split_list $i]
            if {[string length $linee] <= 0 ||
                [string first "-------" $linee] != -1} {
                continue
            }
            debug $linee
            if {[string first "ewlc" $linee] != -1} {
                set output(ewlc_feature_cndtn) "Enabled"
                debug "ewlc feature enabled"
            }
            incr total_feature_cnt
            debug "new feature added"
        } 
    }

    set output(ewlc_cndtn_count)  $ewlc_cndtn_cnt
    set output(total_cndtn_count) $total_cndtn_cnt
    set output(total_feature_count) $total_feature_cnt
    set output(rc) 0

    return [array get output]
}

# ### Generate unique file name based on input condition and system clock
#       if 'to-file' option is not specified or not valid.
#     Expected format: '<dir>:<name>'
proc generate_ra_trace_file_name {cli in_args} {
    upvar $cli cli_sess
    upvar $in_args args
    global DEFAULT_DIR

    set file(path) ""
    set file(name) ""
    set file(rc)   -1

    # Check if 'to-file' option is already specified
    if {$args(to_file) != "" } {
        # Split 'to-file' based on ':' char
        if {[string first ":" $args(to_file)] != -1} {
            set split_list [split $args(to_file) ":"]
            set split_len  [llength $split_list]
            # Set first entry as file-path
            set file(path) [lindex $split_list 0]
            # For valid file name, there should be atleast two entries
            set idx [expr [string length $file(path)] + 1]
            if {$split_len >= 2 && [string length $args(to_file)] > $idx} {
                # set string portion after '<path>:' as file-name
                set file(name) [string range $args(to_file) $idx end]
                set file(rc) 0
                return [array get file]
            } else {
                debug "Only file system dir: '$file(path)' mentioned in to-file"
            }
        } else {
            p_error "Given file-name: '$args(to_file)' is invalid"
        }
    } else {
        debug "to-file option not set"
    }

    if {$file(path) == ""} {
        debug "setting default file system location: '$DEFAULT_DIR'"
        set file(path) $DEFAULT_DIR
    }

    # Get timestamp for generating unique file name
    set clk [clock format [clock seconds] -format "%H%M%S_UTC_%a_%b_%d_%Y" -gmt 1]

    set file(name) "ra_trace_$args(cndtn)_$args(cndtn_val)_$clk.log"
    set file(rc)   0

    return [array get file]
}

proc set_file_prompt_config {cli file_prompt} {
    upvar $cli cli_sess

    debug "Setting 'file prompt' level to '$file_prompt'"

    set cmd_list {"configure terminal"}
    if {$file_prompt != ""} {
        lappend cmd_list "file prompt $file_prompt"
    } else {
        lappend cmd_list "no file prompt"
    }
    lappend cmd_list "end"
    array set ret [execute_command_list cli_sess cmd_list]
    if {$ret(rc) != 0} {
        p_error "Error while preparing FTP copy, Output:\n$ret(rbuf)"
        return -1
    } else {
        debug "\n$ret(rbuf)\n"
    }

    return 0
}

# ### copy_file_to_ftp
# ### 1. Ping ftp_ip, if it is NOT reachable return error
# ### 2. a. Cache the present configuration of 'file prompt'
# ###    b. Set 'file prompt quiet' option to reduce interactive CLIs
# ### 3. Copy file to FTP location
# ###    a. Read file size
# ###    b. Copy file to destination at FTP-server
# ###    c. Verify number of bytes copied matches with file size and echo result
# ### 4. If file copy is successful then remove file from internal storage
# ### 5. Revert 'file prompt' config changes and return
proc copy_file_to_ftp {cli in_path in_file ftp_ip ftp_path} {
    upvar $cli cli_sess

    set in_path   [string trim  $in_path "/"]
    set ftp_path  [string trim  $ftp_path "/"]

    # Check if FTP IP is reachable
    if {![regexp "!!!!" [cli_exec $cli_sess(fd) "ping $ftp_ip"]]} {
        p_error "PING unsuccessful to $ftp_ip"
        return -1
    }

    # Cache 'file prompt' config
    set cmd "show running-config | include file prompt"
    if {[catch {cli_exec $cli_sess(fd) $cmd} result]} {
        p_error "Failed to execute '$cmd', result:\n$result\n"
        return -1
    }
    debug "Command: $cmd, Output:\n$result\n"
    set split_list  [split $result "\n\r"]
    set file_prompt ""
    foreach linee $split_list {
        set linee [string trimright $linee " \n\r"]
        if {[string first "file prompt " $linee] == 0} {
            set file_prompt [string range $linee [string length "file prompt "] end]
            debug "File prompt config exists : '$file_prompt'"
            break
        }
    }

    # Set 'file prompt' level to 'quiet'
    set_file_prompt_config cli_sess "quiet"

    # Get file size
    set cmd "dir $in_path/$in_file"
    if {[catch {cli_exec $cli_sess(fd) $cmd} result]} {
        p_error "Failed to execute '$cmd', result:\n$result\n"
        set_file_prompt_config cli_sess $file_prompt
        return -1
    }
    debug "Command: $cmd, Output:\n$result\n"
    set split_list [split $result "\n\r"]
    set file_size     -1
    foreach linee $split_list {
        if {[string first $in_file $linee]        != -1 &&
            [string first "Directory of " $linee] == -1} {
            set file_size [lindex [regexp -inline -all -- {\S+} $linee] 2]
            break
        }
    }
    if {$file_size == -1} {
        p_error "Failed to read file '$in_path/$in_file' size"
        set_file_prompt_config cli_sess $file_prompt
        return -1
    }
    set    strr "\nPING to $ftp_ip is successful, "
    append strr "Copying file: '$in_path/$in_file' "
    append strr "of size: $file_size bytes to '$ftp_ip@/$ftp_path'"
    p_info $strr

    set cmd "copy $in_path/$in_file ftp://$ftp_ip:/$ftp_path/$in_file"
    if {[catch {cli_exec $cli_sess(fd) "$cmd"} result]} {
        p_error "Error while executing command: $cmd, Result:\n$result"
        set_file_prompt_config cli_sess $file_prompt
        return -1
    }
    action_syslog msg "\nCommand: '$cmd',\nOutput:\n$result\n"

    # Check if copy is successful
    set is_copy_success 0
    set split_list [split $result "\n\r"]
    foreach linee $split_list {
        set linee [string trimright $linee " \n\r"]
        if {[string first "$file_size bytes copied" $linee] != -1} {
            set is_copy_success 1
            break
        }
    }
    if {$is_copy_success != 1} {
        p_error "Copy command seems failed, Not deleting file from internal storage"
        set_file_prompt_config cli_sess $file_prompt
        return -1
    }

    p_info "Copy action success, Deleting file from internal storage ..."

    # Delete file from internal storage (deal interactive command)
    set rresult ""
    set cmd "delete $in_path/$in_file"
    if {[catch {cli_write $cli_sess(fd) "$cmd"} result]} {
        p_error "Failed to write command: '$cmd', Result:\n$result"
        set_file_prompt_config cli_sess $file_prompt
        return -1
    }
    append rresult "cli_write: '$cmd', response:\n$result\n"
    if {[catch {cli_read_pattern $cli_sess(fd) "Delete"} result]} {
        debug "$rresult"
        p_error "Failed to execute interactive command: '$cmd', Result: $result"
        set_file_prompt_config cli_sess $file_prompt
        return -1
    }
    append rresult "Expect string: 'Delete', output:\n$result\n"
    if {[catch {cli_write $cli_sess(fd) "\r"} result]} {
        debug "$rresult"
        p_error "Failed to execute interactive command: '$cmd', Result: $result"
        set_file_prompt_config cli_sess $file_prompt
        return -1
    }
    append rresult "\n$result\n"
    p_info "\nInteractive command: '$cmd' execution is successful, Result:\n$rresult"

    set_file_prompt_config cli_sess $file_prompt

    return 0
}

# ### Role of this procedure:
# ###      Check if given RA trace condition is set from show output
# ###          Disable it if present
# ###      Disable RA Tracing if there is no other
# ###          condition/feature enabled
# ###      Use RA trace decode command to collect logs and rotate them
# ###          to flash with unique file name
# ###      If FTP server IP is mentioned in the argumetns,
# ###          Move file to FTP server if it is reachable
proc stop_cndtn_and_rotate_logs {cli in_args} {
    upvar $cli cli_sess
    upvar $in_args args

    set strr "$args(cndtn) $args(cndtn_val)"
    debug "Stopping RA Tracing condition: $strr"

    # Get platform condition stats and status of input condition
    array set output [parse_sh_pl_cndtns_check_cndtn cli_sess $args(cndtn_val)]
    if {$output(rc) != 0} {
        p_error "Failed to parse 'show platform conditions' output"
        return $output(rc)
    }

    set cmd_list {}

    if {$output(target_cndtn_set) == 1} {
        debug "Condition: $args(cndtn_val) found in show output, disabling it"
        lappend cmd_list "no debug platform condition feature wireless $strr"
        incr output(total_cndtn_count) -1
    } else {
        p_info "Condition: $args(cndtn_val) NOT found in show output"
    }

    if {$output(ewlc_feature_cndtn) == "Enabled"} {
        incr output(total_feature_count) -1
    }

    set str1 "Not stopping conditional tracing,"
    if {$output(gbl_cndtn_state) == "Stop"} {
        p_info "platform condition is already in stop state"
    } elseif {$output(total_feature_count) > 0} {
        p_info "$str1 as there are other($output(total_feature_count)) features enabled"
    } elseif {$output(total_cndtn_count) > 0} {
        p_info "$str1 as there are other conditions($output(total_cndtn_count)) enabled"
    } else {
        lappend cmd_list "debug platform condition stop"
        p_info "Disabling platform conditional tracing"
    }

    array set ret [execute_command_list cli_sess cmd_list]
    if {$ret(rc) != 0} {
        p_error "Error while preparing trace results, Output:\n$ret(rbuf)"
        return -1
    }
    debug "\n$ret(rbuf)\n"

    # Generate file name
    array set file [generate_ra_trace_file_name cli_sess args]
    if {$file(rc) != 0} {
        p_error "Failed to generate decode log file name"
        return $file(rc)
    }

    # Calculate time duration between start and stop events
    set log_time 0
    if {[info exists args(start_time)] && $args(start_time) != 0 &&
        [info exists args(end_time)]   && $args(end_time) > $args(start_time)} {
        set log_time [expr $args(end_time) - $args(start_time)]
        p_info "Decoding logs for last $log_time sec to file: '$file(path):$file(name)'..."
    } else {
        p_info "Decoding logs to file: '$file(path):$file(name)'..."
    }

    set cmd "show logging profile wireless "
    if {$args(internal) == 1} {
        append cmd "internal "
    }
    if {$log_time != 0} {
        append cmd "start last $log_time seconds "
    }
    if {$args(log_level) != ""} {
        append cmd "level $args(log_level) "        
    }
    if {$args(cndtn) == "MAC"} {
        append cmd "filter " $args(cndtn) " " $args(cndtn_val) " "
    } else {
        append cmd "filter ipv4 " $args(cndtn_val) " "
    }
    append cmd "to-file " "$file(path):$file(name)"
    if {[catch {cli_exec $cli_sess(fd) "$cmd"} result]} {
        p_error "Error while executing command: '$cmd', Result:\n$result\n"
        return -1
    } elseif {[string first "Invalid input detected" $result] != -1 ||
              [string first "Incomplete command" $result] != -1} {
        p_error "Failed to execute command: '$cmd', Result:\n$result\n"
        return -1
    } else {
        action_syslog msg "$result"
    }
    set pattern "unified trace decoder estimate: processed 100%"
    if {[string first $pattern $result] == -1} {
        set    strr "Decode action seems failed, couldn't find "
        append strr "'$pattern' in show logging profile output"
        p_error $strr
        return -1
    }

    if {$args(ftp_ip) != ""} {
        set rc [copy_file_to_ftp cli_sess "$file(path):" $file(name) $args(ftp_ip) $args(ftp_path)]
        if {$rc != 0} {
            p_info "Unable to move log file to FTP server, keeping it in internal storage"
        }
    }

    return 0
}


# ##############################################################################
# ############################## MAIN STARTS HERE ##############################
# ##############################################################################

# Get event detector information
array set m_einfo   [event_reqinfo_multi]
array set arr_einfo [event_reqinfo]

# Verify if debug console log flag is set
if {[info exists _ra_tracing_debug] && $_ra_tracing_debug == 1} {
    set DEBUG_FLAG 1
    p_info "setting debug flag"
}

# Determine what type of event has triggered the script
if {[info exists m_einfo(ev_ra_trace)]} {
    set event_name "event_ra_tracing"
    debug "RA tracing CLI event"
} elseif {[info exists m_einfo(ev_none)]} {
    set event_name "event_none"
    debug "RA tracing none event"
} else {
    dump "Unknown event triggered the script"
    print_array m_einfo "m_einfo"
    exit 1
}

# Parse input arguments from event-detector information
if {$event_name == "event_ra_tracing"} {
    array set input_args [parse_cli_evd_inputs arr_einfo]
    print_array input_args "input_args"
    if {$input_args(rc) != 0} {
        p_error "Parsing CLI event info failed"
        print_array arr_einfo "arr_einfo"
        exit 1
    } elseif {$input_args(trigger) == "" || $input_args(cndtn) == ""} {
        debug "Not interested in CLI: '$arr_einfo(msg)'"
        print_array arr_einfo "arr_einfo"
        exit 1
    }
    debug "Parsing inputs from CLI event info is success"
    set input_args(ev_tag) "event_ra_tracing"
} else {
    array set input_args [parse_none_evd_inputs arr_einfo]
    print_array input_args "input_args"
    if {$input_args(rc) != 0} {
        p_error "Parsing none event info failed"
        print_array arr_einfo "arr_einfo"
        exit 1
    }
    debug "Parsing inputs from none event info is success"
    set input_args(ev_tag) "event_none"
}

if {$input_args(trigger) == "start"} {
    # If Max monitor time is not provided in the input, set default value
    if {$input_args(time) == 0} {
        set input_args(time) $DEFAULT_MAX_TIME
    }

    # Store this start-event initiated time
    set input_args(start_time) $arr_einfo(event_pub_sec)
} else {
    # This is Stop event
    set input_args(end_time) $arr_einfo(event_pub_sec)
}

# Open CLI session in enable mode
array set cli_sess [cli_session_start]

# Check TTY line privileges
set cmd "configure terminal"
if {[catch {cli_exec $cli_sess(fd) $cmd} result]} {
    p_error "Error while executing command: '$cmd', Result:\n$result"
    array set cli_sess [cli_session_close cli_sess]
    exit 1
} elseif {[string first "Command authorization failed" $result] != -1} {
    set    dump_str "    Failed to program RA tracing $input_args(trigger) event,\n"
    append dump_str "        Device authorization failed on new TTY line.\n"
    append dump_str "        Configure 'event manager session cli username \"\$USERNAME\"'"
    dump $dump_str
    p_error "Unable to get full privileges for new TTY line"
    array set cli_sess [cli_session_close cli_sess]
    exit 1
} elseif {[catch {cli_exec $cli_sess(fd) "exit"} result]} {
    p_error "Error while executing command: 'exit', Result:\n$result"
    array set cli_sess [cli_session_close cli_sess]
    exit 1
}

# Dump help string on console
set    dump_str ""
append dump_str "    RA tracing $input_args(trigger) event,\n"
append dump_str "       conditioned on $input_args(cndtn) address: "
append dump_str "$input_args(cndtn_val)\n"
if {$input_args(trigger) == "start"} {
    append dump_str "       Trace condition will be automatically stopped in "
    append dump_str "$input_args(time) seconds.\n"
    append dump_str "       Execute 'no debug wireless "
    append dump_str "[string tolower $input_args(cndtn)] "
    append dump_str "$input_args(cndtn_val)' to manually stop RA tracing on "
    append dump_str "this condition.\n"
    if {$input_args(ftp_ip) != ""} {
        append dump_str "       Decoded log file will be moved to FTP server: "
        append dump_str "'$input_args(ftp_ip):/[string trim $input_args(ftp_path) "/"]/'\n"
        append dump_str "       Please make sure that server credentials are globally"
        append dump_str " set using configs: 'ip ftp username/password'"
    }
}
dump $dump_str


set strr "$input_args(cndtn) @ $input_args(cndtn_val)"
if {$input_args(trigger) == "start"} {
    # RA TRACING START TRIGGER
    debug "Invoking start - RA Tracing for condition:  $strr"

    set ret [set_cndtn_and_start_ra_trace cli_sess input_args]
    if {$ret != 0} {
        p_error "Failed to start RA tracing on condition $strr"
        array set cli_sess [cli_session_close cli_sess]
        exit 1
    }
    p_info "Successfully started RA tracing on condition: $strr"
    # Close CLI session
    array set cli_sess [cli_session_close cli_sess]
    exit 1
}

# ### RA TRACING STOP TRIGGER

if {$input_args(ev_tag) == "event_ra_tracing"} {
    # This is CLI trigger for stop, log decode will hang current console
    # CREATE TIMER APPLET TO SCHEDULE LOG DECODE&ROTATION IN NEW CONSOLE LINE
    set   input_args(time) 2
    array set applet [generate_timer_applet_name input_args]
    if {$applet(name) == 0} {
        p_error "Failed to generate applet name"
        array set cli_sess [cli_session_close cli_sess]
        dump "    Failed to (re-)schedule RA trace stop event."
        exit 1
    }

    # Re-schedule countdown timer with 2 seconds to invoke immediately
    set ret [reset_ra_trace_stop_timer_applet_time cli_sess $applet(name) 2]
    array set cli_sess [cli_session_close cli_sess]
    if {$ret != 0} {
        set    strr "    Failed to (re-)schedule RA trace stop event.\n"
        append strr "       Check if this condition is invalid"
        dump "$strr"
        exit 1
    }

    exit 1
}

debug "Invoking stop - RA Tracing for condition:  $strr"
set ret [stop_cndtn_and_rotate_logs cli_sess input_args]
if {$ret != 0} {
    p_error "Failed to collect RA tracing logs for condition: $strr"
    exit 1
}
p_info "Successfully collected RA tracing logs for condition: $strr"

# Close CLI session
array set cli_sess [cli_session_close cli_sess]

exit 1
