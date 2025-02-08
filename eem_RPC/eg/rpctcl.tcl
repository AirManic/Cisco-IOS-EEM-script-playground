::cisco::eem::event_register_rpc

namespace import ::cisco::eem::*
namespace import ::cisco::lib::*

array set arr_einfo [event_reqinfo]

set args $arr_einfo(argc)

# Pass each argument through the Tcl interpreter.
# Any output will be passed back to the caller.
for { set i 0 } { $i < $args } { incr i } {
    set arg "arg${i}"
    eval $arr_einfo($arg)
}
