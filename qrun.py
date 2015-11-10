#!/usr/bin/env python

# Written by: Vincenzo Maffione <v.maffione@gmail.it>

import re
import os
import pickle
import argparse
import subprocess


description = "Python script to launch QEMU VMs"
epilog = "2015 Vincenzo Maffione"

argparser = argparse.ArgumentParser(description = description,
                                    epilog = epilog)
argparser.add_argument('--dry-run', action='store_true',
                       help = "Only show the build QEMU command line")
argparser.add_argument('-p', '--ssh-port',
                       help = "SSH forwarding port",
                       type = int, default = 20010)
argparser.add_argument('-i', '--image',
                       help = "Path to the VM image", type = str,
                       default = 'arch.qcow2')
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
argparser.add_argument('--vhost-net', action='store_true',
                       help = "Enable vhost-net optimization")
argparser.add_argument('--no-mrg-rx-bufs', action='store_false',
                       help = "Disable virtio-net mergeable RX buffers")
argparser.add_argument('--no-ioeventfd', dest='ioeventfd', action='store_false',
                       help = "Disable ioeventfd optimization")
argparser.add_argument('--num-queues',
                       help = "Number of queues in a TAP device",
                       type = int, default = 1)

args = argparser.parse_args()

print(args)
