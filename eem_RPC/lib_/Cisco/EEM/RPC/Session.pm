#-
# Copyright (c) 2008 Joe Marcus Clarke <jclarke@cisco.com>
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
# $Id: Session.pm,v 1.15 2009/06/30 19:34:41 marcus Exp $
#

package Cisco::EEM::RPC::Session;

use strict;
use Carp qw(croak);
use XML::LibXML;
use vars qw(@ISA $VERSION);
@ISA = qw(Exporter);

$VERSION = '1.0.1';

use constant EBADXML          => -1000;
use constant EINVALIDXML      => -999;
use constant EOK              => 0;
use constant EUNKNOWN         => 1;
use constant ESYSERR          => 2;
use constant ENOTSUPPORTED    => 3;
use constant EINITONE         => 4;
use constant ECONNECT         => 5;
use constant EBADEVENTTYPE    => 6;
use constant ENOSUCHKEY       => 7;
use constant EDUPLICATEKEY    => 8;
use constant EMEMORY          => 9;
use constant ECORRUPT         => 10;
use constant ENOSUCHESID      => 11;
use constant ENOSUCHEID       => 12;
use constant ENOEVENTACTIVE   => 13;
use constant ENOSUCHACTION    => 14;
use constant ENOSUCHSYSINFO   => 15;
use constant EBADFMPPTR       => 16;
use constant EBADADDRESS      => 17;
use constant EDATAUNAVAIL     => 18;
use constant EREGERROR        => 19;
use constant ENOPUBDATA       => 20;
use constant EDUPLICATEES     => 21;
use constant ENULLPTR         => 22;
use constant EBADOCCURS       => 23;
use constant ETIMERCREAT      => 24;
use constant ESUBSEXCEED      => 25;
use constant ESUBSIDXINV      => 26;
use constant ETMDELAYZR       => 27;
use constant ENOTREGISTERED   => 28;
use constant ECTBADEXITOPER   => 29;
use constant ECTBADOPER       => 30;
use constant EPUBENTALLOC     => 31;
use constant EPUBENTADD       => 32;
use constant ECTNOTSET        => 33;
use constant EMAXLEN          => 34;
use constant EWRONGTYPE       => 35;
use constant ENOTINCATALOG    => 36;
use constant ENOSNMPDATA      => 37;
use constant EWRONGINDEX      => 38;
use constant EWRONGPARM       => 39;
use constant ESTBADEXITOPER   => 40;
use constant ESTBADOPER       => 41;
use constant ESTBADCOMBOPER   => 42;
use constant EBADLENGTH       => 43;
use constant EHISTEMPTY       => 44;
use constant ESEQNUM          => 45;
use constant EREGEMPTY        => 46;
use constant EMETENTALLOC     => 47;
use constant EMETENTADD       => 48;
use constant ESTBADTYPE       => 49;
use constant EBADOFFSET       => 50;
use constant ESTATSTYP        => 51;
use constant ECONFIG          => 52;
use constant ESTRLNEXCD       => 53;
use constant EFDUNAVAIL       => 54;
use constant ENOPRIORVER      => 55;
use constant EFDCONNERR       => 56;
use constant ETIMEOUT         => 57;
use constant EBADSUBEVTCOMBOP => 58;
use constant EBADSUBEVTYP     => 59;
use constant EBADSUBEVTOP     => 60;
use constant EWDEVENT         => 61;
use constant ENDOFAPI         => 62;
use constant EMOREDATA        => 63;
use constant ENODATA          => 64;
use constant EWATCHQUEUE      => 65;
use constant ECNSEVENTAGENT   => 66;
use constant ESWITCHHARDWARE  => 67;
use constant EENQUEUE         => 68;
use constant EWATCHBOOL       => 69;
use constant EWATCHSEMAPHORE  => 70;
use constant EFOPEN           => 71;
use constant EGETDENTS        => 72;
use constant EFSTAT           => 73;
use constant EFREMOVE         => 74;
use constant EFREAD           => 75;
use constant EFCREATE         => 76;
use constant ECHKPT           => 77;
use constant ESMTPCONNECT     => 78;
use constant ESMTPCHKREPLY    => 79;
use constant ESMTPREAD        => 80;
use constant ESMTPWRITE       => 81;
use constant ESMTPDISCONNECT  => 82;
use constant ENOMORETTY       => 83;
use constant EBADCHECKSUM     => 84;
use constant ERMI             => 85;
use constant ENOTRACK         => 86;
use constant EPARMSEXCEED     => 87;
use constant EPARMSINVALID    => 88;
use constant EJOBIDINVALID    => 89;

sub new {
        my ($that, @args) = @_;
        my $class = ref($that) || $that;

        my $host = shift @args;
        croak "usage: ", __PACKAGE__, "->new(\$host [,%args])"
            unless defined($host) && $host ne "";
        my %attrs = @args;

        my $self = {
                username  => '',
                password  => '',
                transport => 'SSH',
                debug     => '',
                timeout   => 0,
        };

        foreach my $key (keys %attrs) {
                $self->{$key} = $attrs{$key} if (defined($self->{$key}));
        }

        $self->{'_host'}        = $host;
        $self->{'_errcode'}     = 0;
        $self->{'_errmsg'}      = undef;
        $self->{'_trans_class'} = undef;
        $self->{'_logged_in'}   = 0;
        $self->{'_result'}      = undef;
        $self->{'_raw_result'}  = undef;
        $self->{'_xml_parser'}  = new XML::LibXML;

        bless($self, $class);
        $self;
}

sub setHost {
        my $self = shift;
        my $host = shift;
        croak __PACKAGE__ . "::setHost: Hostname cannot be empty or undefined"
            unless defined($host) && $host ne "";

        $self->close;

        $self->{'_host'} = $host;
}

sub setUsername {
        my $self = shift;
        my $user = shift;
        croak __PACKAGE__
            . "::setUsername: Username cannot be empty or undefined"
            unless defined($user) && $user ne "";

        $self->{'username'} = $user;
}

sub setPassword {
        my $self = shift;
        my $pass = shift;

        $self->{'password'} = $pass;
}

sub setTransport {
        my $self  = shift;
        my $tport = shift;

        $self->{'transport'} = $tport;
        $self->_init_transport;
}

sub setDebug {
        my $self  = shift;
        my $debug = shift;

        $self->{'debug'} = ($debug == 0) ? 0 : 1;
}

sub setTimeout {
        my $self    = shift;
        my $timeout = shift;

        ($self->{'timeout'}) = $timeout =~ /(^\d+\.?\d*$)/s;
}

sub getErrorCode {
        my $self = shift;

        return $self->{'_errcode'};
}

sub getErrorMsg {
        my $self = shift;

        return $self->{'_errmsg'};
}

sub getResult {
        my $self = shift;

        return $self->{'_result'};
}

sub getRawResult {
        my $self = shift;

        return $self->{'_raw_result'};
}

sub getTransport {
        my $self = shift;

        return $self->{'transport'};
}

sub getTransportClass {
        my $self = shift;

        return $self->{'_trans_class'};
}

sub _init_transport {
        my $self = shift;
        croak __PACKAGE__ . ": Transport cannot be empty or undefined"
            unless defined($self->{'transport'}) && $self->{'transport'} ne "";

        $self->close;

        $self->_debug("Initializing transport " . $self->{'transport'});
        my $trans_class = 'Cisco::EEM::RPC::Transport::' . $self->{'transport'};
        if (eval "require $trans_class") {
                $trans_class->import();
                $self->{'_trans_class'} = $trans_class->new(
                        $self->{'_host'},
                        (
                                debug   => $self->{'debug'},
                                timeout => $self->{'timeout'}
                        )
                );
        } else {
                croak __PACKAGE__
                    . ": Failed to load transport "
                    . $self->{'transport'} . ": $!";
        }

        $self->{'_logged_in'} = 0;
}

sub _parse_result {
        my $self = shift;
        my ($xml, $doc, @checklist, $nodelist, $node);

        $xml = $self->{'_raw_result'};
        eval { $doc = $self->{'_xml_parser'}->parse_string($xml); };
        if ($@) {
                $self->{'_errcode'} = EBADXML;
                $self->{'_errmsg'}  = "Error parsing XML response";
                return;
        }

        @checklist = $doc->getElementsByTagName('run_eemscript_response');
        if (!@checklist) {
                $self->{'_errcode'} = EINVALIDXML;
                $self->{'_errmsg'}  = "XML response is not valid";
                return;
        }

        $nodelist           = $doc->findnodes('//return_code');
        $node               = $nodelist->shift->firstChild;
        $self->{'_errcode'} = $node->nodeValue;

        if ($node->nodeValue == 0) {
                $self->{'_errmsg'} = undef;
        }

        $nodelist = $doc->findnodes('//output');
        $node     = $nodelist->shift->firstChild;

        if ($self->{'_errcode'} != 0) {
                $self->{'_errmsg'} = $node->nodeValue;
                $self->{'_result'} = undef;
        } else {
                $self->{'_result'} = $node->nodeValue;
        }
}

sub login {
        my $self = shift;
        my ($user, $pass) = @_;

        if (!defined($user) && !defined($self->{'username'})) {
                croak __PACKAGE__ . "::login: Username has not been set";
        } elsif (!defined($user)) {
                $user = $self->{'username'};
        }

        if (!defined($pass)) {
                $pass = $self->{'password'}
        }

        if (!defined($self->{'_trans_class'})) {
                $self->_init_transport;
        }

        $self->{'_trans_class'}->login($user, $pass);
        $self->{'_logged_in'} = 1;
}

sub invoke {
        my $self   = shift;
        my $policy = shift;
        my $soap_string;

        eval { $soap_string = $policy->toSOAPString(); };
        if ($@) {
                croak __PACKAGE__
                    . "::invoke: policy argument is not a valid EEM RPC Policy instance";
        }

        if ($self->{'_logged_in'} == 0) {
                $self->login;
        }

        $self->_debug("Invoking policy '" . $policy->toString() . "'");

        my $result = $self->{'_trans_class'}->invoke($soap_string);
        $self->{'_raw_result'} = $result;
        $self->_parse_result;

        return ($self->{'_errcode'} == 0);
}

sub _debug {
        my $self = shift;
        my $msg  = shift;

        return unless ($self->{'debug'} == 1);

        print STDERR $self->{'_host'} . ": " . $msg . "\n";
}

sub close {
        my $self = shift;

        return unless defined($self->{'_trans_class'});

        $self->_debug("Closing transport socket");

        $self->{'_trans_class'}->close;
        $self->{'_logged_in'}   = 0;
        $self->{'_trans_class'} = undef;
}

1;
__END__

=head1 NAME

Cisco::EEM::RPC::Session - Perl class for executing EEM RPC policies

=head1 SYNOPSIS

	use Cisco::EEM::RPC::Session;
	my $rpc = new Cisco::EEM::RPC::Session($host);
	$rpc->login($user, $pass);
	$rpc->invoke($policy);
	my $result = $rpc->getResult();
	my $errcode = $rpc->getErrorCode();
	my $errmsg = $rpc->getErrorMsg();
	$rpc->close();

=head1 DESCRIPTION

I<Cisco::EEM::RPC::Session> handles executing and processing
Embedded Event Manager Remote Procedure Call (EEM RPC) policies.  It
supports a flexible system of transports (as described by
I<Cisco::EEM::RPC::Transport>), but currently only SSH is provided
and support by Cisco devices.

The module connects to the device, then uses SOAP XML to execute the
desired EEM policy with the specified argument list.

=head1 BASIC USAGE

There are two main ways to use instances of I<Cisco::EEM::RPC::Session>.
Typically, the flow is to create a new instance, then login, then execute
or invoke the desired policy.

=head2 new Cisco::EEM::RPC::Session($host[, %args])

To create a new EEM RPC session, call the I<new> method and specify
a I<$host> argument.  This will instantiate an EEM RPC session to
I<$host>.  However, no network connection will be made at this point.
The optional I<%args> hash contains additional parameters about the
session.  Those parameters can be the following:

=over 4

=item * username

This is the username you wish to use for the session.  If this and the
C<password> parameter are specified, the I<login> method does not need
to be explicitly called.

=item * password

This is the password you wish to use for the session.  If this and the
C<username> parameter are specified, the I<login> method does not need
to be explicitly called.

=item * transport

This is the transport protocol you wish to use for the session.  The
default is C<SSH>.  Currently, SSH is the only supported transport
protocol supported by Cisco devices.  However, various proxy transports
could be created by extending the I<Cisco::EEM::RPC::Transport> class.

If a specified transport module cannot be loaded, the application
will I<croak> when the I<login>, I<invoke>, or I<setTransport>
methods are called.

=item * debug

This is a boolean that controls whether or not to enable debugging.
A value of C<0> (the default) means that debugging should be disabled
where as a value of C<1> will enabled debugging.

=back

=head2 $rpc->setHost($host)

This sets the host for the current session to I<$host>.  By calling
this method, any existing connection will be broken, and the
underlying transport will be reinitialized.

=head2 $rpc->setUsername($user)

This sets the session username to I<$user>.  If both the username and
password are set, then the I<login> method does not need to be
explicitly called.

=head2 $rpc->setPassword($pass)

This sets the session password to I<$pass>.  If both the username and
password are set, then the I<login> method does not need to be
explicitly called.

=head2 $rpc->setTransport($transport)

This sets the session transport protocol to I<$transport>.  Currently,
the only supported transport protocol is C<SSH>.

If the module specified by I<$transport> cannot be loaded, the callto
I<setTransport> will I<croak>.

=head2 $rpc->setDebug($debug)

This sets the the debugging state of the session to I<$debug>.  The
supported values for I<$debug> can be either C<0> (to disable
debugging) or C<1> (to enable debugging).

=head2 $rpc->setTimeout($timeout)

This sets the session timeout for individual operations to I<$timeout> seconds.
The value for I<$timeout> can be fractional (e.g. C<4.75>) or it can be
an integral number of seconds.  The default timeout is C<0> seconds which
means to wait forever for each operation to complete.

=head2 $rpc->getErrorCode()

This returns the last error code for the session.  An error can be one
of the following integers:

=over 4

=item -1000 Cisco::EEM::RPC::Session::EBADXML

I<Error parsing XML response>

=item -999 Cisco::EEM::RPC::Session::EINVALIDXML

I<XML response is not valid>

=item 0 Cisco::EEM::RPC::Session::EOK

I<No error>

=item 1 Cisco::EEM::RPC::Session::EUNKNOWN

I<Unknown error insided Embedded Event Manager>

=item 2 Cisco::EEM::RPC::Session::ESYSERR

I<Error from operating system>

=item 3 Cisco::EEM::RPC::Session::ENOTSUPPORTED

I<Requested function is not support>

=item 4 Cisco::EEM::RPC::Session::EINITONE

I<fm_init() is not yet done, or done twice>

=item 5 Cisco::EEM::RPC::Session::ECONNECT

I<Could not connect to Embedded Event Manager server>

=item 6 Cisco::EEM::RPC::Session::EBADEVENTTYPE

I<Unknown Embedded Event Manager event type>

=item 7 Cisco::EEM::RPC::Session::ENOSUCHKEY

I<Could not find key>

=item 8 Cisco::EEM::RPC::Session::EDUPLICATEKEY

I<Duplicate application info key>

=item 9 Cisco::EEM::RPC::Session::EMEMORY

I<Insufficient memory for request>

=item 10 Cisco::EEM::RPC::Session::ECORRUPT

I<Embedded Event Manager API context is corrupt>

=item 11 Cisco::EEM::RPC::Session::ENOSUCHESID

I<Unknown event specification ID>

=item 12 Cisco::EEM::RPC::Session::ENOSUCHEID

I<Unknown event ID>

=item 13 Cisco::EEM::RPC::Session::ENOEVENTACTIVE

I<No Embedded Event Manager event is active>

=item 14 Cisco::EEM::RPC::Session::ENOSUCHACTION

I<Unknown action type>

=item 15 Cisco::EEM::RPC::Session::ENOSUCHSYSINFO

I<Unknown sys info type>

=item 16 Cisco::EEM::RPC::Session::EBADFMPPTR

I<Bad pointer to fm_p data structure>

=item 17 Cisco::EEM::RPC::Session::EBADADDRESS

I<Bad API control block address>

=item 18 Cisco::EEM::RPC::Session::EDATAUNAVAIL

I<Application data is unavailable>

=item 19 Cisco::EEM::RPC::Session::EREGERROR

I<Regular expression compliation error>

=item 20 Cisco::EEM::RPC::Session::ENOPUBDATA

I<No publish data to send>

=item 21 Cisco::EEM::RPC::Session::EDUPLICATEES

I<Duplicate event specification>

=item 22 Cisco::EEM::RPC::Session::ENULLPTR

I<Event detector internal error - pointer is NULL>

=item 23 Cisco::EEM::RPC::Session::EBADOCCURS

I<Number of ocurrences exceeded>

=item 24 Cisco::EEM::RPC::Session::ETIMERCREAT

I<Timer create error>

=item 25 Cisco::EEM::RPC::Session::ESUBSEXCEED

I<Number of subscribers exceeded>

=item 26 Cisco::EEM::RPC::Session::ESUBSIDXINV

I<Invalid subscriber index>

=item 27 Cisco::EEM::RPC::Session::ETMDELAYZR

I<Zero delay time>

=item 28 Cisco::EEM::RPC::Session::ENOTREGISTERED

I<Request for event spec that is unregistered>

=item 29 Cisco::EEM::RPC::Session::ECTBADEXITOPER

I<Bad counter exit threshold operator>

=item 30 Cisco::EEM::RPC::Session::ECTBADOPER

I<Bad counter threshold operator>

=item 31 Cisco::EEM::RPC::Session::EPUBENTALLOC

I<Publish entry allocation error>

=item 32 Cisco::EEM::RPC::Session::EPUBENTADD

I<Publish entry add into list error>

=item 33 Cisco::EEM::RPC::Session::ECTNOTSET

I<Counter is not set>

=item 34 Cisco::EEM::RPC::Session::EMAXLEN

I<Maximum length exceeded>

=item 35 Cisco::EEM::RPC::Session::EWRONGTYPE

I<Data element type doesn't match catalog>

=item 36 Cisco::EEM::RPC::Session::ENOTINCATALOG

I<Data element not in catalog>

=item 37 Cisco::EEM::RPC::Session::ENOSNMPDATA

I<Can't retrieve data from SNMP>

=item 38 Cisco::EEM::RPC::Session::EWRONGINDEX

I<Index out of catalog range>

=item 39 Cisco::EEM::RPC::Session::EWRONGPARM

I<Data element parameter is not valid>

=item 40 Cisco::EEM::RPC::Session::ESTBADEXITOPER

I<Bad stats exit threshold operator>

=item 41 Cisco::EEM::RPC::Session::ESTBADOPER

I<Bad stats threshold operator>

=item 42 Cisco::EEM::RPC::Session::ESTBADCOMBOPER

I<Bad stats exit combination operator>

=item 43 Cisco::EEM::RPC::Session::EBADLENGTH

I<Bad API length>

=item 44 Cisco::EEM::RPC::Session::EHISTEMPTY

I<History list is empty>

=item 45 Cisco::EEM::RPC::Session::ESEQNUM

I<Sequence or workset number out of sync>

=item 46 Cisco::EEM::RPC::Session::EREGEMPTY

I<Registration list is empty>

=item 47 Cisco::EEM::RPC::Session::EMETENTALLOC

I<Metric entry allocation error>

=item 48 Cisco::EEM::RPC::Session::EMETENTADD

I<Metric entry add into list error>

=item 49 Cisco::EEM::RPC::Session::ESTBADTYPE

I<Bad stats value type>

=item 50 Cisco::EEM::RPC::Session::EBADOFFSET

I<Invalid record offset value>

=item 51 Cisco::EEM::RPC::Session::ESTATSTYP

I<Invalid statistics data type>

=item 52 Cisco::EEM::RPC::Session::ECONFIG

I<Embedded Event Manager configuration error>

=item 53 Cisco::EEM::RPC::Session::ESTRLNEXCD

I<String buffer length exceeded>

=item 54 Cisco::EEM::RPC::Session::EFDUNAVAIL

I<Connection to event detector unavailable>

=item 55 Cisco::EEM::RPC::Session::ENOPRIORVER

I<Prior version not available>

=item 56 Cisco::EEM::RPC::Session::EFDCONNERR

I<Event detector connection error>

=item 57 Cisco::EEM::RPC::Session::ETIMEOUT

I<Timeout error>

=item 58 Cisco::EEM::RPC::Session::EBADSUBEVTCOMBOP

I<Bad subevent spec combination operator>

=item 59 Cisco::EEM::RPC::Session::EBADSUBEVTYP

I<Bad subevent spec type>

=item 60 Cisco::EEM::RPC::Session::EBADSUBEVTOP

I<Bad subevent operator>

=item 61 Cisco::EEM::RPC::Session::EWDEVENT

I<Inconsistent node names in WDSysMon event spec>

=item 62 Cisco::EEM::RPC::Session::ENDOFAPI

I<UNUSED>

=item 63 Cisco::EEM::RPC::Session::EMOREDATA

I<More data to send in response to poll>

=item 64 Cisco::EEM::RPC::Session::ENODATA

I<No data to send in response to poll>

=item 65 Cisco::EEM::RPC::Session::EWATCHQUEUE

I<Failure in watched queue>

=item 66 Cisco::EEM::RPC::Session::ECNSEVENTAGENT

I<Unable to connect to CNS event agent>

=item 67 Cisco::EEM::RPC::Session::ESWITCHHARDWARE

I<Unable to switch hardware>

=item 68 Cisco::EEM::RPC::Session::EENQUEUE

I<Unable to enqueue message>

=item 69 Cisco::EEM::RPC::Session::EWATCHBOOL

I<Failure in watched boolean>

=item 70 Cisco::EEM::RPC::Session::EWATCHSEMAPHORE

I<Failure in watched semaphore>

=item 71 Cisco::EEM::RPC::Session::EFOPEN

I<Error opening file or directory>

=item 72 Cisco::EEM::RPC::Session::EGETDENTS

I<Error getting directory entries>

=item 73 Cisco::EEM::RPC::Session::EFSTAT

I<Error getting file statistics>

=item 74 Cisco::EEM::RPC::Session::EFREMOVE

I<Error removing files>

=item 75 Cisco::EEM::RPC::Session::EFREAD

I<Error reading file>

=item 76 Cisco::EEM::RPC::Session::EFCREATE

I<Error creating file>

=item 77 Cisco::EEM::RPC::Session::ECHKPT

I<Error checkpointing>

=item 78 Cisco::EEM::RPC::Session::ESMTPCONNECT

I<Error in connecting to SMTP server>

=item 79 Cisco::EEM::RPC::Session::ESMTPCHKREPLY

I<Error in reply from SMTP server>

=item 80 Cisco::EEM::RPC::Session::ESMTPREAD

I<Error in reading from SMTP server>

=item 81 Cisco::EEM::RPC::Session::ESMTPWRITE

I<Error in writing to SMTP server>

=item 82 Cisco::EEM::RPC::Session::ESMTPDISCONNECT

I<Error in disconnecting from SMTP server>

=item 83 Cisco::EEM::RPC::Session::ENOMORETTY

I<No TTY lines available, minimum of two required by EEM>

=item 84 Cisco::EEM::RPC::Session::EBADCHECKSUM

I<Checksums do not match>

=item 85 Cisco::EEM::RPC::Session::ERMI

I<RMI API returned failure>

=item 86 Cisco::EEM::RPC::Session::ENOTRACK

I<No tracking object with given track number>

=item 87 Cisco::EEM::RPC::Session::EPARMSEXCEED

I<Maximum number of parameters exceeded>

=item 88 Cisco::EEM::RPC::Session::EPARMSINVALID

I<Invalid parameters>

=item 89 Cisco::EEM::RPC::Session::EJOBIDINVALID

I<Invalid job ID>

=back

=head2 $rpc->getErrorMsg()

This returns the error message associated with the last error that
occurred within the session.  If no error has occurred, this will
return C<undef>.

=head2 $rpc->getResult()

This returns the result string from the last invoked EEM RPC
policy.  If a policy has not been invoked, or an error occurred,
this method will return C<undef>.

=head2 $rpc->getRawResult()

This returns the raw SOAP XML result string from the last invoked
EEM RPC policy.  If a policy has not been invoked, or an error
occurred, this method will return C<undef>.

=head2 $rpc->getTransport()

This returns the current transport module name.

=head2 $rpc->getTransportClass()

This returns a transport class object.  The underlying transport can
be modified by using this object.  Use of this method is discouraged unless
you know what you are doing.  If the transport session has not been
initialized, this method will return C<undef>.

=head2 $rpc->login([$user, $pass])

This method logs into the device specified by I<$host> when the
session was instantiated.  If I<$user> and I<$pass> are not
specified, then the username and password from the initial
I<%attrs> hash are used.  I<login> does not need to be explictly
called if the username and password attributes were passed to
the constructor.

This method will I<croak> if the specified transport protocol is
invalid, or if the connection to the device fails.  Therefore,
calls to I<login> should be wrapped in I<eval> to prevent
the application from terminating.

=head2 $rpc->invoke($policy)

This method executes the I<Cisco::EEM::RPC::Policy> as specified by the
I<$policy> argument.  I<invoke> will return C<1> on success, and
C<0> if an error occurs.

This method may be called without explicitly calling I<login> if
the usernamd password attributes were passed to the session
constructor.  If I<invoke> is called without explicitly calling
I<login> it may I<croak> if a connection to the device cannot
be established.

=head2 $rpc->close()

This method closes the session, and releases any socket connections.
By calling I<close> the last result and error values are not
overwritten, and can still be safely retrieved.

=head1 AUTHOR

Joe Marcus Clarke, jclarke@cisco.com

=head1 COPYRIGHT

Copyright (c) 2007 Joe Marcus Clarke <jclarke@cisco.com>
All rights reserved.

This code is distributed under the BSD License.  See the LICENSE.txt file
for the full license text.

=cut
