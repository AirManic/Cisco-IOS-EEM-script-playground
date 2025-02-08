#-
# Copyright (c) 2007 Joe Marcus Clarke <jclarke@cisco.com>
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
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
# $Id: Transport.pm,v 1.4 2007/11/03 18:07:46 marcus Exp $
#

package Cisco::EEM::RPC::Transport;

use strict;
use Carp qw(croak);
use vars qw(@ISA);
@ISA = qw(Exporter);

# This is an interface that all Transport implementations must implement
# to be compatible with the Perl EEM RPC API.  The Transport module must
# declare Cisco::EEM::RPC::Transport in its @ISA array, then implement
# each one of these methods.

sub new {
        croak __PACKAGE__
            . ": The new method must be implemented by the actual transport implementation";
}

sub login {
        croak __PACKAGE__
            . "::login must be implemented by the actual transport implementation";
}

sub invoke {
        croak __PACKAGE__
            . "::invoke must be implemented by the actual transport implementation";
}

sub close {
        croak __PACKAGE__
            . "::close must be implemented by the actual transport implementation.";
}

1;
__END__

=head1 NAME

Cisco::EEM::RPC::Transport - Perl class describing an EEM RPC transport protocol

=head1 SYNOPSIS

	use Cisco::EEM::RPC::Transport;
	use vars qw(@ISA);
	@ISA = qw(Cisco::EEM::RPC::Transport);


	sub new { ... }
	sub login { ... }
	sub invoke { ... }
	sub close { ... }

=head1 DESCRIPTION

I<Cisco::EEM::RPC::Transport> is a class that enumerates the methods
required to implement an EEM RPC transport protocol.  Any new EEM RPC
transport protocol should extend this class and implement the required
methods.

=head1 USAGE

The following methods must be implemented by the class extending
I<Cisco::EEM::RPC::Transport>.  Once that is done, the transport
module name can be used by I<Cisco::EEM::RPC::Session>.

=head2 new($host, %attrs)

This method creates a new instance of your transport protocol.  It must
accept a I<$host> argument indicating the EEM RPC device, and an optional
I<%attrs> argument which can contain additional parameters for the
constructor.  Currently, I<Cisco::EEM::RPC::Session> will pass a
boolean, C<debug>, and a floating-point number, C<timeout> via the
I<%attrs> hash.

=head2 login($user, $pass)

This method opens a connection to the device specified by the I<$host>
argument to the constructor, and logs into the device with the username
and password specified by the I<$user> and I<$pass> arguments
respectively.

This method must I<croak> if the login fails in any way.

=head2 invoke($SOAPString)

This method executes the EEM RPC policy described by the I<$SOAPString>
argument on the device specified by the I<$host> argument to the
constructor.  I<invoke> must return a SOAP XML string representing
the result of the EEM RPC policy.

=head2 close

This method should release any resources used by the transport protocol.

=head1 AUTHOR

Joe Marcus Clarke, jclarke@cisco.com

=head1 COPYRIGHT

Copyright (c) 2007 Joe Marcus Clarke <jclarke@cisco.com>
All rights reserved.

This code is distributed under the BSD License.  See the LICENSE.txt file
for the full license text.

=cut
