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
    if args.backend_type[i] in ['netmap', 'netmap-pipe-master',
                                'netmap-pipe-slave']:
        if args.netmap[i] == 'vale':
            ifname = 'vale%d:%d' % (args.br_idx[i], args.idx[i])
        else:
            ifname = args.netmap[i]

        if args.backend_type[i] == 'netmap-pipe-master':
            return ifname + '{1'

        if args.backend_type[i] == 'netmap-pipe-slave':
            return ifname + '}1'

        return ifname

    return args.backend_type[i] + '%d_%d' % (args.br_idx[i], args.idx[i])


def get_backend_name(args, i):
    if args.backend_type[i] in ['netmap', 'netmap-pipe-master',
                                'netmap-pipe-slave']:
        return 'netmap'

    if args.backend_type[i] in ['socket-listen', 'socket-connect']:
        return 'socket'

    return args.backend_type[i]


def sysfs_write(filename, s):
    print("echo \"%s\" > %s" % (s, filename))
    sysf = open(filename, 'w')
    sysf.write(s)
    sysf.close()


# Get the name of the current driver bound to @pcidev
def pci_driver_name(pcidev):
    try:
        cwd = os.getcwd()
        os.chdir("/sys/bus/pci/devices/0000:%s/driver" % pcidev)
        dricwd = os.getcwd()
        os.chdir(cwd)
    except:
        print("Cannot find PCI device %s on the PCI subsystem" % pcidev)
        quit(1)

    return os.path.basename(os.path.normpath(dricwd))


# Unbind the given host PCI device from its current driver
# and bind it to the stub PCI driver
def pci_driver_unbind(pcidev):
    try:
        out = subprocess.check_output(["lspci", "-n"])
        out = out.decode('ascii').split('\n')
    except:
        print("Failed to execute 'lspci' command")
        quit(1)

    out = [elem.strip() for elem in out]
    vendor = None
    devid = None
    for elem in out:
        columns = elem.split()
        if len(columns) >= 3 and columns[0] == pcidev:
            # Found
            vendor, devid = columns[2].split(":")
            break

    if vendor is None or devid is None:
        print("Cannot find PCI device %s on the PCI subsystem" % pcidev)
        quit(1)

    cmdexe("sudo modprobe pci_stub")

    try:
        sysfs_write("/sys/bus/pci/drivers/pci-stub/new_id",
                    "%s %s" % (vendor, devid))
        sysfs_write("/sys/bus/pci/devices/0000:%s/driver/unbind" % pcidev,
                    "0000:%s" % pcidev)
        sysfs_write("/sys/bus/pci/drivers/pci-stub/bind",
                    "0000:%s" % pcidev)
    except Exception as e:
        print(e)
        print("Failed to unbind PCI device %s from its driver" % pcidev)
        quit(1)

    print("PCI device with vendor %s and devid %s unbound from "\
            "its driver" % (vendor, devid))


def pci_driver_rebind(pcidev, driver):
    try:
        sysfs_write("/sys/bus/pci/drivers/%s/bind" % driver,
                    "0000:%s" % pcidev)
    except Exception as e:
        print(e)
        print("Failed to rebind PCI device %s to driver %s" % (pcidev, driver))


description = "Python script to launch QEMU VMs"
epilog = "2015 Vincenzo Maffione"

argparser = argparse.ArgumentParser(description = description,
                                    epilog = epilog)
argparser.add_argument('--dry-run', action='store_true',
                       help = "Only show the generated QEMU command line")
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
                       help = "Number of CPUs for the VM",
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
                       choices = ['nat', 'tap', 'netmap', 'netmap-pipe-master',
                                  'netmap-pipe-slave', 'socket-listen',
                                  'socket-connect', 'vhost-user'],
                       default = [])
argparser.add_argument('-f', '--frontend-type', action='append',
                       help = "Network frontend", type = str,
                       choices = ['e1000', 'virtio-net-pci', 'pcnet',
                                  'ne2k_pci', 'rtl8139', 'e1000-paravirt',
                                  'ptnet-pci'],
                       default = [])
argparser.add_argument('--netmap', action='append',
                       help = "Name of netmap port to be nm_open()ed", type = str,
                       default = [])
argparser.add_argument('--unix-socket', action='append',
                       help = "Name of the unix socket to be used with vhost-user backend",
                       type = str, default = [])
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
argparser.add_argument('--kernel',
                       help = "Path to the kernel to be used by the VM "
                              "(direct boot mode)", type = str)
argparser.add_argument('--initramfs',
                       help = "Path to the initramfs image to be used by the "
                              "VM (direct boot mode)", type = str)
argparser.add_argument('--console-tcp', action='store_true',
                       help = "Redirect serial console to TCP port. "
                              "Deprecated, use --console-file instead")
argparser.add_argument('--console-base-port', type = int,
                       help = "Base TCP port to redirect serial console to",
                       default = 30000)
argparser.add_argument('--console-file', type = str,
                       help = "Redirect serial console to local file. "
                              "Deprecated, use --console-file instead")
argparser.add_argument('--no-mgmt', action='store_false', dest='mgmtnet',
                       help = "Don't add management network")
argparser.add_argument('--hostfwd', type = str, action='append', default = [],
                       help='Additional port forwarding <HOSTPORT:VMPORT>')
argparser.add_argument('--nested-kvm', action='store_true',
                       help = "Enable nested KVM for the VM")
argparser.add_argument('--device',
                       help = "Additional device", type = str)
argparser.add_argument('--plus',
                       help = "Additional command line arguments (can be anything)",
                       type = str)
argparser.add_argument('--pci-passthrough',
                       help = "Passthrough an host PCI device xx:yy.z to the VM",
                       type = str)

args = argparser.parse_args()

# Validate append parameters
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

while len(args.netmap) < num_backends:
    args.netmap.append('vale')

if args.kvm and not os.path.isdir('/sys/module/kvm_intel') and not os.path.isdir('/sys/module/kvm_amd'):
        print('KVM is not present')
        quit(1)

if args.nested_kvm:
    try:
        en_kvm = open('/sys/module/kvm_intel/parameters/nested', 'r').read().strip().upper()
    except:
        en_kvm = 'N'

    try:
        en_amd = open('/sys/module/kvm_amd/parameters/nested', 'r').read().strip().upper()
    except:
        en_amd = 'N'

    if en_kvm != 'Y' and en_amd != 'Y':
        print('Nested KVM is not enabled')
        quit(1)

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

    if args.console_tcp or args.console_file:
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

    if args.console_file:
        cmdline += ' -serial file:%s' % (args.console_file)
    elif args.console_tcp:
        cmdline += ' -serial tcp:127.0.0.1:%d,server,nowait' %\
                     (args.console_base_port + args.mgmt_idx)

    if args.mgmtnet:
        # Add management interface with netuser backend
        cmdline += ' -device %s,netdev=mgmt,mac=00:AA:BB:CC:%02x:99' % (args.mgmt_nic, args.mgmt_idx)
        cmdline += ' -netdev user,id=mgmt,hostfwd=tcp::%d-:22' \
                    % (args.ssh_base_port + args.mgmt_idx)
        for hf in args.hostfwd:
            m = re.match(r'(\d+):(\d+)', hf)
            if m == None:
                print('Invalid hostfwd "%s"' % hf)
            else:
                hostport = int(m.group(1))
                guestport = int(m.group(2))
                cmdline += ',hostfwd=tcp::%d-:%d' % (hostport, guestport)

    # When vhost-user is used, add memory backend file object
    for i in range(num_backends):
        if args.backend_type[i] == 'vhost-user':
            cmdline += ' -numa node,memdev=mem0'\
                       ' -object memory-backend-file,id=mem0,size=%s,'\
                       'mem-path=/dev/hugepages,share=on' % args.memory
            break

    for i in range(num_backends):
        backend_ifname = get_backend_ifname(args, i)
        backend_name = get_backend_name(args, i)

        vars_dict = {'idx': args.idx[i], 'vmid': args.mgmt_idx,
                     'fe': args.frontend_type[i]}

        # Add data interface
        cmdline += ' -device %(fe)s,netdev=data%(idx)d,mac=00:AA:BB:CC:%(vmid)02x:%(idx)02x'\
                        % vars_dict
        if args.frontend_type[i] in ['virtio-net-pci', 'e1000-paravirt']:
            cmdline += ',ioeventfd=%s' % ('on' if args.ioeventfd else 'off',)

        if args.frontend_type[i] in ['e1000', 'e1000-paravirt']:
            cmdline += ',mitigation=%s' % ('on' if args.interrupt_mitigation else 'off',)

        if args.frontend_type[i] in ['virtio-net-pci']:
            cmdline += ',mrg_rxbuf=%s' % ('on' if args.mrg_rx_bufs else 'off',)
            if args.num_queues > 1:
                cmdline += ',mq=on,vectors=%d' % (2 * args.num_queues + 1)
                # enable multi-queuing into the guest using
                #         ethtool -L eth0 combined args.num_queues

        # Add data backend
        if args.backend_type[i] == 'nat':
            cmdline += ' -netdev user,net=10.79.%(idx)d.0/24,id=data%(idx)d' % vars_dict

        elif args.backend_type[i] in ['socket-listen', 'socket-connect']:
            cs = args.backend_type[i][7:]
            cmdline += ' -netdev socket,%s=127.0.0.1:%d,id=data%d' % (cs, 4000 + args.idx[i], args.idx[i])

        elif args.backend_type[i] == 'vhost-user':
            if args.frontend_type[i] != 'virtio-net-pci':
                print("vhost-user backend requires virtio-net-pci frontend")
                quit(1)

            if len(args.unix_socket) > 0:
                vars_dict['upath'] = args.unix_socket[0]
                args.unix_socket.pop(0)
            else:
                vars_dict['upath'] = '/var/run/vm%(vmid)d-%(idx)d.socket' % vars_dict

            cmdline += ' -chardev socket,id=char%(idx)d,path=%(upath)s,server'\
                        ' -netdev type=vhost-user,id=data%(idx)d,chardev=char%(idx)s'\
                        % vars_dict

        else:
            cmdline += ' -netdev %s,ifname=%s,id=data%d' % (backend_name, backend_ifname, args.idx[i])

        if args.frontend_type[i] in ['virtio-net-pci'] and args.backend_type[i] in ['tap']:
            cmdline += ',vhost=%s' % ('on' if args.vhost_net else 'off',)

        if args.backend_type[i] in ['tap']:
            cmdline += ',script=no,downscript=no'
            if args.num_queues > 1:
                cmdline += ',queues=%d' % (args.num_queues)

        if args.backend_type[i] in ['netmap', 'netmap-pipe-master', 'netmap-pipe-slave']:
            if args.passthrough or args.frontend_type[i] in ['ptnet-pci']:
                cmdline += ',passthrough=on'

        del vars_dict

    if args.device:
        cmdline += ' -device %s' % (args.device)

    if args.pci_passthrough:
        # PCI device must be in the form xx:yy.z, with exadecimal digits
        m = re.match(r'^[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F]$', args.pci_passthrough)
        if m is None:
            print("Invalid PCI device identifier '%s'" % args.pci_passthrough)
            quit(1)

        # Get the name of current driver
        pci_driver = pci_driver_name(args.pci_passthrough)

        # Unbind device from current driver
        pci_driver_unbind(args.pci_passthrough)
        cmdline += ' -device pci-assign,host=%s' % args.pci_passthrough

    if args.nested_kvm:
        cmdline += ' -cpu host'

    if args.plus:
        cmdline += ' %s' % args.plus

    if args.dry_run:
        print(cmdline)
        quit(1)

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

            cmd = 'sudo ip tuntap add mode tap name %s' % backend_ifname
            if args.num_queues > 1:
                cmd += ' multi_queue'
            cmdexe(cmd)
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

            cmd = 'sudo ip tuntap del mode tap name %s' % backend_ifname
            if args.num_queues > 1:
                cmd += ' multi_queue'
            cmdexe(cmd)

    if args.pci_passthrough:
        pci_driver_rebind(args.pci_passthrough, pci_driver)

except subprocess.CalledProcessError as e:
    print(e.output)

except Exception as e:
    print(e)
