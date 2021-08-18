
# Sample Script to Migrate Guest VMs From Oracle VM To Oracle Linux Virtualization Manager using virt-v2v tool

## Requirements and Assumptions
Oracle VM Server (source) and KVM/OLVM (destination) hosts are network reachable each other

Oracle VM Server is based on 3.4 release (Older releases could work but the same had never been tested)

OLVM/VDSM releases are >= 4.3
ovirt-engine-4.3.6.6-1.0.9 RPM or higher is installed on the Oracle Linux Virtualization Manager Server
vdsm-4.30.33-1.0.3 RPM or higher is installed on the Oracle Linux KVM Server

virt-v2v1.40.2-5.0.1 or higher is installed on the Oracle Linux KVM Server

At least one KVM host and a Storage Domain have already been configured on OLVM and are up and running

This procedure works for OVM Virtual Machines that are configured with virtual disks only.

Please make sure that the guest VM is started before running the script.

## How this script works

The migration procedure relies on following components:

libvirt, both on Oracle VM Server as well as KVM host.

virt-v2v utility on KVM host

OVM Repository Export feature for non NFS repositories.

### For Non NFS repository: 
The repository exports will get created in OVM manager using ovmcli and will get mounted on KVM host. After that libvirt xml configuration file for guest VM will get created using virsh command.
Then virt-v2v tool uses this xml file for importing the guest VMs on Oracle Linux Virtualization Manager / KVM.

### For NFS repository: 
The NFS repository will get mounted on KVM host directly (No need of Repository exports). The rest procedure is same as above.

For more information on migration procedure, Please refer following community document :
https://blogs.oracle.com/scoter/migrate-oracle-vm-to-oracle-linux-kvm
