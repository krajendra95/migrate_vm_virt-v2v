#!/usr/bin/python
# This Python Script is written by Kiran Rajendra

import json
import requests
from requests.auth import HTTPBasicAuth
import time
import os
import subprocess
import logging
from getpass import getpass
import ovirtsdk4 as sdk
import ovirtsdk4.types as types

# this is for For requests < 2.16.0
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logging.basicConfig(level=logging.DEBUG, filename='example.log')


# This is for requests >= 2.16.0
# try:
#    import urllib3
#    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# except ImportError:
#    pass


class OVMManager():
    def __init__(self, name):
        self.name = name
        self.baseuri = "https://" + self.name + ":7002/ovm/core/wsapi/rest"
        self.session = requests.Session()
        self.session.verify = False
        self.session.trust_env = False
        self.session.headers.update({'Accept': 'application/json', 'Content-Type': 'application/json'})
        self.session.auth = ('admin', PASSWORD)

    def getManager(self):
        response = requests.Response()
        response = self.session.get(self.baseuri + "/Manager", auth=HTTPBasicAuth('admin', PASSWORD))
        if response.status_code == 200:
            print "Succesfully accessed Oracle VM Manager " + self.name
            return response.json()
        else:
            return {"result": "an error occured"}

    def get_id_from_name(self, resourceType, name):
        response = self.session.get(self.baseuri + "/" + resourceType + "/id")
        for obj in response.json():
            if 'name' in obj.keys():
                if obj['name'] == name:
                    return obj
        raise Exception('Failed to find id for {name}'.format(name=name))

    def wait_for_job(self, joburi):
        while True:
            time.sleep(1)
            r = self.session.get(joburi)
            job = r.json()
            if job['progressMessage'] != None:
                print job['progressMessage']
            if job['summaryDone']:
                print('{name}: {runState}'.format(name=job['name'], runState=job['jobRunState']))
                if job['jobRunState'].upper() == 'FAILURE':
                    raise Exception('Job failed: {error}'.format(error=job['error']))
                elif job['jobRunState'].upper() == 'SUCCESS':
                    if 'resultId' in job:
                        return job['resultId']
                    break
                else:
                    break

    def set_ovs(self, ovs):
        print "\n Editing xend configuration for enabling http listening port (8000)\n"
        cmd = '''echo '(xend-http-server yes)'>>/etc/xen/xend-config.sxp;echo '(xend-unix-path /var/lib/xend/xend-socket)'>>/etc/xen/xend-config.sxp;echo '(xend-port 8000)'>>/etc/xen/xend-config.sxp;service xend restart;service libvirtd start'''
        subprocess.call('ssh -o StrictHostKeyChecking=no root@"%s" "%s"' % (ovs, cmd), shell=True)
        print "\nOVS setup completed....\n===================================\n"


    def export(self,Myrepo,ovs):
        print "\nCreating Repository Export for all OVM Repositories involved in the migration (required for FC/iSCSI/Local repositories) by OVM CLI \n"
        client = raw_input("Enter clientHostName:")
        name = raw_input("Enter repo export name:")
        ovs_name = raw_input("Oracle VM server name as in OVM manager:")
        print "\n Now we are creating the repository export\n"
        subprocess.call('ssh -l admin "%s" -p 10000 -n "create RepositoryExport clientHostName="%s" name="%s" repository="%s" on Server name="%s" "' % (hostname, client,name,Myrepo,ovs_name),shell=True)
        print "\n Repository export completed...\n"
        repo_id = self.get_id_from_name("Repository", Myrepo)
        subprocess.call('mkdir -p /OVS/Repositories/"%s"' % (repo_id['value']), shell=True)
        subprocess.call('mount -t nfs "%s":/OVS/Repositories/"%s" /OVS/Repositories/"%s"' % (ovs, repo_id['value'], repo_id['value']), shell=True)
        print "\n Repository export mounted in KVM host as NFS\n==================================\n"

    def nfs(self,Myrepo,ovs):
        print "Please make sure that NFS share is exported to this KVM host from NFS Server\n"
        nfs_server = raw_input("Enter NFS server IP/ Host name:")
        print "The available nfs shares are as follows:\n"
        subprocess.call('showmount -e "%s"' % (nfs_server), shell=True)
        repo_id = self.get_id_from_name("Repository", Myrepo)
        nfs_export = raw_input("\nPlease enter nfs share path in format <NFS server IP/ Host name>:<nfs share path>:")
        subprocess.call('mkdir -p /OVS/Repositories/"%s"' % (repo_id['value']), shell=True)
        subprocess.call('mount -t nfs "%s" /OVS/Repositories/"%s"' % (nfs_export, repo_id['value']), shell=True)
        print "\nNFS share mount on KVM host completed...\n=======================================\n"


    def set_kvm(self, ovs, olvm, passwd):
        #repo_id = self.get_id_from_name("Repository", Myrepo)
        print "\n=====================================\nGet OL-KVM VDSM daemon self-authenticated to Xen/OVM host and Create a Passord File for KVM-host access to Oracle Linux Virtualization Manager API\n"
        os.system('sudo -u vdsm ssh-keygen;sudo -u vdsm ssh-copy-id root@"%s";echo "%s" > /tmp/ovirt-admin-password' % (ovs, passwd))
        print "\n=====================================\nCopy the Oracle Linux Virtualization Manager certificate on the KVM host\n"
        subprocess.call('scp root@"%s":/etc/pki/ovirt-engine/ca.pem /root/ca.pem' % (olvm), shell=True)
        # subprocess.call('mkdir -p /OVS/Repositories/"%s"'% (repo_id['value']), shell=True)
        # subprocess.call('mount -t nfs "%s":/OVS/Repositories/"%s" /OVS/Repositories/"%s"'% (ovs,repo_id['value'],repo_id['value']),shell=True)
        print "\n======================================\nTest connectivity to OVM/Xen Host from KVM host\n"
        os.system('virsh -c xen+ssh://root@"%s" list --all'% (ovs))
        print "\nKVM host setup completed....\n=======================================\n"


    def dump_xml(self, ovs,olvm):
        print "\nCreating libvirt XML configuration file for the OVM Virtual Machine\n"
        vm = raw_input("Enter the guest VM name:")
        vm_id = self.get_id_from_name('Vm', vm)
        os.system('virsh -c xen+ssh://root@"%s" dumpxml "%s" > "%s".xml' % (ovs,vm_id['value'], vm))
        print "libvirt XML configuration file for the Virtual Machine got created"
        count= raw_input("Press 1 to stop the guest VM or Press 2 if already stopped:")
        if int(count) == 1:
            self.stopVM(vm)
            import_vm(vm,olvm)

        elif int(count) == 2:
            import_vm(vm,olvm)

    def get_VM_Info_by_Id(self, resourceType, VM_id):
            uri = '{base}/{res}/{VMId}'.format(base=self.baseuri, VMId=VM_id['value'], res=resourceType)
            info = self.session.get(uri)
            infoJson = json.loads(info.text)
            return infoJson

    def stopVM(self, VMNAME):
            VM_id = self.get_id_from_name('Vm', VMNAME)
            # print VM_id
            vminfo = self.get_VM_Info_by_Id('Vm', VM_id)
            print vminfo['id']['value']
            if vminfo["vmRunState"] == 'RUNNING':
                uri = '{base}/Vm/{id}/stop'.format(base=self.baseuri, id=vminfo['id']['value'])
                stopVM = self.session.put(uri)
                jsonstopVM = json.loads(stopVM.text)
                wait = self.wait_for_job(jsonstopVM['id']['uri'])
                print '{VM} guest VM stopped'.format(VM=VMNAME)

            else:
                print '{VM} guest VM is already stopped'.format(VM=VMNAME)

def import_vm(vm, olvm):
        print "\nNow, we are importing the guest VM\n"
        cluster = raw_input("Enter the cluster name in OLVM :")
        domain = raw_input("Enter the Storage domain name in OLVM:")
        uuid = raw_input("Enter UUID of guest VM:")
        # os.system('export LIBGUESTFS_BACKEND=direct')
        os.putenv("LIBGUESTFS_BACKEND", "direct")
        check = raw_input("\nIf guest VM contains sparse disks(thin provisioning)then press 1 or press 2 for preallocated provisioning:")
        if int(check) == 1:
           rtn = os.system(
                'virt-v2v -i libvirtxml "%s".xml -o ovirt-upload -oc https://"%s"/ovirt-engine/api -os %s -op /tmp/ovirt-admin-password -of raw -oo rhv-cluster="%s" -oo rhv-cafile=/root/ca.pem' % (
                vm, olvm, domain, cluster))
        else:
            rtn = os.system(
                'virt-v2v -i libvirtxml "%s".xml -o ovirt-upload -oc https://"%s"/ovirt-engine/api -os %s -op /tmp/ovirt-admin-password -of raw -oo rhv-cluster="%s" -oo rhv-cafile=/root/ca.pem -oa preallocated' % (
                vm, olvm, domain, cluster))

        if rtn :
           print "\nGuest VM migration Failed \n"
        else :
           edit_vm(vm,olvm,uuid)
           print "\nGuest VM import completed..\n"

def edit_vm(vm,olvm,uuid):
        with open('/tmp/ovirt-admin-password', 'r') as file:
             olvm_passwd = file.read().replace('\n', '')
        # Create the connection to the server:
        connection = sdk.Connection(
            url="https://"+olvm+"/ovirt-engine/api",
            username='admin@internal',
            password=olvm_passwd,
            ca_file='/root/ca.pem',
            debug=True,
            log=logging.getLogger(),
        )
        vm_name = uuid
        new_vm_name = vm

        # Find the virtual machine:
        vms_service = connection.system_service().vms_service()
        vm = vms_service.list(search='name= %s'% (vm_name))[0]
        vm_service = vms_service.vm_service(vm.id)

        vm_service.update(
            vm=types.Vm(
                name=new_vm_name,
                display=types.Display(
                   type=types.DisplayType.VNC
                )
            )
        )

        # Close the connection to the server:
        connection.close()


if __name__ == "__main__":
    print "=== Welcome to guest VM migration tool ==="
    print "1.Setup the environment and import the guest VM (complete procedure)\n"
    print "2.Already ovs and kvm host setup completed, just need to dump xml file and import the guest VM\n"
    print "3.The xml file is already dumped. Only need to import the guest VM\n"
    opt = raw_input("\nEnter the option:")

    if int(opt) == 1:
        print  "Checking OVM manager connection\n========================\n"
        hostname = raw_input("Enter hostname/ IP address of OVM manager:")
        PASSWORD = raw_input("Enter the admin password:")
        OVM = OVMManager(hostname)
        result = OVM.getManager()
        #repo = raw_input("Enter Repository name:")
        ovs = raw_input("Enter IP address/hostname of OVS:")
        olvm = raw_input("Enter OLVM manager IP address/hostname:")
        passwd = raw_input("Enter OLVM admin user password:")
        oc = raw_input("Press 1 to setup OVS or Press 2:")
        if int(oc) == 1:
            OVM.set_ovs(ovs)
        kc = raw_input("Press 1 to setup KVM host or Press 2:")
        if int(kc) == 1:
            OVM.set_kvm(ovs, olvm, passwd)

        ec = raw_input("Press 1 to export repository and mount in KVM host(If you are using NFS repositories then press 2):")
        if int(ec) == 1:
            rc = raw_input("\n Please enter number of repositories that you want to export:")
            for i in range(int(rc)):
                repo = raw_input("Enter Repository name:")
                OVM.export(repo, ovs)
        #OVM.export(repo, ovs)

        ec = raw_input("Press 1 for mounting NFS repositories on KVM host or Press 2:")
        if int(ec) == 1:
            rc = raw_input("\n Please enter number of repositories that you want to export:")
            for i in range(int(rc)):
                repo = raw_input("Enter Repository name:")
                OVM.nfs(repo, ovs)


        OVM.dump_xml(ovs,olvm)

    elif int(opt) == 2:
        print  "Checking OVM manager connection\n========================\n"
        hostname = raw_input("Enter hostname/ IP address of OVM manager:")
        PASSWORD = raw_input("Enter the admin password:")
        OVM = OVMManager(hostname)
        result = OVM.getManager()
        ovs = raw_input("Enter IP address/hostname of OVS:")
        olvm = raw_input("Enter OLVM manager IP address/hostname:")
        OVM.dump_xml(ovs,olvm)

    elif int(opt) == 3:
        vm = raw_input("Enter guest VM name:")
        olvm = raw_input("Enter OLVM manager IP address/hostname:")
        import_vm(vm,olvm)

    else:
        print "Invalid option"
