########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.


from pyVim import connect
import atexit
from pyVmomi import vmodl
from pyVmomi import vim
import time


def print_vm_info(vm, depth=1, max_depth=10):
    """
    Print information for a particular virtual machine or recurse into a
    folder with depth protection
    """

    # if this is a group it will have children. if it does, recurse into them
    # and then return
    if hasattr(vm, 'childEntity'):
        if depth > max_depth:
            return
        vmList = vm.childEntity
        for c in vmList:
            print_vm_info(c, depth + 1)
        return

    summary = vm.summary
    print "Name       : ", summary.config.name
    print "Path       : ", summary.config.vmPathName
    print "Guest      : ", summary.config.guestFullName
    annotation = summary.config.annotation
    if annotation:
        print "Annotation : ", annotation
    print "State      : ", summary.runtime.powerState
    if summary.guest is not None:
        ip = summary.guest.ipAddress
        if ip:
            print "IP         : ", ip
    if summary.runtime.question is not None:
        print "Question  : ", summary.runtime.question.text
    print ""


def is_vm_poweredon(vm):
    return vm.summary.runtime.powerState.lower() == "poweredon"


def wait_for_task(task):
    while task.info.state == vim.TaskInfo.State.running:
        time.sleep(15)
    if not task.info.state == vim.TaskInfo.State.success:
        raise task.info.error


# TODO check if before poweroff should connect
def terminate_vm(vm):
    if is_vm_poweredon(vm):
        task = vm.PowerOff()
        wait_for_task(task)
        task = vm.Destroy()
        wait_for_task(task)


def get_all_vms(host, user, pwd, port):
    return get_vm_by_name(host, user, pwd, port, '')


def get_vms_by_prefix(host, user, pwd, port, vm_name, prefix_enabled):
    vms = []
    try:
        service_instance = connect.SmartConnect(host=host,
                                                user=user,
                                                pwd=pwd,
                                                port=int(port))
        atexit.register(connect.Disconnect, service_instance)
        content = service_instance.RetrieveContent()
        object_view = content.viewManager. \
            CreateContainerView(content.rootFolder, [], True)
        for obj in object_view.view:
            if isinstance(obj, vim.VirtualMachine):
                if obj.summary.config.name == vm_name \
                        or vm_name == '' \
                        or (prefix_enabled and
                            obj.summary.config.name.startswith(vm_name)):
                    vms.append(obj)
    except vmodl.MethodFault as error:
        print "Caught vmodl fault : " + error.msg
        return

    object_view.Destroy()
    return vms


def get_vm_by_name(host, user, pwd, port, vm_name):
    return get_vms_by_prefix(host, user, pwd, port, vm_name, False)
