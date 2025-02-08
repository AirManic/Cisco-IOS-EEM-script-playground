::cisco::eem::event_register_rpc

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

proc run_cli_interactive { clist } {
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
        array set sendexp $cmd

	if {[catch {cli_write $cliarr(fd) $sendexp(send)} result]} {
            return -code error $result
	}

	foreach response $sendexp(responses) {
	    array set resp $response

	    if {[catch {cli_read_pattern $cliarr(fd) $resp(expect)} result]} {
                return -code error $result
	    }

	    if {[catch {cli_write $cliarr(fd) $resp(reply)} result]} {
                return -code error $result
	    }
	}

	if {[catch {cli_read $cliarr(fd)} result]} {
            return -code error $result
	}

	append rbuf $result
    }

    if {[catch {cli_close $cliarr(fd) $cliarr(tty_id)} result]} {
        puts "WARNING: $result"
    }

    return -code ok $rbuf
}

array set arr_einfo [event_reqinfo]

set args $arr_einfo(argc)

set cmds [list]

for { set i 0 } { $i < $args } { incr i } {
    set arg "arg${i}"
    # Split each argument on the '^' character.  The first element is
    # the command, and each subsequent element is a prompt followed by
    # a response to that prompt.
    set cmdlist [split $arr_einfo($arg) "^"]
    set cmdarr(send) [lindex $cmdlist 0]
    set cmdarr(responses) [list]
    if { [expr ([llength $cmdlist] - 1) % 2] != 0 } {
	return -code 88
    }
    set cmdarr(responses) [list]
    for { set j 1 } { $j < [llength $cmdlist] } { incr j 2 } {
	set resps(expect) [lindex $cmdlist $j]
	set resps(reply) [lindex $cmdlist [expr $j + 1]]
	lappend cmdarr(responses) [array get resps]
    }
    lappend cmds [array get cmdarr]
}

set rc [catch {run_cli_interactive $cmds} output]

if { $rc != 0 } {
    error $output $errorInfo
    return -code 88
}

puts $output
