::cisco::eem::event_register_rpc

# This is a simple EEM RPC policy that lists all of the arguments
# passed to it.  This will give a good idea of how argument handling
# is done within EEM RPC policies.

namespace import ::cisco::eem::*
namespace import ::cisco::lib::*

array set arr_einfo [event_reqinfo]

# The "argc" element of the array is the total number of arguments
set argc $arr_einfo(argc)

puts "Number of arguments: $argc"

for { set i 0 } { $i < $argc } { incr i } {
    # Each argument is its own member of the reqinfo array.
    # NOTE: Argument counting starts at zero.
    set arg "arg${i}"
    puts "Argument $i: $arr_einfo($arg)"
}
