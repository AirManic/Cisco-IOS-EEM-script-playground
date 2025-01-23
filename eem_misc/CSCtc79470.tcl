::cisco::eem::event_register_none
#-
# Copyright (c) 2009 Joe Marcus Clarke <jclarke@cisco.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
#

if { ![info exists show_timer_name] } {
    set result "ERROR: Policy cannot be run: variable show_timer_name has not been set"
    error $result $errorInfo
}

namespace import ::cisco::eem::*
namespace import ::cisco::lib::*

proc run_cli { clist } {
    set rbuf ""

    if {[llength $clist] < 1} {
	return -code ok $rbuf
    }

    if {[catch {cli_open} result]} {
        return -code error $result
    } else {
	array set cliarr $result
    }

    if {[catch {cli_exec $cliarr(fd) "enable"} result]} {
        return -code error $result
    }

    if {[catch {cli_exec $cliarr(fd) "term length 0"} result]} {
        return -code error $result
    }

    foreach cmd $clist {
	if {[catch {cli_exec $cliarr(fd) $cmd} result]} {
            return -code error $result
	}

	append rbuf $result
    }

    if {[catch {cli_close $cliarr(fd) $cliarr(tty_id)} result]} {
        puts "WARNING: $result"
    }

    return -code ok $rbuf
}

set now [clock seconds]
set lastfire {}

set output [run_cli [list "show event manager history events | include $show_timer_name"]]
set lines [split $output "\n"]
if { [llength $lines] > 0 } {
    set i 0
    set line [lindex $lines end-$i]
    while { ! [regexp "$show_timer_name" $line] } {
	incr i
	if { $i == [llength $lines] } {
	    break
	}
	set line [lindex $lines end-$i]
    }
    set line [string trim $line]
    regsub -all {\s+} $line { } line
    set parts [split $line]
    set datefield 2
    if { [llength $parts] >= 11 && [llength $parts] < 14 } {
	set datefield 4
    } elseif { [llength $parts] >= 12 } {
	set datefield 5
    }
    if { [string length [lindex $parts $datefield]] == 3 } {
	set lastfire [lrange $parts [expr $datefield - 1] [expr $datefield + 3]]
    } else {
        set temp [lindex $parts $datefield]
	if { [regexp {(\w{3})(\d{2})} $temp -> mon day] } {
	    set lastfire "[lindex $parts [expr $datefield - 1]] $mon $day [lindex $parts [expr $datefield + 1]] [lindex $parts [expr $datefield + 2]]"
	} else {
	    set lastfire [lrange $parts [expr $datefield - 1] [expr $datefield + 2]]
	}
    }
}

set output [run_cli [list "show event manager policy registered"]]
set lines [split $output "\n"]

set timer -1
set type {}
set subtype {}
set found 0
set hassecu 0

if { [regexp {\s+Secu\s+} [lindex $lines 0]] } {
    set hassecu 1
}

foreach line $lines {
    set line [string trim $line]
    regsub -all {\s+} $line { } line
    if { ! $found && [regexp {^\d} $line] } {
        set parts [split $line]
	if { $hassecu } {
	    set regdate [lrange $parts end-6 end-2]
	} else {
            set regdate [lrange $parts end-5 end-1]
	}
        set type [lindex $parts 3]
        set subtype [lindex $parts 4]
        if { [lindex $parts end] == $show_timer_name } {
	    set found 1
	    continue
        }
    }

    if { $found && $type == "timer" && ($subtype == "watchdog" || $subtype == "countdown") } {
	if { [regexp {time\s+([\d\.]+)$} $line -> timer] } {
	    set timer [expr int($timer)]
	    break
	}
    } elseif { $found } {
	puts "Found a policy with the name $show_timer_name, but it is of type $type (subtype: $subtype) which is not a valid watchdog or countdown timer"
	exit 1
    }
}

if { ! $found } {
    puts "Failed to find a policy named $show_timer_name."
    exit 1
}

set regsecs [clock scan $regdate]

if { $subtype == "countdown" && $now >= [expr $regsecs + $timer] } {
    puts "Timer $show_timer_name is a countdown, and it has already expired."
    exit 0
}

if { $lastfire != {} && $subtype != "countdown" } {
    set regsecs [clock scan $lastfire]
}

set diff [expr abs([expr $now - $regsecs])]
set remain [expr $timer - [expr $diff % $timer]]

puts "Policy $show_timer_name will fire again in $remain seconds."
