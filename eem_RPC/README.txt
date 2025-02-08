# $Id: README.txt,v 1.3 2008/05/11 04:03:58 marcus Exp $

This is Cisco::EEM::RPC.  It contains a Perl object-oriented interface
to executing Cisco Embedded Event Manager Remote Procedure Call
(EEM RPC) policies.  This release makes use of SOAP XML over SSH version 2
to execute policies and retrieve their results.

PREREQUISITES
	* Net::SSH::Perl (1.00 or greater)
	* XML::LibXML

INSTALLATION

Cisco::EEM::RPC installation is relatively straight-forward.
If your CPAN shell is set up, you can execute the following
command:

	% perl -MCPAN -e 'install Cisco::EEM::RPC'

If that is not possible, then simply download the distribution from
CPAN.  The latest version can be found at:

	<CPAN URL>

Unpack it, then build it per the usual Perl module way:

	% perl Makefile.PL
	% make

Then install it:

	% make install

EXAMPLES

There is one example script distributed with Cisco::EEM::RPC that
can be found in eg/ subdirectory within the distribution:

* eg/rpc.pl shows the typical usage of Cisco::EEM::RPC

There are also some sample EEM RPC TCL policies distributed to give
you an idea of how EEM RPC works:

* eg/listargs.tcl simple prints all of the arguments passed to it

* eg/rpccli.tcl each argument passed to the script is executed as an IOS
  command

* eg/rpctcl.tcl each argument passed to the script is interpreted as Tcl
  code


PROBLEMS

If you encounter any problems using the Cisco::EEM::RPC code, please
contact Joe Marcus Clarke <jclarke@cisco.com>.

AUTHOR

Joe Marcus Clarke <jclarke@cisco.com>
