#!/usr/bin/perl

use Cisco::EEM::RPC::Policy;
use Cisco::EEM::RPC::Session;

my $pol = new Cisco::EEM::RPC::Policy("test_rpc.tcl");
$pol->setArgList('arg0', 'arg1', 'arg2');

my $rpc = new Cisco::EEM::RPC::Session('10.1.1.1');
$rpc->setTimeout(10);
$rpc->login('user', 'pass');

my $result = $rpc->invoke($pol);
if ($result) {
	print "Got result: " . $rpc->getResult() . "\n";
} else {
	print "Got error: " . $rpc->getErrorCode() . ": " . $rpc->getErrorMsg() ."\n";
}

$rpc->close();
