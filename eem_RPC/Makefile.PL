# $Id: Makefile.PL,v 1.1 2007/09/09 18:55:14 marcus Exp $
#
use strict;
use 5.006;
use ExtUtils::MakeMaker qw(WriteMakefile);

my %prereq = (
        'Net::SSH::Perl' => '1.00',
        'XML::LibXML'    => 0,
);

WriteMakefile(
        NAME         => 'Cisco::EEM::RPC',
        DISTNAME     => 'Cisco-EEM-RPC',
        VERSION_FROM => 'lib/Cisco/EEM/RPC/Session.pm',
        PREREQ_PM    => \%prereq,
        AUTHOR       => 'Joe Marcus Clarke <jclarke@cisco.com>',
        ABSTRACT     => 'Perl interface to EEM RPC',
);
