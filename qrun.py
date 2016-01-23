#!/usr/bin/env python

# Written by: Vincenzo Maffione <v.maffione@gmail.it>

import re
import os
import argparse
import subprocess


def cmdexe(cmdstring, print_stderr=True):
    x = None if print_stderr else subprocess.PIPE
    return subprocess.check_output(cmdstring.split(), stderr=x)


def get_backend_ifname(args, i):
    if args.backend_type[i] == 'netmap':
        return 'vale%d:%d' % (args.br_idx[i], args.idx[i])

    return args.backend_type[i] + '%d_%d' % (args.br_idx[i], args.idx[i])


description = "Python script to launch QEMU VMs"
epilog = "2015 Vincenzo Maffione"

argparser = argparse.ArgumentParser(description = description,
                                    epilog = epilog)
argparser.add_argument('--dry-run', action='store_true',
                       help = "Only show the built QEMU command line")
argparser.add_argument('--install-from-iso',
                       help = "Path to the installation ISO", type = str,
                       default = '')
argparser.add_argument('-o', '--vm-output-mode',
                       help = "How to access VM console I/O", type = str,
                       choices = ['window', 'stdio', 'none'],
                       default = 'window')
argparser.add_argument('-p', '--ssh-base-port',
                       help = "SSH forwarding port",
                       type = int, default = 20000)
argparser.add_argument('-i', '--image',
                       help = "Path to the VM disk image", type = str)
argparser.add_argument('--num-cpus',
                       help = "Number of CPUs ofthe VM",
                       type = int, default = 2)
argparser.add_argument('--memory',
                       help = "Size of the VM memory (e.g. 256M, 2G)",
                       type = str, default = '2G')
argparser.add_argument('--temp', dest = 'temp_mode',
                       action='store_true',
                       help = "Enable non persistent disk mode")
argparser.add_argument('-m', '--mgmt-idx', type = int,
                       help = "An index for the VM, to be used for the "
                              "management port",
                       default = 1)
argparser.add_argument('--mgmt-nic',
                       help = "NIC model to use for mgmt", type = str,
                       choices = ['e1000', 'virtio-net-pci', 'pcnet',
                                  'ne2k_pci', 'rtl8139', 'e1000-paravirt'],
                       default = 'e1000')
argparser.add_argument('-n', '--idx', action='append',
                       help = "Port index to be used with TAP and VALE",
                       default = [])
argparser.add_argument('--br-idx', action='append',
                       help = "Bridge index to be used with TAP and VALE",
                       type = int, default = [])
argparser.add_argument('-b', '--backend-type', action='append',
                       help = "Network backend", type = str,
                       choices = ['tap', 'netmap'],
                       default = [])
argparser.add_argument('-f', '--frontend-type', action='append',
                       help = "Network frontend", type = str,
                       choices = ['e1000', 'virtio-net-pci', 'pcnet',
                                  'ne2k_pci', 'rtl8139', 'e1000-paravirt',
                                  'ptnet-pci'],
                       default = [])
argparser.add_argument('--no-bridging', dest='bridging', action='store_false',
                       help = "When TAP backend is used, don't attach it to a bridge")
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
argparser.add_argument('--passthrough', action='store_true',
                       help = "Enable netmap passthrough optimization")
argparser.add_argument('--vmpi', action='store_true',
                       help = "Add a VMPI device")
argparser.add_argument('--kernel',
                       help = "Path to the kernel to be used by the VM "
                              "(direct boot mode)", type = str)
argparser.add_argument('--initramfs',
                       help = "Path to the initramfs image to be used by the "
                              "VM (direct boot mode)", type = str)
argparser.add_argument('--console-tcp', action='store_true',
                       help = "Redirect serial console to TCP port")
argparser.add_argument('--console-base-port', type = int,
                       help = "Base TCP port to redirect serial console to",
                       default = 30000)
argparser.add_argument('--no-mgmt', action='store_false', dest='mgmtnet',
                       help = "Don't add management network")

args = argparser.parse_args()

# Validate append integer parameters
for i in range(len(args.idx)):
    try:
        idx = int(args.idx[i])
        args.idx[i] = idx
    except ValueError:
        argparser.error('argument --idx: invalid int value %s' % idx)

for i in range(len(args.br_idx)):
    try:
        idx = int(args.br_idx[i])
        args.br_idx[i] = idx
    except ValueError:
        argparser.error('argument --br-idx: invalid int value %s' % idx)

# Complete append lists
num_backends = max(len(args.idx), len(args.br_idx), len(args.backend_type),
                   len(args.frontend_type))

if num_backends > 0 and len(args.idx) == 0:
    args.idx.append(args.mgmt_idx)
while len(args.idx) < num_backends:
    args.idx.append(args.idx[-1] + 1)

if num_backends > 0 and len(args.br_idx) == 0:
    args.br_idx.append(1)
while len(args.br_idx) < num_backends:
    args.br_idx.append(args.br_idx[-1])

while len(args.backend_type) < num_backends:
    args.backend_type.append('tap')

while len(args.frontend_type) < num_backends:
    args.frontend_type.append('e1000')

#print(args)

if args.install_from_iso:
    args.temp = False
    args.vm_output_mode = 'window'

try:
    cmdline = 'qemu-system-x86_64'
    if args.image:
        cmdline += ' %s' % args.image

    if args.kernel:
        cmdline += ' -kernel %s' % args.kernel
        cmdline += ' -append "console=ttyS0"'
    if args.initramfs:
        cmdline += ' -initrd %s' % args.initramfs

    if args.kvm:
        cmdline += ' -enable-kvm'
    cmdline += ' -smp %d' % args.num_cpus
    cmdline += ' -m %s' % args.memory

    if args.console_tcp:
        args.vm_output_mode = 'none'

    cmdline += ' -vga std'
    if args.vm_output_mode == 'stdio':
        cmdline += ' -nographic'
    elif args.vm_output_mode == 'none':
        cmdline += ' -display none'
    elif args.vm_output_mode == 'window':
        pass

    if args.temp_mode:
        cmdline += ' -snapshot'

    if args.install_from_iso:
        cmdline += ' -cdrom %s' % args.install_from_iso
        cmdline += ' -boot order=dc'

    if args.console_tcp:
        cmdline += ' -serial tcp:127.0.0.1:%d,server,nowait' %\
                     (args.console_base_port + args.mgmt_idx)

    if args.mgmtnet:
        # Add management interface with netuser backend
        cmdline += ' -device %s,netdev=mgmt,mac=00:AA:BB:CC:%02x:99' % (args.mgmt_nic, args.mgmt_idx)
        cmdline += ' -netdev user,id=mgmt,hostfwd=tcp::%d-:22' \
                    % (args.ssh_base_port + args.mgmt_idx)

    for i in range(num_backends):
        backend_ifname = get_backend_ifname(args, i)

        # Add data interface
        cmdline += ' -device %s,netdev=data%d,mac=00:AA:BB:CC:%02x:%02x' \
                    % (args.frontend_type[i], args.idx[i], args.mgmt_idx, args.idx[i])
        if args.frontend_type[i] in ['virtio-net-pci', 'e1000-paravirt']:
            cmdline += ',ioeventfd=%s' % ('on' if args.ioeventfd else 'off',)
        if args.frontend_type[i] in ['e1000', 'e1000-paravirt']:
            cmdline += ',mitigation=%s' % ('on' if args.interrupt_mitigation else 'off',)
        if args.frontend_type[i] in ['virtio-net-pci']:
            cmdline += ',mrg_rxbuf=%s' % ('on' if args.mrg_rx_bufs else 'off',)
            if args.num_queues > 1:
                cmdline += ',mq=on,vectors=%d' % 2*args.num_queues+1
                # enable multi-queuing into the guest using
                #         ethtool -L eth0 combined args.num_queues

        # Add data backend
        cmdline += ' -netdev %s,ifname=%s,id=data%d' % (args.backend_type[i], backend_ifname, args.idx[i])
        if args.frontend_type[i] in ['virtio-net-pci'] and args.backend_type[i] in ['tap']:
            cmdline += ',vhost=%s' % ('on' if args.vhost_net else 'off',)
        if args.backend_type[i] in ['tap']:
            cmdline += ',script=no,downscript=no'
            if args.num_queues > 1:
                cmdline += ',queues=%d' % args.num_queues
        if args.backend_type[i] in ['netmap']:
            if args.passthrough or args.frontend_type[i] in ['ptnet-pci']:
                cmdline += ',passthrough=on'

    if args.dry_run:
        print(cmdline)
        exit(0)

    for i in range(num_backends):
        backend_ifname = get_backend_ifname(args, i)

        if args.backend_type[i] == 'tap':
            if args.bridging:
                try:
                    cmdexe('sudo brctl addbr br%02d' % args.br_idx[i], False)
                    cmdexe('sudo ip link set br%02d up' % args.br_idx[i])
                except:
                    # They bridge may already exist
                    pass

            cmdexe('sudo ip tuntap add mode tap name %s' % backend_ifname)
            cmdexe('sudo ip link set %s up' % backend_ifname)

            if args.bridging:
                cmdexe('sudo brctl addif br%02d %s' % (args.br_idx[i], backend_ifname))

    try:
        subprocess.check_call(cmdline, shell=True)
    except:
        print('QEMU terminated with an exception')

    for i in range(num_backends):
        backend_ifname = get_backend_ifname(args, i)

        if args.backend_type[i] == 'tap':
            cmdexe('sudo ip link set %s down' % backend_ifname)

            if args.bridging:
                cmdexe('sudo brctl delif br%02d %s' % (args.br_idx[i], backend_ifname))

            cmdexe('sudo ip tuntap del mode tap name %s' % backend_ifname)

except subprocess.CalledProcessError as e:
    print(e.output)

except Exception as e:
    print(e)
