package Cisco::EEM::RPC::Transport::SSH;

use strict;
use Carp qw(croak);
use Net::SSH::Perl;
use Net::SSH::Perl::Constants qw(:protocol :compat :hosts);
use vars qw(@ISA);
@ISA = qw(Net::SSH::Perl);

# We need to override some of the methods in Net::SSH::Perl to work with Cisco
# IOS.  Specifically, Cisco IOS only supports the opening of one SSHv2 channel.
# Therefore, we only open the eem_rpc channel.

sub new {
        my $class = shift;
        my $host  = shift;
        my %attrs = @_;

        $attrs{'protocol'} = 2;

        if ($attrs{'timeout'} > 0) {
                $SIG{'ALRM'} =
                    sub { croak __PACKAGE__ . ": Connection timed out"; };
                alarm $attrs{'timeout'};
        }
        my $ssh = $class->SUPER::new($host, %attrs);
        if ($attrs{'timeout'} > 0) {
                alarm 0;
                $SIG{'ALRM'} = 'DEFAULT';
        }
        if (defined($attrs{'timeout'})) {
                $ssh->_set_timeout($attrs{'timeout'});
        }
        $ssh;
}

# This is taken from Net::SSH::Perl, but modified to support our overridden
# code.
sub set_protocol {
        my $ssh            = shift;
        my $proto          = shift;
        my $protocol_class = "";

        if ($proto == PROTOCOL_SSH2) {
                $protocol_class = "Cisco::EEM::RPC::Transport::SSH::CiscoSSH2";
        } else {
                croak __PACKAGE__ . ": EEM RPC only supports SSHv2";
        }
        $ssh->{use_protocol} = $proto;

        (my $lib = $protocol_class . ".pm") =~ s!::!/!g;
        require $lib;
        bless $ssh, $protocol_class;

        $ssh->debug($protocol_class->version_string);
        $ssh->_proto_init;
}

1;
