package Cisco::EEM::RPC::Transport::SSH::CiscoSSH2;

use strict;
use Cisco::EEM::RPC::Transport;
use Net::SSH::Perl::SSH2;
use Net::SSH::Perl::Constants qw( :protocol :msg2
    CHAN_INPUT_CLOSED CHAN_INPUT_WAIT_DRAIN );
use Carp qw(croak);
use vars qw(@ISA);
@ISA = qw(Cisco::EEM::RPC::Transport Net::SSH::Perl::SSH2);

use constant EEM_RPC_SUBSYS  => 'eem_rpc';
use constant EEM_RPC_TRAILER => ']]>]]>';

sub login {
        my $ssh = shift;
        $ssh->Net::SSH::Perl::login(@_);
        $ssh->_login or $ssh->fatal_disconnect("Failed to login successfully");

        $ssh->debug("Login completed, opening EEM RPC session.");
        my $cmgr    = $ssh->channel_mgr;
        my $channel = $ssh->_session_channel;
        $ssh->{eem_channel} = $channel;
        $channel->open;

        $channel->register_handler(SSH2_MSG_CHANNEL_OPEN_CONFIRMATION,
                sub {
                        my ($channel, $packet) = @_;
                        my $r_packet = $channel->request_start("subsystem", 1);
                        $r_packet->put_str(EEM_RPC_SUBSYS);
                        $r_packet->send;
                        $channel->send_data(EEM_RPC_TRAILER);
                        $channel->drain_outgoing;
                }
        );

        $channel->register_handler(SSH2_MSG_CHANNEL_REQUEST,
                sub {
                        my ($channel, $packet) = @_;
                        my $rtype = $packet->get_str;
                        my $reply = $packet->get_int8;
                        if ($rtype eq "exit-status") {
                                $channel->{ssh}->fatal_disconnect("Subsystem "
                                            . EEM_RPC_SUBSYS
                                            . " not allowed by the server");

                                $channel->{ssh}->break_client_loop;

                        }

                        if ($reply) {
                                my $r_packet =
                                    $channel->{ssh}
                                    ->packet_start(SSH2_MSG_CHANNEL_SUCCESS);
                                $r_packet->put_int($channel->{remote_id});
                                $r_packet->send;
                        }

                }
        );

        $cmgr->register_handler(SSH2_MSG_CHANNEL_FAILURE,
                sub {
                        my ($channel, $packet) = @_;
                        if ($packet->type == SSH2_MSG_CHANNEL_FAILURE) {
                                $channel->{ssh}->fatal_disconnect("Subsystem "
                                            . EEM_RPC_SUBSYS
                                            . " not allowed by the server");
                        }
                        $channel->{ssh}->break_client_loop;
                }
        );

        $cmgr->register_handler(SSH2_MSG_CHANNEL_SUCCESS,
                sub {
                        my ($channel, $packet) = @_;
                        if ($packet->type == SSH2_MSG_CHANNEL_SUCCESS) {
                                $ssh->debug(
                                        "Received SSH2_MSG_CHANNEL_SUCCESS from server; however "
                                            . EEM_RPC_SUBSYS
                                            . " subsystem may still not be available"
                                );
                        }
                }
        );

        my $h = $ssh->{client_handlers};
        if (my $r = $h->{stdout}) {
                $channel->register_handler("_output_buffer", $r->{code},
                        @{$r->{extra}});
        } else {
                $channel->register_handler(
                        "_output_buffer",
                        sub {
                                $ssh->{stdout} .= $_[1]->bytes;
                                my $trailer = EEM_RPC_TRAILER;
                                if ($ssh->{stdout} =~ /$trailer\s*$/) {
                                        $_[0]->{ssh}->break_client_loop;
                                }
                        }
                );
        }
        if (my $r = $h->{stderr}) {
                $channel->register_handler("_extended_buffer", $r->{code},
                        @{$r->{extra}});
        } else {
                $channel->register_handler(
                        "_extended_buffer",
                        sub {
                                $ssh->{stderr} .= $_[1]->bytes;
                        }
                );
        }

        $ssh->debug("Done preparing EEM RPC channel.");
        $ssh->client_loop;
}

sub invoke {
        my $ssh       = shift;
        my ($request) = @_;
        my $cmgr      = $ssh->channel_mgr;
        my $channel   = $ssh->{eem_channel};

        $request .= EEM_RPC_TRAILER;

        $ssh->_clear_buffers;

        $ssh->debug("Sending EEM RPC request: '$request'");
        $channel->send_data($request);

        $ssh->debug("Entering interactive session.");
        $ssh->client_loop;

        my $trailer = EEM_RPC_TRAILER;

        $ssh->debug("invoke: stdout buffer: " . $ssh->{stdout});
        $ssh->debug("invoke: stderr buffer: " . $ssh->{stderr});

        my $result = $ssh->{stdout};
        $result =~ s/$trailer\s*$//;

        return $result;
}

sub client_loop {
        my $ssh  = shift;
        my $cmgr = $ssh->channel_mgr;

        my $h            = $cmgr->handlers;
        my $select_class = $ssh->select_class;

    CLOOP:
        $ssh->{_cl_quit_pending} = 0;
        while (!$ssh->_quit_pending) {
                while (my $packet = Net::SSH::Perl::Packet->read_poll($ssh)) {
                        if (my $code = $h->{$packet->type}) {
                                $code->($cmgr, $packet);
                        } else {
                                $ssh->debug("Warning: ignore packet type "
                                            . $packet->type);
                        }
                }
                last if $ssh->_quit_pending;

                $cmgr->process_output_packets;

                my $rb = $select_class->new;
                my $wb = $select_class->new;
                $rb->add($ssh->sock);
                $cmgr->prepare_channels($rb, $wb);

                my $oc = grep { defined } @{$cmgr->{channels}};
                last unless $oc > 0;    # Cisco IOS only gives us one channel

                my @select_list =
                    $select_class->select($rb, $wb, undef,
                        $ssh->{session}{timeout});
                if (!@select_list) {
                        croak __PACKAGE__
                            . ": Timeout attempting to read from SSH socket (no data received for "
                            . $ssh->{session}{timeout}
                            . " seconds)";
                }
                my ($rready, $wready) = @select_list;
                $cmgr->process_input_packets($rready, $wready);

                for my $a (@$rready) {
                        if ($a == $ssh->{session}{sock}) {
                                my $buf;
                                my $len = sysread $a, $buf, 8192;
                                $ssh->break_client_loop if $len == 0;
                                ($buf) = $buf =~
                                    /(.*)/s;  ## Untaint data. Anything allowed.
                                $ssh->incoming_data->append($buf);
                        }
                }
        }
}

sub _clear_buffers {
        my $ssh = shift;

        $ssh->{stdout} = "";
        $ssh->{stderr} = "";
}

sub _set_timeout {
        my $ssh     = shift;
        my $timeout = shift;

        $ssh->{session}{timeout} = $timeout;
}

sub close {
        my $ssh = shift;

        close($ssh->{session}{sock});
        close($ssh->sock);
}

1;
