#!/usr/bin/env python

# Written by: Vincenzo Maffione <v.maffione@gmail.it>

import re
import os
import argparse
import subprocess


def cmdexe(cmdstring):
    return subprocess.check_output(cmdstring.split())


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
                       help = "Index port to be used with TAP and VALE",
                       type = int, default = 1)
argparser.add_argument('-b', '--backend-type',
                       help = "Network backend", type = str,
                       choices = ['tap', 'vale'],
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
argparser.add_argument('--no-mrg-rx-bufs', action='store_false',
                       help = "Disable virtio-net mergeable RX buffers")
argparser.add_argument('--no-ioeventfd', dest='ioeventfd', action='store_false',
                       help = "Disable ioeventfd optimization")
argparser.add_argument('--num-queues',
                       help = "Number of queues in a TAP device",
                       type = int, default = 1)
argparser.add_argument('--vmpi', action='store_true',
                       help = "Add a VMPI device")

args = argparser.parse_args()

print(args)

if args.install_from_iso != '':
    args.temp = False
    args.vm_output_mode = 'window'

try:
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

    if args.dry_run:
        print(cmdline)

except subprocess.CalledProcessError as e:
    print(e.output)

except Exception as e:
    print(e)
