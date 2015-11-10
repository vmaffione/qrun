#!/usr/bin/env python

# Written by: Vincenzo Maffione <v.maffione@gmail.it>

import re
import os
import argparse
import subprocess


def cmdexe(cmdstring, print_stderr=True):
    x = None if print_stderr else subprocess.PIPE
    return subprocess.check_output(cmdstring.split(), stderr=x)


def get_backend_ifname(args):
    if args.backend_type == 'vale':
        return args.backend_type + '%d:%d' % (args.br_idx, args.idx)

    return args.backend_type + '%d_%d' % (args.br_idx, args.idx)


description = "Python script to launch QEMU VMs"
epilog = "2015 Vincenzo Maffione"

argparser = argparse.ArgumentParser(description = description,
                                    epilog = epilog)
argparser.add_argument('--dry-run', action='store_true',
                       help = "Only show the build QEMU command line")
argparser.add_argument('--install-from-iso',
                       help = "Path to the installation ISO", type = str,
                       default = '')
argparser.add_argument('-o', '--vm-output-mode',
                       help = "How to access VM console I/O", type = str,
                       choices = ['window', 'stdio', 'none'],
                       default = 'window')
argparser.add_argument('-p', '--ssh-port',
                       help = "SSH forwarding port",
                       type = int, default = 20010)
argparser.add_argument('-i', '--image',
                       help = "Path to the VM image", type = str,
                       default = 'arch.qcow2')
argparser.add_argument('--num-cpus',
                       help = "Number of CPUs ofthe VM",
                       type = int, default = 2)
argparser.add_argument('-m', '--memory',
                       help = "Size of the VM memory (e.g. 256M, 2G)",
                       type = str, default = '2G')
argparser.add_argument('--temp', dest = 'temp_mode',
                       action='store_true',
                       help = "Enable non persistent disk mode")
argparser.add_argument('-n', '--idx',
                       help = "Port index to be used with TAP and VALE",
                       type = int, default = 1)
argparser.add_argument('--br-idx',
                       help = "Bridge index to be used with TAP and VALE",
                       type = int, default = 1)
argparser.add_argument('-b', '--backend-type',
                       help = "Network backend", type = str,
                       choices = ['tap', 'vale', 'none'],
                       default = 'tap')
argparser.add_argument('-f', '--frontend-type',
                       help = "Network frontend", type = str,
                       choices = ['e1000', 'virtio-net-pci', 'pcnet',
                                  'ne2k_pci', 'rtl8139', 'e1000-paravirt'],
                       default = 'e1000')
argparser.add_argument('--no-kvm', dest='kvm', action='store_false',
                       help = "Disable KVM, falling back to userspace emulation")
argparser.add_argument('--vhost-net', action='store_true',
                       help = "Enable vhost-net optimization")
argparser.add_argument('--no-mrg-rx-bufs', dest='mrg_rx_bufs', action='store_false',
                       help = "Disable virtio-net mergeable RX buffers")
argparser.add_argument('--no-ioeventfd', dest='ioeventfd', action='store_false',
                       help = "Disable ioeventfd optimization")
argparser.add_argument('--num-queues',
                       help = "Number of queues in a TAP device",
                       type = int, default = 1)
argparser.add_argument('--interrupt-mitigation', action='store_true',
                       help = "Enable NIC interrupt mitigation")
argparser.add_argument('--vmpi', action='store_true',
                       help = "Add a VMPI device")

args = argparser.parse_args()
#print(args)

if args.install_from_iso != '':
    args.temp = False
    args.vm_output_mode = 'window'

try:
    backend_ifname = get_backend_ifname(args)

    cmdline = 'qemu-system-x86_64'
    cmdline += ' %s' % args.image
    if args.kvm:
        cmdline += ' -enable-kvm'
    cmdline += ' -smp %d' % args.num_cpus
    cmdline += ' -m %s' % args.memory

    cmdline += ' -vga std'
    if args.vm_output_mode == 'stdio':
        cmdline += ' -nographic'
    elif args.vm_output_mode == 'none':
        cmdline += ' -display none'
    elif args.vm_output_mode == 'window':
        pass

    if args.temp_mode:
        cmdline += ' -snapshot'

    if args.install_from_iso != '':
        cmdline += ' -cdrom %s' % args.install_from_iso
        cmdline += ' boot order=dc'

    # Add management interface with netuser backend
    cmdline += ' -device e1000,netdev=mgmt,mac=00:AA:BB:CC:%02x:99' % args.idx
    cmdline += ' -netdev user,id=mgmt,hostfwd=tcp::%d-:22' % args.ssh_port

    if args.backend_type != 'none':
        # Add data interface
        cmdline += ' -device %s,netdev=data%d,mac=00:AA:BB:CC:%02x:01' \
                    % (args.frontend_type, args.idx, args.idx)
        if args.frontend_type in ['virtio-net-pci', 'e1000-paravirt']:
            cmdline += ',ioeventfd=%s' % ('on' if args.ioeventfd else 'off',)
        if args.frontend_type in ['e1000', 'e1000-paravirt']:
            cmdline += ',mitigation=%s' % ('on' if args.interrupt_mitigation else 'off',)
        if args.frontend_type in ['virtio-net-pci']:
            cmdline += ',mrg_rxbuf=%s' % ('on' if args.mrg_rx_bufs else 'off',)
            if args.num_queues > 1:
                cmdline += ',mq=on,vectors=%d' % 2*args.num_queues+1
                # enable multi-queuing into the guest using
                #         ethtool -L eth0 combined args.num_queues

        # Add data backend
        cmdline += ' -netdev %s,ifname=%s,id=data%d' % (args.backend_type, backend_ifname, args.idx )
        if args.frontend_type in ['virtio-net-pci'] and args.backend_type in ['tap']:
            cmdline += ',vhost=%s' % ('on' if args.vhost_net else 'off',)
        if args.backend_type in ['tap']:
            cmdline += ',script=no,downscript=no'
            if args.num_queues > 1:
                cmdline += ',queues=%d' % args.num_queues

    if args.dry_run:
        print(cmdline)
        exit(0)

    if args.backend_type == 'tap':
        try:
            cmdexe('sudo brctl addbr br%02d' % args.br_idx, False)
            cmdexe('sudo ip link set br%02d up' % args.br_idx)
        except:
            # They bridge may already exist
            pass
        cmdexe('sudo ip tuntap add mode tap name %s' % backend_ifname)
        cmdexe('sudo ip link set %s up' % backend_ifname)
        cmdexe('sudo brctl addif br%02d %s' % (args.br_idx, backend_ifname))

    try:
        subprocess.check_call(cmdline, shell=True)
    except:
        print('QEMU terminated with an exception')

    if args.backend_type == 'tap':
        cmdexe('sudo ip link set %s down' % backend_ifname)
        cmdexe('sudo brctl delif br%02d %s' % (args.br_idx, backend_ifname))
        cmdexe('sudo ip tuntap del mode tap name %s' % backend_ifname)

except subprocess.CalledProcessError as e:
    print(e.output)

except Exception as e:
    print(e)
