import base64
import time
import requests
import shutil
import re


class RhevmAction:
    """a rhevm rest-client warpper class
    currently can registe a rhvh to rhevm
    example:
    RhevmAction("rhevm-40-1.englab.nay.redhat.com").add_new_host("10.66.8.217", "autotest01", "redhat")
    """

    auth_format = "{user}@{domain}:{password}"
    api_url = "https://{rhevm_fqdn}/ovirt-engine/api/{item}"

    headers = {
        "Prefer": "persistent-auth",
        "Accept": "application/json",
        "Content-type": "application/xml"
    }

    cert_url = ("https://{rhevm_fqdn}/ovirt-engine/services"
                "/pki-resource?resource=ca-certificate&format=X509-PEM-CA")

    rhevm_cert = "/tmp/rhevm.cert"

    def __init__(self,
                 rhevm_fqdn,
                 user="admin",
                 password="password",
                 domain="internal"):

        self.rhevm_fqdn = rhevm_fqdn
        self.user = user
        self.password = password
        self.domain = domain
        self.token = base64.b64encode(
            self.auth_format.format(
                user=self.user, domain=self.domain, password=self.password))
        self.headers.update({
            "Authorization": "Basic {token}".format(token=self.token)
        })
        self._get_rhevm_cert_file()
        self.req = requests.Session()

    def _get_rhevm_cert_file(self):
        r = requests.get(self.cert_url.format(rhevm_fqdn=self.rhevm_fqdn),
                         stream=True,
                         verify=False)

        if r.status_code == 200:
            with open(self.rhevm_cert, 'wb') as f:
                r.raw.decode_content = True
                shutil.copyfileobj(r.raw, f)
        else:
            raise RuntimeError("Can not get the cert file from %s" %
                               self.rhevm_fqdn)

    ###################################
    # Datacenter related functions
    # https://rhvm41-vlan50-1.lab.eng.pek2.redhat.com/ovirt-engine/apidoc/#services-data_centers
    ###################################
    def create_datacenter(self, dc_name, is_local=False):
        api_url = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn,
            item="datacenters")
        new_dc_post_body = '''
        <data_center>
          <name>{dc_name}</name>
          <local>{is_local}</local>
        </data_center>
        '''
        body = new_dc_post_body.format(
            dc_name=dc_name, is_local=is_local)

        r = self.req.post(
            api_url, headers=self.headers, verify=self.rhevm_cert, data=body)

        if r.status_code != 201:
            raise RuntimeError("Failed to create datacenter "
                               "%s as\n%s" % (dc_name, r.text))

    def remove_datacenter(self, dc_name, force=False):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn,
            item="datacenters")

        dc_id = self.list_datacenter(dc_name)['id']
        api_url = api_url_base + '/{}'.format(dc_id)

        params = {'force': force}
        r = self.req.delete(
            api_url, headers=self.headers, verify=self.rhevm_cert, params=params)

        if r.status_code != 200:
            raise RuntimeError("Failed to remove datacenter "
                               "%s as\n%s" % (dc_name, r.text))

    def list_datacenter(self, dc_name):
        api_url = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn,
            item="datacenters")

        r = self.req.get(api_url, headers=self.headers, verify=self.rhevm_cert)

        if r.status_code != 200:
            raise RuntimeError("Failed to list datacenter "
                               "%s as\n%s" % (dc_name, r.text))

        dcs = r.json()
        if dcs:
            for dc in dcs['data_center']:
                if dc['name'] == dc_name:
                    return dc
        else:
            return

    ##################################
    # Cluster related functions
    # https://rhvm41-vlan50-1.lab.eng.pek2.redhat.com/ovirt-engine/apidoc/#services-clusters
    ##################################
    def create_cluster(self, dc_name, cluster_name, cpu_type):
        api_url = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn,
            item="clusters")

        new_cluster_post_body = '''
        <cluster>
          <name>{cluster_name}</name>
          <cpu>
            <type>{cpu_type}</type>
          </cpu>
          <data_center>
            <name>{dc_name}</name>
          </data_center>
        </cluster>
        '''
        body = new_cluster_post_body.format(
            dc_name=dc_name, cluster_name=cluster_name, cpu_type=cpu_type)

        r = self.req.post(
            api_url, headers=self.headers, verify=self.rhevm_cert, data=body)

        if r.status_code != 201:
            raise RuntimeError("Failed to create cluster "
                               "%s as\n%s" % (cluster_name, r.text))

    def remove_cluster(self, cluster_name):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn,
            item="clusters")
        cluster_id = self.list_cluster(cluster_name)['id']
        api_url = api_url_base + '/{}'.format(cluster_id)

        r = self.req.delete(api_url, headers=self.headers, verify=self.rhevm_cert)

        if r.status_code != 200:
            raise RuntimeError("Failed to remove cluster "
                               "%s as\n%s" % (cluster_name, r.text))

    def list_cluster(self, cluster_name):
        api_url = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn,
            item="clusters")

        r = self.req.get(api_url, headers=self.headers, verify=self.rhevm_cert)

        if r.status_code != 200:
            raise RuntimeError("Failed to list cluster "
                               "%s as\n%s" % (cluster_name, r.text))

        clusters = r.json()
        if clusters:
            for cluster in clusters['cluster']:
                if cluster['name'] == cluster_name:
                    return cluster
        else:
            return

    def update_cluster_cpu(self, cluster_name, cpu_type):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn,
            item="clusters")
        cluster_id = self.list_cluster(cluster_name)['id']
        api_url = api_url_base + "/%s" % cluster_id

        cluster_cpu_post_body = '''
        <cluster>
          <cpu>
            <type>{cpu_type}</type>
          </cpu>
        </cluster>
        '''
        body = cluster_cpu_post_body.format(cpu_type=cpu_type)

        r = self.req.put(api_url, headers=self.headers, verify=self.rhevm_cert, data=body)

        if r.status_code != 200:
            raise RuntimeError("Failed to update the cpu of cluster "
                               "%s as\n%s" % (cluster_name, r.text))

    ############################################
    # Host related functions
    # https://rhvm41-vlan50-1.lab.eng.pek2.redhat.com/ovirt-engine/apidoc/#services-hosts
    ############################################
    def create_new_host(self, ip, host_name, password, cluster_name='Default'):
        api_url = self.api_url.format(rhevm_fqdn=self.rhevm_fqdn, item="hosts")

        new_host_post_body = '''
        <host>
            <name>{host_name}</name>
            <address>{ip}</address>
            <root_password>{password}</root_password>
            <cluster>
              <name>{cluster_name}</name>
            </cluster>
        </host>
        '''
        body = new_host_post_body.format(
            host_name=host_name, ip=ip, password=password, cluster_name=cluster_name)

        r = self.req.post(
            api_url, data=body, headers=self.headers, verify=self.rhevm_cert)

        if r.status_code != 201:
            raise RuntimeError("Failed to create host "
                               "%s as\n%s" % (host_name, r.text))

    def deactive_host(self, host_name):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item='hosts')

        host = self.list_host(host_name)
        host_status = host['status']
        if host_status == 'maintenance':
            return

        host_id = host['id']
        api_url = api_url_base + "/%s/deactivate" % host_id
        r = self.req.post(
            api_url,
            headers=self.headers,
            verify=self.rhevm_cert,
            data="<action/>")
        ret = r.json()
        if ret['status'] != 'complete':
            raise RuntimeError("Failed to deactive host "
                               "%s as\n%s" % (host_name, r.text))

    def remove_host(self, host_name):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="hosts")

        host_status = self.list_host(host_name)['status']
        if host_status == 'up':
            self.deactive_host(host_name)

        host_id = self.list_host(host_name)['id']
        time.sleep(5)
        api_url = api_url_base + '/%s' % host_id

        r = self.req.delete(
            api_url, headers=self.headers, verify=self.rhevm_cert)

        if r.status_code != 200:
            raise RuntimeError("Failed to remove host "
                               "%s as\n%s" % (host_name, r.text))

    def list_host(self, host_name):
        api_url = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn,
            item="hosts")
        r = self.req.get(api_url, headers=self.headers, verify=self.rhevm_cert)

        if r.status_code != 200:
            raise RuntimeError("Failed to list host "
                               "%s as\n%s" % (host_name, r.text))

        hosts = r.json()
        if hosts:
            for host in hosts['host']:
                if host['name'] == host_name:
                    return host
        else:
            return

    ######################################
    # Storage domain related functions
    # https://rhvm41-vlan50-1.lab.eng.pek2.redhat.com/ovirt-engine/apidoc/#services-storage_domains
    ######################################
    def create_plain_storage_domain(
            self,
            sd_name,
            sd_type,
            storage_type,
            storage_addr,
            storage_path,
            host):
        storage_domain_post_body = '''
        <storage_domain>
          <name>{sd_name}</name>
          <type>{sd_type}</type>
          <storage>
            <type>{storage_type}</type>
            <address>{storage_addr}</address>
            <path>{storage_path}</path>
          </storage>
          <host>
            <name>{host}</name>
          </host>
        </storage_domain>
        '''
        api_url = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="storagedomains")

        body = storage_domain_post_body.format(
            sd_name=sd_name,
            sd_type=sd_type,
            storage_type=storage_type,
            storage_addr=storage_addr,
            storage_path=storage_path,
            host=host)

        r = self.req.post(
            api_url, data=body, headers=self.headers, verify=self.rhevm_cert)

        if r.status_code != 201:
            raise RuntimeError("Failed to create storage domain "
                               "%s as\n%s" % (sd_name, r.text))

    def create_fc_scsi_storage_domain(
            self,
            sd_name,
            sd_type,
            storage_type,
            lun_id,
            host):
        api_url = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="storagedomains")
        storage_domain_post_body = '''
        <storage_domain>
          <name>{sd_name}</name>
          <type>{sd_type}</type>
          <storage>
            <type>{storage_type}</type>
            <logical_units>
              <logical_unit id="{lun_id}"/>
            </logical_units>
          </storage>
          <discard_after_delete>false</discard_after_delete>
          <host>
            <name>{host}</name>
          </host>
        </storage_domain>
        '''
        body = storage_domain_post_body.format(
            sd_name=sd_name,
            sd_type=sd_type,
            storage_type=storage_type,
            lun_id=lun_id,
            host=host)

        r = self.req.post(
            api_url, data=body, headers=self.headers, verify=self.rhevm_cert)

        if r.status_code != 201:
            raise RuntimeError("Failed to create storage domain "
                               "%s as\n%s" % (sd_name, r.text))

    def list_host_storage(self, host_name):
        api_url_base = self.api_url.format(rhevm_fqdn=self.rhevm_fqdn, item="hosts")

        host_id = self.list_host(host_name)['id']
        api_url = api_url_base + '/{}'.format(host_id) + '/storage'

        r = self.req.get(api_url, headers=self.headers, verify=self.rhevm_cert)

        if r.status_code != 200:
            raise RuntimeError("Failed to list the strages of host "
                               "%s as\n%s" % (host_name, r.text))

        sts = r.json()
        return sts

    def attach_sd_to_datacenter(self, sd_name, dc_name):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="datacenters")

        dc_id = self.list_datacenter(dc_name)['id']
        api_url = api_url_base + '/%s/storagedomains' % dc_id

        new_storage_post_body = '''
        <storage_domain>
          <name>{storage_name}</name>
        </storage_domain>
        '''
        body = new_storage_post_body.format(storage_name=sd_name)

        r = self.req.post(
            api_url, data=body, headers=self.headers, verify=self.rhevm_cert)

        if r.status_code != 201:
            raise RuntimeError("Failed to attach storage domain %s to "
                               "%s as\n%s" % (sd_name, dc_name, r.text))

    def list_storage_domain(self, sd_name):
        api_url = self.api_url.format(rhevm_fqdn=self.rhevm_fqdn, item="storagedomains")

        r = self.req.get(api_url, headers=self.headers, verify=self.rhevm_cert)

        if r.status_code != 200:
            raise RuntimeError("Failed to list storage domain "
                               "%s as\n%s" % (sd_name, r.text))

        sds = r.json()
        if sds:
            for sd in sds['storage_domain']:
                if sd['name'] == sd_name:
                    return sd
        else:
            return

    def remove_storage_domain(self, sd_name, host_name, destroy=True):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn,
            item="storagedomains")

        sd_id = self.list_storage_domain(sd_name)['id']
        api_url = api_url_base + '/{}'.format(sd_id)

        params = {'destroy': destroy, 'host': host_name}
        r = self.req.delete(
            api_url, headers=self.headers, verify=self.rhevm_cert, params=params)

        if r.status_code != 200:
            raise RuntimeError("Failed to remove storage domain "
                               "%s as\n%s" % (sd_name, r.text))

    ##########################################
    # Network related functions
    # https://rhvm41-vlan50-1.lab.eng.pek2.redhat.com/ovirt-engine/apidoc/#services-network
    ##########################################
    def list_network(self, dc_name, network_name):
        api_url = self.api_url.format(rhevm_fqdn=self.rhevm_fqdn, item="networks")

        dc_id = self.list_datacenter(dc_name)['id']

        r = self.req.get(api_url, headers=self.headers, verify=self.rhevm_cert)

        if r.status_code != 200:
            raise RuntimeError("Failed to list network of "
                               "%s as\n%s" % (dc_name, r.text))

        networks = r.json()
        if networks:
            for network in networks['network']:
                if network['data_center']['id'] == dc_id:
                    if network['name'] == network_name:
                        return network
        else:
            return

    def update_dc_network(self, dc_name, network_name, key, value):
        """
        Update the network of the datacenter
        key: [name, description, ip, vlan, stp, display]
        """
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn,
            item="datacenters")
        dc_id = self.list_datacenter(dc_name)['id']
        network_id = self.list_network(dc_name, network_name)['id']
        api_url = api_url_base + "/%s" % dc_id + "/networks/%s" % network_id

        if key == "vlan":
            dc_network_post_body = '''
            <network>
              <vlan id="{value}"/>
            </network>
            '''
        else:
            dc_network_post_body = '''
            <network>
              <{key}>{value}</{key}>
            </network>
            '''
        body = dc_network_post_body.format(key=key, value=value)

        r = self.req.put(api_url, headers=self.headers, verify=self.rhevm_cert, data=body)
        if r.status_code != 200:
            raise RuntimeError("Failed to update the network of "
                               "%s as\n%s" % (dc_name, r.text))

    ##########################################
    # Disk related functions
    # https://rhvm41-vlan50-1.lab.eng.pek2.redhat.com/ovirt-engine/apidoc/#services-disks
    ##########################################
    def create_float_image_disk(self, sd_name, disk_name, size):
        api_url = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="disks")

        new_disk_post_body = '''
        <disk>
          <storage_domains>
            <storage_domain id="{sd_id}"/>
          </storage_domains>
          <name>{disk_name}</name>
          <provisioned_size>{size}</provisioned_size>
          <format>cow</format>
        </disk>
        '''
        sd_id = self.list_storage_domain(sd_name)['id']
        body = new_disk_post_body.format(
            sd_id=sd_id, disk_name=disk_name, size=size)

        r = self.req.post(
            api_url, data=body, headers=self.headers, verify=self.rhevm_cert)

        if r.status_code != 201:
            raise RuntimeError("Failed to create float image disk "
                               "%s as\n%s" % (disk_name, r.text))

    def create_float_direct_lun_disk(
            self,
            disk_name,
            host_name,
            lun_type,
            lun_id,
            lun_addr="",
            lun_port="",
            lun_target=""):
        #
        # lun_type = {'iscsi', 'fcp', 'nfs', 'localfs', 'posixfs',
        # 'glusterfs', 'glance', 'cinder'}
        #
        api_url = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="disks")

        new_disk_post_body = '''
        <disk>
          <alias>{disk_name}</alias>
          <lun_storage>
            <host id="{host_id}"/>
            <type>{lun_type}</type>
            <logical_units>
              <logical_unit id="{lun_id}">
                <address>{lun_addr}</address>
                <port>{lun_port}</port>
                <target>{lun_target}</target>
              </logical_unit>
            </logical_units>
          </lun_storage>
        </disk>
        '''
        host_id = self.list_host(host_name)['id']
        body = new_disk_post_body.format(
            disk_name=disk_name,
            host_id=host_id,
            lun_type=lun_type,
            lun_id=lun_id,
            lun_addr=lun_addr,
            lun_port=lun_port,
            lun_target=lun_target)

        r = self.req.post(
            api_url, data=body, headers=self.headers, verify=self.rhevm_cert)

        if r.status_code != 201:
            raise RuntimeError("Failed to create float lun disk "
                               "%s as\n%s" % (disk_name, r.text))

    def attach_disk_to_vm(self, disk_name, vm_name, bootable=False):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="vms")

        vm_id = self.list_vm(vm_name)['id']
        disk_id = self.list_disk(disk_name)['id']

        api_url = api_url_base + '/{}'.format(vm_id) + '/diskattachments'

        attach_disk_post_body = '''
        <disk_attachment>
          <bootable>{bootable}</bootable>
          <interface>ide</interface>
          <active>true</active>
          <disk id="{disk_id}"/>
        </disk_attachment>
        '''

        body = attach_disk_post_body.format(disk_id=disk_id, bootable=bootable)

        r = self.req.post(
            api_url,
            data=body,
            headers=self.headers,
            verify=self.rhevm_cert)

        if r.status_code != 201:
            raise RuntimeError("Failed to attach disk %s to "
                               "%s as\n%s" % (disk_name, vm_name, r.text))

    def list_disk(self, disk_name):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="disks")

        r = self.req.get(
            api_url_base,
            headers=self.headers,
            verify=self.rhevm_cert)

        if r.status_code != 200:
            raise RuntimeError("Failed to list disk "
                               "%s as\n%s" % (disk_name, r.text))

        disks = r.json()
        if disks:
            for disk in disks['disk']:
                if disk['name'] == disk_name:
                    return disk
        else:
            return

    ##########################################
    # VM related functions
    # https://rhvm41-vlan50-1.lab.eng.pek2.redhat.com/ovirt-engine/apidoc/#services-vms
    ##########################################
    def create_vm(self, vm_name, tpl_name="Blank", cluster="default"):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="vms")

        new_vm_body = '''
        <vm>
        <name>{vm_name}</name>
        <description>{vm_name}</description>
        <cluster>
        <name>{cluster_name}</name>
        </cluster>
        <template>
        <name>{tpl_name}</name>
        </template>
        </vm>
        '''
        body = new_vm_body.format(
            vm_name=vm_name, tpl_name=tpl_name, cluster_name=cluster)

        r = self.req.post(
            api_url_base,
            data=body,
            headers=self.headers,
            verify=self.rhevm_cert)

        if r.status_code != 201:
            raise RuntimeError("Failed to create vm "
                               "%s as\n%s" % (vm_name, r.text))
        else:
            return r.json()["id"]

    def list_vm(self, vm_name):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="vms")

        r = self.req.get(
            api_url_base,
            headers=self.headers,
            verify=self.rhevm_cert)

        if r.status_code != 200:
            raise RuntimeError("Failed to list vm "
                               "%s as\n%s" % (vm_name, r.text))

        vms = r.json()
        if vms:
            for vm in vms['vm']:
                if vm['name'] == vm_name:
                    return vm
        else:
            return

    def start_vm(self, vm_name):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="vms")

        vm_id = self.list_vm(vm_name)['id']
        api_url = api_url_base + '/%s/start' % vm_id

        vm_action = '''
        <action>
          <vm>
            <os>
              <boot>
                <devices>
                  <device>hd</device>
                </devices>
              </boot>
            </os>
          </vm>
        </action>
        '''
        r = self.req.post(
            api_url,
            data=vm_action,
            headers=self.headers,
            verify=self.rhevm_cert)

        if r.status_code != 200:
            raise RuntimeError("Failed to start vm "
                               "%s as\n%s" % (vm_name, r.text))

    def operate_vm(self, vm_name, operation):
        normal_operations = ['start', 'reboot', 'shutdown', 'stop', 'suspend']
        if operation not in normal_operations:
            raise RuntimeError("Only support operations ['reboot', 'shutdown', 'stop', 'suspend']")

        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="vms")

        vm_id = self.list_vm(vm_name)['id']
        api_url = api_url_base + '/%s/%s' % (vm_id, operation)

        vm_action = '''
        <action/>
        '''
        r = self.req.post(
            api_url,
            data=vm_action,
            headers=self.headers,
            verify=self.rhevm_cert)

        if r.status_code != 200:
            raise RuntimeError("Failed to %s vm "
                               "%s as\n%s" % (operation, vm_name, r.text))

    def remove_vm(self, vm_name):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="vms")

        vm_id = self.list_vm(vm_name)['id']
        api_url = api_url_base + '/%s' % vm_id

        r = self.req.delete(
            api_url,
            headers=self.headers,
            verify=self.rhevm_cert)

        if r.status_code != 200:
            raise RuntimeError("Failed to remove vm "
                               "%s as\n%s" % (vm_name, r.text))

    def create_vm_image_disk(self, vm_name, sd_name, disk_name, disk_size):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="vms")

        vm_id = self.list_vm(vm_name)['id']
        api_url = api_url_base + '/{}'.format(vm_id) + '/diskattachments'

        attach_disk_post_body = '''
        <disk_attachment>
          <bootable>true</bootable>
          <interface>virtio</interface>
          <active>true</active>
          <disk>
            <format>cow</format>
            <name>{disk_name}</name>
            <provisioned_size>{disk_size}</provisioned_size>
            <storage_domains>
              <storage_domain>
                <name>{sd_name}</name>
              </storage_domain>
            </storage_domains>
          </disk>
        </disk_attachment>
        '''

        body = attach_disk_post_body.format(
            disk_name=disk_name, disk_size=disk_size, sd_name=sd_name)

        r = self.req.post(
            api_url,
            data=body,
            headers=self.headers,
            verify=self.rhevm_cert)

        if r.status_code != 201:
            raise RuntimeError("Failed to create image disk for vm "
                               "%s as\n%s" % (vm_name, r.text))

    def create_vm_direct_lun_disk(
            self,
            vm_name,
            disk_name,
            host_name,
            lun_type,
            lun_id,
            lun_addr="",
            lun_port="",
            lun_target=""):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="vms")

        host_id = self.list_host(host_name)['id']
        vm_id = self.list_vm(vm_name)['id']
        api_url = api_url_base + '/{}'.format(vm_id) + '/diskattachments'

        if lun_type == "iscsi":
            attach_disk_post_body = '''
            <disk_attachment>
              <bootable>false</bootable>
              <interface>virtio</interface>
              <active>true</active>
                <disk>
                  <alias>{disk_name}</alias>
                  <lun_storage>
                    <host id="{host_id}"/>
                    <type>{lun_type}</type>
                    <logical_units>
                      <logical_unit id="{lun_id}">
                        <address>{lun_addr}</address>
                        <port>{lun_port}</port>
                        <target>{lun_target}</target>
                      </logical_unit>
                    </logical_units>
                  </lun_storage>
                </disk>
            </disk_attachment>
            '''
            body = attach_disk_post_body.format(
                disk_name=disk_name,
                host_id=host_id,
                lun_type=lun_type,
                lun_id=lun_id,
                lun_addr=lun_addr,
                lun_port=lun_port,
                lun_target=lun_target)
        else:
            attach_disk_post_body = '''
            <disk_attachment>
              <bootable>false</bootable>
              <interface>virtio</interface>
              <active>true</active>
                <disk>
                  <alias>{disk_name}</alias>
                  <lun_storage>
                    <host id="{host_id}"/>
                    <type>{lun_type}</type>
                    <logical_units>
                      <logical_unit id="{lun_id}"/>
                    </logical_units>
                  </lun_storage>
                </disk>
            </disk_attachment>
            '''
            body = attach_disk_post_body.format(
                disk_name=disk_name, host_id=host_id, lun_type=lun_type, lun_id=lun_id)

        r = self.req.post(
            api_url,
            data=body,
            headers=self.headers,
            verify=self.rhevm_cert)

        if r.status_code != 201:
            raise RuntimeError("Failed to create lun disk for vm "
                               "%s as\n%s" % (vm_name, r.text))

    def list_vm_disk_attachments(self, vm_name, disk_name):
        api_url_base = self.api_url.format(
            rhevm_fqdn=self.rhevm_fqdn, item="vms")
        vm_id = self.list_vm(vm_name)['id']
        api_url = api_url_base + '/{}'.format(vm_id) + '/diskattachments'

        r = self.req.get(
            api_url,
            headers=self.headers,
            verify=self.rhevm_cert)

        if r.status_code != 200:
            raise RuntimeError("Failed to list disk %s of "
                               "%s as\n%s" % (disk_name, vm_name, r.text))

        diskattachment = r.json()
        if diskattachment:
            disk_id = self.list_disk(disk_name)['id']
            for disk in diskattachment['disk_attachment']:
                if disk['id'] == disk_id:
                    return disk
        else:
            return


if __name__ == '__main__':
    rhvm = RhevmAction("rhvm41-vlan50-2.lab.eng.pek2.redhat.com")
    print rhvm.list_network(dc_name="vdsm_bva_dc", network_name="ovirtmgmt")
    rhvm.update_dc_network(dc_name="vdsm_bva_dc", network_name="ovirtmgmt", key="vlan", value="60")
    print rhvm.list_network(dc_name="vdsm_bva_dc", network_name="ovirtmgmt")
