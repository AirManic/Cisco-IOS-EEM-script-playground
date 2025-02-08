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
# $Id: Policy.pm,v 1.7 2007/09/09 18:51:35 marcus Exp $
#

package Cisco::EEM::RPC::Policy;

use strict;
use Carp qw(croak);
use vars qw(@ISA $VERSION);
@ISA = qw(Exporter);

$VERSION = '1.0';

sub new {
        my ($that, @args) = @_;
        my $class = ref($that) || $that;

        my $name = shift @args;

        croak __PACKAGE__ . ": The policy name cannot be undefined or empty"
            if (!defined($name) || $name eq "");

        my $self = {
                _name => $name,
                _args => \@args,
        };

        bless($self, $class);
        $self;
}

sub getName {
        my $self = shift;

        return $self->{'_name'};
}

sub getArgCount {
        my $self = shift;

        return (scalar @{$self->{'_args'}});
}

sub getArgList {
        my $self = shift;

        return wantarray ? @{$self->{'_args'}} : $self->{'_args'};
}

sub setName {
        my $self = shift;
        my $name = shift;

        croak __PACKAGE__ . ": The policy name cannot be undefined or empty"
            if (!defined($name) || $name eq "");

        $self->{'_name'} = $name;
}

sub setArgList {
        my $self = shift;
        my @args = @_;

        $self->{'_args'} = \@args;
}

sub toString {
        my $self = shift;

        return (join(" ", $self->{'_name'}, @{$self->{'_args'}}));
}

sub toSOAPString {
        my $self = shift;

        my $name = $self->{'_name'};
        my $argc = $self->getArgCount();

        my $string = <<EOS;
<?xml version="1.0" encoding="UTF-8"?>
<SOAP:Envelope xmlns:SOAP="http://www.cisco.com/eem.xsd">
  <SOAP:Body>
    <run_eemscript>
      <script_name>$name</script_name>
      <argc>$argc</argc>
      <arglist>
EOS

        foreach my $arg (@{$self->{'_args'}}) {
                $string .= "        <l>$arg</l>\n";
        }

        $string .= <<EOS;
      </arglist>
    </run_eemscript>
  </SOAP:Body>
</SOAP:Envelope>
EOS

        return $string;
}

1;
__END__

=head1 NAME

Cisco::EEM::RPC::Policy - Perl class describing an EEM policy

=head1 SYNOPSIS

	use Cisco::EEM::RPC::Policy;
	my $policy = new Cisco::EEM::RPC::Policy($name);
	$policy->setArgList(@args);
	$string = $policy->toString();
	$SOAPString = $policy->toSOAPString();

=head1 DESCRIPTION

I<Cisco::EEM::RPC::Policy> is a Perl module that describes an Embedded Event
Manager (EEM) RPC policy.  The module is typically used with the
I<Cisco::EEM::RPC::Session> class to execute an EEM RPC policy on a
device.

=head1 BASIC USAGE

Usage of I<Cisco::EEM::RPC::Policy> is very straight-forward.

=head2 new Cisco::EEM::RPC::Policy($name[, @args])

To create a new policy, call the I<new> method which instantiates a
policy called I<$name> with an optional argument list I<@args>.

=head2 $policy->getName()

The I<getName> method returns the current policy's name.

=head2 $policy->getArgList()

The I<getArgList> method will return the current policy's argument list.
It can be called in one of two ways:

=over 4

=item @list = $policy->getArgList()

This will return the argument list as an array.

=item $list = $policy->getArgList()

This will return the argument list as an array reference.

=back

=head2 $policy->getArgCount()

The I<getArgCount> method returns the count of arguments in the argument
list.

=head2 $policy->setName($name)

The I<setName> method sets the name of the policy to I<$name>.

=head2 $policy->setArgList(@args)

The I<setArgList> method sets the policy argument list to I<@args>.

=head2 $policy->toString()

The I<toString> method returns a scalar string representation of the policy
including the name and argument list.

=head2 $policy->toSOAPString()

The I<toSOAPString> method converts the internal representation of the
policy into a SOAP string for use with the SOAP XML-based EEM RPC.

=head1 AUTHOR

Joe Marcus Clarke, jclarke@cisco.com

=head1 COPYRIGHT

Copyright (c) 2007 Joe Marcus Clarke <jclarke@cisco.com>
All rights reserved.

This code is distributed under the BSD License.  See the LICENSE.txt file
for the full license text.

=cut
